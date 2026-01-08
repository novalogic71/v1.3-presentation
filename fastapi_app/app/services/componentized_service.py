"""
Componentized Analysis Service

Provides multi-component sync analysis functionality including:
- Mixdown offset detection
- Anchor-based per-component detection
- Channel-aware analysis with optimal method selection
- Cross-channel voting for consensus
"""

import os
import re
import logging
import subprocess
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

try:
    import numpy as np
except ImportError:
    np = None

try:
    import soundfile as sf
except ImportError:
    sf = None

from sync_analyzer.analysis import analyze
from .job_manager import job_manager

logger = logging.getLogger(__name__)

# Configuration
MOUNT_PATH = "/mnt/data"
PROXY_CACHE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web_ui", "proxy_cache")
)


def _ensure_proxy_cache_dir() -> str:
    """Ensure proxy cache directory exists and is writable."""
    global PROXY_CACHE_DIR
    try:
        os.makedirs(PROXY_CACHE_DIR, exist_ok=True)
    except Exception as e:
        logger.warning(f"Proxy cache create failed at {PROXY_CACHE_DIR}: {e}")
    
    if os.path.isdir(PROXY_CACHE_DIR) and os.access(PROXY_CACHE_DIR, os.W_OK):
        return PROXY_CACHE_DIR
    
    # Fallback to /tmp
    fallback = os.path.abspath(os.path.join("/tmp", f"sync_proxy_cache_{os.getuid()}"))
    try:
        os.makedirs(fallback, exist_ok=True)
        PROXY_CACHE_DIR = fallback
        logger.warning(f"Proxy cache not writable; using fallback: {PROXY_CACHE_DIR}")
    except Exception as e:
        raise RuntimeError(f"Proxy cache fallback failed: {e}")
    
    return PROXY_CACHE_DIR


def is_safe_path(path: str) -> bool:
    """Check if path is safe and within allowed directory."""
    try:
        resolved = Path(path).resolve()
        mount_resolved = Path(MOUNT_PATH).resolve()
        return str(resolved).startswith(str(mount_resolved))
    except Exception:
        return False


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
    """Generate hash for proxy caching."""
    try:
        st = os.stat(path)
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")
    except Exception:
        key = path.encode("utf-8")
    return hashlib.sha1(key).hexdigest()


def _ensure_wav_proxy(src_path: str, role: str) -> str:
    """Create or reuse a WAV proxy for the given source."""
    _ensure_proxy_cache_dir()
    h = _hash_for_proxy(src_path)
    base = f"{h}_{role}.wav"
    out_path = os.path.join(PROXY_CACHE_DIR, base)
    
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path
    
    # Atmos-aware extraction
    try:
        from sync_analyzer.core.audio_channels import is_atmos_file, extract_atmos_bed_stereo
        if is_atmos_file(src_path):
            logger.info(f"Detected Atmos file, using specialized extraction: {Path(src_path).name}")
            temp_atmos_path = out_path + ".atmos_temp.wav"
            extract_atmos_bed_stereo(src_path, temp_atmos_path, sample_rate=48000)
            if os.path.exists(temp_atmos_path) and os.path.getsize(temp_atmos_path) > 0:
                norm_cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", temp_atmos_path,
                    "-acodec", "pcm_s16le", out_path,
                ]
                logger.info(f"Transcoding Atmos proxy (role={role})")
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
    
    # Standard transcode to WAV 48k stereo
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src_path,
        "-vn", "-ac", "2", "-ar", "48000", "-acodec", "pcm_s16le",
        out_path,
    ]
    logger.info(f"Creating WAV proxy for {role}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error(f"Proxy creation failed: {result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out_path


def _require_mixdown_deps() -> None:
    """Ensure numpy and soundfile are available."""
    if np is None or sf is None:
        raise RuntimeError("Mixdown analysis requires numpy and soundfile")


def _normalize_series(values) -> np.ndarray:
    """Normalize a series to zero mean and unit variance."""
    values = np.asarray(values, dtype=np.float32)
    if values.size == 0:
        return values
    mean = float(np.mean(values))
    std = float(np.std(values)) + 1e-8
    return (values - mean) / std


def _rms_envelope_stream(path: str, sample_rate: int, hop_seconds: float) -> np.ndarray:
    """Compute RMS envelope from audio file using streaming."""
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
            buffer = block[n_frames * hop:]
        else:
            buffer = block
    
    return np.asarray(rms_vals, dtype=np.float32)


def _read_segment(path: str, start_seconds: float, duration_seconds: float, sample_rate: int) -> np.ndarray:
    """Read a segment of audio from file."""
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


def _mixdown_components(component_wavs: List[str], output_path: str) -> int:
    """Mix multiple component WAVs into a single mono file."""
    if not component_wavs:
        raise RuntimeError("No component audio to mixdown")
    
    files = [sf.SoundFile(wav) for wav in component_wavs]
    sample_rate = files[0].samplerate
    
    for f in files[1:]:
        if f.samplerate != sample_rate:
            logger.warning(f"Mixdown sample rate mismatch: {sample_rate} vs {f.samplerate}")
    
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


def _hash_component_list(paths: List[str]) -> str:
    """Generate hash for a list of component paths."""
    key = "|".join(_hash_for_proxy(p) for p in sorted(paths))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _choose_anchor_window(rms_values: np.ndarray, hop_seconds: float, window_seconds: float) -> Tuple[int, int, float]:
    """Choose best anchor window based on RMS energy."""
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


def _choose_anchor_windows(
    rms_values: np.ndarray,
    hop_seconds: float,
    window_seconds: float,
    top_k: int = 3,
    min_separation_seconds: float = 20.0
) -> List[Tuple[int, int, float]]:
    """Choose multiple anchor windows for analysis."""
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


def _compute_mixdown_offset(
    master_path: str,
    component_paths: List[str],
    hop_seconds: float,
    anchor_window_seconds: float,
    refine_window_seconds: float,
    refine_pad_seconds: float,
    max_candidates: int = 3,
    job_id: str = None
) -> Dict[str, Any]:
    """Compute offset using mixdown of all components."""
    _require_mixdown_deps()
    
    if job_id:
        job_manager.update_progress(job_id, 15, "Creating audio proxies...")
    
    master_wav = _ensure_wav_proxy(master_path, "master")
    component_wavs = [_ensure_wav_proxy(p, "component") for p in component_paths]
    mix_hash = _hash_component_list(component_paths)
    mix_path = os.path.join(PROXY_CACHE_DIR, f"{mix_hash}_mixdown.wav")
    
    if not os.path.exists(mix_path) or os.path.getsize(mix_path) == 0:
        _mixdown_components(component_wavs, mix_path)
    
    if job_id:
        job_manager.update_progress(job_id, 30, "Computing audio envelopes...")
    
    sample_rate = sf.info(master_wav).samplerate
    master_rms = _rms_envelope_stream(master_wav, sample_rate, hop_seconds)
    mix_rms = _rms_envelope_stream(mix_path, sample_rate, hop_seconds)
    master_rms_n = _normalize_series(master_rms)
    mix_rms_n = _normalize_series(mix_rms)
    
    if master_rms_n.size == 0 or mix_rms_n.size == 0:
        return {"offset_seconds": 0.0, "confidence": 0.0, "mixdown_path": mix_path}
    
    if job_id:
        job_manager.update_progress(job_id, 45, "Finding anchor windows...")
    
    candidates = _choose_anchor_windows(
        mix_rms, hop_seconds, anchor_window_seconds,
        top_k=max_candidates,
        min_separation_seconds=max(anchor_window_seconds, 10.0),
    )
    
    if job_id:
        job_manager.update_progress(job_id, 55, f"Analyzing {len(candidates)} candidate regions...")
    
    best = None
    for idx, (anchor_idx, win, _) in enumerate(candidates):
        if job_id:
            progress = 55 + int((idx / len(candidates)) * 30)
            job_manager.update_progress(job_id, progress, f"Analyzing candidate {idx + 1}/{len(candidates)}...")
        
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
        
        # Refine with sample-level correlation
        master_start = max(master_match_s - refine_pad_seconds, 0.0)
        master_seg = _read_segment(
            master_wav, master_start,
            refine_window_seconds + 2 * refine_pad_seconds, sample_rate,
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
        # Fallback to full correlation
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
        job_manager.update_progress(job_id, 90, "Mixdown analysis complete")
    
    return {
        "offset_seconds": float(best["offset_seconds"]),
        "confidence": float(best["confidence"]),
        "coarse_offset_seconds": float(best["coarse_offset_seconds"]),
        "mixdown_path": mix_path,
    }


def _compute_anchor_offset(
    master_wav: str,
    component_wav: str,
    master_rms_n: np.ndarray,
    hop_seconds: float,
    anchor_window_seconds: float,
    refine_window_seconds: float,
    refine_pad_seconds: float,
    job_id: str = None,
    component_idx: int = 0,
    total_components: int = 1
) -> Dict[str, Any]:
    """Compute offset for a single component using anchor-based correlation."""
    if job_id:
        base_progress = 10 + int((component_idx / total_components) * 80)
        job_manager.update_progress(job_id, base_progress, f"Computing envelope for component {component_idx + 1}/{total_components}...")
    
    sample_rate = sf.info(master_wav).samplerate
    comp_rms = _rms_envelope_stream(component_wav, sample_rate, hop_seconds)
    
    if comp_rms.size == 0 or master_rms_n.size == 0:
        return {"offset_seconds": 0.0, "confidence": 0.0}
    
    if job_id:
        job_manager.update_progress(job_id, base_progress + 5, f"Finding anchor for component {component_idx + 1}...")
    
    anchor_idx, win, anchor_mean = _choose_anchor_window(comp_rms, hop_seconds, anchor_window_seconds)
    comp_anchor_s = anchor_idx * hop_seconds
    comp_window = comp_rms[anchor_idx: anchor_idx + win]
    comp_window_n = _normalize_series(comp_window)
    
    if comp_window_n.size == 0 or master_rms_n.size < comp_window_n.size:
        return {"offset_seconds": 0.0, "confidence": 0.0}
    
    if job_id:
        job_manager.update_progress(job_id, base_progress + 10, f"Correlating component {component_idx + 1}...")
    
    corr = np.correlate(master_rms_n, comp_window_n, mode="valid")
    best_idx = int(np.argmax(corr))
    master_match_s = best_idx * hop_seconds
    coarse_offset = master_match_s - comp_anchor_s
    
    peak = float(corr[best_idx]) if corr.size else 0.0
    median = float(np.median(np.abs(corr))) if corr.size else 0.0
    coarse_conf = peak / (median + 1e-8)
    
    # Refine
    master_start = max(master_match_s - refine_pad_seconds, 0.0)
    master_seg = _read_segment(
        master_wav, master_start,
        refine_window_seconds + 2 * refine_pad_seconds, sample_rate,
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


def detect_channel_type(filename: str) -> str:
    """Detect channel type from filename pattern."""
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
    if re.search(r'[_\-\.]lfe[_\-\.]?|[_\-\.]sub[_\-\.]?', fn_lower):
        return 'center_lfe'
    if re.search(r'[_\-\.]c[_\-\.]|[_\-\.]center[_\-\.]?|[_\-\.]dialogue[_\-\.]?', fn_lower):
        return 'center_lfe'
    if re.search(r'[_\-\.](ls|rs|lrs|rrs|lss|rss)[_\-\.]?|[_\-\.]surround|[_\-\.]rear', fn_lower):
        return 'surround'
    if re.search(r'[_\-\.](lt|rt)[_\-\.]|[_\-\.]ltrt|[_\-\.]mix[_\-\.]?|[_\-\.]stereo[_\-\.]?|[_\-\.]2ch', fn_lower):
        return 'mixdown'
    if re.search(r'[_\-\.](l|r|left|right)[_\-\.]', fn_lower):
        return 'stereo_lr'
    
    return 'unknown'


def get_optimal_method(channel_type: str) -> List[str]:
    """Return optimal analysis method(s) for channel type."""
    return {
        'stereo_lr': ['spectral'],
        'center_lfe': ['onset'],
        'surround': ['spectral'],
        'mixdown': ['onset', 'spectral'],
        'unknown': ['spectral', 'onset']
    }.get(channel_type, ['spectral'])


def vote_for_offset(results: List[Dict[str, Any]], tolerance: float = 1.0) -> Tuple[float, int, int]:
    """
    Find most common offset across all channel results using cluster voting.
    
    Args:
        results: List of analysis result dicts with 'offset_seconds' key
        tolerance: Offsets within this many seconds are grouped together
    
    Returns:
        (voted_offset, vote_count, total_count)
    """
    if not results:
        return (0.0, 0, 0)
    
    offsets = [
        r.get('offset_seconds', 0)
        for r in results 
        if r.get('offset_seconds') is not None
    ]
    if not offsets:
        return (0.0, 0, len(results))
    
    # Use cluster-based voting: group offsets within tolerance
    # This handles cases like [93.1, 93.5, 93.2, 456.0] -> cluster at ~93.3
    clusters = []
    for offset in sorted(offsets):
        # Try to add to existing cluster
        added = False
        for cluster in clusters:
            cluster_center = sum(cluster) / len(cluster)
            if abs(offset - cluster_center) <= tolerance:
                cluster.append(offset)
                added = True
                break
        if not added:
            clusters.append([offset])
    
    # Find largest cluster
    if not clusters:
        return (0.0, 0, len(offsets))
    
    largest_cluster = max(clusters, key=len)
    voted_offset = sum(largest_cluster) / len(largest_cluster)
    vote_count = len(largest_cluster)
    
    logger.info(f"Vote clustering: {len(clusters)} clusters, largest has {vote_count} offsets around {voted_offset:.2f}s")
    
    return (round(voted_offset, 2), vote_count, len(offsets))


def run_componentized_analysis(
    master_path: str,
    components: List[Dict[str, Any]],
    offset_mode: str = "mixdown",
    methods: List[str] = None,
    hop_seconds: float = 0.2,
    anchor_window_seconds: float = 10.0,
    refine_window_seconds: float = 8.0,
    refine_pad_seconds: float = 2.0,
    frame_rate: float = 23.976,
    job_id: str = None
) -> Dict[str, Any]:
    """
    Run componentized analysis with the specified mode.
    
    Args:
        master_path: Path to master audio/video file
        components: List of component dicts with 'path', 'label', 'name'
        offset_mode: 'mixdown', 'anchor', or 'channel_aware'
        methods: Detection methods to use (mfcc, onset, spectral, gpu)
        job_id: Optional job ID for progress tracking
    
    Returns:
        Analysis results dict
    """
    if job_id:
        job_manager.update_progress(job_id, 5, "Starting componentized analysis...")
    
    logger.info(f"📋 Componentized analysis request: mode={offset_mode}, methods={methods}")
    
    # Check if GPU fast mode is requested
    if methods and 'gpu' in methods:
        logger.info("🚀 GPU method detected - routing to GPU analysis")
        return _run_gpu_analysis(master_path, components, job_id)
    
    # Check if fingerprint mode is requested
    if methods and 'fingerprint' in methods:
        logger.info("🔊 Fingerprint method detected - routing to fingerprint analysis")
        return _run_fingerprint_analysis(master_path, components, job_id)
    
    if offset_mode == "mixdown":
        return _run_mixdown_analysis(
            master_path, components, hop_seconds, anchor_window_seconds,
            refine_window_seconds, refine_pad_seconds, job_id
        )
    elif offset_mode == "anchor":
        return _run_anchor_analysis(
            master_path, components, hop_seconds, anchor_window_seconds,
            refine_window_seconds, refine_pad_seconds, job_id
        )
    elif offset_mode == "channel_aware":
        return _run_channel_aware_analysis(
            master_path, components, frame_rate, job_id, methods
        )
    else:
        raise ValueError(f"Unsupported offset_mode: {offset_mode}")


def _run_mixdown_analysis(
    master_path: str,
    components: List[Dict[str, Any]],
    hop_seconds: float,
    anchor_window_seconds: float,
    refine_window_seconds: float,
    refine_pad_seconds: float,
    job_id: str = None
) -> Dict[str, Any]:
    """Run mixdown-based analysis."""
    job_manager.update_progress(job_id, 10, "Starting mixdown analysis...")
    
    mix_result = _compute_mixdown_offset(
        master_path,
        [c["path"] for c in components],
        hop_seconds, anchor_window_seconds,
        refine_window_seconds, refine_pad_seconds,
        job_id=job_id,
    )
    
    offset_seconds = float(mix_result.get("offset_seconds") or 0.0)
    confidence = float(mix_result.get("confidence") or 0.0)
    
    component_results = []
    for comp in components:
        component_results.append({
            "component": comp["label"],
            "componentName": comp["name"],
            "offset_seconds": offset_seconds,
            "confidence": confidence,
            "quality_score": 0.0,
            "method_results": [{
                "method": "mixdown",
                "offset_seconds": offset_seconds,
                "confidence": confidence,
            }],
            "status": "completed",
        })
    
    return {
        "offset_mode": "mixdown",
        "mixdown_offset_seconds": offset_seconds,
        "mixdown_confidence": confidence,
        "analysis_methods": ["mixdown"],
        "method_used": "mixdown",
        "component_results": component_results,
        "overall_offset": {"offset_seconds": offset_seconds, "confidence": confidence}
    }


def _run_gpu_analysis(
    master_path: str,
    components: List[Dict[str, Any]],
    job_id: str = None
) -> Dict[str, Any]:
    """
    Run GPU-accelerated analysis using Wav2Vec2 embeddings.
    
    This is the fastest single-method detection mode, using GPU acceleration
    for embedding extraction and correlation.
    """
    logger.info("="*60)
    logger.info("🚀 GPU FAST MODE ACTIVATED - Wav2Vec2 Analysis")
    logger.info("="*60)
    job_manager.update_progress(job_id, 5, "Starting GPU-accelerated analysis (Wav2Vec2)...")
    
    # Import the GPU detector
    try:
        from sync_analyzer.core.simple_gpu_sync import SimpleGPUSyncDetector
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🖥️  GPU Device: {device}")
        if device == "cuda":
            logger.info(f"🎮 CUDA GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"💾 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            logger.warning("⚠️  CUDA not available, GPU analysis will run on CPU (slower)")
    except ImportError as e:
        logger.error(f"GPU analysis requires torch and transformers: {e}")
        raise RuntimeError("GPU analysis unavailable: missing dependencies (torch, transformers)")
    
    job_manager.update_progress(job_id, 10, "Loading Wav2Vec2 model...")
    detector = SimpleGPUSyncDetector(device=device)
    
    component_results = []
    total_comps = len(components)
    
    for comp_idx, comp in enumerate(components):
        base_progress = 15 + int((comp_idx / total_comps) * 80)
        job_manager.update_progress(
            job_id, base_progress,
            f"GPU analyzing component {comp_idx + 1}/{total_comps}: {comp['name']}"
        )
        
        channel_type = detect_channel_type(comp["name"])
        
        try:
            # Run GPU analysis
            result = detector.detect_sync(master_path, comp["path"])
            
            component_results.append({
                "component": comp["label"],
                "componentName": comp["name"],
                "channel_type": channel_type,
                "optimal_methods": ["gpu"],
                "offset_seconds": result.offset_seconds,
                "confidence": result.confidence,
                "quality_score": result.confidence,
                "method_used": "gpu (wav2vec2)",
                "method_results": [{
                    "method": "gpu",
                    "offset_seconds": result.offset_seconds,
                    "confidence": result.confidence,
                    "time_taken": result.time_taken if hasattr(result, 'time_taken') else 0,
                    "device": result.device if hasattr(result, 'device') else device,
                }],
                "status": "completed",
            })
            logger.info(f"GPU analysis for {comp['name']}: offset={result.offset_seconds:.3f}s, conf={result.confidence:.2%}")
        except Exception as comp_err:
            logger.error(f"GPU analysis error for {comp['name']}: {comp_err}")
            component_results.append({
                "component": comp["label"],
                "componentName": comp["name"],
                "channel_type": channel_type,
                "optimal_methods": ["gpu"],
                "offset_seconds": 0.0,
                "confidence": 0.0,
                "error": str(comp_err),
                "status": "failed",
            })
    
    # Vote for consensus offset
    job_manager.update_progress(job_id, 95, "Computing GPU consensus...")
    voted_offset, vote_count, total_count = vote_for_offset(component_results)
    vote_agreement = vote_count / total_count if total_count > 0 else 0.0
    
    # Override outliers with voted offset if we have agreement
    if vote_agreement >= 0.5:
        tolerance = 0.5  # Tighter tolerance for GPU mode (0.5s)
        for comp_result in component_results:
            comp_offset = comp_result.get('offset_seconds', 0)
            if abs(comp_offset - voted_offset) > tolerance:
                original_offset = comp_offset
                comp_result['offset_seconds'] = voted_offset
                comp_result['original_offset_seconds'] = original_offset
                comp_result['offset_overridden'] = True
    
    overall_confidence = sum(r.get('confidence', 0) for r in component_results) / len(component_results) if component_results else 0.0
    
    return {
        "offset_mode": "gpu",
        "voted_offset_seconds": voted_offset,
        "vote_agreement": vote_agreement,
        "vote_count": vote_count,
        "total_components": total_count,
        "analysis_methods": ["gpu"],
        "method_used": "gpu (wav2vec2)",
        "component_results": component_results,
        "overall_offset": {
            "offset_seconds": voted_offset,
            "confidence": overall_confidence,
        },
    }


def _run_fingerprint_analysis(
    master_path: str,
    components: List[Dict[str, Any]],
    job_id: str = None
) -> Dict[str, Any]:
    """
    Run fingerprint-based analysis using Chromaprint.
    
    This method is robust to codec differences and compression artifacts,
    making it ideal for dubbed content where the underlying audio pattern
    is preserved but the encoding may differ.
    """
    logger.info("="*60)
    logger.info("🔊 FINGERPRINT MODE ACTIVATED - Chromaprint Analysis")
    logger.info("="*60)
    job_manager.update_progress(job_id, 5, "Starting fingerprint-based analysis...")
    
    # Import the fingerprint detector
    try:
        from sync_analyzer.core.fingerprint_sync import FingerprintSyncDetector
    except ImportError as e:
        logger.error(f"Fingerprint analysis requires chromaprint: {e}")
        raise RuntimeError("Fingerprint analysis unavailable: missing dependencies (pyacoustid, fpcalc)")
    
    job_manager.update_progress(job_id, 10, "Initializing Chromaprint...")
    detector = FingerprintSyncDetector()
    
    component_results = []
    total_comps = len(components)
    
    for comp_idx, comp in enumerate(components):
        base_progress = 15 + int((comp_idx / total_comps) * 80)
        job_manager.update_progress(
            job_id, base_progress,
            f"Fingerprinting component {comp_idx + 1}/{total_comps}: {comp['name']}"
        )
        
        channel_type = detect_channel_type(comp["name"])
        
        try:
            # Run fingerprint analysis
            result = detector.detect_sync(master_path, comp["path"])
            
            component_results.append({
                "component": comp["label"],
                "componentName": comp["name"],
                "channel_type": channel_type,
                "optimal_methods": ["fingerprint"],
                "offset_seconds": result.offset_seconds,
                "confidence": result.confidence,
                "quality_score": result.confidence,
                "method_used": "fingerprint (chromaprint)",
                "method_results": [{
                    "method": "fingerprint",
                    "offset_seconds": result.offset_seconds,
                    "confidence": result.confidence,
                    "master_duration": result.master_duration,
                    "dub_duration": result.dub_duration,
                    "fingerprint_frames": result.fingerprint_frames_dub,
                    "correlation_peak": result.correlation_peak,
                }],
                "status": "completed",
            })
            logger.info(f"Fingerprint analysis for {comp['name']}: offset={result.offset_seconds:.3f}s, conf={result.confidence:.2%}")
        except Exception as comp_err:
            logger.error(f"Fingerprint analysis error for {comp['name']}: {comp_err}")
            component_results.append({
                "component": comp["label"],
                "componentName": comp["name"],
                "channel_type": channel_type,
                "optimal_methods": ["fingerprint"],
                "offset_seconds": 0.0,
                "confidence": 0.0,
                "error": str(comp_err),
                "status": "failed",
            })
    
    # Vote for consensus offset
    job_manager.update_progress(job_id, 95, "Computing fingerprint consensus...")
    voted_offset, vote_count, total_count = vote_for_offset(component_results)
    vote_agreement = vote_count / total_count if total_count > 0 else 0.0
    
    # Override outliers with voted offset if we have agreement
    if vote_agreement >= 0.5:
        tolerance = 0.5  # 0.5s tolerance for fingerprint mode
        for comp_result in component_results:
            comp_offset = comp_result.get('offset_seconds', 0)
            if abs(comp_offset - voted_offset) > tolerance:
                original_offset = comp_offset
                comp_result['offset_seconds'] = voted_offset
                comp_result['original_offset_seconds'] = original_offset
                comp_result['offset_overridden'] = True
    
    overall_confidence = sum(r.get('confidence', 0) for r in component_results) / len(component_results) if component_results else 0.0
    
    return {
        "offset_mode": "fingerprint",
        "voted_offset_seconds": voted_offset,
        "vote_agreement": vote_agreement,
        "vote_count": vote_count,
        "total_components": total_count,
        "analysis_methods": ["fingerprint"],
        "method_used": "fingerprint (chromaprint)",
        "component_results": component_results,
        "overall_offset": {
            "offset_seconds": voted_offset,
            "confidence": overall_confidence,
        },
    }


def _run_anchor_analysis(
    master_path: str,
    components: List[Dict[str, Any]],
    hop_seconds: float,
    anchor_window_seconds: float,
    refine_window_seconds: float,
    refine_pad_seconds: float,
    job_id: str = None
) -> Dict[str, Any]:
    """Run anchor-based per-component analysis."""
    _require_mixdown_deps()
    
    job_manager.update_progress(job_id, 5, "Starting anchor-based analysis...")
    
    master_wav = _ensure_wav_proxy(master_path, "master")
    sample_rate = sf.info(master_wav).samplerate
    master_rms = _rms_envelope_stream(master_wav, sample_rate, hop_seconds)
    master_rms_n = _normalize_series(master_rms)
    
    component_results = []
    total_comps = len(components)
    
    for comp_idx, comp in enumerate(components):
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
            "method_results": [{
                "method": "anchor",
                "offset_seconds": float(anchor_result.get("offset_seconds", 0.0)),
                "confidence": float(anchor_result.get("confidence", 0.0)),
            }],
            "status": "completed",
        })
    
    return {
        "offset_mode": "anchor",
        "analysis_methods": ["anchor"],
        "method_used": "anchor",
        "component_results": component_results,
    }


def _run_channel_aware_analysis(
    master_path: str,
    components: List[Dict[str, Any]],
    frame_rate: float,
    job_id: str = None,
    methods: List[str] = None
) -> Dict[str, Any]:
    """
    Run channel-aware analysis with CONSISTENT method across all channels.
    
    For multi-channel audio files (MXF stems), all channels come from the same
    source and should have the SAME offset. We use MFCC+spectral+onset on ALL
    channels to ensure consistency, then vote for consensus.
    """
    job_manager.update_progress(job_id, 5, "Starting channel-aware analysis...")
    
    # Use provided methods or default to consistent multi-method approach
    # Filter out 'gpu' and 'fingerprint' since they're handled separately
    if methods:
        consistent_methods = [m for m in methods if m not in ('gpu', 'fingerprint')]
    if not methods or not consistent_methods:
        consistent_methods = ['mfcc', 'spectral', 'onset']
    
    component_results = []
    total_comps = len(components)
    
    for comp_idx, comp in enumerate(components):
        base_progress = 10 + int((comp_idx / total_comps) * 75)
        job_manager.update_progress(
            job_id, base_progress,
            f"Analyzing component {comp_idx + 1}/{total_comps}: {comp['name']}"
        )
        
        channel_type = detect_channel_type(comp["name"])
        
        try:
            # Use SAME methods for all components to ensure consistent offsets
            consensus, sync_results, _ = analyze(
                Path(master_path), Path(comp["path"]),
                methods=consistent_methods,
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
                "optimal_methods": consistent_methods,
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
                "optimal_methods": consistent_methods,
                "offset_seconds": 0.0,
                "confidence": 0.0,
                "error": str(comp_err),
                "status": "failed",
            })
    
    # Vote for consensus offset
    job_manager.update_progress(job_id, 90, "Computing cross-channel vote...")
    voted_offset, vote_count, total_count = vote_for_offset(component_results)
    vote_agreement = vote_count / total_count if total_count > 0 else 0.0
    
    logger.info(f"Channel-aware voting: offset={voted_offset}s with {vote_count}/{total_count} agreement ({vote_agreement:.0%})")
    
    # CRITICAL: When we have majority agreement (>=50%), override outliers with voted offset
    # This ensures all channels from the same source show consistent offsets
    if vote_agreement >= 0.5:
        tolerance = 1.0  # seconds - offsets within 1s of voted are considered "agreeing"
        for comp_result in component_results:
            comp_offset = comp_result.get('offset_seconds', 0)
            if abs(comp_offset - voted_offset) > tolerance:
                # This component is an outlier - override with voted offset
                original_offset = comp_offset
                comp_result['offset_seconds'] = voted_offset
                comp_result['original_offset_seconds'] = original_offset
                comp_result['offset_overridden'] = True
                comp_result['override_reason'] = f"Outlier overridden by vote ({vote_count}/{total_count} agree on {voted_offset:.1f}s)"
                logger.warning(
                    f"Overriding outlier offset for {comp_result.get('componentName')}: "
                    f"{original_offset:.1f}s -> {voted_offset:.1f}s (voted consensus)"
                )
            else:
                comp_result['offset_overridden'] = False
    
    # Apply voted offset to all components for display consistency
    overall_offset = voted_offset
    overall_confidence = sum(r.get('confidence', 0) for r in component_results) / len(component_results) if component_results else 0.0
    
    return {
        "offset_mode": "channel_aware",
        "voted_offset_seconds": voted_offset,
        "vote_agreement": vote_agreement,
        "vote_count": vote_count,
        "total_components": total_count,
        "analysis_methods": consistent_methods,
        "method_used": "channel_aware (voted)",
        "component_results": component_results,
        "overall_offset": {
            "offset_seconds": overall_offset,
            "confidence": overall_confidence,
        },
    }

