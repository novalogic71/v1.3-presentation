#!/usr/bin/env python3
"""
Channel probing and stem extraction utilities for multi-channel analysis.

Supports:
- Standard multi-channel audio (stereo, 5.1, 7.1)
- Multi-mono streams
- Dolby Atmos bed extraction (EC3, EAC3, ADM WAV)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ChannelSpec:
    """Specification for extracting a single channel stem."""
    kind: str  # 'multichannel' or 'stream'
    stream_index: int  # audio stream index within input (0-based across audio streams)
    channel_index: Optional[int] = None  # for multichannel stream
    role: Optional[str] = None  # e.g., FL, FR, FC, LFE, SL, SR, DL, DR


def _run_ffprobe_json(path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def probe_audio_layout(path: str) -> Dict:
    """Return a simplified description of audio streams and channels.

    Output keys:
    - streams: list of {index, codec_name, channels, channel_layout}
    - has_multichannel_stream: bool
    - has_multi_mono: bool (more than one mono stream)
    """
    data = _run_ffprobe_json(path)
    streams = []
    for s in data.get("streams", []):
        if s.get("codec_type") != "audio":
            continue
        streams.append(
            {
                "index": s.get("index"),
                "codec_name": s.get("codec_name"),
                "channels": int(s.get("channels", 0) or 0),
                "channel_layout": s.get("channel_layout") or "",
            }
        )
    mono_count = sum(1 for s in streams if s["channels"] == 1)
    has_multichannel_stream = any(s["channels"] > 1 for s in streams)
    has_multi_mono = mono_count > 1
    return {
        "streams": streams,
        "has_multichannel_stream": has_multichannel_stream,
        "has_multi_mono": has_multi_mono,
    }


def _layout_roles(layout: str, channels: int) -> List[str]:
    """Best-effort mapping from layout to channel role names used by pan.

    Returns a list of roles (e.g., [FL, FR, FC, LFE, SL, SR]) length==channels,
    or generic [c0, c1, ...] when unknown.

    Supports Atmos bed configurations:
    - 7.1.2: 10 channels (7.1 + 2 height)
    - 7.1.4: 12 channels (7.1 + 4 height)
    - 9.1.6: 16 channels (9.1 + 6 height)
    """
    layout = (layout or "").lower()
    known = {
        "stereo": ["FL", "FR"],
        "2.0": ["FL", "FR"],
        "mono": ["c0"],
        "5.1": ["FL", "FR", "FC", "LFE", "SL", "SR"],
        "5.1(side)": ["FL", "FR", "FC", "LFE", "SL", "SR"],
        "4.0": ["FL", "FR", "FC", "BC"],
        "7.1": ["FL", "FR", "FC", "LFE", "SL", "SR", "BL", "BR"],
        # Atmos bed configurations
        "7.1.2": ["FL", "FR", "FC", "LFE", "SL", "SR", "BL", "BR", "TpFL", "TpFR"],
        "7.1.4": ["FL", "FR", "FC", "LFE", "SL", "SR", "BL", "BR", "TpFL", "TpFR", "TpBL", "TpBR"],
        "9.1.6": ["FL", "FR", "FC", "LFE", "SL", "SR", "BL", "BR", "FLC", "FRC",
                  "TpFL", "TpFR", "TpBL", "TpBR", "TpSL", "TpSR"],
    }
    for key, roles in known.items():
        if key in layout and len(roles) == channels:
            return roles
    # Generic fallback
    return [f"c{i}" for i in range(channels)]


def list_channel_specs(path: str) -> List[ChannelSpec]:
    """Derive channel specs for extraction.

    - If there is a multichannel audio stream, extract its channels as roles
      using pan indices or role names.
    - For additional mono streams (multi-mono), map each stream separately.
    """
    info = probe_audio_layout(path)
    specs: List[ChannelSpec] = []
    audio_streams = [s for s in info["streams"]]
    # Normalize audio stream order by appearance (ffprobe index order)
    audio_streams.sort(key=lambda s: s["index"])
    for si, s in enumerate(audio_streams):
        ch = s["channels"]
        if ch <= 0:
            continue
        if ch == 1:
            specs.append(ChannelSpec(kind="stream", stream_index=si, channel_index=None, role=f"S{si}"))
        else:
            roles = _layout_roles(s.get("channel_layout", ""), ch)
            for ci in range(ch):
                role = roles[ci] if ci < len(roles) else f"c{ci}"
                specs.append(ChannelSpec(kind="multichannel", stream_index=si, channel_index=ci, role=role))
    return specs


def extract_stem(input_path: str, out_wav: str, spec: ChannelSpec) -> None:
    """Extract a single mono channel stem to WAV 48k/16-bit.

    For multichannel streams, use pan to isolate by channel index/role.
    For mono streams, map the specific audio stream directly.
    """
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    if spec.kind == "stream":
        # Map the mono audio stream
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            input_path,
            "-map",
            f"0:a:{spec.stream_index}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            out_wav,
        ]
    else:
        # Use the first audio stream with channels>1 as the base, then pan out the channel
        # Determine selector (role or c{index})
        selector = spec.role if spec.role and spec.role.startswith("F") or spec.role in {"FC", "LFE", "SL", "SR", "BL", "BR"} else None
        if not selector:
            selector = f"c{spec.channel_index or 0}"
        pan_expr = f"pan=mono|c0={selector}"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            input_path,
            "-map",
            f"0:a:{spec.stream_index}",
            "-filter:a",
            pan_expr,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            out_wav,
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg stem extraction failed ({spec}): {proc.stderr.strip()}")


def extract_all_stems(input_path: str, out_dir: str) -> Dict[str, str]:
    """Extract all detectable channels to mono WAV stems. Returns role->path map.

    Role keys are best-effort: FL/FR/FC/LFE/SL/SR when available, otherwise
    placeholders like c0/c1 for multichannel, or S0/S1 for mono streams.
    """
    stems: Dict[str, str] = {}
    specs = list_channel_specs(input_path)
    for spec in specs:
        role = spec.role or (f"c{spec.channel_index}" if spec.channel_index is not None else f"S{spec.stream_index}")
        out_wav = str(Path(out_dir) / f"{Path(input_path).stem}_{role}.wav")
        extract_stem(input_path, out_wav, spec)
        stems[role] = out_wav
    return stems


def make_temp_stems(input_path: str) -> Tuple[str, Dict[str, str]]:
    """Create a temporary directory with stems for all channels.

    Returns (temp_dir, role_to_path). Caller should remove the directory when done.
    """
    tmp = tempfile.mkdtemp(prefix="stems_")
    try:
        mapping = extract_all_stems(input_path, tmp)
        return tmp, mapping
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


# ============================================================================
# Dolby Atmos Support
# ============================================================================


def is_atmos_file(file_path: str) -> bool:
    """
    Check if file contains Dolby Atmos audio

    Args:
        file_path: Path to audio/video file

    Returns:
        True if file has Atmos audio, False otherwise
    """
    try:
        # Import here to avoid circular dependency
        from ..dolby.atmos_metadata import extract_atmos_metadata, is_atmos_codec

        metadata = extract_atmos_metadata(file_path)
        if metadata:
            # ADM WAV files have is_adm_wav flag set (they use PCM codec)
            # IAB files have is_iab flag set
            # Other Atmos formats are detected by codec
            return metadata.is_adm_wav or metadata.is_iab or metadata.is_mxf or is_atmos_codec(metadata.codec)
        return False
    except ImportError:
        # Fallback if dolby module not available
        return _is_atmos_fallback(file_path)
    except Exception:
        return False


def _is_atmos_fallback(file_path: str) -> bool:
    """
    Fallback Atmos detection using file extension and ffprobe

    Args:
        file_path: Path to audio/video file

    Returns:
        True if likely Atmos, False otherwise
    """
    ext = Path(file_path).suffix.lower()
    if ext in ['.ec3', '.eac3', '.adm']:
        return True

    try:
        data = _run_ffprobe_json(file_path)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                codec = stream.get("codec_name", "").lower()
                if codec in ['eac3', 'ec3', 'truehd']:
                    return True
    except Exception:
        pass

    return False


def extract_atmos_bed_stereo(input_path: str, output_path: str, sample_rate: int = 22050) -> str:
    """
    Extract Atmos bed as stereo downmix for sync analysis

    For Atmos files (EC3, EAC3, ADM WAV, IAB):
    1. Convert to MP4 with black video using dlb_mp4base/FFmpeg
    2. Extract audio from MP4 to WAV
    3. Convert to stereo at target sample rate

    Args:
        input_path: Path to Atmos file (EC3/EAC3/MP4 with Atmos)
        output_path: Output WAV path
        sample_rate: Target sample rate (default: 22050 for analysis)

    Returns:
        Path to extracted stereo WAV
    """
    import tempfile
    import os
    import logging

    logger = logging.getLogger(__name__)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Check file extension to determine format
    ext = Path(input_path).suffix.lower()

    # Atmos formats that need conversion to MP4 first
    needs_conversion = ext in ['.ec3', '.eac3', '.adm', '.iab']

    if needs_conversion:
        # Use dlb_mp4base pipeline: Atmos → MP4 → WAV extraction
        logger.info(f"Converting Atmos file to MP4 for proper extraction: {input_path}")

        try:
            from ..dolby.atmos_converter import convert_atmos_to_mp4

            # Step 1: Convert Atmos file to MP4 with black video
            temp_mp4 = tempfile.mktemp(suffix=".mp4", prefix="atmos_temp_")

            result = convert_atmos_to_mp4(
                atmos_path=input_path,
                output_path=temp_mp4,
                fps=24.0,
                resolution="1920x1080",
                preserve_original=True
            )

            if not result or not os.path.exists(temp_mp4):
                raise RuntimeError(f"Failed to convert Atmos to MP4: {input_path}")

            logger.info(f"Atmos converted to MP4: {temp_mp4}")

            # Step 2: Extract audio from MP4 to stereo WAV
            logger.info(f"Extracting audio from MP4 to stereo WAV...")
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                temp_mp4,
                "-vn",  # No video
                "-ac",
                "2",  # Stereo downmix
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                output_path,
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            # Clean up temp MP4
            try:
                os.remove(temp_mp4)
            except:
                pass

            if proc.returncode != 0:
                raise RuntimeError(f"Failed to extract audio from MP4: {proc.stderr.strip()}")

            logger.info(f"Successfully extracted Atmos bed to stereo WAV: {output_path}")
            return output_path

        except ImportError as e:
            logger.warning(f"Dolby module not available, using direct FFmpeg: {e}")
            # Fallback to direct FFmpeg

    # For MP4/MOV/MXF with Atmos audio, or fallback extraction
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_path,
        "-vn",  # No video
        "-ac",
        "2",  # Stereo downmix
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        output_path,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to extract Atmos bed stereo: {proc.stderr.strip()}")

    return output_path


def extract_atmos_bed_mono(input_path: str, output_path: str, sample_rate: int = 22050) -> str:
    """
    Extract Atmos bed as mono downmix for sync analysis

    For Atmos files (EC3, EAC3, ADM WAV, IAB):
    1. Convert to MP4 with black video using dlb_mp4base/FFmpeg
    2. Extract audio from MP4 to WAV
    3. Convert to mono at target sample rate

    This ensures proper Atmos decoding and avoids FFmpeg extraction issues.

    Args:
        input_path: Path to Atmos file
        output_path: Output WAV path
        sample_rate: Target sample rate (default: 22050 for analysis)

    Returns:
        Path to extracted mono WAV
    """
    import tempfile
    import os
    import logging

    logger = logging.getLogger(__name__)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Check file extension to determine format
    ext = Path(input_path).suffix.lower()

    # Atmos formats that need conversion to MP4 first
    needs_conversion = ext in ['.ec3', '.eac3', '.adm', '.iab']

    if needs_conversion:
        # Use dlb_mp4base pipeline: Atmos → MP4 → WAV extraction
        logger.info(f"Converting Atmos file to MP4 for proper extraction: {input_path}")

        try:
            from ..dolby.atmos_converter import convert_atmos_to_mp4

            # Step 1: Convert Atmos file to MP4 with black video
            temp_mp4 = tempfile.mktemp(suffix=".mp4", prefix="atmos_temp_")

            result = convert_atmos_to_mp4(
                atmos_path=input_path,
                output_path=temp_mp4,
                fps=24.0,
                resolution="1920x1080",
                preserve_original=True
            )

            if not result or not os.path.exists(temp_mp4):
                raise RuntimeError(f"Failed to convert Atmos to MP4: {input_path}")

            logger.info(f"Atmos converted to MP4: {temp_mp4}")

            # Step 2: Extract audio from MP4 to mono WAV
            logger.info(f"Extracting audio from MP4 to WAV...")
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                temp_mp4,
                "-vn",  # No video
                "-ac",
                "1",  # Mono downmix
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                output_path,
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            # Clean up temp MP4
            try:
                os.remove(temp_mp4)
            except:
                pass

            if proc.returncode != 0:
                raise RuntimeError(f"Failed to extract audio from MP4: {proc.stderr.strip()}")

            logger.info(f"Successfully extracted Atmos bed to mono WAV: {output_path}")
            return output_path

        except ImportError as e:
            logger.warning(f"Dolby module not available, using direct FFmpeg: {e}")
            # Fallback to direct FFmpeg

    # For MP4/MOV/MXF with Atmos audio, or fallback extraction
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_path,
        "-vn",  # No video
        "-ac",
        "1",  # Mono downmix
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        output_path,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to extract Atmos bed mono: {proc.stderr.strip()}")

    return output_path


def extract_atmos_bed_channels(input_path: str, out_dir: str, sample_rate: int = 48000) -> Dict[str, str]:
    """
    Extract Atmos bed as individual 7.1 channel stems

    This is for per-channel analysis of the Atmos bed (objects ignored).

    Args:
        input_path: Path to Atmos file
        out_dir: Output directory for channel stems
        sample_rate: Target sample rate (default: 48000 to preserve quality)

    Returns:
        Dictionary mapping channel roles to WAV file paths
        Example: {"FL": "path/to/FL.wav", "FR": "path/to/FR.wav", ...}
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # First, check if we have a multichannel stream or need to extract bed
    info = probe_audio_layout(input_path)

    # Look for the bed stream (typically 7.1 or 5.1)
    bed_stream = None
    for stream in info["streams"]:
        channels = stream["channels"]
        if channels >= 6:  # 5.1 or higher
            bed_stream = stream
            break

    if not bed_stream:
        raise ValueError(f"No multichannel bed found in Atmos file: {input_path}")

    # Extract bed channels using the standard extraction
    # This will work because Atmos MP4 files have the bed as a multichannel stream
    return extract_all_stems(input_path, out_dir)

