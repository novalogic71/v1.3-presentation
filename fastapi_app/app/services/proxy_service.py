"""
Proxy Service

Handles audio proxy creation and caching for browser playback.
Converts various audio formats to browser-compatible WAV/MP4.
"""

import os
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import Optional

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


def hash_for_proxy(path: str) -> str:
    """Generate hash for proxy caching based on file path, size, and mtime."""
    try:
        st = os.stat(path)
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")
    except Exception:
        key = path.encode("utf-8")
    return hashlib.sha1(key).hexdigest()


def ensure_wav_proxy(src_path: str, role: str = "audio") -> str:
    """
    Create or reuse a WAV proxy for the given source file.
    
    Args:
        src_path: Path to source audio/video file
        role: Role identifier for cache naming (e.g., 'master', 'component')
    
    Returns:
        Path to the WAV proxy file
    """
    cache_dir = _ensure_proxy_cache_dir()
    h = hash_for_proxy(src_path)
    base = f"{h}_{role}.wav"
    out_path = os.path.join(cache_dir, base)
    
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        logger.debug(f"Using cached proxy: {out_path}")
        return out_path
    
    # Try Atmos-aware extraction
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
        logger.warning(f"Atmos detection unavailable: {e}")
    except Exception as e:
        logger.warning(f"Atmos extraction failed: {e}, falling back to ffmpeg")
    
    # Standard transcode to WAV 48k stereo
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src_path,
        "-vn", "-ac", "2", "-ar", "48000", "-acodec", "pcm_s16le",
        out_path,
    ]
    logger.info(f"Creating WAV proxy for {role}: {Path(src_path).name}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error(f"Proxy creation failed: {result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    
    return out_path


def transcode_to_format(
    src_path: str,
    target_format: str = "wav",
    max_duration: int = 600
) -> str:
    """
    Transcode audio to a browser-friendly format.
    
    Args:
        src_path: Path to source audio/video file
        target_format: Target format ('wav', 'mp4', 'webm', 'opus', 'aac')
        max_duration: Maximum duration in seconds (default 10 minutes)
    
    Returns:
        Path to the transcoded file
    """
    cache_dir = _ensure_proxy_cache_dir()
    h = hash_for_proxy(src_path)
    
    # Determine output extension and codec settings
    format_settings = {
        "wav": {
            "ext": "wav",
            "codec": ["-acodec", "pcm_s16le"],
            "mimetype": "audio/wav",
        },
        "mp4": {
            "ext": "m4a",
            "codec": ["-acodec", "aac", "-b:a", "192k"],
            "mimetype": "audio/mp4",
        },
        "aac": {
            "ext": "m4a",
            "codec": ["-acodec", "aac", "-b:a", "192k"],
            "mimetype": "audio/mp4",
        },
        "webm": {
            "ext": "webm",
            "codec": ["-acodec", "libopus", "-b:a", "128k"],
            "mimetype": "audio/webm",
        },
        "opus": {
            "ext": "opus",
            "codec": ["-acodec", "libopus", "-b:a", "128k"],
            "mimetype": "audio/opus",
        },
    }
    
    if target_format not in format_settings:
        raise ValueError(f"Unsupported format: {target_format}")
    
    settings = format_settings[target_format]
    out_path = os.path.join(cache_dir, f"{h}_stream.{settings['ext']}")
    
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path
    
    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", src_path,
        "-vn", "-ac", "2", "-ar", "48000",
        "-t", str(max_duration),
    ] + settings["codec"] + [out_path]
    
    logger.info(f"Transcoding to {target_format}: {Path(src_path).name}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=max_duration + 60)
    
    if result.returncode != 0:
        logger.error(f"Transcode failed: {result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    
    return out_path


def get_proxy_path(filename: str) -> Optional[str]:
    """Get full path to a proxy file if it exists."""
    cache_dir = _ensure_proxy_cache_dir()
    full_path = os.path.join(cache_dir, filename)
    
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return full_path
    return None


def cleanup_old_proxies(max_age_hours: int = 24) -> int:
    """Remove proxy files older than max_age_hours."""
    import time
    
    cache_dir = _ensure_proxy_cache_dir()
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    removed = 0
    
    try:
        for filename in os.listdir(cache_dir):
            filepath = os.path.join(cache_dir, filename)
            if os.path.isfile(filepath):
                age = now - os.path.getmtime(filepath)
                if age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        removed += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove old proxy {filename}: {e}")
    except Exception as e:
        logger.error(f"Proxy cleanup error: {e}")
    
    if removed > 0:
        logger.info(f"Cleaned up {removed} old proxy files")
    return removed

