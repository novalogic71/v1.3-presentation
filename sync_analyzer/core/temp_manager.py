"""
Temp File Manager
=================

Centralized management of temporary files for the sync analyzer pipeline.
All temp files are organized by job UUID for easy tracking and cleanup.

Features:
- Creates job-specific temp directories with UUID
- Automatic cleanup on job completion
- Manual cleanup utilities
- Configurable temp location and retention

Usage:
    from sync_analyzer.core.temp_manager import TempManager, get_temp_manager
    
    # Get the singleton manager
    mgr = get_temp_manager()
    
    # Create a job workspace
    with mgr.job_context("my_job_name") as job:
        # Get temp file paths within this job
        wav_path = job.get_path("audio.wav")
        mp4_path = job.get_path("video.mp4")
        
        # ... do processing ...
        
    # Cleanup happens automatically when context exits
    
    # Or manual usage:
    job = mgr.create_job("my_job")
    try:
        path = job.get_path("file.wav")
        # ... process ...
    finally:
        job.cleanup()
"""

import atexit
import logging
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# Default temp base directory - prefer /mnt/data for large files if available
DEFAULT_TEMP_BASE = os.environ.get(
    "SYNC_TEMP_DIR",
    "/mnt/data/amcmurray/Sync_dub/v1.3-presentation/temp_jobs"
    if os.path.exists("/mnt/data/amcmurray/Sync_dub/v1.3-presentation")
    else "/tmp/sync_analyzer_jobs"
)

# Max age for temp directories before auto-cleanup (hours)
DEFAULT_MAX_AGE_HOURS = int(os.environ.get("SYNC_TEMP_MAX_AGE_HOURS", "24"))

# Minimum free space required (GB) before cleanup triggers
MIN_FREE_SPACE_GB = int(os.environ.get("SYNC_TEMP_MIN_FREE_GB", "10"))


def _ensure_writable_dir(path: Path, fallback: Path) -> Path:
    """
    Make sure the target path is writable, otherwise fall back to a safe temp path.
    """
    candidates = []
    if path:
        candidates.append(path)
    if fallback and fallback not in candidates:
        candidates.append(fallback)

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text(str(time.time()))
            test_file.unlink(missing_ok=True)
            return candidate
        except Exception as e:
            logger.warning(f"[TempManager] Temp dir not writable ({candidate}): {e}")

    raise RuntimeError("No writable temp directory available")


@dataclass
class TempJob:
    """Represents a single processing job with its temp directory."""
    
    job_id: str
    job_name: str
    base_path: Path
    created_at: datetime = field(default_factory=datetime.now)
    files: List[str] = field(default_factory=list)
    _cleaned: bool = field(default=False, repr=False)
    
    @property
    def path(self) -> Path:
        """Get the job's temp directory path."""
        return self.base_path / f"{self.job_name}_{self.job_id}"
    
    def get_path(self, filename: str) -> str:
        """Get a full path for a temp file within this job."""
        self.path.mkdir(parents=True, exist_ok=True)
        file_path = self.path / filename
        self.files.append(str(file_path))
        return str(file_path)
    
    def get_subdir(self, dirname: str) -> str:
        """Get a subdirectory path within this job."""
        subdir = self.path / dirname
        subdir.mkdir(parents=True, exist_ok=True)
        return str(subdir)
    
    def cleanup(self) -> bool:
        """Remove all temp files for this job."""
        if self._cleaned:
            return True
        
        try:
            if self.path.exists():
                shutil.rmtree(self.path)
                logger.info(f"[TempManager] Cleaned up job {self.job_id}: {self.path}")
            self._cleaned = True
            return True
        except Exception as e:
            logger.error(f"[TempManager] Failed to cleanup job {self.job_id}: {e}")
            return False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


class TempManager:
    """
    Centralized temp file manager for the sync analyzer pipeline.
    
    Organizes temp files by job UUID and provides automatic cleanup.
    """
    
    def __init__(self, base_dir: Optional[str] = None, max_age_hours: int = DEFAULT_MAX_AGE_HOURS):
        preferred_dir = Path(base_dir or DEFAULT_TEMP_BASE)
        fallback_dir = Path("/tmp/sync_analyzer_jobs")
        
        resolved_dir = _ensure_writable_dir(preferred_dir, fallback_dir)
        if resolved_dir != preferred_dir:
            logger.warning(f"[TempManager] Using fallback temp dir: {resolved_dir} (preferred was {preferred_dir})")

        self.base_dir = resolved_dir
        self.max_age_hours = max_age_hours
        self._jobs: Dict[str, TempJob] = {}
        self._lock = Lock()
        
        # Register cleanup on exit
        atexit.register(self.cleanup_all_jobs)
        
        logger.info(f"[TempManager] Initialized with base_dir={self.base_dir}")
    
    def create_job(self, job_name: str = "job") -> TempJob:
        """Create a new temp job with a unique ID."""
        job_id = str(uuid.uuid4())[:8]
        
        with self._lock:
            job = TempJob(
                job_id=job_id,
                job_name=job_name,
                base_path=self.base_dir
            )
            self._jobs[job_id] = job
            
            # Ensure the job directory is created
            job.path.mkdir(parents=True, exist_ok=True)
            
            # Write a metadata file for debugging
            meta_file = job.path / "_job_meta.txt"
            meta_file.write_text(
                f"job_id: {job_id}\n"
                f"job_name: {job_name}\n"
                f"created_at: {job.created_at.isoformat()}\n"
                f"pid: {os.getpid()}\n"
            )
            
            logger.info(f"[TempManager] Created job {job_id} ({job_name}): {job.path}")
            return job
    
    @contextmanager
    def job_context(self, job_name: str = "job") -> Iterator[TempJob]:
        """Context manager for automatic job cleanup."""
        job = self.create_job(job_name)
        try:
            yield job
        finally:
            self.cleanup_job(job.job_id)
    
    def get_job(self, job_id: str) -> Optional[TempJob]:
        """Get an existing job by ID."""
        return self._jobs.get(job_id)
    
    def cleanup_job(self, job_id: str) -> bool:
        """Cleanup a specific job by ID."""
        with self._lock:
            job = self._jobs.pop(job_id, None)
            if job:
                return job.cleanup()
            return False
    
    def cleanup_all_jobs(self):
        """Cleanup all tracked jobs."""
        with self._lock:
            job_ids = list(self._jobs.keys())
        
        for job_id in job_ids:
            self.cleanup_job(job_id)
        
        logger.info(f"[TempManager] Cleaned up {len(job_ids)} jobs")
    
    def cleanup_old_jobs(self, max_age_hours: Optional[int] = None) -> int:
        """
        Cleanup job directories older than max_age_hours.
        
        This scans the base directory for orphaned job folders.
        
        Returns:
            Number of directories cleaned up
        """
        max_age = max_age_hours or self.max_age_hours
        cutoff = datetime.now() - timedelta(hours=max_age)
        cleaned = 0
        
        try:
            for item in self.base_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # Check if it's a job directory (has metadata file or matches pattern)
                meta_file = item / "_job_meta.txt"
                
                # Get directory age
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if mtime < cutoff:
                        shutil.rmtree(item)
                        logger.info(f"[TempManager] Removed old job dir: {item}")
                        cleaned += 1
                except Exception as e:
                    logger.warning(f"[TempManager] Could not check/remove {item}: {e}")
            
            logger.info(f"[TempManager] Cleaned up {cleaned} old job directories")
            return cleaned
            
        except Exception as e:
            logger.error(f"[TempManager] Error during old job cleanup: {e}")
            return cleaned
    
    def cleanup_system_temp(self) -> Dict[str, int]:
        """
        Clean up orphaned temp files from /tmp that match our patterns.
        
        Returns:
            Dict with counts of removed files by pattern
        """
        patterns = {
            "iab_*": 0,
            "atmos_*": 0,
            "proxy_*": 0,
            "adm_*": 0,
            "sync_*": 0,
        }
        
        tmp_dir = Path("/tmp")
        
        for pattern, _ in patterns.items():
            for item in tmp_dir.glob(pattern):
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                    patterns[pattern] += 1
                except Exception as e:
                    logger.warning(f"[TempManager] Could not remove {item}: {e}")
        
        total = sum(patterns.values())
        if total > 0:
            logger.info(f"[TempManager] Cleaned up {total} items from /tmp: {patterns}")
        
        return patterns
    
    def get_disk_usage(self) -> Dict[str, any]:
        """Get disk usage statistics for temp directory."""
        import shutil as sh
        
        try:
            total, used, free = sh.disk_usage(self.base_dir)
            
            # Calculate temp dir size
            temp_size = sum(
                f.stat().st_size for f in self.base_dir.rglob("*") if f.is_file()
            )
            
            return {
                "base_dir": str(self.base_dir),
                "total_gb": total / (1024**3),
                "used_gb": used / (1024**3),
                "free_gb": free / (1024**3),
                "temp_size_gb": temp_size / (1024**3),
                "job_count": len(self._jobs),
            }
        except Exception as e:
            logger.error(f"[TempManager] Could not get disk usage: {e}")
            return {"error": str(e)}
    
    def check_and_cleanup(self) -> bool:
        """
        Check disk space and trigger cleanup if needed.
        
        Returns:
            True if cleanup was performed
        """
        usage = self.get_disk_usage()
        
        if "error" in usage:
            return False
        
        if usage["free_gb"] < MIN_FREE_SPACE_GB:
            logger.warning(
                f"[TempManager] Low disk space ({usage['free_gb']:.1f}GB free), "
                f"triggering cleanup..."
            )
            self.cleanup_old_jobs(max_age_hours=1)  # More aggressive cleanup
            self.cleanup_system_temp()
            return True
        
        return False


# Singleton instance
_manager: Optional[TempManager] = None
_manager_lock = Lock()


def get_temp_manager(base_dir: Optional[str] = None) -> TempManager:
    """Get or create the singleton TempManager instance."""
    global _manager
    
    with _manager_lock:
        if _manager is None:
            _manager = TempManager(base_dir=base_dir)
        return _manager


def create_job(job_name: str = "job") -> TempJob:
    """Convenience function to create a job using the default manager."""
    return get_temp_manager().create_job(job_name)


def cleanup_all():
    """Convenience function to cleanup all temp files."""
    mgr = get_temp_manager()
    mgr.cleanup_all_jobs()
    mgr.cleanup_old_jobs()
    mgr.cleanup_system_temp()


# CLI for manual cleanup
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Temp File Manager Cleanup Utility")
    parser.add_argument("--max-age", type=int, default=24, help="Max age in hours for old jobs")
    parser.add_argument("--system", action="store_true", help="Also clean /tmp")
    parser.add_argument("--stats", action="store_true", help="Show disk usage stats")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    mgr = get_temp_manager()
    
    if args.stats:
        usage = mgr.get_disk_usage()
        print(f"\n=== Temp Manager Stats ===")
        print(f"Base directory: {usage.get('base_dir', 'N/A')}")
        print(f"Temp size: {usage.get('temp_size_gb', 0):.2f} GB")
        print(f"Disk free: {usage.get('free_gb', 0):.2f} GB")
        print(f"Active jobs: {usage.get('job_count', 0)}")
        print()
    
    print(f"Cleaning up jobs older than {args.max_age} hours...")
    cleaned = mgr.cleanup_old_jobs(max_age_hours=args.max_age)
    print(f"  Removed {cleaned} old job directories")
    
    if args.system:
        print("Cleaning up system temp files...")
        patterns = mgr.cleanup_system_temp()
        total = sum(patterns.values())
        print(f"  Removed {total} files from /tmp")
    
    print("\n✅ Cleanup complete!")
