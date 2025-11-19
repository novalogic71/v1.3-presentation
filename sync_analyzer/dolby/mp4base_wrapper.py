"""
dlb_mp4base Python Wrapper

Python wrapper for Dolby's dlb_mp4base library for MP4 file manipulation.

Note: This module provides a thin wrapper around dlb_mp4base command-line tools
or shared libraries. For the initial implementation, we primarily use FFmpeg
for MP4 operations, but this wrapper is available for advanced Dolby-specific
metadata handling when needed.

Future enhancements may include:
- Direct C++ library bindings via ctypes/pybind11
- Advanced Dolby Vision metadata handling
- Custom MP4 atom manipulation for Atmos metadata
"""

import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DlbMp4Base:
    """
    Wrapper for dlb_mp4base library operations
    """

    def __init__(self):
        """Initialize dlb_mp4base wrapper"""
        self.mp4base_path = self._find_mp4base()
        if not self.mp4base_path:
            logger.warning("dlb_mp4base not found in PATH. "
                         "Advanced Dolby metadata operations may not be available.")

    def _find_mp4base(self) -> Optional[str]:
        """
        Find dlb_mp4base executable in system PATH

        Returns:
            Path to mp4base executable or None
        """
        # Common dlb_mp4base executable names
        executables = [
            "mp4muxer",      # MP4 muxer tool
            "mp4demuxer",    # MP4 demuxer tool
            "mp4info",       # MP4 info tool
            "dlb_mp4base"    # Generic name
        ]

        for exe in executables:
            path = shutil.which(exe)
            if path:
                logger.info(f"Found dlb_mp4base tool: {path}")
                return path

        return None

    def is_available(self) -> bool:
        """
        Check if dlb_mp4base is available

        Returns:
            True if dlb_mp4base tools are available
        """
        return self.mp4base_path is not None

    def get_mp4_info(self, mp4_path: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed MP4 file information using dlb_mp4base

        Args:
            mp4_path: Path to MP4 file

        Returns:
            Dictionary with MP4 metadata or None
        """
        if not self.is_available():
            logger.warning("dlb_mp4base not available, using fallback method")
            return self._get_mp4_info_fallback(mp4_path)

        try:
            # This is a placeholder - actual dlb_mp4base command syntax
            # would depend on the specific tools available
            cmd = [self.mp4base_path, "info", mp4_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Parse output (format depends on dlb_mp4base tools)
            info = self._parse_mp4_info(result.stdout)
            return info

        except subprocess.CalledProcessError as e:
            logger.error(f"dlb_mp4base info command failed: {e.stderr}")
            return self._get_mp4_info_fallback(mp4_path)
        except Exception as e:
            logger.error(f"Failed to get MP4 info: {e}")
            return None

    def _get_mp4_info_fallback(self, mp4_path: str) -> Optional[Dict[str, Any]]:
        """
        Fallback method to get MP4 info using ffprobe

        Args:
            mp4_path: Path to MP4 file

        Returns:
            Dictionary with MP4 metadata or None
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                mp4_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            import json
            return json.loads(result.stdout)

        except Exception as e:
            logger.error(f"Fallback MP4 info failed: {e}")
            return None

    def _parse_mp4_info(self, output: str) -> Dict[str, Any]:
        """
        Parse dlb_mp4base info output

        Args:
            output: Raw output from dlb_mp4base info command

        Returns:
            Parsed metadata dictionary
        """
        # Placeholder - actual parsing depends on dlb_mp4base output format
        info = {
            "raw_output": output
        }

        # TODO: Parse specific Dolby metadata atoms when using real dlb_mp4base
        # - Dolby Vision atoms
        # - Dolby Atmos object metadata
        # - Custom Dolby-specific MP4 boxes

        return info

    def mux_mp4(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        preserve_metadata: bool = True
    ) -> Optional[str]:
        """
        Mux video and audio into MP4 container using dlb_mp4base

        Args:
            video_path: Path to video file
            audio_path: Path to audio file (Atmos audio)
            output_path: Output MP4 path
            preserve_metadata: Whether to preserve Dolby metadata

        Returns:
            Path to output MP4 or None
        """
        if not self.is_available():
            logger.warning("dlb_mp4base not available, using FFmpeg fallback")
            return self._mux_mp4_fallback(video_path, audio_path, output_path)

        try:
            # Placeholder for dlb_mp4base muxing command
            # Actual syntax depends on available dlb_mp4base tools
            cmd = [
                self.mp4base_path,
                "mux",
                "-v", video_path,
                "-a", audio_path,
                "-o", output_path
            ]

            if preserve_metadata:
                cmd.append("--preserve-metadata")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if not Path(output_path).exists():
                logger.error("Muxing completed but output file not found")
                return None

            logger.info(f"MP4 muxed successfully: {output_path}")
            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"dlb_mp4base mux failed: {e.stderr}")
            return self._mux_mp4_fallback(video_path, audio_path, output_path)
        except Exception as e:
            logger.error(f"Failed to mux MP4: {e}")
            return None

    def _mux_mp4_fallback(
        self,
        video_path: str,
        audio_path: str,
        output_path: str
    ) -> Optional[str]:
        """
        Fallback method to mux MP4 using FFmpeg

        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Output MP4 path

        Returns:
            Path to output MP4 or None
        """
        try:
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "copy",
                "-y",
                output_path
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)

            if not Path(output_path).exists():
                return None

            logger.info(f"MP4 muxed with FFmpeg: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"FFmpeg mux fallback failed: {e}")
            return None

    def demux_mp4(self, mp4_path: str, output_dir: str) -> Optional[Dict[str, str]]:
        """
        Demux MP4 file into separate video and audio tracks

        Args:
            mp4_path: Path to MP4 file
            output_dir: Output directory for demuxed tracks

        Returns:
            Dictionary with paths to demuxed tracks or None
        """
        if not self.is_available():
            logger.warning("dlb_mp4base not available, using FFmpeg fallback")
            return self._demux_mp4_fallback(mp4_path, output_dir)

        try:
            # Placeholder for dlb_mp4base demuxing
            cmd = [
                self.mp4base_path,
                "demux",
                "-i", mp4_path,
                "-o", output_dir
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Find demuxed files
            output_dir = Path(output_dir)
            video_file = list(output_dir.glob("*.video.*"))[0] if output_dir.glob("*.video.*") else None
            audio_file = list(output_dir.glob("*.audio.*"))[0] if output_dir.glob("*.audio.*") else None

            return {
                "video": str(video_file) if video_file else None,
                "audio": str(audio_file) if audio_file else None
            }

        except Exception as e:
            logger.error(f"dlb_mp4base demux failed: {e}")
            return self._demux_mp4_fallback(mp4_path, output_dir)

    def _demux_mp4_fallback(self, mp4_path: str, output_dir: str) -> Optional[Dict[str, str]]:
        """
        Fallback method to demux MP4 using FFmpeg

        Args:
            mp4_path: Path to MP4 file
            output_dir: Output directory

        Returns:
            Dictionary with demuxed track paths or None
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            mp4_name = Path(mp4_path).stem

            # Extract video
            video_path = output_dir / f"{mp4_name}.video.mp4"
            cmd_video = [
                "ffmpeg",
                "-i", mp4_path,
                "-an",  # No audio
                "-c:v", "copy",
                "-y",
                str(video_path)
            ]
            subprocess.run(cmd_video, capture_output=True, text=True, check=True)

            # Extract audio
            audio_path = output_dir / f"{mp4_name}.audio.m4a"
            cmd_audio = [
                "ffmpeg",
                "-i", mp4_path,
                "-vn",  # No video
                "-c:a", "copy",
                "-y",
                str(audio_path)
            ]
            subprocess.run(cmd_audio, capture_output=True, text=True, check=True)

            return {
                "video": str(video_path) if video_path.exists() else None,
                "audio": str(audio_path) if audio_path.exists() else None
            }

        except Exception as e:
            logger.error(f"FFmpeg demux fallback failed: {e}")
            return None


# Global instance
_mp4base_instance = None


def get_mp4base() -> DlbMp4Base:
    """
    Get global dlb_mp4base wrapper instance

    Returns:
        DlbMp4Base instance
    """
    global _mp4base_instance
    if _mp4base_instance is None:
        _mp4base_instance = DlbMp4Base()
    return _mp4base_instance


if __name__ == "__main__":
    # Test dlb_mp4base wrapper
    import sys

    logging.basicConfig(level=logging.INFO)

    mp4base = get_mp4base()

    print("\n" + "="*60)
    print("dlb_mp4base Wrapper Test")
    print("="*60)
    print(f"Available: {mp4base.is_available()}")
    print(f"Path: {mp4base.mp4base_path}")
    print("="*60)

    if len(sys.argv) > 1:
        mp4_file = sys.argv[1]
        print(f"\nGetting info for: {mp4_file}")
        info = mp4base.get_mp4_info(mp4_file)
        if info:
            import json
            print(json.dumps(info, indent=2))
