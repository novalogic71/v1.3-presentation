"""
Componentized Analysis Endpoints

Provides API endpoints for multi-component sync analysis including:
- Synchronous componentized analysis
- Asynchronous background job analysis
- Job status retrieval
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from ....services.componentized_service import (
    run_componentized_analysis,
    is_safe_path,
    _json_safe,
)
from ....services.job_manager import job_manager, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models

class ComponentFile(BaseModel):
    """Component file specification."""
    path: str
    label: Optional[str] = None
    name: Optional[str] = None


class ComponentizedAnalysisRequest(BaseModel):
    """Request for componentized analysis."""
    master: str = Field(..., description="Path to master audio/video file")
    components: List[ComponentFile] = Field(..., description="List of component files")
    offset_mode: str = Field(default="mixdown", description="Analysis mode: mixdown, anchor, or channel_aware")
    methods: Optional[List[str]] = Field(default=None, description="Detection methods: mfcc, onset, spectral, or gpu")
    hop_seconds: float = Field(default=0.2)
    anchor_window_seconds: float = Field(default=10.0)
    refine_window_seconds: float = Field(default=8.0)
    refine_pad_seconds: float = Field(default=2.0)
    frameRate: float = Field(default=23.976, alias="frame_rate")
    job_id: Optional[str] = None

    class Config:
        populate_by_name = True


class ComponentResult(BaseModel):
    """Result for a single component."""
    component: str
    componentName: str
    offset_seconds: float
    confidence: float
    quality_score: float = 0.0
    channel_type: Optional[str] = None
    optimal_methods: Optional[List[str]] = None
    method_used: Optional[str] = None
    method_results: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "completed"
    error: Optional[str] = None


class ComponentizedAnalysisResponse(BaseModel):
    """Response for componentized analysis."""
    success: bool
    result: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None
    error: Optional[str] = None


class AsyncJobResponse(BaseModel):
    """Response for async job submission."""
    success: bool
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    success: bool
    job_id: str
    status: str
    progress: int
    status_message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[float] = None
    completed_at: Optional[float] = None


def _normalize_components(components: List[ComponentFile]) -> List[Dict[str, Any]]:
    """Normalize component input to standard format."""
    normalized = []
    for idx, comp in enumerate(components):
        path = comp.path
        label = comp.label or f"C{idx + 1}"
        name = comp.name or (Path(path).name if path else f"component_{idx + 1}")
        normalized.append({"path": path, "label": label, "name": name})
    return normalized


def _validate_paths(master_path: str, components: List[Dict[str, Any]]) -> None:
    """Validate that all paths are safe and files exist."""
    import os
    
    if not master_path:
        raise HTTPException(status_code=400, detail="Master path is required")
    if not is_safe_path(master_path):
        raise HTTPException(status_code=400, detail="Invalid or unsafe master path")
    if not os.path.exists(master_path):
        raise HTTPException(status_code=404, detail="Master file does not exist")
    
    if not components:
        raise HTTPException(status_code=400, detail="At least one component is required")
    
    for idx, comp in enumerate(components):
        path = comp.get("path")
        if not path:
            raise HTTPException(status_code=400, detail=f"Component {idx + 1} missing path")
        if not is_safe_path(path):
            raise HTTPException(status_code=400, detail=f"Invalid or unsafe component path: {path}")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"Component file does not exist: {path}")


@router.post("", response_model=ComponentizedAnalysisResponse)
@router.post("/", response_model=ComponentizedAnalysisResponse)
async def analyze_componentized_sync(request: ComponentizedAnalysisRequest):
    """
    Run synchronous componentized analysis.
    
    This endpoint blocks until analysis is complete. For long-running analysis,
    use the /async endpoint instead.
    """
    try:
        components = _normalize_components(request.components)
        _validate_paths(request.master, components)
        
        job_id = request.job_id or str(uuid.uuid4())
        
        result = run_componentized_analysis(
            master_path=request.master,
            components=components,
            offset_mode=request.offset_mode.lower(),
            methods=request.methods,
            hop_seconds=request.hop_seconds,
            anchor_window_seconds=request.anchor_window_seconds,
            refine_window_seconds=request.refine_window_seconds,
            refine_pad_seconds=request.refine_pad_seconds,
            frame_rate=request.frameRate,
            job_id=job_id,
        )
        
        return ComponentizedAnalysisResponse(
            success=True,
            result=_json_safe(result),
            job_id=job_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Componentized analysis error: {e}")
        return ComponentizedAnalysisResponse(
            success=False,
            error=str(e),
        )


@router.post("/async", response_model=AsyncJobResponse)
async def analyze_componentized_async(request: ComponentizedAnalysisRequest):
    """
    Start asynchronous componentized analysis using Celery.
    
    Returns immediately with a task_id. Poll /api/v1/jobs/{task_id} for status and results.
    
    Jobs are persisted in Redis and survive:
    - Browser refresh
    - Server restart
    - Network disconnections
    """
    try:
        components = _normalize_components(request.components)
        _validate_paths(request.master, components)
        
        # Import Celery task
        from ....tasks.analysis_tasks import run_componentized_analysis_task
        
        # Dispatch task to Celery
        logger.info(f"🚀 API: methods={request.methods}, offset_mode={request.offset_mode}")
        task = run_componentized_analysis_task.delay(
            master_path=request.master,
            components=components,
            offset_mode=request.offset_mode.lower(),
            methods=request.methods,
            hop_seconds=request.hop_seconds,
            anchor_window_seconds=request.anchor_window_seconds,
            refine_window_seconds=request.refine_window_seconds,
            refine_pad_seconds=request.refine_pad_seconds,
            frame_rate=request.frameRate,
        )
        
        task_id = task.id
        logger.info(f"Dispatched componentized analysis task: {task_id}")
        
        return AsyncJobResponse(
            success=True,
            job_id=task_id,
            status="queued",
            message="Analysis queued in Celery. Poll /api/v1/jobs/<task_id> for status.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to dispatch Celery task: {e}")
        
        # Fallback to in-memory job manager if Celery is not available
        logger.warning("Falling back to in-memory job processing")
        
        job_id = request.job_id or str(uuid.uuid4())
        components = _normalize_components(request.components)
        
        # Create job entry
        params = {
            "master_path": request.master,
            "components": components,
            "offset_mode": request.offset_mode.lower(),
            "hop_seconds": request.hop_seconds,
            "anchor_window_seconds": request.anchor_window_seconds,
            "refine_window_seconds": request.refine_window_seconds,
            "refine_pad_seconds": request.refine_pad_seconds,
            "frame_rate": request.frameRate,
        }
        job_manager.create_job(job_id, "componentized", params)
        job_manager.update_progress(job_id, 0, "Job queued (fallback mode)...")
        
        # Define background worker
        def run_analysis():
            try:
                job_manager.update_job_status(
                    job_id, JobStatus.PROCESSING,
                    progress=5, message="Starting componentized analysis..."
                )
                
                result = run_componentized_analysis(
                    master_path=request.master,
                    components=components,
                    offset_mode=request.offset_mode.lower(),
                    hop_seconds=request.hop_seconds,
                    anchor_window_seconds=request.anchor_window_seconds,
                    refine_window_seconds=request.refine_window_seconds,
                    refine_pad_seconds=request.refine_pad_seconds,
                    frame_rate=request.frameRate,
                    job_id=job_id,
                )
                
                job_manager.complete_job(job_id, _json_safe(result))
                logger.info(f"Background job {job_id} completed successfully")
            
            except Exception as e:
                logger.error(f"Background job {job_id} failed: {e}")
                job_manager.fail_job(job_id, str(e))
        
        # Submit to thread pool
        job_manager.submit_job(job_id, run_analysis)
        logger.info(f"Started background job {job_id} for componentized analysis")
        
        return AsyncJobResponse(
            success=True,
            job_id=job_id,
            status="processing",
            message="Analysis started in background. Poll /api/v1/jobs/<job_id> for status.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start async job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_componentized_job_status(job_id: str):
    """
    Get status and result of a componentized analysis job.
    
    This is an alias for /api/v1/jobs/{job_id} for convenience.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
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

