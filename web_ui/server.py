#!/usr/bin/env python3
"""
Backend server for Professional Audio Sync Analyzer UI
Provides file system access and sync analysis API endpoints
"""

import os
import json
import time
import asyncio
import subprocess
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import logging
import mimetypes
import json as _json
from typing import Any
from sync_analyzer.analysis import analyze
try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency for JSON coercion
    np = None
try:
    import soundfile as sf
except Exception:  # pragma: no cover - optional dependency for mixdown analysis
    sf = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
MOUNT_PATH = "/mnt/data"
PROXY_CACHE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "proxy_cache")
)


def _ensure_proxy_cache_dir() -> None:
    """Ensure proxy cache directory exists and is writable; fall back to /tmp if needed."""
    global PROXY_CACHE_DIR
    try:
        os.makedirs(PROXY_CACHE_DIR, exist_ok=True)
    except Exception as e:
        logger.warning(f"Proxy cache create failed at {PROXY_CACHE_DIR}: {e}")
    if os.path.isdir(PROXY_CACHE_DIR) and os.access(PROXY_CACHE_DIR, os.W_OK):
        return
    fallback = os.path.abspath(os.path.join("/tmp", f"sync_proxy_cache_{os.getuid()}"))
    try:
        os.makedirs(fallback, exist_ok=True)
        PROXY_CACHE_DIR = fallback
        logger.warning(f"Proxy cache not writable; using fallback: {PROXY_CACHE_DIR}")
    except Exception as e:
        raise RuntimeError(f"Proxy cache fallback failed: {e}")


_ensure_proxy_cache_dir()
ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aiff",
    ".ogg",
    ".mov",
    ".mp4",
    ".avi",
    ".mkv",
    ".mxf",
    ".ec3",
    ".eac3",
    ".adm",
    ".iab",
}

# Progress tracking for long-running analysis jobs
_progress_store = {}

# Background job storage - stores job results and status
_background_jobs = {}

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

# Thread pool for background analysis jobs
_job_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="analysis_worker")

def _update_progress(job_id: str, percentage: int, message: str) -> None:
    """Update progress for a job."""
    _progress_store[job_id] = {
        "percentage": percentage,
        "message": message,
        "timestamp": time.time()
    }
    # Also update background job if it exists
    if job_id in _background_jobs:
        _background_jobs[job_id]["progress"] = percentage
        _background_jobs[job_id]["status_message"] = message

def _get_progress(job_id: str) -> dict:
    """Get progress for a job."""
    return _progress_store.get(job_id, {"percentage": 0, "message": "Unknown job", "timestamp": 0})

def _clear_progress(job_id: str) -> None:
    """Clear progress for a job."""
    _progress_store.pop(job_id, None)

def _create_background_job(job_id: str, job_type: str, params: dict) -> dict:
    """Create a new background job entry."""
    job = {
        "job_id": job_id,
        "type": job_type,
        "status": "pending",
        "progress": 0,
        "status_message": "Queued",
        "params": params,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "completed_at": None
    }
    _background_jobs[job_id] = job
    return job

def _update_job_status(job_id: str, status: str, progress: int = None, message: str = None, result: dict = None, error: str = None) -> None:
    """Update background job status."""
    if job_id not in _background_jobs:
        return
    job = _background_jobs[job_id]
    job["status"] = status
    if progress is not None:
        job["progress"] = progress
    if message is not None:
        job["status_message"] = message
    if result is not None:
        job["result"] = result
    if error is not None:
        job["error"] = error
    if status in ["completed", "failed"]:
        job["completed_at"] = time.time()

def _get_job(job_id: str) -> dict:
    """Get background job by ID."""
    return _background_jobs.get(job_id)


def is_safe_path(path):
    """Check if path is safe and within allowed directory"""
    try:
        resolved = Path(path).resolve()
        mount_resolved = Path(MOUNT_PATH).resolve()
        return str(resolved).startswith(str(mount_resolved))
    except:
        return False


def get_file_type(filepath):
    """Determine file type based on extension"""
    ext = Path(filepath).suffix.lower()
    if ext in {".wav", ".mp3", ".flac", ".m4a", ".aiff", ".ogg", ".ec3", ".eac3", ".adm", ".iab"}:
        return "audio"
    elif ext in {".mov", ".mp4", ".avi", ".mkv", ".wmv", ".mxf"}:
        return "video"
    else:
        return "file"


def _json_safe(value: Any) -> Any:
    """Coerce numpy/scalar types into JSON-serializable values."""
    if np is not None:
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _hash_for_proxy(path: str) -> str:
    import hashlib

    try:
        st = os.stat(path)
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")
    except Exception:
        key = path.encode("utf-8")
    return hashlib.sha1(key).hexdigest()


def _ensure_wav_proxy(src_path: str, role: str) -> str:
    """Create or reuse a WAV proxy for the given source. Returns absolute output path."""
    _ensure_proxy_cache_dir()
    h = _hash_for_proxy(src_path)
    base = f"{h}_{role}.wav"
    out_path = os.path.join(PROXY_CACHE_DIR, base)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path
    
    # Atmos-aware extraction (matches atmos-support branch behavior)
    try:
        from sync_analyzer.core.audio_channels import is_atmos_file, extract_atmos_bed_stereo
        if is_atmos_file(src_path):
            logger.info(f"Detected Atmos file, using specialized extraction: {Path(src_path).name}")
            temp_atmos_path = out_path + ".atmos_temp.wav"
            extract_atmos_bed_stereo(src_path, temp_atmos_path, sample_rate=48000)
            if os.path.exists(temp_atmos_path) and os.path.getsize(temp_atmos_path) > 0:
                norm_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    temp_atmos_path,
                    "-acodec",
                    "pcm_s16le",
                    out_path,
                ]
                logger.info(f"Transcoding Atmos proxy (role={role}): {' '.join(norm_cmd)}")
                norm_result = subprocess.run(norm_cmd, capture_output=True, text=True, timeout=300)
                try:
                    os.remove(temp_atmos_path)
                except Exception:
                    pass
                if norm_result.returncode == 0 and os.path.exists(out_path):
                    logger.info(f"Atmos proxy created: {out_path}")
                    return out_path
                logger.error(f"Atmos transcode failed: {norm_result.stderr}")
    except ImportError as e:
        logger.warning(f"Atmos detection unavailable: {e}, falling back to ffmpeg")
    except Exception as e:
        logger.warning(f"Atmos extraction failed: {e}, falling back to ffmpeg")
    # Transcode to WAV 48k stereo for Chrome/WebAudio compatibility
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        src_path,
        "-vn",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-acodec",
        "pcm_s16le",
        out_path,
    ]
    logger.info(f"Creating WAV proxy: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error(f"Proxy creation failed: {result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out_path


def _probe_audio_layout(path: str) -> dict:
    """Minimal ffprobe helper mirroring core util for server-side repair."""
    try:
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
        pr = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if pr.returncode != 0:
            return {"streams": []}
        data = _json.loads(pr.stdout)
        streams = []
        for s in data.get("streams", []):
            if s.get("codec_type") == "audio":
                streams.append(
                    {
                        "index": s.get("index"),
                        "codec_name": s.get("codec_name"),
                        "channels": int(s.get("channels") or 0),
                        "channel_layout": s.get("channel_layout") or "",
                    }
                )
        return {"streams": streams}
    except Exception:
        return {"streams": []}


def _detect_channel_type(filename: str) -> str:
    """Detect channel type from filename pattern like _a0.mxf or Pro Tools naming.
    
    Supported patterns:
    - MXF style: _a0, _a1, _a2, _a3
    - Pro Tools: _L, _R, _C, _LFE, _Ls, _Rs, _Lt, _Rt, etc.
    
    Channel mapping:
    - stereo_lr: Left/Right stereo pair
    - center_lfe: Center and/or LFE (dialogue + bass)
    - surround: Surround channels (Ls, Rs, Lrs, Rrs)
    - mixdown: Stereo mixdown (Lt/Rt, stereo mix)
    """
    import re
    fn_lower = filename.lower()
    
    # Pattern 1: _a0, _a1, _a2, _a3 MXF format
    match = re.search(r'_a(\d+)\.', fn_lower)
    if match:
        idx = int(match.group(1))
        return {
            0: 'stereo_lr',
            1: 'center_lfe',
            2: 'surround',
            3: 'mixdown'
        }.get(idx, 'unknown')
    
    # Pattern 2: Pro Tools / standard channel naming
    # LFE detection (highest priority - very specific content)
    if re.search(r'[_\-\.]lfe[_\-\.]?|[_\-\.]sub[_\-\.]?', fn_lower):
        return 'center_lfe'
    
    # Center channel
    if re.search(r'[_\-\.]c[_\-\.]|[_\-\.]center[_\-\.]?|[_\-\.]dialogue[_\-\.]?', fn_lower):
        return 'center_lfe'
    
    # Surround channels (Ls, Rs, Lrs, Rrs, rear)
    if re.search(r'[_\-\.](ls|rs|lrs|rrs|lss|rss)[_\-\.]?|[_\-\.]surround|[_\-\.]rear', fn_lower):
        return 'surround'
    
    # Stereo mixdown (Lt/Rt, mix, stereo)
    if re.search(r'[_\-\.](lt|rt)[_\-\.]|[_\-\.]ltrt|[_\-\.]mix[_\-\.]?|[_\-\.]stereo[_\-\.]?|[_\-\.]2ch', fn_lower):
        return 'mixdown'
    
    # Left/Right stereo pair
    if re.search(r'[_\-\.](l|r|left|right)[_\-\.]', fn_lower):
        return 'stereo_lr'
    
    return 'unknown'


def _get_optimal_method(channel_type: str) -> list:
    """Return optimal analysis method(s) for channel type.
    
    Method selection rationale:
    - stereo_lr: Spectral works better for sparse stereo content
    - center_lfe: Onset detects LFE bass transients well
    - surround: Spectral for ambience/effects frequency patterns
    - mixdown: Both work well since it has all content
    """
    return {
        'stereo_lr': ['spectral'],
        'center_lfe': ['onset'],
        'surround': ['spectral'],
        'mixdown': ['onset', 'spectral'],
        'unknown': ['spectral', 'onset']
    }.get(channel_type, ['spectral'])


def _vote_for_offset(results: list) -> tuple:
    """Find most common offset across all channel results using voting.
    
    All stems from the same delivery should have the same sync offset,
    so we use voting to find the correct one when methods disagree.
    
    Returns:
        tuple: (voted_offset, vote_count, total_results)
    """
    from collections import Counter
    if not results:
        return (0.0, 0, 0)
    # Round to nearest 0.1s to handle minor timing variations
    offsets = [round(r.get('offset_seconds', 0), 1) for r in results if r.get('offset_seconds') is not None]
    if not offsets:
        return (0.0, 0, len(results))
    counter = Counter(offsets)
    most_common = counter.most_common(1)
    if most_common:
        voted_offset, vote_count = most_common[0]
        return (voted_offset, vote_count, len(offsets))
    return (0.0, 0, len(offsets))


def _probe_duration_seconds(path: str) -> float:
    try:
        pr = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if pr.returncode == 0:
            data = _json.loads(pr.stdout)
            return float(data.get("format", {}).get("duration") or 0.0)
    except Exception:
        pass
    return 0.0


def _require_mixdown_deps() -> None:
    if np is None or sf is None:
        raise RuntimeError("Mixdown analysis requires numpy and soundfile")


def _normalize_series(values):
    values = np.asarray(values, dtype=np.float32)
    if values.size == 0:
        return values
    mean = float(np.mean(values))
    std = float(np.std(values)) + 1e-8
    return (values - mean) / std


def _rms_envelope_stream(path: str, sample_rate: int, hop_seconds: float) -> np.ndarray:
    hop = max(1, int(sample_rate * hop_seconds))
    rms_vals = []
    buffer = np.zeros(0, dtype=np.float32)
    blocksize = hop * 200
    for block in sf.blocks(path, blocksize=blocksize, dtype="float32", always_2d=False):
        if block is None or len(block) == 0:
            break
        if block.ndim > 1:
            block = block.mean(axis=1)
        if buffer.size:
            block = np.concatenate([buffer, block])
            buffer = np.zeros(0, dtype=np.float32)
        n_frames = len(block) // hop
        if n_frames > 0:
            frames = block[: n_frames * hop].reshape(n_frames, hop)
            rms_vals.extend(np.sqrt(np.mean(frames * frames, axis=1)))
            buffer = block[n_frames * hop :]
        else:
            buffer = block
    return np.asarray(rms_vals, dtype=np.float32)


def _read_segment(path: str, start_seconds: float, duration_seconds: float, sample_rate: int) -> np.ndarray:
    if duration_seconds <= 0:
        return np.zeros(0, dtype=np.float32)
    start = max(0, int(start_seconds * sample_rate))
    frames = int(duration_seconds * sample_rate)
    with sf.SoundFile(path) as f:
        f.seek(start)
        data = f.read(frames, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data


def _mixdown_components(component_wavs, output_path: str) -> int:
    if not component_wavs:
        raise RuntimeError("No component audio to mixdown")
    files = [sf.SoundFile(wav) for wav in component_wavs]
    sample_rate = files[0].samplerate
    for f in files[1:]:
        if f.samplerate != sample_rate:
            logger.warning("Mixdown sample rate mismatch: %s vs %s", sample_rate, f.samplerate)
    blocksize = 131072
    with sf.SoundFile(output_path, mode="w", samplerate=sample_rate, channels=1, subtype="PCM_16") as out_f:
        while True:
            mix = np.zeros(blocksize, dtype=np.float32)
            any_data = False
            for f in files:
                data = f.read(blocksize, dtype="float32", always_2d=False)
                if data is None or len(data) == 0:
                    continue
                any_data = True
                if data.ndim > 1:
                    data = data.mean(axis=1)
                if len(data) < blocksize:
                    data = np.pad(data, (0, blocksize - len(data)))
                mix += data
            if not any_data:
                break
            mix *= 1.0 / max(1, len(files))
            out_f.write(mix)
    for f in files:
        f.close()
    return sample_rate


def _hash_component_list(paths) -> str:
    import hashlib

    key = "|".join(_hash_for_proxy(p) for p in sorted(paths))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _compute_mixdown_offset(master_path: str, component_paths, hop_seconds: float,
                            anchor_window_seconds: float, refine_window_seconds: float,
                            refine_pad_seconds: float, max_candidates: int = 3, job_id: str = None) -> dict:
    _require_mixdown_deps()

    if job_id:
        _update_progress(job_id, 15, "Creating audio proxies...")

    master_wav = _ensure_wav_proxy(master_path, "master")
    component_wavs = [_ensure_wav_proxy(p, "component") for p in component_paths]
    mix_hash = _hash_component_list(component_paths)
    mix_path = os.path.join(PROXY_CACHE_DIR, f"{mix_hash}_mixdown.wav")
    if not os.path.exists(mix_path) or os.path.getsize(mix_path) == 0:
        _mixdown_components(component_wavs, mix_path)

    if job_id:
        _update_progress(job_id, 30, "Computing audio envelopes...")

    sample_rate = sf.info(master_wav).samplerate
    master_rms = _rms_envelope_stream(master_wav, sample_rate, hop_seconds)
    mix_rms = _rms_envelope_stream(mix_path, sample_rate, hop_seconds)
    master_rms_n = _normalize_series(master_rms)
    mix_rms_n = _normalize_series(mix_rms)
    if master_rms_n.size == 0 or mix_rms_n.size == 0:
        return {"offset_seconds": 0.0, "confidence": 0.0, "mixdown_path": mix_path}

    if job_id:
        _update_progress(job_id, 45, "Finding anchor windows...")

    candidates = _choose_anchor_windows(
        mix_rms,
        hop_seconds,
        anchor_window_seconds,
        top_k=max_candidates,
        min_separation_seconds=max(anchor_window_seconds, 10.0),
    )

    if job_id:
        _update_progress(job_id, 55, f"Analyzing {len(candidates)} candidate regions...")

    best = None
    for idx, (anchor_idx, win, _) in enumerate(candidates):
        if job_id:
            progress = 55 + int((idx / len(candidates)) * 30)
            _update_progress(job_id, progress, f"Analyzing candidate {idx + 1}/{len(candidates)}...")

        comp_anchor_s = anchor_idx * hop_seconds
        comp_window = mix_rms[anchor_idx: anchor_idx + win]
        comp_window_n = _normalize_series(comp_window)
        if comp_window_n.size == 0 or master_rms_n.size < comp_window_n.size:
            continue

        corr = np.correlate(master_rms_n, comp_window_n, mode="valid")
        if corr.size == 0:
            continue
        best_idx = int(np.argmax(corr))
        master_match_s = best_idx * hop_seconds
        coarse_offset = master_match_s - comp_anchor_s

        peak = float(corr[best_idx]) if corr.size else 0.0
        median = float(np.median(np.abs(corr))) if corr.size else 0.0
        coarse_conf = peak / (median + 1e-8)

        master_start = max(master_match_s - refine_pad_seconds, 0.0)
        master_seg = _read_segment(
            master_wav,
            master_start,
            refine_window_seconds + 2 * refine_pad_seconds,
            sample_rate,
        )
        mix_seg = _read_segment(mix_path, comp_anchor_s, refine_window_seconds, sample_rate)
        if master_seg.size > 0 and mix_seg.size > 0 and master_seg.size >= mix_seg.size:
            corr2 = np.correlate(master_seg, mix_seg, mode="valid")
            best2 = int(np.argmax(np.abs(corr2)))
            refined_match = master_start + (best2 / float(sample_rate))
            refined_offset = refined_match - comp_anchor_s
            peak2 = float(np.abs(corr2[best2])) if corr2.size else 0.0
            median2 = float(np.median(np.abs(corr2))) if corr2.size else 0.0
            refine_conf = peak2 / (median2 + 1e-8)
        else:
            refined_offset = coarse_offset
            refine_conf = 0.0

        confidence = float(refine_conf or coarse_conf or 0.0)
        candidate = {
            "offset_seconds": float(refined_offset),
            "confidence": confidence,
            "coarse_offset_seconds": float(coarse_offset),
            "anchor_start_seconds": float(comp_anchor_s),
        }
        if best is None:
            best = candidate
        else:
            better_conf = candidate["confidence"] > best["confidence"]
            tie = candidate["confidence"] == best["confidence"]
            smaller = abs(candidate["offset_seconds"]) < abs(best["offset_seconds"])
            if better_conf or (tie and smaller):
                best = candidate

    if best is None:
        corr = np.correlate(master_rms_n, mix_rms_n, mode="full")
        if corr.size == 0:
            return {"offset_seconds": 0.0, "confidence": 0.0, "mixdown_path": mix_path}
        best_idx = int(np.argmax(np.abs(corr)))
        zero_lag = mix_rms_n.size - 1
        coarse_offset = (best_idx - zero_lag) * hop_seconds
        peak = float(np.abs(corr[best_idx])) if corr.size else 0.0
        median = float(np.median(np.abs(corr))) if corr.size else 0.0
        coarse_conf = peak / (median + 1e-8)
        best = {
            "offset_seconds": float(coarse_offset),
            "confidence": float(coarse_conf or 0.0),
            "coarse_offset_seconds": float(coarse_offset),
            "anchor_start_seconds": 0.0,
        }

    if job_id:
        _update_progress(job_id, 90, "Mixdown analysis complete")

    return {
        "offset_seconds": float(best["offset_seconds"]),
        "confidence": float(best["confidence"]),
        "coarse_offset_seconds": float(best["coarse_offset_seconds"]),
        "mixdown_path": mix_path,
    }


def _choose_anchor_window(rms_values, hop_seconds: float, window_seconds: float):
    if rms_values.size == 0:
        return 0, 0, 0.0
    win = max(1, int(round(window_seconds / hop_seconds)))
    if rms_values.size <= win:
        idx = int(np.argmax(rms_values))
        return idx, min(win, rms_values.size), float(np.mean(rms_values))
    kernel = np.ones(win, dtype=np.float32) / float(win)
    window_mean = np.convolve(rms_values, kernel, mode="valid")
    best_idx = int(np.argmax(window_mean))
    return best_idx, win, float(window_mean[best_idx])


def _choose_anchor_windows(rms_values, hop_seconds: float, window_seconds: float,
                           top_k: int = 3, min_separation_seconds: float = 20.0):
    if rms_values.size == 0:
        return []
    win = max(1, int(round(window_seconds / hop_seconds)))
    if rms_values.size <= win:
        idx = int(np.argmax(rms_values))
        return [(idx, min(win, rms_values.size), float(np.mean(rms_values)))]

    kernel = np.ones(win, dtype=np.float32) / float(win)
    window_mean = np.convolve(rms_values, kernel, mode="valid")
    ranked = np.argsort(window_mean)[::-1]
    min_sep = max(1, int(round(min_separation_seconds / hop_seconds)))

    chosen = []
    for idx in ranked:
        if all(abs(idx - c) >= min_sep for c in chosen):
            chosen.append(int(idx))
        if len(chosen) >= max(1, int(top_k)):
            break
    if not chosen:
        chosen = [int(np.argmax(window_mean))]

    return [(idx, win, float(window_mean[idx])) for idx in chosen]


def _compute_anchor_offset(master_wav: str, component_wav: str, master_rms_n: np.ndarray,
                           hop_seconds: float, anchor_window_seconds: float,
                           refine_window_seconds: float, refine_pad_seconds: float, job_id: str = None,
                           component_idx: int = 0, total_components: int = 1) -> dict:
    if job_id:
        base_progress = 10 + int((component_idx / total_components) * 80)
        _update_progress(job_id, base_progress, f"Computing envelope for component {component_idx + 1}/{total_components}...")

    sample_rate = sf.info(master_wav).samplerate
    comp_rms = _rms_envelope_stream(component_wav, sample_rate, hop_seconds)
    if comp_rms.size == 0 or master_rms_n.size == 0:
        return {"offset_seconds": 0.0, "confidence": 0.0}

    if job_id:
        _update_progress(job_id, base_progress + 5, f"Finding anchor for component {component_idx + 1}...")

    anchor_idx, win, anchor_mean = _choose_anchor_window(comp_rms, hop_seconds, anchor_window_seconds)
    comp_anchor_s = anchor_idx * hop_seconds
    comp_window = comp_rms[anchor_idx: anchor_idx + win]
    comp_window_n = _normalize_series(comp_window)
    if comp_window_n.size == 0 or master_rms_n.size < comp_window_n.size:
        return {"offset_seconds": 0.0, "confidence": 0.0}

    if job_id:
        _update_progress(job_id, base_progress + 10, f"Correlating component {component_idx + 1}...")

    corr = np.correlate(master_rms_n, comp_window_n, mode="valid")
    best_idx = int(np.argmax(corr))
    master_match_s = best_idx * hop_seconds
    coarse_offset = master_match_s - comp_anchor_s

    peak = float(corr[best_idx]) if corr.size else 0.0
    median = float(np.median(np.abs(corr))) if corr.size else 0.0
    coarse_conf = peak / (median + 1e-8)

    master_start = max(master_match_s - refine_pad_seconds, 0.0)
    master_seg = _read_segment(
        master_wav,
        master_start,
        refine_window_seconds + 2 * refine_pad_seconds,
        sample_rate,
    )
    comp_seg = _read_segment(component_wav, comp_anchor_s, refine_window_seconds, sample_rate)
    if master_seg.size > 0 and comp_seg.size > 0 and master_seg.size >= comp_seg.size:
        corr2 = np.correlate(master_seg, comp_seg, mode="valid")
        best2 = int(np.argmax(np.abs(corr2)))
        refined_match = master_start + (best2 / float(sample_rate))
        refined_offset = refined_match - comp_anchor_s
        peak2 = float(np.abs(corr2[best2])) if corr2.size else 0.0
        median2 = float(np.median(np.abs(corr2))) if corr2.size else 0.0
        refine_conf = peak2 / (median2 + 1e-8)
    else:
        refined_offset = coarse_offset
        refine_conf = 0.0

    confidence = float(refine_conf or coarse_conf or 0.0)
    return {
        "offset_seconds": float(refined_offset),
        "confidence": confidence,
        "anchor_comp_start_s": float(comp_anchor_s),
        "anchor_mean_rms": float(anchor_mean),
    }


@app.route("/api/v1/files/raw")
def api_v1_files_raw():
    """Serve a raw file from the mounted data directory (read-only).

    Mirrors the FastAPI endpoint so the browser can fetch from the same origin
    as the UI without CORS/preflight issues. Validates that the path is under
    MOUNT_PATH to avoid unsafe access.
    """
    path = request.args.get("path", type=str)
    if not path:
        return jsonify({"success": False, "error": "Missing path"}), 400
    if not is_safe_path(path):
        return jsonify({"success": False, "error": "Invalid or unsafe path"}), 400
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({"success": False, "error": "File not found"}), 404
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    try:
        # Use send_file to stream efficiently
        return send_file(
            path,
            mimetype=media_type,
            as_attachment=False,
            download_name=os.path.basename(path),
        )
    except Exception as e:
        logger.error(f"Error serving raw file {path}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v1/files/proxy-audio")
def api_v1_files_proxy_audio():
    """Transcode source file's audio track to a browser-friendly audio stream.

    Defaults to WAV (PCM) for maximum compatibility. Supports format query:
    - format=wav | mp4 | aac | webm | opus
    - max_duration=600 (optional, limit output to N seconds for preview, default 600 = 10 min)
    """
    path = request.args.get("path", type=str)
    fmt = (request.args.get("format", "wav") or "wav").lower()
    max_duration = request.args.get("max_duration", type=int, default=600)
    if max_duration is None or max_duration <= 0:
        max_duration = 600
    if not path:
        return jsonify({"success": False, "error": "Missing path"}), 400
    if not is_safe_path(path):
        return jsonify({"success": False, "error": "Invalid or unsafe path"}), 400
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({"success": False, "error": "File not found"}), 404
    if fmt not in {"wav", "mp4", "webm", "opus", "aac"}:
        return jsonify({"success": False, "error": "Unsupported target format"}), 400

    temp_wav_path = None
    source_path = path
    try:
        from sync_analyzer.core.audio_channels import is_atmos_file, extract_atmos_bed_stereo
        import tempfile as _tempfile
        if is_atmos_file(path):
            logger.info(f"[PROXY-AUDIO] Detected Atmos file for streaming: {os.path.basename(path)}")
            temp_wav_path = _tempfile.mktemp(suffix=".wav", prefix="proxy_atmos_stream_")
            extract_atmos_bed_stereo(path, temp_wav_path, sample_rate=48000)
            if os.path.exists(temp_wav_path):
                source_path = temp_wav_path
                logger.info(f"[PROXY-AUDIO] Atmos proxy WAV created for streaming: {temp_wav_path}")
    except Exception as e:
        logger.warning(f"[PROXY-AUDIO] Atmos detection/extraction failed: {e}, falling back to direct ffmpeg")

    try:
        import subprocess

        args = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            source_path,
            "-t",
            str(max_duration),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
        ]
        media_type = "audio/wav"
        if fmt == "wav":
            args += ["-f", "wav", "-acodec", "pcm_s16le", "pipe:1"]
            media_type = "audio/wav"
        elif fmt == "mp4":
            args += [
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "frag_keyframe+empty_moov",
                "-f",
                "mp4",
                "pipe:1",
            ]
            media_type = "audio/mp4"
        elif fmt == "aac":
            args += ["-c:a", "aac", "-b:a", "192k", "-f", "adts", "pipe:1"]
            media_type = "audio/aac"
        elif fmt in {"webm", "opus"}:
            args += ["-c:a", "libopus", "-b:a", "128k", "-f", "webm", "pipe:1"]
            media_type = "audio/webm"

        proc = subprocess.Popen(args, stdout=subprocess.PIPE)

        def cleanup_temp():
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                    logger.info(f"[PROXY-AUDIO] Cleaned up temp Atmos WAV: {temp_wav_path}")
                except Exception as e:
                    logger.warning(f"[PROXY-AUDIO] Failed to clean up temp WAV: {e}")

        def generate():
            try:
                while True:
                    chunk = proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                try:
                    proc.terminate()
                except Exception:
                    pass
                cleanup_temp()

        return app.response_class(generate(), mimetype=media_type)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "ffmpeg not found in PATH"}), 500
    except Exception as e:
        logger.error(f"Error proxying audio for {path}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/")
def index():
    """Serve the splash screen landing page"""
    return send_from_directory(".", "splash.html")


@app.route("/app")
def main_app():
    """Serve the main application UI"""
    return send_from_directory(".", "app.html")


@app.route("/PRESENTATION_GUIDE.md")
def presentation_guide():
    """Serve the presentation guide markdown file from parent directory"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return send_from_directory(parent_dir, "PRESENTATION_GUIDE.md", mimetype="text/markdown")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(".", filename)


@app.route("/api/files")
def list_files():
    """List files and directories in specified path"""
    path = request.args.get("path", MOUNT_PATH)

    if not is_safe_path(path):
        return jsonify({"success": False, "error": "Invalid or unsafe path"}), 400

    try:
        if not os.path.exists(path):
            return jsonify({"success": False, "error": "Path does not exist"}), 404

        if not os.path.isdir(path):
            return jsonify({"success": False, "error": "Path is not a directory"}), 400

        files = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)

            try:
                if os.path.isdir(item_path):
                    files.append({"name": item, "type": "directory", "path": item_path})
                elif os.path.isfile(item_path):
                    ext = Path(item).suffix.lower()
                    if ext in ALLOWED_EXTENSIONS:
                        file_type = get_file_type(item)
                        file_info = {
                            "name": item,
                            "type": file_type,
                            "path": item_path,
                            "size": os.path.getsize(item_path),
                            "extension": ext,
                        }
                        files.append(file_info)

                        # Debug logging for Dunkirk files
                        if "Dunkirk" in item:
                            logger.info(
                                f"File detected: {item} | Type: {file_type} | Ext: {ext}"
                            )
            except PermissionError:
                continue  # Skip files we can't access

        return jsonify({"success": True, "path": path, "files": files})

    except PermissionError:
        return jsonify({"success": False, "error": "Permission denied"}), 403
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/progress/<job_id>", methods=["GET"])
def get_progress(job_id):
    """Get progress for a running analysis job"""
    progress = _get_progress(job_id)
    return jsonify(progress)


@app.route("/api/job/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Get status and result of a background job."""
    job = _get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    
    return jsonify({
        "success": True,
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"],
        "status_message": job["status_message"],
        "result": job["result"],
        "error": job["error"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"]
    })


@app.route("/api/analyze", methods=["POST"])
def analyze_sync():
    """Run sync analysis on selected files"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    master_path = data.get("master")
    dub_path = data.get("dub")
    methods = data.get("methods", ["mfcc"])

    # Validate paths
    if not master_path or not dub_path:
        return jsonify({
            'success': False,
            'error': 'Both master and dub paths required'
        }), 400
    
    if not is_safe_path(master_path) or not is_safe_path(dub_path):
        return jsonify({
            'success': False,
            'error': 'Invalid or unsafe file paths'
        }), 400
    
    if not os.path.exists(master_path) or not os.path.exists(dub_path):
        return jsonify({
            'success': False,
            'error': 'One or both files do not exist'
        }), 404
    
    try:
        # Use the unified analysis API from the codex branch
        ai_enabled = "ai" in methods
        regular_methods = [m for m in methods if m != "ai"]
        if ai_enabled and not regular_methods:
            regular_methods = ["mfcc"]

        enable_gpu = data.get("enableGpu")
        use_gpu = (enable_gpu is True) or (enable_gpu is None and ai_enabled)

        consensus, sync_results, ai_result = analyze(
            Path(master_path),
            Path(dub_path),
            methods=regular_methods,
            enable_ai=ai_enabled,
            ai_model=data.get("aiModel", "wav2vec2"),
            use_gpu=use_gpu,
        )

        method_list = list(regular_methods)
        if ai_enabled:
            method_list.append("ai")

        # Build method_results array with all individual method results
        method_results = []
        for method_name, method_result in sync_results.items():
            method_results.append({
                "method": method_name,
                "offset_seconds": getattr(method_result, 'offset_seconds', 0),
                "confidence": getattr(method_result, 'confidence', 0),
                "quality_score": getattr(method_result, 'quality_score', 0),
            })

        # Add AI result if available
        if ai_result:
            method_results.append({
                "method": "ai",
                "offset_seconds": getattr(ai_result, 'offset_seconds', 0),
                "confidence": getattr(ai_result, 'confidence', 0),
                "quality_score": getattr(ai_result, 'quality_score', 0),
            })

        result_data = {
            "offset_seconds": consensus.offset_seconds,
            "confidence": consensus.confidence,
            "quality_score": consensus.quality_score,
            "method_used": consensus.method_used,
            "analysis_methods": method_list,
            "method_results": method_results,
            "consensus_offset": {
                "offset_seconds": consensus.offset_seconds,
                "confidence": consensus.confidence,
            },
            "per_channel_results": {},
            "recommendations": [],
            "technical_details": {
                "all_methods": method_list,
                "primary_method": consensus.method_used,
                "method_agreement": 1.0,
            },
        }

        logger.info(
            f"Analysis results: {result_data['method_used']} | Methods: {result_data['analysis_methods']} | Offset: {result_data['offset_seconds']:.3f}s"
        )

        return jsonify({"success": True, "result": _json_safe(result_data)})

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analyze/componentized", methods=["POST"])
def analyze_componentized():
    """Run componentized analysis using mixdown or anchor-based alignment."""
    data = request.get_json() or {}
    master_path = data.get("master")
    components = data.get("components") or []
    offset_mode = str(data.get("offset_mode") or "mixdown").lower()
    hop_seconds = float(data.get("hop_seconds") or 0.2)
    anchor_window_seconds = float(data.get("anchor_window_seconds") or 10.0)
    refine_window_seconds = float(data.get("refine_window_seconds") or 8.0)
    refine_pad_seconds = float(data.get("refine_pad_seconds") or 2.0)

    # Generate unique job ID for progress tracking
    import uuid
    job_id = data.get("job_id") or str(uuid.uuid4())
    _update_progress(job_id, 5, "Starting componentized analysis...")

    if not master_path or not components:
        return jsonify({"success": False, "error": "master and components required"}), 400
    if not is_safe_path(master_path):
        return jsonify({"success": False, "error": "Invalid or unsafe master path"}), 400
    if not os.path.exists(master_path):
        return jsonify({"success": False, "error": "Master file does not exist"}), 404

    normalized_components = []
    for idx, comp in enumerate(components):
        if isinstance(comp, dict):
            path = comp.get("path")
            label = comp.get("label") or f"C{idx + 1}"
            name = comp.get("name") or (Path(path).name if path else f"component_{idx + 1}")
        else:
            path = str(comp)
            label = f"C{idx + 1}"
            name = Path(path).name
        if not path:
            return jsonify({"success": False, "error": f"Component {idx + 1} missing path"}), 400
        if not is_safe_path(path):
            return jsonify({"success": False, "error": f"Invalid or unsafe component path: {path}"}), 400
        if not os.path.exists(path):
            return jsonify({"success": False, "error": f"Component file does not exist: {path}"}), 404
        normalized_components.append({"path": path, "label": label, "name": name})

    try:
        if offset_mode == "mixdown":
            _update_progress(job_id, 10, "Starting mixdown analysis...")
            mix_result = _compute_mixdown_offset(
                master_path,
                [c["path"] for c in normalized_components],
                hop_seconds,
                anchor_window_seconds,
                refine_window_seconds,
                refine_pad_seconds,
                job_id=job_id,
            )
            offset_seconds = float(mix_result.get("offset_seconds") or 0.0)
            confidence = float(mix_result.get("confidence") or 0.0)
            component_results = []
            for comp in normalized_components:
                component_results.append(
                    {
                        "component": comp["label"],
                        "componentName": comp["name"],
                        "offset_seconds": offset_seconds,
                        "confidence": confidence,
                        "quality_score": 0.0,
                        "method_results": [
                            {
                                "method": "mixdown",
                                "offset_seconds": offset_seconds,
                                "confidence": confidence,
                            }
                        ],
                        "status": "completed",
                    }
                )
            result_data = {
                "offset_mode": "mixdown",
                "mixdown_offset_seconds": offset_seconds,
                "mixdown_confidence": confidence,
                "analysis_methods": ["mixdown"],
                "method_used": "mixdown",
                "component_results": component_results,
            }
            _update_progress(job_id, 100, "Analysis complete!")
            _clear_progress(job_id)  # Clean up after completion
            return jsonify({"success": True, "result": _json_safe(result_data), "job_id": job_id})

        if offset_mode == "anchor":
            _update_progress(job_id, 5, "Starting anchor-based analysis...")
            _require_mixdown_deps()
            master_wav = _ensure_wav_proxy(master_path, "master")
            sample_rate = sf.info(master_wav).samplerate
            master_rms = _rms_envelope_stream(master_wav, sample_rate, hop_seconds)
            master_rms_n = _normalize_series(master_rms)
            component_results = []
            total_comps = len(normalized_components)
            for comp_idx, comp in enumerate(normalized_components):
                comp_wav = _ensure_wav_proxy(comp["path"], "component")
                anchor_result = _compute_anchor_offset(
                    master_wav,
                    comp_wav,
                    master_rms_n,
                    hop_seconds,
                    anchor_window_seconds,
                    refine_window_seconds,
                    refine_pad_seconds,
                    job_id=job_id,
                    component_idx=comp_idx,
                    total_components=total_comps,
                )
                offset_seconds = float(anchor_result.get("offset_seconds") or 0.0)
                confidence = float(anchor_result.get("confidence") or 0.0)
                component_results.append(
                    {
                        "component": comp["label"],
                        "componentName": comp["name"],
                        "offset_seconds": offset_seconds,
                        "confidence": confidence,
                        "quality_score": 0.0,
                        "method_results": [
                            {
                                "method": "anchor",
                                "offset_seconds": offset_seconds,
                                "confidence": confidence,
                            }
                        ],
                        "status": "completed",
                    }
                )
            result_data = {
                "offset_mode": "anchor",
                "analysis_methods": ["anchor"],
                "method_used": "anchor",
                "component_results": component_results,
            }
            _update_progress(job_id, 100, "Analysis complete!")
            _clear_progress(job_id)  # Clean up after completion
            return jsonify({"success": True, "result": _json_safe(result_data), "job_id": job_id})

        if offset_mode == "channel_aware":
            # Channel-aware mode: select optimal method per channel type
            # and use cross-channel voting to find correct offset
            _update_progress(job_id, 5, "Starting channel-aware analysis...")
            component_results = []
            total_comps = len(normalized_components)

            for comp_idx, comp in enumerate(normalized_components):
                # Update progress for this component
                base_progress = 10 + int((comp_idx / total_comps) * 75)
                _update_progress(job_id, base_progress, f"Analyzing component {comp_idx + 1}/{total_comps}: {comp['name']}")

                # Detect channel type from filename
                channel_type = _detect_channel_type(comp["name"])
                optimal_methods = _get_optimal_method(channel_type)

                logger.info(f"Channel-aware: {comp['name']} detected as '{channel_type}', using methods: {optimal_methods}")

                # Run analysis with optimal method(s)
                try:
                    consensus, sync_results, ai_result = analyze(
                        Path(master_path),
                        Path(comp["path"]),
                        methods=optimal_methods,
                        enable_ai=False,
                        use_gpu=False,
                    )
                    
                    method_results = []
                    for method_name, method_result in sync_results.items():
                        method_results.append({
                            "method": method_name,
                            "offset_seconds": getattr(method_result, 'offset_seconds', 0),
                            "confidence": getattr(method_result, 'confidence', 0),
                            "quality_score": getattr(method_result, 'quality_score', 0),
                        })
                    
                    component_results.append({
                        "component": comp["label"],
                        "componentName": comp["name"],
                        "channel_type": channel_type,
                        "optimal_methods": optimal_methods,
                        "offset_seconds": consensus.offset_seconds,
                        "confidence": consensus.confidence,
                        "quality_score": consensus.quality_score,
                        "method_used": consensus.method_used,
                        "method_results": method_results,
                        "status": "completed",
                    })
                except Exception as comp_err:
                    logger.error(f"Channel-aware analysis failed for {comp['name']}: {comp_err}")
                    component_results.append({
                        "component": comp["label"],
                        "componentName": comp["name"],
                        "channel_type": channel_type,
                        "optimal_methods": optimal_methods,
                        "offset_seconds": 0,
                        "confidence": 0,
                        "quality_score": 0,
                        "error": str(comp_err),
                        "status": "failed",
                    })
            
            # Apply cross-channel voting to find the correct offset
            _update_progress(job_id, 90, "Computing cross-channel vote...")
            voted_offset, vote_count, total_count = _vote_for_offset(component_results)
            vote_agreement = vote_count / total_count if total_count > 0 else 0.0

            logger.info(f"Channel-aware voting: offset={voted_offset}s with {vote_count}/{total_count} agreement ({vote_agreement:.0%})")

            result_data = {
                "offset_mode": "channel_aware",
                "voted_offset_seconds": voted_offset,
                "vote_agreement": vote_agreement,
                "vote_count": vote_count,
                "total_components": total_count,
                "analysis_methods": ["channel_aware"],
                "method_used": "channel_aware (voted)",
                "component_results": component_results,
            }
            _update_progress(job_id, 100, "Channel-aware analysis complete!")
            _clear_progress(job_id)  # Clean up after completion
            return jsonify({"success": True, "result": _json_safe(result_data), "job_id": job_id})

        return jsonify({"success": False, "error": f"Unsupported offset_mode: {offset_mode}"}), 400

    except Exception as e:
        logger.error(f"Componentized analysis error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analyze/componentized/async", methods=["POST"])
def analyze_componentized_async():
    """Start componentized analysis in background and return immediately with job ID."""
    data = request.get_json() or {}
    master_path = data.get("master")
    components = data.get("components") or []
    offset_mode = str(data.get("offset_mode") or "mixdown").lower()
    hop_seconds = float(data.get("hop_seconds") or 0.2)
    anchor_window_seconds = float(data.get("anchor_window_seconds") or 10.0)
    refine_window_seconds = float(data.get("refine_window_seconds") or 8.0)
    refine_pad_seconds = float(data.get("refine_pad_seconds") or 2.0)
    frame_rate = data.get("frameRate", 23.976)

    # Generate unique job ID
    job_id = data.get("job_id") or str(uuid.uuid4())

    # Validate inputs before starting background job
    if not master_path or not components:
        return jsonify({"success": False, "error": "master and components required"}), 400
    if not is_safe_path(master_path):
        return jsonify({"success": False, "error": "Invalid or unsafe master path"}), 400
    if not os.path.exists(master_path):
        return jsonify({"success": False, "error": "Master file does not exist"}), 404

    # Normalize and validate components
    normalized_components = []
    for idx, comp in enumerate(components):
        if isinstance(comp, dict):
            path = comp.get("path")
            label = comp.get("label") or f"C{idx + 1}"
            name = comp.get("name") or (Path(path).name if path else f"component_{idx + 1}")
        else:
            path = str(comp)
            label = f"C{idx + 1}"
            name = Path(path).name
        if not path:
            return jsonify({"success": False, "error": f"Component {idx + 1} missing path"}), 400
        if not is_safe_path(path):
            return jsonify({"success": False, "error": f"Invalid or unsafe component path: {path}"}), 400
        if not os.path.exists(path):
            return jsonify({"success": False, "error": f"Component file does not exist: {path}"}), 404
        normalized_components.append({"path": path, "label": label, "name": name})

    # Create background job entry
    params = {
        "master_path": master_path,
        "components": normalized_components,
        "offset_mode": offset_mode,
        "hop_seconds": hop_seconds,
        "anchor_window_seconds": anchor_window_seconds,
        "refine_window_seconds": refine_window_seconds,
        "refine_pad_seconds": refine_pad_seconds,
        "frame_rate": frame_rate
    }
    _create_background_job(job_id, "componentized", params)
    _update_progress(job_id, 0, "Job queued, waiting to start...")

    # Define the background worker function
    def run_componentized_analysis():
        try:
            _update_job_status(job_id, "processing", 5, "Starting componentized analysis...")
            _update_progress(job_id, 5, "Starting componentized analysis...")

            if offset_mode == "mixdown":
                _update_progress(job_id, 10, "Starting mixdown analysis...")
                mix_result = _compute_mixdown_offset(
                    master_path,
                    [c["path"] for c in normalized_components],
                    hop_seconds,
                    anchor_window_seconds,
                    refine_window_seconds,
                    refine_pad_seconds,
                    job_id=job_id,
                )
                offset_seconds = float(mix_result.get("offset_seconds") or 0.0)
                confidence = float(mix_result.get("confidence") or 0.0)
                component_results = []
                for comp in normalized_components:
                    component_results.append({
                        "component": comp["label"],
                        "componentName": comp["name"],
                        "offset_seconds": offset_seconds,
                        "confidence": confidence,
                        "quality_score": 0.0,
                        "method_results": [{"method": "mixdown", "offset_seconds": offset_seconds, "confidence": confidence}],
                        "status": "completed",
                    })
                result_data = {
                    "offset_mode": "mixdown",
                    "mixdown_offset_seconds": offset_seconds,
                    "mixdown_confidence": confidence,
                    "analysis_methods": ["mixdown"],
                    "method_used": "mixdown",
                    "component_results": component_results,
                    "overall_offset": {"offset_seconds": offset_seconds, "confidence": confidence}
                }
            
            elif offset_mode == "anchor":
                _update_progress(job_id, 5, "Starting anchor-based analysis...")
                _require_mixdown_deps()
                master_wav = _ensure_wav_proxy(master_path, "master")
                sample_rate = sf.info(master_wav).samplerate
                master_rms = _rms_envelope_stream(master_wav, sample_rate, hop_seconds)
                master_rms_n = _normalize_series(master_rms)
                component_results = []
                total_comps = len(normalized_components)
                for comp_idx, comp in enumerate(normalized_components):
                    comp_wav = _ensure_wav_proxy(comp["path"], "component")
                    anchor_result = _compute_anchor_offset(
                        master_wav, comp_wav, master_rms_n, hop_seconds,
                        anchor_window_seconds, refine_window_seconds, refine_pad_seconds,
                        job_id=job_id, component_idx=comp_idx, total_components=total_comps,
                    )
                    component_results.append({
                        "component": comp["label"],
                        "componentName": comp["name"],
                        "offset_seconds": float(anchor_result.get("offset_seconds", 0.0)),
                        "confidence": float(anchor_result.get("confidence", 0.0)),
                        "quality_score": 0.0,
                        "method_results": [{"method": "anchor", "offset_seconds": float(anchor_result.get("offset_seconds", 0.0)),
                                            "confidence": float(anchor_result.get("confidence", 0.0))}],
                        "status": "completed",
                    })
                result_data = {
                    "offset_mode": "anchor",
                    "analysis_methods": ["anchor"],
                    "method_used": "anchor",
                    "component_results": component_results,
                }
            
            elif offset_mode == "channel_aware":
                _update_progress(job_id, 5, "Starting channel-aware analysis...")
                component_results = []
                total_comps = len(normalized_components)
                for comp_idx, comp in enumerate(normalized_components):
                    base_progress = 10 + int((comp_idx / total_comps) * 75)
                    _update_progress(job_id, base_progress, f"Analyzing component {comp_idx + 1}/{total_comps}: {comp['name']}")
                    channel_type = _detect_channel_type(comp["name"])
                    optimal_methods = _get_optimal_method(channel_type)
                    try:
                        consensus, sync_results, _ = analyze(
                            Path(master_path), Path(comp["path"]),
                            methods=optimal_methods,
                        )
                        method_results = []
                        for method_name, method_result in sync_results.items():
                            method_results.append({
                                "method": method_name,
                                "offset_seconds": getattr(method_result, 'offset_seconds', 0),
                                "confidence": getattr(method_result, 'confidence', 0),
                                "quality_score": getattr(method_result, 'quality_score', 0),
                            })
                        component_results.append({
                            "component": comp["label"],
                            "componentName": comp["name"],
                            "channel_type": channel_type,
                            "optimal_methods": optimal_methods,
                            "offset_seconds": consensus.offset_seconds,
                            "confidence": consensus.confidence,
                            "quality_score": getattr(consensus, 'quality_score', 0.0),
                            "method_used": getattr(consensus, 'method_used', 'unknown'),
                            "method_results": method_results,
                            "status": "completed",
                        })
                    except Exception as comp_err:
                        logger.error(f"Component analysis error for {comp['name']}: {comp_err}")
                        component_results.append({
                            "component": comp["label"],
                            "componentName": comp["name"],
                            "channel_type": channel_type,
                            "optimal_methods": optimal_methods,
                            "offset_seconds": 0.0,
                            "confidence": 0.0,
                            "error": str(comp_err),
                            "status": "failed",
                        })
                
                _update_progress(job_id, 90, "Computing cross-channel vote...")
                voted_offset, vote_count, total_count = _vote_for_offset(component_results)
                vote_agreement = vote_count / total_count if total_count > 0 else 0.0
                logger.info(f"Channel-aware voting: offset={voted_offset}s with {vote_count}/{total_count} agreement ({vote_agreement:.0%})")
                
                result_data = {
                    "offset_mode": "channel_aware",
                    "voted_offset_seconds": voted_offset,
                    "vote_agreement": vote_agreement,
                    "vote_count": vote_count,
                    "total_components": total_count,
                    "analysis_methods": ["channel_aware"],
                    "method_used": "channel_aware (voted)",
                    "component_results": component_results,
                }
            else:
                raise ValueError(f"Unsupported offset_mode: {offset_mode}")

            # Mark job as completed
            _update_progress(job_id, 100, "Analysis complete!")
            _update_job_status(job_id, "completed", 100, "Analysis complete!", _json_safe(result_data))
            logger.info(f"Background job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Background job {job_id} failed: {e}")
            _update_job_status(job_id, "failed", error=str(e), message=f"Analysis failed: {e}")
            _update_progress(job_id, 0, f"Failed: {e}")

    # Submit to thread pool
    _job_executor.submit(run_componentized_analysis)
    logger.info(f"Started background job {job_id} for componentized analysis")

    # Return immediately with job ID
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "processing",
        "message": "Analysis started in background. Poll /api/job/<job_id> for status."
    })


@app.route("/api/proxy/prepare", methods=["POST"])
def prepare_proxies():
    """Pre-create Chrome/WebAudio compatible proxies for master and dub.

    Request JSON: { master: <abs_path>, dub: <abs_path> }
    Returns URLs served by this UI server: { master_url, dub_url, format }
    """
    data = request.get_json() or {}
    master_path = data.get("master")
    dub_path = data.get("dub")
    if not master_path or not dub_path:
        return jsonify({"success": False, "error": "master and dub required"}), 400
    if not is_safe_path(master_path) or not is_safe_path(dub_path):
        return jsonify({"success": False, "error": "Invalid or unsafe file paths"}), 400
    if not os.path.exists(master_path) or not os.path.exists(dub_path):
        return (
            jsonify({"success": False, "error": "One or both files do not exist"}),
            404,
        )
    try:
        m_out = _ensure_wav_proxy(master_path, "master")
        d_out = _ensure_wav_proxy(dub_path, "dub")
        m_name = os.path.basename(m_out)
        d_name = os.path.basename(d_out)
        return jsonify(
            {
                "success": True,
                "format": "wav",
                "master_url": f"/proxy/{m_name}",
                "dub_url": f"/proxy/{d_name}",
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Proxy creation timed out"}), 408
    except Exception as e:
        logger.error(f"prepare_proxies error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/proxy/<path:filename>")
def serve_proxy(filename):
    """Serve files from the proxy cache directory."""
    full = os.path.join(PROXY_CACHE_DIR, filename)
    if not os.path.abspath(full).startswith(PROXY_CACHE_DIR):
        return jsonify({"success": False, "error": "Invalid path"}), 400
    if not os.path.exists(full):
        return jsonify({"success": False, "error": "Not found"}), 404
    # Assume WAV for now
    return send_from_directory(PROXY_CACHE_DIR, filename, mimetype="audio/wav")


@app.route("/api/status")
def get_status():
    """Get system status"""
    return jsonify(
        {
            "success": True,
            "status": "ready",
            "mount_path": MOUNT_PATH,
            "mount_exists": os.path.exists(MOUNT_PATH),
        }
    )

@app.route("/api/repair", methods=["POST"])
def repair_sync():
    """Repair sync issues in audio/video file"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    file_path = data.get("file_path")
    offset_seconds = data.get("offset_seconds")
    preserve_quality = data.get("preserve_quality", True)
    create_backup = data.get("create_backup", True)
    output_dir = data.get("output_dir", "./repaired_sync_files/")
    repair_mode = data.get("repair_mode", "auto")

    # Validate inputs
    if not file_path or offset_seconds is None:
        return (
            jsonify({"success": False, "error": "File path and offset required"}),
            400,
        )

    if not is_safe_path(file_path):
        return jsonify({"success": False, "error": "Invalid or unsafe file path"}), 400

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "File does not exist"}), 404

    try:
        # Create output directory - make it absolute from the project root
        if not Path(output_dir).is_absolute():
            # Make relative paths relative to the main project directory, not sync_ui
            output_path = (
                Path("/mnt/data/amcmurray/Sync_dub/Sync_dub_final") / output_dir
            )
        else:
            output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate output filename
        input_file = Path(file_path)
        timestamp = int(time.time())
        output_filename = f"{input_file.stem}_repaired_{offset_seconds:.3f}s_{timestamp}{input_file.suffix}"
        output_file_path = output_path / output_filename

        # Create backup if requested
        backup_file_path = None
        if create_backup:
            backup_filename = f"{input_file.stem}_backup_{timestamp}{input_file.suffix}"
            backup_file_path = output_path / backup_filename
            import shutil

            shutil.copy2(file_path, backup_file_path)
            logger.info(f"Backup created: {backup_file_path}")

        # Build FFmpeg command for sync repair
        # Use -itsoffset before the input it applies to
        cmd = [
            "ffmpeg",
            "-i",
            file_path,  # First input (video)
            "-itsoffset",
            str(offset_seconds),
            "-i",
            file_path,  # Second input (audio with offset)
            "-c:v",
            "copy",  # Copy video stream
            "-c:a",
            "copy",  # Copy audio stream
            "-map",
            "0:v:0",  # Use video from first input
            "-map",
            "1:a:0",  # Use audio from second input (with offset)
            "-y",  # Overwrite output
            str(output_file_path),
        ]

        # Quality preservation is already handled above with -c:v copy -c:a copy

        logger.info(f"Running repair command: {' '.join(cmd)}")

        # Execute repair
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd="/mnt/data/amcmurray/Sync_dub/Sync_dub_final",
        )
        logger.info(f"FFmpeg completed with return code: {result.returncode}")
        if result.stdout:
            logger.info(f"FFmpeg stdout: {result.stdout[:500]}...")  # First 500 chars
        if result.stderr:
            logger.info(f"FFmpeg stderr: {result.stderr[:500]}...")  # First 500 chars

        if result.returncode != 0:
            logger.error(f"FFmpeg repair failed with return code {result.returncode}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")

            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"FFmpeg repair failed: {result.stderr}",
                        "details": {
                            "command": " ".join(cmd),
                            "return_code": result.returncode,
                            "stderr": result.stderr,
                            "stdout": result.stdout,
                        },
                    }
                ),
                500,
            )

        # Verify output file was created
        logger.info(f"Checking if output file exists: {output_file_path}")
        logger.info(f"Output file absolute path: {output_file_path.absolute()}")
        logger.info(f"File exists check: {output_file_path.exists()}")

        if not output_file_path.exists():
            logger.error(f"Output file was not created at: {output_file_path}")
            return (
                jsonify({"success": False, "error": "Output file was not created"}),
                500,
            )

        # Get file size for verification
        output_size = output_file_path.stat().st_size
        logger.info(
            f"Repair completed successfully. Output file: {output_file_path}, Size: {output_size}"
        )

        return jsonify(
            {
                "success": True,
                "output_file": str(output_file_path),
                "applied_offset": offset_seconds,
                "backup_created": create_backup,
                "backup_file": str(backup_file_path) if backup_file_path else None,
                "output_size": output_size,
                "repair_mode": repair_mode,
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Repair operation timed out"}), 408
    except Exception as e:
        logger.error(f"Repair error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/repair/per-channel", methods=["POST"])
def repair_per_channel():
    """Apply per-channel offsets using FFmpeg, preserving video."""
    try:
        data = request.get_json() or {}
        file_path = data.get("file_path")
        per_channel = data.get("per_channel_results") or {}
        output_path = data.get("output_path")
        keep_duration = bool(data.get("keep_duration", True))

        if (
            not file_path
            or not is_safe_path(file_path)
            or not os.path.exists(file_path)
        ):
            return (
                jsonify({"success": False, "error": "Invalid or missing file_path"}),
                400,
            )
        if not isinstance(per_channel, dict) or not per_channel:
            return (
                jsonify({"success": False, "error": "per_channel_results is required"}),
                400,
            )
        if not output_path:
            p = Path(file_path)
            output_path = str(p.with_name(p.stem + "_perch_repaired" + p.suffix))

        info = _probe_audio_layout(file_path)
        streams = [s for s in info.get("streams", [])]
        if not streams:
            return jsonify({"success": False, "error": "No audio streams found"}), 400

        orig_dur = _probe_duration_seconds(file_path)

        def _get_offset(role: str):
            v = per_channel.get(role)
            if isinstance(v, dict) and "offset_seconds" in v:
                try:
                    return float(v["offset_seconds"])
                except Exception:
                    return None
            return None

        fc_parts = []
        map_parts = []

        mc = next((s for s in streams if int(s.get("channels") or 0) > 1), None)
        if mc:
            si = streams.index(mc)
            ch = int(mc.get("channels") or 0)
            labels = []
            for ci in range(ch):
                src_label = f"c{ci}"
                out_label = f"ch{ci}"
                fc_parts.append(f"[0:a:{si}]pan=mono|c0={src_label}[{out_label}]")
                role_candidates = [
                    {0: "FL", 1: "FR", 2: "FC", 3: "LFE", 4: "SL", 5: "SR"}.get(
                        ci, f"c{ci}"
                    ),
                    f"c{ci}",
                ]
                osec = None
                for rn in role_candidates:
                    osec = _get_offset(rn)
                    if osec is not None:
                        break
                in_lbl = out_label
                out_lbl2 = f"{out_label}d"
                if osec is None or abs(osec) < 1e-6:
                    fc_parts.append(f"[{in_lbl}]anull[{out_lbl2}]")
                elif osec > 0:
                    ms = int(round(osec * 1000))
                    fc_parts.append(f"[{in_lbl}]adelay={ms}|{ms}[{out_lbl2}]")
                else:
                    sec = abs(osec)
                    fc_parts.append(
                        f"[{in_lbl}]atrim=start={sec},asetpts=PTS-STARTPTS[{out_lbl2}]"
                    )
                labels.append(out_lbl2)
            merged = "aout"
            fc_parts.append(
                "".join(f"[{l}]" for l in labels)
                + f"amerge=inputs={len(labels)}[{merged}]"
            )
            if keep_duration and orig_dur > 0:
                fc_parts.append(
                    f"[{merged}]apad=whole_dur=1,atrim=duration={orig_dur}[aout]"
                )
            else:
                if merged != "aout":
                    fc_parts.append(f"[{merged}]anull[aout]")
            args = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                file_path,
                "-filter_complex",
                ";".join(fc_parts),
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "48000",
                "-ac",
                str(len(labels)),
                output_path,
            ]
        else:
            for ai, _s in enumerate(streams):
                in_ref = f"[0:a:{ai}]"
                out_lbl = f"o{ai}"
                osec = _get_offset(f"S{ai}")
                if osec is None or abs(osec) < 1e-6:
                    fc_parts.append(f"{in_ref}anull[{out_lbl}]")
                elif osec > 0:
                    ms = int(round(osec * 1000))
                    fc_parts.append(f"{in_ref}adelay={ms}|{ms}[{out_lbl}]")
                else:
                    sec = abs(osec)
                    fc_parts.append(
                        f"{in_ref}atrim=start={sec},asetpts=PTS-STARTPTS[{out_lbl}]"
                    )
                if keep_duration and orig_dur > 0:
                    pad_lbl = f"{out_lbl}p"
                    fc_parts.append(
                        f"[{out_lbl}]apad=whole_dur=1,atrim=duration={orig_dur}[{pad_lbl}]"
                    )
                    map_parts += ["-map", f"[{pad_lbl}]"]
                else:
                    map_parts += ["-map", f"[{out_lbl}]"]
            args = (
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    file_path,
                    "-filter_complex",
                    ";".join(fc_parts),
                    "-map",
                    "0:v:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    "48000",
                ]
                + map_parts
                + [output_path]
            )

        logger.info(f"Per-channel repair command: {' '.join(args)}")
        result = subprocess.run(args, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            logger.error(f"Per-channel repair failed: {result.stderr}")
            return jsonify({"success": False, "error": result.stderr}), 500
        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return jsonify(
            {
                "success": True,
                "output_file": output_path,
                "output_size": size,
                "keep_duration": keep_duration,
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Per-channel repair timed out"}), 408
    except Exception as e:
        logger.error(f"Per-channel repair error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logs")
def get_logs():
    """Get recent log entries (placeholder for real logging)"""
    return jsonify(
        {
            "success": True,
            "logs": [
                {
                    "timestamp": "22:30:15",
                    "level": "info",
                    "message": "Server started successfully",
                },
                {
                    "timestamp": "22:30:15",
                    "level": "info",
                    "message": f"File system mounted: {MOUNT_PATH}",
                },
            ],
        }
    )


if __name__ == "__main__":
    if not os.path.exists(MOUNT_PATH):
        logger.warning(f"Mount path {MOUNT_PATH} does not exist")

    logger.info("Starting Professional Audio Sync Analyzer UI Server...")
    logger.info(f"Serving files from: {MOUNT_PATH}")

    # Run the server
    app.run(host="0.0.0.0", port=3002, debug=True, threaded=True)
