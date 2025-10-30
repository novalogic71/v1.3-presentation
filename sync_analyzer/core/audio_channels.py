#!/usr/bin/env python3
"""
Channel probing and stem extraction utilities for multi-channel analysis.
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

