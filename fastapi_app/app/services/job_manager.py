"""
Background Job Manager Service

Manages background analysis jobs with in-memory storage and thread pool execution.
Provides job creation, status tracking, progress updates, and result retrieval.
"""

import time
import logging
from typing import Dict, Optional, Any, List
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a background job."""
    job_id: str
    job_type: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    status_message: str = "Queued"
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "type": self.job_type,
            "status": self.status.value,
            "progress": self.progress,
            "status_message": self.status_message,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class JobManager:
    """
    Singleton job manager for background analysis tasks.
    
    Uses ThreadPoolExecutor for parallel job execution and
    in-memory storage for job state.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_workers: int = 4):
        if self._initialized:
            return
        self._jobs: Dict[str, Job] = {}
        self._progress_store: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="analysis_worker"
        )
        self._initialized = True
        logger.info(f"JobManager initialized with {max_workers} workers")
    
    def create_job(self, job_id: str, job_type: str, params: Dict[str, Any] = None) -> Job:
        """Create a new background job entry."""
        job = Job(
            job_id=job_id,
            job_type=job_type,
            params=params or {},
        )
        self._jobs[job_id] = job
        logger.info(f"Created job {job_id} of type {job_type}")
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[Job]:
        """List jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """Update job status and optionally other fields."""
        job = self._jobs.get(job_id)
        if not job:
            logger.warning(f"Attempted to update non-existent job {job_id}")
            return
        
        job.status = status
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.status_message = message
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.completed_at = time.time()
        
        logger.debug(f"Updated job {job_id}: status={status.value}, progress={progress}")
    
    def update_progress(self, job_id: str, percentage: int, message: str) -> None:
        """Update progress for a job (convenience method)."""
        # Update progress store for backward compatibility
        self._progress_store[job_id] = {
            "percentage": percentage,
            "message": message,
            "timestamp": time.time()
        }
        # Also update job if it exists
        job = self._jobs.get(job_id)
        if job:
            job.progress = percentage
            job.status_message = message
    
    def get_progress(self, job_id: str) -> Dict[str, Any]:
        """Get progress for a job."""
        return self._progress_store.get(job_id, {
            "percentage": 0,
            "message": "Unknown job",
            "timestamp": 0
        })
    
    def clear_progress(self, job_id: str) -> None:
        """Clear progress entry for a job."""
        self._progress_store.pop(job_id, None)
    
    def complete_job(self, job_id: str, result: Dict[str, Any]) -> None:
        """Mark a job as completed with results."""
        self.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress=100,
            message="Analysis complete!",
            result=result
        )
        logger.info(f"Job {job_id} completed successfully")
    
    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed with error message."""
        self.update_job_status(
            job_id,
            JobStatus.FAILED,
            message=f"Failed: {error}",
            error=error
        )
        logger.error(f"Job {job_id} failed: {error}")
    
    def submit_job(self, job_id: str, func, *args, **kwargs):
        """Submit a job function to the thread pool."""
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.PROCESSING
        return self._executor.submit(func, *args, **kwargs)
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the store."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._progress_store.pop(job_id, None)
            logger.info(f"Deleted job {job_id}")
            return True
        return False
    
    def cleanup_old_jobs(self, max_age_seconds: int = 86400) -> int:
        """Remove completed/failed jobs older than max_age_seconds."""
        now = time.time()
        to_delete = []
        for job_id, job in self._jobs.items():
            if job.completed_at and (now - job.completed_at) > max_age_seconds:
                to_delete.append(job_id)
        
        for job_id in to_delete:
            self.delete_job(job_id)
        
        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old jobs")
        return len(to_delete)


# Global singleton instance
job_manager = JobManager()

