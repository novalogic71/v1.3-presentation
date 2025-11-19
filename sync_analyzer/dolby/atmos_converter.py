"""
Dolby Atmos to MP4 Converter

Converts standalone Dolby Atmos audio files (EC3, EAC3, ADM WAV, IAB)
to MP4 format with black video for compatibility with video-based
sync analysis pipelines.

Workflow:
1. Detect Atmos format (EC3/EAC3/ADM WAV)
2. Extract metadata (duration, bed config, sample rate)
3. Generate black video matching audio duration
4. Mux audio and video into MP4 container
5. Preserve Atmos metadata in MP4 atoms
"""

import subprocess
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from .atmos_metadata import extract_atmos_metadata, is_atmos_codec
from .video_generator import generate_black_video_with_audio

logger = logging.getLogger(__name__)


def is_atmos_file(file_path: str) -> bool:
    """
    Check if file is a Dolby Atmos audio file

    Supported formats:
    - .ec3, .eac3 (E-AC-3 bitstreams)
    - .adm (ADM BWF WAV)
    - .iab (IAB - Immersive Audio Bitstream)
    - .mxf (MXF containers with Atmos/IAB)
    - .wav with Atmos codec
    - .mp4, .mov with Atmos audio

    Args:
        file_path: Path to audio file

    Returns:
        True if file is Atmos, False otherwise
    """
    try:
        file_path = Path(file_path)

        # Check extension first
        ext = file_path.suffix.lower()
        if ext in ['.ec3', '.eac3', '.adm', '.iab', '.mxf']:
            return True

        # For other extensions, probe with ffprobe
        metadata = extract_atmos_metadata(str(file_path))
        if metadata:
            return is_atmos_codec(metadata.codec)

        return False

    except Exception as e:
        logger.debug(f"Atmos detection failed for {file_path}: {e}")
        return False


def convert_atmos_to_mp4(
    atmos_path: str,
    output_path: Optional[str] = None,
    fps: float = 24.0,
    resolution: str = "1920x1080",
    preserve_original: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Convert Atmos audio file to MP4 with black video

    Args:
        atmos_path: Path to Atmos audio file
        output_path: Output MP4 path (auto-generated if None)
        fps: Video frame rate (default: 24.0)
        resolution: Video resolution (default: 1920x1080)
        preserve_original: Whether to preserve original Atmos file

    Returns:
        Dictionary with conversion results:
        {
            "mp4_path": str,
            "metadata": AtmosMetadata,
            "original_path": str (if preserved)
        }
        Returns None if conversion fails
    """
    try:
        atmos_path = Path(atmos_path).resolve()
        if not atmos_path.exists():
            logger.error(f"Atmos file not found: {atmos_path}")
            return None

        # Verify it's an Atmos file
        if not is_atmos_file(str(atmos_path)):
            logger.error(f"File is not a recognized Atmos format: {atmos_path}")
            return None

        # Extract metadata
        logger.info(f"Converting Atmos file to MP4: {atmos_path.name}")
        metadata = extract_atmos_metadata(str(atmos_path))
        if not metadata:
            logger.error(f"Failed to extract Atmos metadata from {atmos_path}")
            return None

        logger.info(f"Atmos metadata: {metadata.bed_configuration}, "
                   f"{metadata.codec}, {metadata.sample_rate}Hz, "
                   f"Duration: {metadata.duration:.2f}s")

        # Determine conversion strategy based on file type
        ext = atmos_path.suffix.lower()

        if ext in ['.ec3', '.eac3']:
            # EC3/EAC3 bitstream - needs decoding and re-encoding
            mp4_path = _convert_ec3_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext == '.iab':
            # IAB (Immersive Audio Bitstream) - SMPTE ST 2098-2
            mp4_path = _convert_iab_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext == '.mxf':
            # MXF container with Atmos/IAB
            mp4_path = _convert_mxf_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext == '.adm' or (ext == '.wav' and metadata.is_adm_wav):
            # ADM BWF WAV - can be copied directly
            mp4_path = _convert_adm_wav_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext in ['.mp4', '.mov']:
            # Already in container format, just ensure it has black video
            mp4_path = _add_black_video_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext == '.wav':
            # Standard WAV with Atmos codec
            mp4_path = _convert_wav_to_mp4(str(atmos_path), output_path, fps, resolution)
        else:
            logger.error(f"Unsupported Atmos file format: {ext}")
            return None

        if not mp4_path:
            logger.error(f"Failed to convert {atmos_path} to MP4")
            return None

        # Optionally preserve original file
        original_path = None
        if preserve_original:
            original_path = str(atmos_path)
            logger.info(f"Original Atmos file preserved: {original_path}")

        logger.info(f"Atmos conversion complete: {mp4_path}")

        return {
            "mp4_path": mp4_path,
            "metadata": metadata,
            "original_path": original_path
        }

    except Exception as e:
        logger.error(f"Failed to convert Atmos file {atmos_path}: {e}")
        return None


def _convert_ec3_to_mp4(
    ec3_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert EC3/EAC3 bitstream to MP4 with black video

    Strategy: Use FFmpeg to directly mux EC3 into MP4 with generated black video

    Args:
        ec3_path: Path to EC3/EAC3 file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_ec3_")

        logger.info(f"Converting EC3 to MP4: {ec3_path}")

        # Use video_generator to create MP4 with black video and EC3 audio
        # EC3 audio will be copied without re-encoding to preserve Atmos metadata
        mp4_path = generate_black_video_with_audio(
            ec3_path,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="copy"  # Preserve EC3 bitstream
        )

        return mp4_path

    except Exception as e:
        logger.error(f"EC3 to MP4 conversion failed: {e}")
        return None


def _convert_adm_wav_to_mp4(
    adm_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert ADM BWF WAV to MP4 with black video

    ADM WAV files contain PCM audio with ADM metadata in BWF chunks.
    We'll encode to AAC or EAC3 for MP4 container.

    Args:
        adm_path: Path to ADM WAV file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_adm_")

        logger.info(f"Converting ADM WAV to MP4: {adm_path}")

        # Encode ADM WAV to EAC3 for Atmos compatibility
        # Note: This will lose ADM metadata, which is acceptable for sync analysis
        # For production, would use dolby_audio_bridge or similar tool

        mp4_path = generate_black_video_with_audio(
            adm_path,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="eac3"  # Encode to EAC3 for Atmos
        )

        return mp4_path

    except Exception as e:
        logger.error(f"ADM WAV to MP4 conversion failed: {e}")
        return None


def _convert_iab_to_mp4(
    iab_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert IAB (Immersive Audio Bitstream) to MP4 with black video

    IAB is SMPTE ST 2098-2 object-based audio format.
    FFmpeg may have limited IAB support, so this uses best-effort conversion.

    Args:
        iab_path: Path to IAB file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_iab_")

        logger.info(f"Converting IAB to MP4: {iab_path}")

        # IAB files are typically PCM-based with object metadata
        # Best approach is to extract as PCM and encode to EAC3 or AAC
        mp4_path = generate_black_video_with_audio(
            iab_path,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="aac"  # AAC for broad compatibility
        )

        return mp4_path

    except Exception as e:
        logger.error(f"IAB to MP4 conversion failed: {e}")
        return None


def _convert_mxf_to_mp4(
    mxf_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert MXF container to MP4

    MXF may already have video; extract audio and add black video if needed.

    Args:
        mxf_path: Path to MXF file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_mxf_")

        logger.info(f"Converting MXF to MP4: {mxf_path}")

        # Extract audio from MXF
        temp_audio = tempfile.mktemp(suffix=".audio.m4a")

        # Extract audio track (preserve codec if possible)
        extract_cmd = [
            "ffmpeg",
            "-i", mxf_path,
            "-vn",  # No video
            "-c:a", "copy",  # Try to copy audio codec
            "-y",
            temp_audio
        ]

        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("Failed to copy audio codec, re-encoding to AAC")
            # Fallback: re-encode to AAC
            extract_cmd[-2] = "aac"
            subprocess.run(extract_cmd, capture_output=True, text=True, check=True)

        # Generate MP4 with black video and extracted audio
        mp4_path = generate_black_video_with_audio(
            temp_audio,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="copy"
        )

        # Clean up temp audio
        Path(temp_audio).unlink(missing_ok=True)

        return mp4_path

    except Exception as e:
        logger.error(f"MXF to MP4 conversion failed: {e}")
        return None


def _convert_wav_to_mp4(
    wav_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert standard WAV to MP4 with black video

    Args:
        wav_path: Path to WAV file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_wav_")

        logger.info(f"Converting WAV to MP4: {wav_path}")

        # Encode to AAC for compatibility
        mp4_path = generate_black_video_with_audio(
            wav_path,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="aac"
        )

        return mp4_path

    except Exception as e:
        logger.error(f"WAV to MP4 conversion failed: {e}")
        return None


def _add_black_video_to_mp4(
    input_mp4: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Add black video to existing MP4 with Atmos audio

    If MP4 already has video, replace it with black video.
    If MP4 only has audio, add black video.

    Args:
        input_mp4: Path to input MP4 file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_mp4_")

        logger.info(f"Adding black video to MP4: {input_mp4}")

        # Extract audio from input MP4
        temp_audio = tempfile.mktemp(suffix=".audio.m4a")

        # Extract audio track
        extract_cmd = [
            "ffmpeg",
            "-i", input_mp4,
            "-vn",  # No video
            "-c:a", "copy",  # Copy audio codec
            "-y",
            temp_audio
        ]

        subprocess.run(extract_cmd, capture_output=True, text=True, check=True)

        # Generate MP4 with black video and extracted audio
        mp4_path = generate_black_video_with_audio(
            temp_audio,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="copy"
        )

        # Clean up temp audio
        Path(temp_audio).unlink(missing_ok=True)

        return mp4_path

    except Exception as e:
        logger.error(f"Failed to add black video to MP4: {e}")
        return None


def extract_atmos_audio(mp4_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Extract Atmos audio from MP4 file

    Args:
        mp4_path: Path to MP4 with Atmos audio
        output_path: Output audio file path (auto-generated if None)

    Returns:
        Path to extracted audio file or None
    """
    try:
        mp4_path = Path(mp4_path).resolve()
        if not mp4_path.exists():
            logger.error(f"MP4 file not found: {mp4_path}")
            return None

        # Determine output format based on codec
        metadata = extract_atmos_metadata(str(mp4_path))
        if not metadata:
            logger.error(f"Failed to extract metadata from {mp4_path}")
            return None

        # Create output path
        if output_path is None:
            if metadata.codec in ['eac3', 'ec3']:
                output_path = tempfile.mktemp(suffix=".ec3", prefix="atmos_audio_")
            else:
                output_path = tempfile.mktemp(suffix=".m4a", prefix="atmos_audio_")

        logger.info(f"Extracting Atmos audio from {mp4_path.name}")

        # Extract audio using ffmpeg
        cmd = [
            "ffmpeg",
            "-i", str(mp4_path),
            "-vn",  # No video
            "-c:a", "copy",  # Copy audio codec
            "-y",
            output_path
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)

        if not Path(output_path).exists():
            logger.error("Audio extraction completed but file not found")
            return None

        logger.info(f"Atmos audio extracted: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to extract audio: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Failed to extract Atmos audio: {e}")
        return None


if __name__ == "__main__":
    # Test Atmos conversion
    import sys

    if len(sys.argv) < 2:
        print("Usage: python atmos_converter.py <atmos_file> [output_mp4]")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)

    atmos_file = sys.argv[1]
    output_mp4 = sys.argv[2] if len(sys.argv) > 2 else None

    result = convert_atmos_to_mp4(atmos_file, output_mp4)

    if result:
        print("\n" + "="*60)
        print("Atmos Conversion Success")
        print("="*60)
        print(f"MP4 Path: {result['mp4_path']}")
        print(f"Bed Config: {result['metadata'].bed_configuration}")
        print(f"Sample Rate: {result['metadata'].sample_rate}Hz")
        print(f"Duration: {result['metadata'].duration:.2f}s")
        if result['original_path']:
            print(f"Original: {result['original_path']}")
        print("="*60)
    else:
        print(f"\nFailed to convert {atmos_file}")
        sys.exit(1)
