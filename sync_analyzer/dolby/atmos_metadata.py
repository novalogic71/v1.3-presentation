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
    codec: str  # ec3, eac3, truehd, iab, etc.
    bed_configuration: str  # "7.1", "7.1.2", "7.1.4", "9.1.6", etc.
    channels: int  # Total channel count
    channel_layout: str  # FFmpeg channel layout string
    sample_rate: int
    bit_rate: Optional[int] = None
    object_count: Optional[int] = None
    max_objects: int = 128  # Dolby Atmos spec maximum
    duration: Optional[float] = None
    is_adm_wav: bool = False
    is_iab: bool = False  # IAB (Immersive Audio Bitstream)
    is_mxf: bool = False  # MXF container
    adm_metadata: Optional[Dict[str, Any]] = None
    iab_metadata: Optional[Dict[str, Any]] = None
    mxf_metadata: Optional[Dict[str, Any]] = None

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
        file_path: Path to Atmos audio file (EC3, EAC3, ADM WAV, IAB, MXF, or MP4 with Atmos)

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

        # Check file format specifics
        is_adm = _check_adm_wav(str(file_path))
        is_iab = _check_iab_stream(str(file_path))
        is_mxf = _check_mxf_container(str(file_path))

        # Parse metadata
        atmos_meta = _parse_atmos_metadata(metadata, str(file_path), is_adm, is_iab, is_mxf)

        format_type = "IAB" if is_iab else "ADM" if is_adm else "MXF" if is_mxf else "Atmos"
        logger.info(f"Extracted {format_type} metadata from {file_path.name}: "
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

    ADM WAV files contain an 'axml' chunk with Audio Definition Model metadata.
    Also detects multichannel WAV files (6+ channels) which are likely Atmos/ADM.

    Args:
        file_path: Path to WAV file

    Returns:
        True if file is ADM WAV or multichannel WAV, False otherwise
    """
    try:
        # Check file extension - .adm extension means it's ADM WAV
        if file_path.lower().endswith('.adm'):
            return True

        # For .wav extension, check metadata
        if not file_path.lower().endswith('.wav'):
            return False

        # Use ffprobe to check for ADM metadata and channel count
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

        # Check audio streams
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                # Check for ADM metadata tags
                tags = stream.get("tags", {})
                if any("adm" in key.lower() or "axml" in key.lower() for key in tags.keys()):
                    return True

                # Check for multichannel audio (6+ channels = likely Atmos/ADM)
                channels = stream.get("channels", 0)
                if channels >= 6:
                    logger.info(f"Detected multichannel WAV ({channels} channels), treating as ADM/Atmos")
                    return True

        return False

    except Exception as e:
        logger.debug(f"ADM check failed: {e}")
        return False


def _check_iab_stream(file_path: str) -> bool:
    """
    Check if file contains IAB (Immersive Audio Bitstream) using ffprobe metadata.

    IAB is Dolby's SMPTE ST 2098-2 format for object-based audio.
    Can be in standalone .iab files or embedded in MXF/MP4 containers.

    Detection priority (ffprobe is authoritative):
    1. ffprobe format metadata (product_name, company_name)
    2. ffprobe stream metadata (codec, tags)
    3. File extension (.iab only as fallback)

    Args:
        file_path: Path to audio/video file

    Returns:
        True if file contains IAB, False otherwise
    """
    try:
        file_lower = file_path.lower()
        
        # .iab extension is definitive
        if file_lower.endswith('.iab'):
            return True
        
        # PRIMARY: Check ffprobe format metadata (most reliable for MXF/containers)
        format_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path
        ]
        result = subprocess.run(format_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.debug(f"ffprobe failed for IAB check: {file_path}")
            return False
        
        data = json.loads(result.stdout)
        
        # Check format-level tags (most reliable for Dolby Atmos MXF)
        format_tags = data.get("format", {}).get("tags", {})
        product_name = str(format_tags.get("product_name", "")).lower()
        company_name = str(format_tags.get("company_name", "")).lower()
        
        # Dolby Atmos Storage System IDK = IAB MXF from Dolby tools
        if "dolby" in company_name and "atmos" in product_name:
            logger.info(f"[IAB] Detected from ffprobe: product_name='{product_name}', company_name='{company_name}'")
            return True
        
        # Also check for Dolby company with audio-only MXF (IAB essence)
        if "dolby" in company_name:
            # Check if audio stream has no recognized codec (IAB can't be decoded by ffmpeg)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    codec = stream.get("codec_name", "")
                    # IAB streams show as "none" or unknown codec in ffprobe
                    if codec in ["none", "", "unknown"] or codec is None:
                        logger.info(f"[IAB] Detected Dolby MXF with undecoded audio stream (likely IAB)")
                        return True
        
        # Check stream-level metadata for IAB indicators
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                codec = stream.get("codec_name", "").lower()
                codec_long = stream.get("codec_long_name", "").lower()

                # Explicit IAB codec reference
                if "iab" in codec or "iab" in codec_long:
                    return True

                # Check stream tags for IAB/SMPTE references
                tags = stream.get("tags", {})
                for key, value in tags.items():
                    value_str = str(value).lower()
                    if "iab" in key.lower() or "iab" in value_str:
                        return True
                    if "2098" in str(value):  # SMPTE ST 2098-2
                        return True
                    if "atmos" in value_str and "dolby" in value_str:
                        return True

        return False

    except Exception as e:
        logger.debug(f"IAB check failed: {e}")
        return False

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)

        # Check for IAB codec or SMPTE ST 2098-2 references
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                codec = stream.get("codec_name", "").lower()
                codec_long = stream.get("codec_long_name", "").lower()

                # IAB may be reported as pcm_s24le or other PCM variants
                # with specific metadata indicating IAB
                if "iab" in codec or "iab" in codec_long:
                    return True

                # Check tags for IAB/SMPTE references
                tags = stream.get("tags", {})
                for key, value in tags.items():
                    if "iab" in key.lower() or "iab" in str(value).lower():
                        return True
                    if "2098" in str(value):  # SMPTE ST 2098-2
                        return True

        return False

    except Exception as e:
        logger.debug(f"IAB check failed: {e}")
        return False


def _check_mxf_container(file_path: str) -> bool:
    """
    Check if file is MXF (Material eXchange Format) container

    MXF is a professional broadcast container that can contain Atmos/IAB audio.

    Args:
        file_path: Path to file

    Returns:
        True if file is MXF container, False otherwise
    """
    try:
        # Check file extension
        if file_path.lower().endswith('.mxf'):
            return True

        # Check container format
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            file_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)
        format_name = data.get("format", {}).get("format_name", "").lower()

        # FFmpeg reports MXF as "mxf" or "mxf_*"
        if "mxf" in format_name:
            return True

        return False

    except Exception as e:
        logger.debug(f"MXF check failed: {e}")
        return False


def _parse_atmos_metadata(
    probe_data: Dict[str, Any],
    file_path: str,
    is_adm: bool,
    is_iab: bool = False,
    is_mxf: bool = False
) -> AtmosMetadata:
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

    # Format-specific metadata extraction
    adm_metadata = None
    iab_metadata = None
    mxf_metadata = None

    if is_adm:
        adm_metadata = _extract_adm_metadata(probe_data)
        # ADM files may have explicit object counts
        if adm_metadata and "objects" in adm_metadata:
            object_count = adm_metadata["objects"]

    if is_iab:
        iab_metadata = _extract_iab_metadata(probe_data)
        # IAB files have object-based audio
        if iab_metadata and "objects" in iab_metadata:
            object_count = iab_metadata["objects"]
        # Override codec for clarity
        codec = "iab"

    if is_mxf:
        mxf_metadata = _extract_mxf_metadata(probe_data)
        # MXF may contain additional technical metadata

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
        is_iab=is_iab,
        is_mxf=is_mxf,
        adm_metadata=adm_metadata,
        iab_metadata=iab_metadata,
        mxf_metadata=mxf_metadata
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


def _extract_iab_metadata(probe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract IAB-specific metadata from probe data

    Args:
        probe_data: ffprobe JSON output

    Returns:
        Dictionary with IAB metadata or None
    """
    iab_data = {}

    # Parse IAB-related tags from streams
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "audio":
            tags = stream.get("tags", {})
            for key, value in tags.items():
                if "iab" in key.lower() or "smpte" in key.lower() or "2098" in str(value):
                    iab_data[key] = value

            # IAB-specific attributes
            if "iab" in stream.get("codec_name", "").lower():
                iab_data["codec"] = stream.get("codec_name")
                iab_data["codec_long_name"] = stream.get("codec_long_name")

    # Estimate object count for IAB (if not explicitly available)
    # IAB can contain up to 128 objects per SMPTE ST 2098-2
    if iab_data and "objects" not in iab_data:
        iab_data["objects"] = None  # Unknown without parsing bitstream
        iab_data["max_objects"] = 128  # SMPTE spec maximum

    return iab_data if iab_data else None


def _extract_mxf_metadata(probe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract MXF-specific metadata from probe data

    Args:
        probe_data: ffprobe JSON output

    Returns:
        Dictionary with MXF metadata or None
    """
    mxf_data = {}

    # MXF format-level metadata
    format_info = probe_data.get("format", {})
    if "mxf" in format_info.get("format_name", "").lower():
        mxf_data["format_name"] = format_info.get("format_name")
        mxf_data["format_long_name"] = format_info.get("format_long_name")

        # MXF-specific tags
        tags = format_info.get("tags", {})
        for key, value in tags.items():
            # Common MXF metadata fields
            if any(field in key.lower() for field in ["uid", "material_package", "operational_pattern", "essence"]):
                mxf_data[key] = value

    # MXF operational pattern and essence descriptors
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "audio":
            tags = stream.get("tags", {})
            # Extract MXF audio essence metadata
            for key, value in tags.items():
                if "mxf" in key.lower() or "essence" in key.lower():
                    mxf_data[key] = value

    return mxf_data if mxf_data else None


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
        "iab",   # IAB (Immersive Audio Bitstream)
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
