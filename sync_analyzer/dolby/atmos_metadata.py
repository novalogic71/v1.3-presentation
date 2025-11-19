"""
Dolby Atmos Metadata Extraction

Extracts and parses Dolby Atmos metadata from audio files including:
- Channel bed configuration (7.1, 7.1.2, 7.1.4, etc.)
- Object count and bitrate
- Codec information (EC3, EAC-3, TrueHD)
- ADM BWF metadata for ADM WAV files
"""

import json
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AtmosMetadata:
    """Dolby Atmos metadata container"""

    file_path: str
    codec: str  # ec3, eac3, truehd, etc.
    bed_configuration: str  # "7.1", "7.1.2", "7.1.4", "9.1.6", etc.
    channels: int  # Total channel count
    channel_layout: str  # FFmpeg channel layout string
    sample_rate: int
    bit_rate: Optional[int] = None
    object_count: Optional[int] = None
    max_objects: int = 128  # Dolby Atmos spec maximum
    duration: Optional[float] = None
    is_adm_wav: bool = False
    adm_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


def extract_atmos_metadata(file_path: str) -> Optional[AtmosMetadata]:
    """
    Extract Dolby Atmos metadata from audio file

    Args:
        file_path: Path to Atmos audio file (EC3, EAC3, ADM WAV, or MP4 with Atmos)

    Returns:
        AtmosMetadata object or None if extraction fails
    """
    try:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        # Run ffprobe to get detailed audio metadata
        metadata = _probe_with_ffprobe(str(file_path))
        if not metadata:
            return None

        # Check if it's an ADM BWF WAV file
        is_adm = _check_adm_wav(str(file_path))

        # Parse metadata
        atmos_meta = _parse_atmos_metadata(metadata, str(file_path), is_adm)

        logger.info(f"Extracted Atmos metadata from {file_path.name}: "
                   f"{atmos_meta.bed_configuration} @ {atmos_meta.sample_rate}Hz")

        return atmos_meta

    except Exception as e:
        logger.error(f"Failed to extract Atmos metadata from {file_path}: {e}")
        return None


def _probe_with_ffprobe(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Use ffprobe to extract audio metadata

    Args:
        file_path: Path to audio file

    Returns:
        Dictionary with ffprobe output or None
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            file_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        return json.loads(result.stdout)

    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ffprobe JSON output: {e}")
        return None


def _check_adm_wav(file_path: str) -> bool:
    """
    Check if file is an ADM BWF WAV file

    ADM WAV files contain an 'axml' chunk with Audio Definition Model metadata

    Args:
        file_path: Path to WAV file

    Returns:
        True if file is ADM WAV, False otherwise
    """
    try:
        # Check file extension first
        if not file_path.lower().endswith(('.wav', '.adm')):
            return False

        # Use ffprobe to check for ADM metadata
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            file_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)

        # Check if any stream has ADM-related metadata
        for stream in data.get("streams", []):
            tags = stream.get("tags", {})
            # ADM WAV files may have specific BWF tags or axml references
            if any("adm" in key.lower() or "axml" in key.lower() for key in tags.keys()):
                return True

        return False

    except Exception as e:
        logger.debug(f"ADM check failed: {e}")
        return False


def _parse_atmos_metadata(probe_data: Dict[str, Any], file_path: str, is_adm: bool) -> AtmosMetadata:
    """
    Parse ffprobe data into AtmosMetadata object

    Args:
        probe_data: ffprobe JSON output
        file_path: Original file path
        is_adm: Whether file is ADM WAV

    Returns:
        AtmosMetadata object
    """
    # Find audio stream
    audio_stream = None
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    if not audio_stream:
        raise ValueError("No audio stream found in file")

    # Extract basic metadata
    codec = audio_stream.get("codec_name", "unknown")
    channels = audio_stream.get("channels", 0)
    channel_layout = audio_stream.get("channel_layout", "unknown")
    sample_rate = int(audio_stream.get("sample_rate", 48000))

    # Extract bitrate (may be in stream or format)
    bit_rate = audio_stream.get("bit_rate")
    if not bit_rate and "format" in probe_data:
        bit_rate = probe_data["format"].get("bit_rate")
    bit_rate = int(bit_rate) if bit_rate else None

    # Extract duration
    duration = audio_stream.get("duration")
    if not duration and "format" in probe_data:
        duration = probe_data["format"].get("duration")
    duration = float(duration) if duration else None

    # Determine bed configuration based on channel count and layout
    bed_config = _infer_bed_configuration(channels, channel_layout)

    # Parse object count if available (would be in codec-specific metadata)
    object_count = _parse_object_count(audio_stream)

    # ADM-specific metadata
    adm_metadata = None
    if is_adm:
        adm_metadata = _extract_adm_metadata(probe_data)
        # ADM files may have explicit object counts
        if adm_metadata and "objects" in adm_metadata:
            object_count = adm_metadata["objects"]

    return AtmosMetadata(
        file_path=file_path,
        codec=codec,
        bed_configuration=bed_config,
        channels=channels,
        channel_layout=channel_layout,
        sample_rate=sample_rate,
        bit_rate=bit_rate,
        object_count=object_count,
        duration=duration,
        is_adm_wav=is_adm,
        adm_metadata=adm_metadata
    )


def _infer_bed_configuration(channels: int, layout: str) -> str:
    """
    Infer Atmos bed configuration from channel count and layout

    Common Atmos configurations:
    - 7.1: 8 channels (FL, FR, FC, LFE, BL, BR, SL, SR)
    - 7.1.2: 10 channels (7.1 + 2 height: TpFL, TpFR)
    - 7.1.4: 12 channels (7.1 + 4 height: TpFL, TpFR, TpBL, TpBR)
    - 9.1.6: 16 channels (extended bed with 6 height)

    Args:
        channels: Number of channels
        layout: FFmpeg channel layout string

    Returns:
        Bed configuration string (e.g., "7.1", "7.1.2")
    """
    # Parse layout for height channels
    layout_lower = layout.lower()
    height_channels = 0

    if "top" in layout_lower or "ceiling" in layout_lower or "height" in layout_lower:
        # Count height channel indicators
        height_keywords = ["top", "ceiling", "height", "tpfl", "tpfr", "tpbl", "tpbr"]
        height_channels = sum(1 for keyword in height_keywords if keyword in layout_lower)

    # Determine base bed config
    base_channels = channels - height_channels

    if base_channels == 8:
        bed = "7.1"
    elif base_channels == 10:
        bed = "9.1"
    elif base_channels == 6:
        bed = "5.1"
    elif base_channels == 2:
        bed = "2.0"
    else:
        bed = f"{base_channels}.0"

    # Add height channels if present
    if height_channels > 0:
        return f"{bed}.{height_channels}"
    else:
        return bed


def _parse_object_count(audio_stream: Dict[str, Any]) -> Optional[int]:
    """
    Parse object count from audio stream metadata

    Note: Object count may not be directly available in ffprobe output
    for all Atmos files. This is a best-effort extraction.

    Args:
        audio_stream: Audio stream dict from ffprobe

    Returns:
        Object count if found, None otherwise
    """
    # Check stream tags for object count
    tags = audio_stream.get("tags", {})

    # Dolby may use various tag names
    for key in tags:
        if "object" in key.lower() and "count" in key.lower():
            try:
                return int(tags[key])
            except ValueError:
                pass

    return None


def _extract_adm_metadata(probe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract ADM-specific metadata from probe data

    Args:
        probe_data: ffprobe JSON output

    Returns:
        Dictionary with ADM metadata or None
    """
    adm_data = {}

    # Parse ADM-related tags from streams
    for stream in probe_data.get("streams", []):
        tags = stream.get("tags", {})
        for key, value in tags.items():
            if "adm" in key.lower() or "axml" in key.lower():
                adm_data[key] = value

    return adm_data if adm_data else None


def is_atmos_codec(codec: str) -> bool:
    """
    Check if codec is Dolby Atmos compatible

    Args:
        codec: Codec name from ffprobe

    Returns:
        True if codec supports Atmos, False otherwise
    """
    atmos_codecs = [
        "eac3",  # E-AC-3 (Dolby Digital Plus)
        "ec3",   # Alternative name
        "ac3",   # AC-3 may have Atmos
        "truehd",  # TrueHD with Atmos
        "mlp",   # MLP lossless (TrueHD base)
    ]

    return codec.lower() in atmos_codecs


if __name__ == "__main__":
    # Test metadata extraction
    import sys

    if len(sys.argv) < 2:
        print("Usage: python atmos_metadata.py <atmos_file>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)

    file_path = sys.argv[1]
    metadata = extract_atmos_metadata(file_path)

    if metadata:
        print("\n" + "="*60)
        print("Dolby Atmos Metadata")
        print("="*60)
        print(metadata.to_json())
        print("="*60)
    else:
        print(f"Failed to extract metadata from {file_path}")
        sys.exit(1)
