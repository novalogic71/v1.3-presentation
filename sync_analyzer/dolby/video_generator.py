"""
Black Video Generator

Generates black video tracks for MP4 containers to package Atmos audio files.
Used when converting standalone Atmos audio (EC3/EAC3/ADM WAV) to MP4 format
for compatibility with the sync analysis pipeline.
"""

import subprocess
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def generate_black_video(
    duration: float,
    output_path: Optional[str] = None,
    fps: float = 24.0,
    resolution: str = "1920x1080",
    codec: str = "libx264",
    preset: str = "ultrafast",
    pix_fmt: str = "yuv420p"
) -> Optional[str]:
    """
    Generate a black video file using FFmpeg

    Args:
        duration: Video duration in seconds
        output_path: Output file path (auto-generated if None)
        fps: Frame rate (default: 24.0)
        resolution: Video resolution (default: 1920x1080)
        codec: Video codec (default: libx264)
        preset: Encoding preset for speed/quality trade-off (default: ultrafast)
        pix_fmt: Pixel format (default: yuv420p for compatibility)

    Returns:
        Path to generated video file, or None if generation fails
    """
    try:
        # Create output path if not provided
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="black_video_")
        else:
            output_path = str(Path(output_path).resolve())

        # Parse resolution
        width, height = _parse_resolution(resolution)

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=black:{width}x{height}:d={duration}:r={fps}",
            "-c:v", codec,
            "-preset", preset,
            "-pix_fmt", pix_fmt,
            "-y",  # Overwrite output file
            output_path
        ]

        logger.info(f"Generating black video: {duration}s @ {fps}fps, {resolution}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        # Run FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Verify output file was created
        if not Path(output_path).exists():
            logger.error("FFmpeg completed but output file not found")
            return None

        file_size = Path(output_path).stat().st_size
        logger.info(f"Black video generated: {output_path} ({file_size / 1024:.1f} KB)")

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to generate black video: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Failed to generate black video: {e}")
        return None


def generate_black_video_with_audio(
    audio_path: str,
    output_path: Optional[str] = None,
    fps: float = 24.0,
    resolution: str = "1920x1080",
    audio_codec: str = "copy"
) -> Optional[str]:
    """
    Generate black video and mux with audio in a single step

    This is a convenience function that combines black video generation
    and audio muxing into one FFmpeg command for efficiency.

    Args:
        audio_path: Path to audio file
        output_path: Output file path (auto-generated if None)
        fps: Frame rate (default: 24.0)
        resolution: Video resolution (default: 1920x1080)
        audio_codec: Audio codec ('copy' to preserve original, or codec name)

    Returns:
        Path to generated MP4 file, or None if generation fails
    """
    try:
        audio_path = Path(audio_path).resolve()
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None

        # Get audio duration
        duration = _get_audio_duration(str(audio_path))
        if duration is None:
            logger.error(f"Failed to determine audio duration for {audio_path}")
            return None

        # Create output path if not provided
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_mp4_")
        else:
            output_path = str(Path(output_path).resolve())

        # Parse resolution
        width, height = _parse_resolution(resolution)

        # Build FFmpeg command to generate black video and mux audio
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=black:{width}x{height}:d={duration}:r={fps}",
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-c:a", audio_codec,
            "-shortest",  # Match shortest stream (should be equal)
            "-y",  # Overwrite output file
            output_path
        ]

        logger.info(f"Generating MP4 with black video and audio: {audio_path.name}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        # Run FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Verify output file was created
        if not Path(output_path).exists():
            logger.error("FFmpeg completed but output file not found")
            return None

        file_size = Path(output_path).stat().st_size
        logger.info(f"MP4 with black video generated: {output_path} ({file_size / 1024:.1f} KB)")

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to generate MP4: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Failed to generate MP4 with audio: {e}")
        return None


def _parse_resolution(resolution: str) -> Tuple[int, int]:
    """
    Parse resolution string to width and height

    Args:
        resolution: Resolution string (e.g., "1920x1080", "1280x720")

    Returns:
        Tuple of (width, height)

    Raises:
        ValueError: If resolution format is invalid
    """
    try:
        if "x" not in resolution.lower():
            raise ValueError(f"Invalid resolution format: {resolution}")

        parts = resolution.lower().split("x")
        width = int(parts[0].strip())
        height = int(parts[1].strip())

        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid resolution dimensions: {width}x{height}")

        return width, height

    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse resolution '{resolution}': {e}")


def _get_audio_duration(audio_path: str) -> Optional[float]:
    """
    Get audio file duration using ffprobe

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds, or None if probe fails
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            audio_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        import json
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])

        logger.debug(f"Audio duration: {duration:.2f}s")
        return duration

    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Failed to get audio duration: {e}")
        return None


if __name__ == "__main__":
    # Test black video generation
    import sys

    if len(sys.argv) < 2:
        print("Usage: python video_generator.py <duration_seconds> [output_path]")
        print("   or: python video_generator.py --with-audio <audio_file> [output_path]")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)

    if sys.argv[1] == "--with-audio":
        # Generate with audio
        if len(sys.argv) < 3:
            print("Error: Audio file path required")
            sys.exit(1)

        audio_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None

        result = generate_black_video_with_audio(audio_path, output_path)
        if result:
            print(f"\nSuccess! MP4 generated: {result}")
        else:
            print("\nFailed to generate MP4")
            sys.exit(1)
    else:
        # Generate video only
        duration = float(sys.argv[1])
        output_path = sys.argv[2] if len(sys.argv) > 2 else None

        result = generate_black_video(duration, output_path)
        if result:
            print(f"\nSuccess! Black video generated: {result}")
        else:
            print("\nFailed to generate black video")
            sys.exit(1)
