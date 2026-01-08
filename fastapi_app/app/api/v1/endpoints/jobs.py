#!/usr/bin/env python3
"""
Jobs endpoints for managing and monitoring analysis jobs.

Provides REST API for job lifecycle management, enabling reconnection
to in-progress jobs and retry of failed/orphaned jobs.

Supports both:
- In-memory job store (for background componentized analysis)
- SQLite database (for persistent job history)
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Path as FastAPIPath, Query, BackgroundTasks
from pydantic import BaseModel, Field

# Import job manager for in-memory jobs
from ....services.job_manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class JobResponse(BaseModel):
    """Response model for a single job."""
    job_id: str
    job_type: str
    status: str
    progress: float = 0.0
    status_message: Optional[str] = None
    request_params: Optional[Dict[str, Any]] = None
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: str
    server_pid: Optional[int] = None


class JobListResponse(BaseModel):
    """Response model for job list."""
    success: bool = True
    jobs: List[JobResponse]
    total_count: int
    page: int
    page_size: int
    message: Optional[str] = None


class JobRetryResponse(BaseModel):
    """Response model for job retry operation."""
    success: bool
    message: str
    new_job_id: Optional[str] = None
    original_job_id: str


class JobStatsResponse(BaseModel):
    """Response model for job statistics."""
    success: bool = True
    total_jobs: int
    pending: int
    processing: int
    completed: int
    failed: int
    orphaned: int


# ============================================================================
# Helper Functions
# ============================================================================

def _db_row_to_response(row: Dict[str, Any]) -> JobResponse:
    """Convert database row dict to JobResponse model."""
    # Parse JSON fields
    request_params = None
    result_data = None
    
    if row.get('request_params'):
        try:
            request_params = json.loads(row['request_params'])
        except (json.JSONDecodeError, TypeError):
            request_params = None
    
    if row.get('result_data'):
        try:
            result_data = json.loads(row['result_data'])
        except (json.JSONDecodeError, TypeError):
            result_data = None
    
    return JobResponse(
        job_id=row['job_id'],
        job_type=row['job_type'],
        status=row['status'],
        progress=row.get('progress', 0.0) or 0.0,
        status_message=row.get('status_message'),
        request_params=request_params,
        result_data=result_data,
        error_message=row.get('error_message'),
        created_at=row['created_at'],
        started_at=row.get('started_at'),
        completed_at=row.get('completed_at'),
        updated_at=row['updated_at'],
        server_pid=row.get('server_pid')
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(
        None, 
        description="Filter by status (pending, processing, completed, failed, orphaned)"
    ),
    job_type: Optional[str] = Query(
        None,
        description="Filter by job type (single, batch_item)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page")
):
    """
    List all jobs with optional filters.
    
    Returns paginated list of jobs, most recent first.
    
    ## Status Values
    - **pending**: Job created but not started
    - **processing**: Job currently running
    - **completed**: Job finished successfully
    - **failed**: Job failed with error
    - **orphaned**: Job interrupted by server restart
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "jobs": [
        {
          "job_id": "analysis_20250105_143052_abc123",
          "job_type": "single",
          "status": "completed",
          "progress": 100.0,
          "status_message": "Analysis complete",
          "created_at": "2025-01-05T14:30:52Z",
          "completed_at": "2025-01-05T14:31:15Z"
        }
      ],
      "total_count": 1,
      "page": 1,
      "page_size": 50
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/jobs/?status=completed&page=1&page_size=20"
    ```
    """
    try:
        from sync_analyzer.db.job_db import list_jobs as db_list_jobs
        
        # Calculate offset from page
        offset = (page - 1) * page_size
        
        # Get jobs from database
        rows = db_list_jobs(
            status=status,
            job_type=job_type,
            limit=page_size,
            offset=offset
        )
        
        # Convert to response models
        jobs = [_db_row_to_response(row) for row in rows]
        
        return JobListResponse(
            success=True,
            jobs=jobs,
            total_count=len(jobs),
            page=page,
            page_size=page_size,
            message=f"Retrieved {len(jobs)} job(s)"
        )
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats():
    """
    Get job statistics by status.
    
    Returns counts of jobs in each status category.
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "total_jobs": 42,
      "pending": 2,
      "processing": 1,
      "completed": 35,
      "failed": 3,
      "orphaned": 1
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/jobs/stats"
    ```
    """
    try:
        from sync_analyzer.db.job_db import list_jobs as db_list_jobs
        
        # Get counts by status
        all_jobs = db_list_jobs(limit=10000)  # High limit to get all
        
        stats = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'orphaned': 0
        }
        
        for job in all_jobs:
            status = job.get('status', 'unknown')
            if status in stats:
                stats[status] += 1
        
        return JobStatsResponse(
            success=True,
            total_jobs=len(all_jobs),
            **stats
        )
        
    except Exception as e:
        logger.error(f"Error getting job stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orphaned", response_model=JobListResponse)
async def list_orphaned_jobs():
    """
    List jobs orphaned by server restart.
    
    Returns jobs that were interrupted when the server restarted.
    These jobs can be retried using the retry endpoint.
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "jobs": [
        {
          "job_id": "analysis_20250105_120000_xyz789",
          "job_type": "single",
          "status": "orphaned",
          "progress": 45.0,
          "status_message": "Processing...",
          "error_message": "Server restarted during processing",
          "created_at": "2025-01-05T12:00:00Z"
        }
      ],
      "total_count": 1,
      "page": 1,
      "page_size": 100,
      "message": "Retrieved 1 orphaned job(s)"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/jobs/orphaned"
    ```
    """
    try:
        from sync_analyzer.db.job_db import list_jobs as db_list_jobs
        
        # Get orphaned jobs
        rows = db_list_jobs(status='orphaned', limit=100)
        
        # Convert to response models
        jobs = [_db_row_to_response(row) for row in rows]
        
        return JobListResponse(
            success=True,
            jobs=jobs,
            total_count=len(jobs),
            page=1,
            page_size=100,
            message=f"Retrieved {len(jobs)} orphaned job(s)"
        )
        
    except Exception as e:
        logger.error(f"Error listing orphaned jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=JobListResponse)
async def list_active_jobs():
    """
    List currently active jobs (pending or processing).
    
    Returns jobs that are currently in progress or waiting to start.
    Useful for reconnecting to active jobs after page refresh.
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "jobs": [
        {
          "job_id": "analysis_20250105_143052_abc123",
          "job_type": "single",
          "status": "processing",
          "progress": 65.0,
          "status_message": "Analyzing audio segments...",
          "created_at": "2025-01-05T14:30:52Z"
        }
      ],
      "total_count": 1,
      "page": 1,
      "page_size": 100,
      "message": "Retrieved 1 active job(s)"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/jobs/active"
    ```
    """
    try:
        from sync_analyzer.db.job_db import list_jobs as db_list_jobs
        from ....services.job_manager import job_manager, JobStatus
        
        jobs = []
        existing_ids = set()
        
        # 1. First check Celery for active tasks
        try:
            from ....core.celery_app import get_active_tasks, get_task_progress
            
            celery_tasks = get_active_tasks()
            for task in celery_tasks:
                task_id = task.get("task_id")
                if task_id and task_id not in existing_ids:
                    progress = get_task_progress(task_id)
                    jobs.append(JobResponse(
                        job_id=task_id,
                        job_type=task.get("name", "celery_task"),
                        status=task.get("status", "processing"),
                        progress=float(progress.get("progress", 0)),
                        status_message=progress.get("message", "Running..."),
                        request_params={"args": task.get("args"), "kwargs": task.get("kwargs")},
                        result_data=None,
                        error_message=None,
                        created_at=str(task.get("started", "")),
                        started_at=str(task.get("started", "")),
                        completed_at=None,
                        updated_at=str(task.get("started", "")),
                        server_pid=None
                    ))
                    existing_ids.add(task_id)
        except Exception as celery_err:
            logger.debug(f"Celery inspection failed: {celery_err}")
        
        # 2. Check in-memory job store for fallback background jobs
        in_memory_jobs = job_manager.list_jobs()
        for job in in_memory_jobs:
            if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
                if job.job_id not in existing_ids:
                    jobs.append(JobResponse(
                        job_id=job.job_id,
                        job_type=job.job_type,
                        status=job.status.value,
                        progress=float(job.progress),
                        status_message=job.status_message,
                        request_params=job.params,
                        result_data=job.result,
                        error_message=job.error,
                        created_at=str(job.created_at) if job.created_at else "",
                        started_at=None,
                        completed_at=str(job.completed_at) if job.completed_at else None,
                        updated_at=str(job.created_at) if job.created_at else "",
                        server_pid=None
                    ))
                    existing_ids.add(job.job_id)
        
        # 3. Check database for any other active jobs
        try:
            pending = db_list_jobs(status='pending', limit=100)
            processing = db_list_jobs(status='processing', limit=100)
            all_db_active = pending + processing
            
            for row in all_db_active:
                if row['job_id'] not in existing_ids:
                    jobs.append(_db_row_to_response(row))
                    existing_ids.add(row['job_id'])
        except Exception as db_err:
            logger.warning(f"Database query failed: {db_err}")
        
        return JobListResponse(
            success=True,
            jobs=jobs,
            total_count=len(jobs),
            page=1,
            page_size=100,
            message=f"Retrieved {len(jobs)} active job(s)"
        )
        
    except Exception as e:
        logger.error(f"Error listing active jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class InMemoryJobResponse(BaseModel):
    """Response for in-memory job status (used by frontend polling)."""
    success: bool = True
    job_id: str
    status: str
    progress: int
    status_message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[float] = None
    completed_at: Optional[float] = None


@router.get("/{job_id}", response_model=InMemoryJobResponse)
async def get_job(
    job_id: str = FastAPIPath(..., description="Job identifier")
):
    """
    Get job status - checks Celery first, then in-memory, then database.
    
    This is the primary endpoint for polling job status from the frontend.
    It checks multiple sources in order:
    1. Celery/Redis (for persistent background jobs)
    2. In-memory job store (for fallback jobs)
    3. SQLite database (for historical jobs)
    
    ## Example Response (Running Celery Task)
    
    ```json
    {
      "success": true,
      "job_id": "abc123-def456-...",
      "status": "processing",
      "progress": 45,
      "status_message": "Analyzing component 2/4...",
      "result": null,
      "error": null
    }
    ```
    
    ## Example Response (Completed Task)
    
    ```json
    {
      "success": true,
      "job_id": "abc123-def456-...",
      "status": "completed",
      "progress": 100,
      "status_message": "Analysis complete!",
      "result": {
        "offset_mode": "channel_aware",
        "voted_offset_seconds": 60.4,
        "component_results": [...]
      }
    }
    ```
    """
    # 1. First check Celery for task status
    try:
        from ....core.celery_app import celery_app, get_task_progress
        
        task_result = celery_app.AsyncResult(job_id)
        
        if task_result.state != "PENDING" or task_result.result is not None:
            # Task exists in Celery
            progress_data = get_task_progress(job_id)
            
            status_map = {
                "PENDING": "queued",
                "STARTED": "processing",
                "PROGRESS": "processing",
                "SUCCESS": "completed",
                "FAILURE": "failed",
                "REVOKED": "cancelled",
            }
            
            status = status_map.get(task_result.state, task_result.state.lower())
            
            # Get result if completed
            result = None
            error = None
            if task_result.state == "SUCCESS":
                result = task_result.result
            elif task_result.state == "FAILURE":
                error = str(task_result.result) if task_result.result else "Task failed"
            
            return InMemoryJobResponse(
                success=True,
                job_id=job_id,
                status=status,
                progress=progress_data.get("progress", 0) if status != "completed" else 100,
                status_message=progress_data.get("message", "") if status != "completed" else "Analysis complete!",
                result=result,
                error=error,
            )
    except Exception as celery_err:
        logger.debug(f"Celery check failed for {job_id}: {celery_err}")
    
    # 2. Check in-memory job store (fallback)
    job = job_manager.get_job(job_id)
    if job:
        return InMemoryJobResponse(
            success=True,
            job_id=job.job_id,
            status=job.status.value,
            progress=job.progress,
            status_message=job.status_message,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
    
    # 3. Fall back to database
    try:
        from sync_analyzer.db.job_db import get_job as db_get_job
        
        row = db_get_job(job_id)
        
        if not row:
            # Return a "not found" response
            return InMemoryJobResponse(
                success=False,
                job_id=job_id,
                status="not_found",
                progress=0,
                status_message="Job not found",
                error="Job not found",
            )
        
        # Parse result_data from database
        result_data = None
        if row.get('result_data'):
            try:
                result_data = json.loads(row['result_data'])
            except (json.JSONDecodeError, TypeError):
                pass
        
        return InMemoryJobResponse(
            success=True,
            job_id=row['job_id'],
            status=row['status'],
            progress=int(row.get('progress', 0) or 0),
            status_message=row.get('status_message', ''),
            result=result_data,
            error=row.get('error_message'),
        )
        
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        return InMemoryJobResponse(
            success=False,
            job_id=job_id,
            status="error",
            progress=0,
            status_message=f"Error: {e}",
            error=str(e),
        )


@router.get("/{job_id}/progress")
async def get_job_progress(
    job_id: str = FastAPIPath(..., description="Job identifier")
):
    """
    Get just the progress percentage for a job.
    
    Lightweight endpoint for frequent polling.
    
    ## Example Response
    
    ```json
    {
      "percentage": 45,
      "message": "Analyzing component 2/4..."
    }
    ```
    """
    # Check in-memory first
    job = job_manager.get_job(job_id)
    if job:
        return {
            "percentage": job.progress,
            "message": job.status_message,
        }
    
    # Check progress store
    progress = job_manager.get_progress(job_id)
    return progress


@router.get("/{job_id}/detail", response_model=JobResponse)
async def get_job_detail(
    job_id: str = FastAPIPath(..., description="Job identifier")
):
    """
    Get detailed job information from database (legacy endpoint).
    
    Returns complete job details including request parameters,
    result data (if completed), and error message (if failed).
    """
    try:
        from sync_analyzer.db.job_db import get_job as db_get_job
        
        row = db_get_job(job_id)
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return _db_row_to_response(row)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/retry", response_model=JobRetryResponse)
async def retry_job(
    background_tasks: BackgroundTasks,
    job_id: str = FastAPIPath(..., description="Job identifier to retry")
):
    """
    Retry a failed or orphaned job.
    
    Creates a new job using the original request parameters.
    The original job remains unchanged for reference.
    
    ## Retryable Statuses
    - **failed**: Job that failed with an error
    - **orphaned**: Job interrupted by server restart
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "message": "Job retry initiated",
      "new_job_id": "analysis_20250105_150000_def456",
      "original_job_id": "analysis_20250105_143052_abc123"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X POST "http://localhost:8000/api/v1/jobs/analysis_20250105_143052_abc123/retry"
    ```
    """
    try:
        from sync_analyzer.db.job_db import get_job as db_get_job
        from app.models.sync_models import SyncAnalysisRequest
        from app.services.sync_analyzer_service import sync_analyzer_service
        
        # Get the original job
        row = db_get_job(job_id)
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Check if job is retryable
        status = row.get('status')
        if status not in ('failed', 'orphaned'):
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot retry job with status '{status}'. Only 'failed' or 'orphaned' jobs can be retried."
            )
        
        # Parse original request parameters
        try:
            request_params = json.loads(row['request_params'])
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Could not parse original request parameters: {e}"
            )
        
        # Create new analysis request
        request = SyncAnalysisRequest(**request_params)
        
        # Start new analysis
        new_job_id = await sync_analyzer_service.analyze_sync(request, background_tasks)
        
        logger.info(f"Retried job {job_id} as new job {new_job_id}")
        
        return JobRetryResponse(
            success=True,
            message="Job retry initiated",
            new_job_id=new_job_id,
            original_job_id=job_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str = FastAPIPath(..., description="Job identifier to cancel")
):
    """
    Cancel a pending or processing job.
    
    Note: Cancellation is best-effort. Jobs that are deep in processing
    may complete before the cancellation takes effect.
    
    ## Cancellable Statuses
    - **pending**: Job waiting to start
    - **processing**: Job currently running (may still complete)
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "message": "Job cancelled",
      "job_id": "analysis_20250105_143052_abc123"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/jobs/analysis_20250105_143052_abc123"
    ```
    """
    try:
        from sync_analyzer.db.job_db import get_job as db_get_job, update_job_status
        from app.services.sync_analyzer_service import sync_analyzer_service
        
        # Get the job
        row = db_get_job(job_id)
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Check if job is cancellable
        status = row.get('status')
        if status not in ('pending', 'processing'):
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot cancel job with status '{status}'. Only 'pending' or 'processing' jobs can be cancelled."
            )
        
        # Update status to cancelled
        update_job_status(job_id, status='cancelled', status_message='Cancelled by user')
        
        # Also remove from active analyses if present
        if job_id in sync_analyzer_service.active_analyses:
            del sync_analyzer_service.active_analyses[job_id]
        
        logger.info(f"Cancelled job {job_id}")
        
        return {
            "success": True,
            "message": "Job cancelled",
            "job_id": job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

