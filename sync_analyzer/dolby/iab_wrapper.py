"""
IAB (Immersive Audio Bitstream) processing helpers.

This module wraps a Dolby IAB renderer (or Atmos Conversion Tool) to render
IAB streams from MXF/.iab inputs to PCM WAV for the sync analysis pipeline.
"""

import copy
import json
import logging
import os
import shutil
import subprocess
import tempfile
from ..core.temp_manager import get_temp_manager
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "iab_renderer": {
        "binary_name": "iab_renderer",
        "binary_candidates": ["iab_renderer", "cmdline_atmos_conversion_tool"],
        "args": [
            "-i",
            "{input}",
            "-o",
            "{output}",
            "-sr",
            "{sample_rate}",
            "-ch",
            "{channels}",
        ],
        "default_sample_rate": 48000,
        "downmix_format": "stereo",
        "render_quality": "high",
    },
}

DEFAULT_BIN_DIR = Path(__file__).resolve().parent / "bin"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "iab_config.json"


class IabProcessor:
    """
    Thin wrapper around dlb_mp4base utilities for IAB extraction and rendering.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.bin_dir = DEFAULT_BIN_DIR
        self.iab_renderer_path = self._find_tool(
            self.config["iab_renderer"].get("binary_candidates")
            or self.config["iab_renderer"].get("binary_name", "iab_renderer")
        )
        if self.iab_renderer_path:
            logger.info(f"[IAB] Using renderer binary: {self.iab_renderer_path}")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        base = copy.deepcopy(DEFAULT_CONFIG)
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if not path.exists():
            return base

        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._merge_dicts(base, data)
        except Exception as exc:
            logger.warning(f"Failed to load IAB config from {path}: {exc}")
        return base

    def _merge_dicts(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def _find_tool(self, binary_names: Union[str, Sequence[str]]) -> Optional[str]:
        names = [binary_names] if isinstance(binary_names, str) else list(binary_names)
        repo_root = Path(__file__).resolve().parents[2]
        for binary_name in names:
            env_key = f"IAB_{binary_name.upper()}_PATH".replace("-", "_")
            env_value = os.getenv(env_key)
            if env_value and Path(env_value).exists():
                return str(Path(env_value).resolve())

            candidate = Path(binary_name)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())

            bin_candidate = self.bin_dir / binary_name
            if bin_candidate.is_file() and os.access(bin_candidate, os.X_OK):
                return str(bin_candidate.resolve())

            extra_home = (
                os.getenv("ATMOS_CONVERSION_TOOL_HOME")
                or os.getenv("IAB_CONVERSION_TOOL_HOME")
                or os.getenv("DOLBY_ATMOS_CONVERSION_TOOL_HOME")
            )
            if extra_home:
                for prefix in (Path(extra_home), Path(extra_home) / "bin"):
                    extra_candidate = prefix / binary_name
                    if extra_candidate.is_file() and os.access(extra_candidate, os.X_OK):
                        return str(extra_candidate.resolve())

            if "cmdline_atmos_conversion_tool" in binary_name:
                for candidate in repo_root.glob(
                    "dolby-atmos-conversion-tool*/bin/cmdline_atmos_conversion_tool"
                ):
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        return str(candidate.resolve())

            located = shutil.which(binary_name)
            if located:
                return located

        return None

    def _format_args(self, args: List[str], **values: Any) -> List[str]:
        formatted: List[str] = []
        for item in args:
            try:
                formatted.append(item.format(**values))
            except Exception:
                formatted.append(item)
        return formatted

    def _run_command(self, cmd: List[str], description: str) -> bool:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                logger.error(
                    f"{description} failed with code {result.returncode}: "
                    f"{result.stderr.strip()}"
                )
                return False
            if result.stderr:
                logger.debug(f"{description} stderr: {result.stderr.strip()}")
            return True
        except FileNotFoundError:
            logger.error(f"{description} failed: command not found ({cmd[0]})")
            return False
        except Exception as exc:
            logger.error(f"{description} failed: {exc}")
            return False

    def is_available(self) -> bool:
        return bool(self.iab_renderer_path)

    def render_iab_to_wav(
        self,
        iab_path: str,
        output_wav: str,
        sample_rate: int = 48000,
        channels: int = 2,
        trim_duration: Optional[int] = None,
    ) -> bool:
        """
        Render an IAB bitstream to PCM WAV using the Dolby renderer.
        """
        if not self.iab_renderer_path:
            logger.warning("IAB renderer not available")
            return False

        if not Path(iab_path).exists():
            logger.error(f"IAB payload not found: {iab_path}")
            return False

        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)

        renderer_name = Path(self.iab_renderer_path).name.lower()
        if "cmdline_atmos_conversion_tool" in renderer_name:
            return self._render_with_conversion_tool(
                iab_path,
                output_wav,
                sample_rate=sample_rate,
                channels=channels,
                trim_duration=trim_duration,
            )

        args = self.config["iab_renderer"].get("args") or [
            "-i",
            "{input}",
            "-o",
            "{output}",
            "-sr",
            "{sample_rate}",
            "-ch",
            "{channels}",
        ]
        cmd = [
            self.iab_renderer_path,
            *self._format_args(
                args,
                input=iab_path,
                output=output_wav,
                sample_rate=sample_rate,
                channels=channels,
            ),
        ]

        logger.info(
            f"[IAB] Rendering {iab_path} -> {output_wav} "
            f"({channels}ch @ {sample_rate}Hz)"
        )

        success = self._run_command(cmd, "IAB render")
        if success and not Path(output_wav).exists():
            logger.error("IAB renderer reported success but no output WAV was produced")
            return False
        return success

    def convert_to_adm_wav(
        self,
        iab_path: str,
        output_wav: str,
        trim_duration: Optional[int] = None,
        sample_rate: int = 48000,
    ) -> bool:
        """
        Render IAB to a full-resolution WAV (ADM-style) using the Atmos Conversion Tool.
        Falls back to the standard render when the conversion tool is not available.
        """
        if not self.iab_renderer_path:
            logger.warning("IAB renderer not available for ADM conversion")
            return False

        Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
        renderer_name = Path(self.iab_renderer_path).name.lower()

        if "cmdline_atmos_conversion_tool" in renderer_name:
            # Use TempManager for organized cleanup
            mgr = get_temp_manager()
            job = mgr.create_job("iab_to_adm")
            temp_dir = job.path
            try:
                cmd = [
                    self.iab_renderer_path,
                    "-i",
                    iab_path,
                    "-o",
                    str(temp_dir),
                    "-f",
                    "wav",
                    "--target_sample_rate",
                    str(sample_rate),
                ]
                if trim_duration and trim_duration > 0:
                    cmd += ["--trim_duration", str(trim_duration)]

                logger.info(f"[IAB] Converting to ADM WAV via Dolby tool -> {temp_dir}")
                if not self._run_command(cmd, "IAB conversion tool render"):
                    return False

                wav_candidates = sorted(temp_dir.glob("*.wav"))
                if not wav_candidates:
                    logger.error("Conversion tool did not produce any WAV output")
                    return False

                shutil.move(str(wav_candidates[0]), output_wav)
                return True
            finally:
                job.cleanup()

        # Fallback: use standard render path (may be downmixed depending on renderer)
        return self.render_iab_to_wav(
            iab_path,
            output_wav,
            sample_rate=sample_rate,
            channels=int(self.config["iab_renderer"].get("channels", 2) or 2),
            trim_duration=trim_duration,
        )

    def _render_with_conversion_tool(
        self,
        iab_path: str,
        output_wav: str,
        sample_rate: int,
        channels: int,
        trim_duration: Optional[int],
    ) -> bool:
        """
        Use Dolby Atmos Conversion Tool to convert to WAV, then downmix/re-sample with ffmpeg.
        """
        # Use TempManager for organized cleanup
        mgr = get_temp_manager()
        job = mgr.create_job("iab_convert")
        temp_dir = job.path
        try:
            cmd = [
                self.iab_renderer_path,
                "-i",
                iab_path,
                "-o",
                str(temp_dir),
                "-f",
                "wav",
                "--target_sample_rate",
                str(sample_rate),
            ]
            if channels == 2:
                cmd += ["--set_warp_mode", "downmix_loro"]
            if trim_duration and trim_duration > 0:
                cmd += ["--trim_duration", str(trim_duration)]

            logger.info(f"[IAB] Using Dolby Conversion Tool -> {temp_dir}")
            if not self._run_command(cmd, "IAB conversion tool render"):
                return False

            wav_candidates = sorted(temp_dir.glob("*.wav"))
            if not wav_candidates:
                logger.error("Conversion tool did not produce any WAV output")
                return False

            source_wav = wav_candidates[0]
            
            # Use professional ITU-R BS.775 downmix for stereo
            if channels == 2:
                try:
                    from .atmos_downmix import downmix_to_stereo_file
                    result_path = downmix_to_stereo_file(
                        str(source_wav),
                        output_wav,
                        include_lfe=False,
                        normalize=True,
                        bit_depth=16
                    )
                    if result_path:
                        logger.info("[IAB] Applied ITU-R BS.775 professional downmix to stereo")
                        return True
                    else:
                        logger.warning("[IAB] Professional downmix failed, falling back to ffmpeg")
                except ImportError:
                    logger.warning("[IAB] atmos_downmix module not available, using ffmpeg")
                except Exception as dm_exc:
                    logger.warning(f"[IAB] Professional downmix error: {dm_exc}, falling back to ffmpeg")
            
            # Fallback: use ffmpeg for non-stereo or if downmix failed
            ffmpeg_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source_wav),
                "-ac",
                str(channels),
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                output_wav,
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"ffmpeg downmix failed: {result.stderr.strip()}")
                try:
                    shutil.move(str(source_wav), output_wav)
                    logger.warning("[IAB] Using raw conversion-tool WAV (no downmix) due to ffmpeg failure")
                    return True
                except Exception as move_exc:
                    logger.error(f"[IAB] Unable to copy conversion-tool WAV after ffmpeg failure: {move_exc}")
                    return False
            return True
        finally:
            job.cleanup()

    def extract_and_render(
        self,
        mxf_path: str,
        output_wav: str,
        sample_rate: int = 48000,
        channels: int = 2,
        trim_duration: Optional[int] = None,
    ) -> Optional[str]:
        """
        Full pipeline: MXF/.iab -> PCM WAV render.
        """
        rendered = self.render_iab_to_wav(
            mxf_path,
            output_wav,
            sample_rate=sample_rate,
            channels=channels,
            trim_duration=trim_duration,
        )
        if not rendered:
            return None
        if not Path(output_wav).exists():
            logger.error("IAB render completed but output WAV is missing")
            return None
        return output_wav
