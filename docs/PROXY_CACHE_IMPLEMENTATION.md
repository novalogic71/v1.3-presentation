# Proxy Cache Implementation Guide (Option 3)
## Eliminate Fade-In Effect with Cached Two-Pass Loudnorm

---

## Overview

This guide implements a proxy caching system that eliminates the fade-in effect caused by FFmpeg's linear loudnorm filter. The solution generates high-quality normalized proxies on first request and serves cached files on subsequent requests.

### Key Benefits
- ✅ No fade-in effect after first generation
- ✅ Fast playback on subsequent requests
- ✅ Maintains broadcast-quality normalization (-14 LUFS)
- ✅ Leverages existing cache infrastructure
- ✅ Automatic cache invalidation when source files change

---

## Architecture Changes

### Current Flow (With Fade-In)
```
User Request → FastAPI → FFmpeg (linear loudnorm) → Stream Audio → Browser
                         ↑
                   Fade-in occurs here (1-3 seconds)
```

### New Flow (No Fade-In)
```
User Request → FastAPI → Check Cache
                         ├─ Cache Hit → Serve Cached File → Browser (instant)
                         └─ Cache Miss → Generate Proxy (two-pass loudnorm)
                                         ├─ Save to Cache
                                         └─ Serve File → Browser
```

---

## Docker Configuration Changes

### 1. Add Cache Volume Mount

**File**: `docker-compose.yml` or your Docker run command

**Add volume mount for proxy cache**:

```yaml
services:
  fastapi:
    volumes:
      - ./web_ui/proxy_cache:/app/web_ui/proxy_cache:rw
      # ... your existing mounts ...
```

Or for Docker run:
```bash
docker run -v ./web_ui/proxy_cache:/app/web_ui/proxy_cache:rw ...
```

### 2. Create Cache Directory

**Before building/running Docker**:

```bash
mkdir -p web_ui/proxy_cache
chmod 777 web_ui/proxy_cache  # Or set appropriate user permissions
```

### 3. Update Dockerfile (If Needed)

**File**: `Dockerfile` or `Dockerfile.runtime`

**Ensure cache directory exists**:

```dockerfile
# Add after workdir setup
RUN mkdir -p /app/web_ui/proxy_cache && \
    chmod 777 /app/web_ui/proxy_cache
```

### 4. Docker Environment Variables

**File**: `docker-compose.yml` or `.env`

**Add cache configuration**:

```yaml
environment:
  - PROXY_CACHE_DIR=/app/web_ui/proxy_cache
  - PROXY_CACHE_MAX_SIZE_GB=50
  - PROXY_CACHE_ENABLED=true
```

Or in `.env`:
```bash
PROXY_CACHE_DIR=/app/web_ui/proxy_cache
PROXY_CACHE_MAX_SIZE_GB=50
PROXY_CACHE_ENABLED=true
```

---

## Code Implementation

### Step 1: Create Proxy Cache Service

**File**: `fastapi_app/app/services/audio_proxy_service.py` (NEW FILE)

```python
"""
Audio proxy caching service for fade-in-free playback.
Generates and caches normalized audio proxies with two-pass loudnorm.
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings
from sync_analyzer.core.audio_channels import is_atmos_file
from sync_analyzer.dolby.atmos_extraction import extract_atmos_bed_stereo

logger = logging.getLogger(__name__)
settings = get_settings()


class AudioProxyCache:
    """Manages cached audio proxies with two-pass loudnorm normalization."""

    def __init__(self, cache_dir: Optional[str] = None, max_size_gb: int = 50):
        """
        Initialize proxy cache.

        Args:
            cache_dir: Directory for cached proxies (default: web_ui/proxy_cache)
            max_size_gb: Maximum cache size in GB (default: 50)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Default to web_ui/proxy_cache relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            self.cache_dir = project_root / "web_ui" / "proxy_cache"

        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"AudioProxyCache initialized: {self.cache_dir}")

    def _get_cache_key(self, file_path: str, role: str) -> str:
        """
        Generate cache key from file path, modification time, and size.

        Args:
            file_path: Source audio file path
            role: master or dub

        Returns:
            SHA1 hash as cache key
        """
        try:
            st = os.stat(file_path)
            key_string = f"{file_path}|{st.st_size}|{int(st.st_mtime)}|{role}"
            return hashlib.sha1(key_string.encode("utf-8")).hexdigest()
        except OSError as e:
            logger.error(f"Failed to stat file {file_path}: {e}")
            raise HTTPException(status_code=404, detail=f"Source file not found: {file_path}")

    def _get_cache_path(self, cache_key: str, role: str) -> Path:
        """Get cache file path for a given cache key."""
        return self.cache_dir / f"{cache_key}_{role}.wav"

    def _get_metadata_path(self, cache_key: str, role: str) -> Path:
        """Get metadata file path for a given cache key."""
        return self.cache_dir / f"{cache_key}_{role}.json"

    def get_cached_proxy(self, file_path: str, role: str) -> Optional[Path]:
        """
        Get cached proxy if it exists and is valid.

        Args:
            file_path: Source audio file path
            role: master or dub

        Returns:
            Path to cached proxy or None if not cached
        """
        cache_key = self._get_cache_key(file_path, role)
        cache_path = self._get_cache_path(cache_key, role)

        if cache_path.exists():
            logger.info(f"Cache HIT for {file_path} (role={role})")
            # Update access time for LRU eviction
            cache_path.touch()
            return cache_path

        logger.info(f"Cache MISS for {file_path} (role={role})")
        return None

    def _measure_loudness(self, input_path: str) -> Dict[str, float]:
        """
        First pass: Measure loudness statistics using FFmpeg.

        Args:
            input_path: Path to audio file

        Returns:
            Dictionary with loudness measurements
        """
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i", input_path,
            "-af", "loudnorm=I=-14:TP=0:LRA=7:print_format=json",
            "-f", "null",
            "-"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # Extract JSON from stderr (loudnorm outputs to stderr)
            output = result.stderr

            # Find JSON block in output
            json_start = output.rfind("{")
            json_end = output.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                logger.warning("Could not extract loudness measurements, using defaults")
                return {}

            json_str = output[json_start:json_end]
            measurements = json.loads(json_str)

            logger.info(f"Loudness measurements: {measurements}")
            return measurements

        except Exception as e:
            logger.error(f"Failed to measure loudness: {e}")
            return {}

    def _apply_normalization(
        self,
        input_path: str,
        output_path: str,
        role: str,
        measurements: Optional[Dict[str, float]] = None
    ):
        """
        Second pass: Apply loudnorm with measured values.

        Args:
            input_path: Source audio file
            output_path: Output normalized file
            role: master or dub
            measurements: Loudness measurements from first pass (optional)
        """
        # Build loudnorm filter with measured values if available
        if measurements and "input_i" in measurements:
            measured_i = measurements["input_i"]
            measured_tp = measurements.get("input_tp", "-1.5")
            measured_lra = measurements.get("input_lra", "7.0")
            measured_thresh = measurements.get("input_thresh", "-24.0")

            loudnorm_filter = (
                f"loudnorm=I=-14:TP=0:LRA=7:linear=true:"
                f"measured_I={measured_i}:"
                f"measured_TP={measured_tp}:"
                f"measured_LRA={measured_lra}:"
                f"measured_thresh={measured_thresh}"
            )
        else:
            # Fallback: use linear mode without measurements (still better than streaming)
            loudnorm_filter = "loudnorm=I=-14:TP=0:LRA=7:linear=true"

        # Add dub volume boost if needed
        volume_boost = ",volume=5dB" if role.lower() == "dub" else ""
        audio_filter = f"{loudnorm_filter}{volume_boost}"

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",  # Overwrite output
            "-i", input_path,
            "-af", audio_filter,
            "-ac", "2",
            "-ar", "48000",
            "-acodec", "pcm_s16le",
            output_path
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Generated normalized proxy: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg normalization failed: {e.stderr.decode()}")
            raise HTTPException(status_code=500, detail="Audio normalization failed")

    def generate_and_cache_proxy(
        self,
        file_path: str,
        role: str,
        max_duration: int = 600
    ) -> Path:
        """
        Generate cached proxy with two-pass loudnorm normalization.

        Args:
            file_path: Source audio file path
            role: master or dub
            max_duration: Maximum duration in seconds (default: 600)

        Returns:
            Path to cached proxy file
        """
        cache_key = self._get_cache_key(file_path, role)
        cache_path = self._get_cache_path(cache_key, role)
        metadata_path = self._get_metadata_path(cache_key, role)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Handle Atmos files (extract stereo bed first)
            if is_atmos_file(file_path):
                logger.info(f"Detected Atmos file: {file_path}")
                atmos_temp_path = temp_path / "atmos_stereo.wav"

                try:
                    extract_atmos_bed_stereo(
                        input_path=file_path,
                        output_path=str(atmos_temp_path),
                        sample_rate=48000
                    )
                    source_file = str(atmos_temp_path)
                except Exception as e:
                    logger.warning(f"Atmos extraction failed, using FFmpeg fallback: {e}")
                    source_file = file_path
            else:
                source_file = file_path

            # Truncate to max_duration if needed
            if max_duration < 600:
                truncated_path = temp_path / "truncated.wav"
                truncate_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-i", source_file,
                    "-t", str(max_duration),
                    "-ac", "2",
                    "-ar", "48000",
                    "-acodec", "pcm_s16le",
                    str(truncated_path)
                ]
                subprocess.run(truncate_cmd, check=True)
                source_file = str(truncated_path)

            # Pass 1: Measure loudness
            logger.info(f"Pass 1: Measuring loudness for {file_path}")
            measurements = self._measure_loudness(source_file)

            # Pass 2: Apply normalization
            logger.info(f"Pass 2: Applying normalization for {file_path}")
            temp_output = temp_path / "normalized.wav"
            self._apply_normalization(
                input_path=source_file,
                output_path=str(temp_output),
                role=role,
                measurements=measurements
            )

            # Move to cache directory
            shutil.move(str(temp_output), cache_path)

            # Save metadata
            metadata = {
                "source_path": file_path,
                "role": role,
                "cache_key": cache_key,
                "loudness_measurements": measurements,
                "is_atmos": is_atmos_file(file_path)
            }
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Cached proxy generated: {cache_path}")

        # Clean up old cache entries if needed
        self._evict_if_needed()

        return cache_path

    def _evict_if_needed(self):
        """Evict least recently used cache entries if cache is too large."""
        total_size = sum(
            f.stat().st_size
            for f in self.cache_dir.glob("*.wav")
            if f.is_file()
        )

        if total_size <= self.max_size_bytes:
            return

        logger.info(f"Cache size {total_size / 1024 / 1024:.1f} MB exceeds limit, evicting...")

        # Get all cache files sorted by access time (oldest first)
        cache_files = sorted(
            self.cache_dir.glob("*.wav"),
            key=lambda f: f.stat().st_atime
        )

        # Evict oldest files until under limit
        for cache_file in cache_files:
            if total_size <= self.max_size_bytes * 0.9:  # Leave 10% headroom
                break

            file_size = cache_file.stat().st_size
            cache_file.unlink()

            # Also remove metadata file
            metadata_file = cache_file.with_suffix(".json")
            if metadata_file.exists():
                metadata_file.unlink()

            total_size -= file_size
            logger.info(f"Evicted cache file: {cache_file.name}")


# Global cache instance
_proxy_cache: Optional[AudioProxyCache] = None


def get_proxy_cache() -> AudioProxyCache:
    """Get or create global proxy cache instance."""
    global _proxy_cache

    if _proxy_cache is None:
        cache_dir = os.getenv("PROXY_CACHE_DIR", "web_ui/proxy_cache")
        max_size_gb = int(os.getenv("PROXY_CACHE_MAX_SIZE_GB", "50"))
        _proxy_cache = AudioProxyCache(cache_dir=cache_dir, max_size_gb=max_size_gb)

    return _proxy_cache
```

---

### Step 2: Update FastAPI Endpoint

**File**: `fastapi_app/app/api/v1/endpoints/files.py`

**Modify the `proxy_audio()` function** (lines 340-440):

```python
from app.services.audio_proxy_service import get_proxy_cache

@router.get("/proxy-audio")
async def proxy_audio(
    path: str = Query(..., description="Absolute path under mount to transcode/stream as browser-friendly audio"),
    format: str = Query("wav", description="Output format: wav|mp4|webm|opus|aac"),
    max_duration: int = Query(600, description="Max duration in seconds for preview (default 600 = 10 min)"),
    role: str = Query("master", description="Role: master or dub (dub gets +5dB boost for balance)"),
    use_cache: bool = Query(True, description="Use cached proxy if available (disable for testing)")
):
    """
    Stream or serve cached audio proxy with loudnorm normalization.

    NEW BEHAVIOR:
    - First request: Generates cached proxy with two-pass loudnorm (no fade-in)
    - Subsequent requests: Serves cached file directly (instant playback)
    - Cache automatically invalidated when source file changes
    """
    settings = get_settings()

    # Security: Validate path is under mount
    if not _is_safe_path(path, settings.MOUNT_PATH):
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    # Check cache first (if enabled)
    if use_cache and format == "wav":
        try:
            proxy_cache = get_proxy_cache()

            # Try to get cached proxy
            cached_proxy = proxy_cache.get_cached_proxy(path, role)

            if cached_proxy:
                # Serve cached file directly (no fade-in, instant playback)
                return FileResponse(
                    path=cached_proxy,
                    media_type="audio/wav",
                    filename=f"{Path(path).stem}_{role}_proxy.wav"
                )

            # Cache miss: Generate and cache proxy
            logger.info(f"Generating cached proxy for {path} (role={role})")
            cached_proxy = proxy_cache.generate_and_cache_proxy(
                file_path=path,
                role=role,
                max_duration=max_duration
            )

            # Serve newly cached file
            return FileResponse(
                path=cached_proxy,
                media_type="audio/wav",
                filename=f"{Path(path).stem}_{role}_proxy.wav"
            )

        except Exception as e:
            logger.error(f"Cache error, falling back to streaming: {e}")
            # Fall through to streaming path

    # Fallback: Stream in real-time (original behavior for non-WAV formats)
    # ... [keep existing streaming code for format != "wav" or use_cache=False] ...
```

---

### Step 3: Update Configuration

**File**: `fastapi_app/app/core/config.py`

**Add cache settings**:

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...

    # Proxy cache settings
    PROXY_CACHE_DIR: str = "web_ui/proxy_cache"
    PROXY_CACHE_MAX_SIZE_GB: int = 50
    PROXY_CACHE_ENABLED: bool = True

    class Config:
        env_file = ".env"
```

---

### Step 4: Add Cache Management CLI

**File**: `fastapi_app/app/cli/cache.py` (NEW FILE)

```python
"""CLI commands for proxy cache management."""

import click
from pathlib import Path

from app.services.audio_proxy_service import get_proxy_cache


@click.group()
def cache():
    """Proxy cache management commands."""
    pass


@cache.command()
def clear():
    """Clear all cached proxy files."""
    proxy_cache = get_proxy_cache()
    cache_dir = proxy_cache.cache_dir

    count = 0
    total_size = 0

    for cache_file in cache_dir.glob("*"):
        if cache_file.is_file():
            size = cache_file.stat().st_size
            cache_file.unlink()
            count += 1
            total_size += size

    click.echo(f"Cleared {count} cache files ({total_size / 1024 / 1024:.1f} MB)")


@cache.command()
def stats():
    """Show cache statistics."""
    proxy_cache = get_proxy_cache()
    cache_dir = proxy_cache.cache_dir

    wav_files = list(cache_dir.glob("*.wav"))
    json_files = list(cache_dir.glob("*.json"))

    total_size = sum(f.stat().st_size for f in wav_files)
    max_size = proxy_cache.max_size_bytes

    click.echo(f"Cache Directory: {cache_dir}")
    click.echo(f"Cached Proxies: {len(wav_files)}")
    click.echo(f"Metadata Files: {len(json_files)}")
    click.echo(f"Total Size: {total_size / 1024 / 1024:.1f} MB")
    click.echo(f"Max Size: {max_size / 1024 / 1024 / 1024:.1f} GB")
    click.echo(f"Usage: {total_size / max_size * 100:.1f}%")


if __name__ == "__main__":
    cache()
```

**Register in main CLI**:

**File**: `fastapi_app/app/cli/__init__.py`

```python
from app.cli.cache import cache

# Register cache commands
# ... in your main CLI group ...
```

---

## Testing

### 1. Manual Testing

**Test fade-in elimination**:

```bash
# First request (generates cache)
curl "http://localhost:8000/api/v1/files/proxy-audio?path=/path/to/dub.mov&role=dub" \
  --output first_request.wav

# Second request (serves from cache)
curl "http://localhost:8000/api/v1/files/proxy-audio?path=/path/to/dub.mov&role=dub" \
  --output second_request.wav

# Listen to both files - second should have no fade-in and start immediately
```

**Test cache invalidation**:

```bash
# Request file
curl "http://localhost:8000/api/v1/files/proxy-audio?path=/path/to/dub.mov&role=dub" \
  --output before.wav

# Modify source file (touch to update mtime)
touch /path/to/dub.mov

# Request again (should regenerate cache)
curl "http://localhost:8000/api/v1/files/proxy-audio?path=/path/to/dub.mov&role=dub" \
  --output after.wav
```

**Check cache stats**:

```bash
python -m app.cli.cache stats
```

### 2. Automated Tests

**File**: `fastapi_app/tests/test_proxy_cache.py` (NEW FILE)

```python
import os
import pytest
from pathlib import Path

from app.services.audio_proxy_service import AudioProxyCache


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "proxy_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def proxy_cache(temp_cache_dir):
    """Create AudioProxyCache instance with temp directory."""
    return AudioProxyCache(cache_dir=str(temp_cache_dir), max_size_gb=1)


def test_cache_key_generation(proxy_cache):
    """Test that cache keys are generated consistently."""
    test_file = "/path/to/test.wav"

    # Same file should generate same key
    key1 = proxy_cache._get_cache_key(test_file, "dub")
    key2 = proxy_cache._get_cache_key(test_file, "dub")

    assert key1 == key2

    # Different roles should generate different keys
    key_master = proxy_cache._get_cache_key(test_file, "master")
    key_dub = proxy_cache._get_cache_key(test_file, "dub")

    assert key_master != key_dub


def test_cache_miss(proxy_cache):
    """Test that non-existent files return cache miss."""
    cached = proxy_cache.get_cached_proxy("/nonexistent.wav", "dub")
    assert cached is None


def test_cache_eviction(proxy_cache, temp_cache_dir):
    """Test that LRU eviction works when cache is full."""
    # Set very small cache size
    proxy_cache.max_size_bytes = 1024  # 1 KB

    # Create dummy cache files
    for i in range(10):
        cache_file = temp_cache_dir / f"cache_{i}.wav"
        cache_file.write_bytes(b"x" * 200)  # 200 bytes each

    # Trigger eviction
    proxy_cache._evict_if_needed()

    # Should have evicted oldest files
    remaining = list(temp_cache_dir.glob("*.wav"))
    total_size = sum(f.stat().st_size for f in remaining)

    assert total_size <= proxy_cache.max_size_bytes
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Create `web_ui/proxy_cache` directory
- [ ] Set appropriate permissions (777 or user-specific)
- [ ] Add volume mount to Docker configuration
- [ ] Update `.env` with cache settings
- [ ] Test cache generation locally

### Deployment

- [ ] Build new Docker image with updated code
- [ ] Deploy with cache volume mounted
- [ ] Verify cache directory is writable
- [ ] Test proxy endpoint returns audio without fade-in
- [ ] Monitor cache size growth

### Post-Deployment

- [ ] Check cache statistics: `python -m app.cli.cache stats`
- [ ] Verify no fade-in on dub playback in QC interface
- [ ] Monitor logs for cache hit/miss rates
- [ ] Adjust `PROXY_CACHE_MAX_SIZE_GB` if needed
- [ ] Set up cache cleanup cron job (optional)

---

## Monitoring

### Log Messages

The implementation logs useful information:

```
INFO: AudioProxyCache initialized: /app/web_ui/proxy_cache
INFO: Cache HIT for /path/to/dub.mov (role=dub)
INFO: Cache MISS for /path/to/dub.mov (role=dub)
INFO: Pass 1: Measuring loudness for /path/to/dub.mov
INFO: Pass 2: Applying normalization for /path/to/dub.mov
INFO: Cached proxy generated: /app/web_ui/proxy_cache/a1b2c3d4_dub.wav
INFO: Cache size 5123.4 MB exceeds limit, evicting...
INFO: Evicted cache file: a1b2c3d4_dub.wav
```

### Metrics to Monitor

1. **Cache Hit Rate**: `cache_hits / (cache_hits + cache_misses)`
2. **Cache Size**: Monitor disk usage of `/web_ui/proxy_cache`
3. **Generation Time**: Time for first request (cache miss)
4. **Serve Time**: Time for subsequent requests (cache hit)

---

## Troubleshooting

### Issue: Permission Denied on Cache Directory

**Symptoms**: `PermissionError: [Errno 13] Permission denied: '/app/web_ui/proxy_cache/...'`

**Solution**:
```bash
chmod 777 web_ui/proxy_cache
# Or set to match Docker user
chown -R 1000:1000 web_ui/proxy_cache  # Adjust UID:GID as needed
```

### Issue: Cache Not Being Used

**Symptoms**: Every request generates new proxy (logs show cache MISS repeatedly)

**Diagnostics**:
1. Check if `use_cache=true` in query params
2. Verify cache directory exists and is writable
3. Check `PROXY_CACHE_ENABLED=true` in environment
4. Look for errors in logs

### Issue: Fade-In Still Occurs

**Symptoms**: Cached proxies still have fade-in effect

**Possible Causes**:
1. Cache was generated with linear mode (not two-pass)
2. Clear cache and regenerate: `python -m app.cli.cache clear`
3. Verify FFmpeg version supports two-pass loudnorm

### Issue: Out of Disk Space

**Symptoms**: `OSError: [Errno 28] No space left on device`

**Solutions**:
1. Reduce `PROXY_CACHE_MAX_SIZE_GB`
2. Clear cache: `python -m app.cli.cache clear`
3. Add more disk space to volume
4. Implement more aggressive eviction policy

---

## Performance Characteristics

### First Request (Cache Miss)
- **Duration**: 2-5 seconds for typical file
- **Overhead**: Two-pass loudnorm (2x file processing)
- **CPU**: High during generation
- **Disk I/O**: High (writes cache file)

### Subsequent Requests (Cache Hit)
- **Duration**: <100ms (direct file serve)
- **Overhead**: Minimal (FileResponse)
- **CPU**: Negligible
- **Disk I/O**: Sequential read only

### Cache Size Estimates
- **Typical proxy size**: ~5-15 MB per minute (48kHz stereo PCM)
- **10-minute proxy**: ~50-150 MB
- **50 GB cache**: ~300-1000 proxies (depending on duration)

---

## Future Enhancements

### Optional Improvements

1. **Pre-generation**: Generate proxies during batch analysis
2. **Distributed cache**: Use Redis/Memcached for multi-server setups
3. **Compression**: Store as FLAC instead of WAV (50% size reduction)
4. **Partial caching**: Cache only first N minutes for long files
5. **Cache warming**: Pre-generate proxies for frequently accessed files
6. **Analytics**: Track cache hit rates and popular files

---

## Questions & Support

If you encounter issues or have questions:

1. Check logs for error messages
2. Run `python -m app.cli.cache stats` to verify cache health
3. Clear cache and retry: `python -m app.cli.cache clear`
4. Verify Docker volume mount is correct
5. Check permissions on cache directory

---

## Summary

This implementation:
- ✅ Eliminates fade-in effect using two-pass loudnorm
- ✅ Caches proxies for instant subsequent playback
- ✅ Handles Atmos files correctly
- ✅ Implements LRU eviction for size management
- ✅ Provides CLI tools for cache management
- ✅ Works seamlessly in Docker environments

**Result**: High-quality, fade-in-free audio playback with minimal latency after first request.
