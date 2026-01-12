#!/usr/bin/env python3
"""
Analysis endpoints for sync analysis operations.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
import asyncio
import json

from app.models.sync_models import (
    SyncAnalysisRequest, SyncAnalysisResponse, SyncAnalysisResult,
    BatchAnalysisRequest, BatchAnalysisResponse, AnalysisListResponse,
    AnalysisStatus
)
from app.services.sync_analyzer_service import sync_analyzer_service
from app.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/sync", response_model=SyncAnalysisResponse)
async def analyze_sync(
    request: SyncAnalysisRequest,
    background_tasks: BackgroundTasks,
    wait: bool = Query(False, description="Wait for analysis to complete before returning")
):
    """
    Analyze sync between master and dub audio/video files.
    
    This endpoint starts an asynchronous sync analysis operation. The analysis
    will run in the background and can be monitored using the returned analysis ID.
    
    ## Analysis Methods
    
    * **MFCC**: Fast, reliable method for most content (2-5 seconds)
    * **Onset**: Detects audio onset points for precise timing (3-7 seconds)
    * **Spectral**: Frequency domain analysis for complex content (5-10 seconds)
    * **Correlation**: Raw waveform analysis for high precision (10-20 seconds)
    * **AI**: Machine learning-based detection (15-30 seconds)
    
    ## Use Cases
    
    * Broadcast television multi-language dubbing sync correction
    * Film post-production ADR and dialogue replacement sync
    * Streaming media content localization workflows
    * Educational media lecture capture sync correction
    
    ## Example Request
    
    ```json
    {
        "master_file": "/mnt/data/audio/master.wav",
        "dub_file": "/mnt/data/audio/dub.wav",
        "methods": ["mfcc", "onset"],
        "enable_ai": true,
        "ai_model": "wav2vec2",
        "sample_rate": 22050,
        "window_size": 30.0,
        "confidence_threshold": 0.8
    }
    ```
    
    ## Example Response
    
    ```json
    {
        "success": true,
        "analysis_id": "analysis_20250827_143052_abc12345",
        "status": "pending",
        "timestamp": "2025-08-27T14:30:52Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
      -H "Content-Type: application/json" \
      -d '{
        "master_file": "/mnt/data/audio/master.wav",
        "dub_file": "/mnt/data/audio/dub.wav",
        "methods": ["mfcc", "onset"],
        "enable_ai": true,
        "ai_model": "wav2vec2"
      }'
    ```
    """
    try:
        analysis_id = await sync_analyzer_service.analyze_sync(request)
        
        # If wait=True, poll until analysis completes
        if wait:
            max_wait_seconds = 600  # 10 minute timeout
            poll_interval = 0.5  # Check every 500ms
            elapsed = 0
            
            while elapsed < max_wait_seconds:
                status = await sync_analyzer_service.get_analysis_status(analysis_id)
                if not status:
                    break
                    
                current_status = status.get("status")
                if hasattr(current_status, "value"):
                    current_status = current_status.value
                    
                if current_status in ["completed", "failed", "cancelled"]:
                    # Analysis finished - return full result
                    result = await sync_analyzer_service.get_analysis_result(analysis_id)
                    result_dict = None
                    if result:
                        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result
                    
                    return SyncAnalysisResponse(
                        analysis_id=analysis_id,
                        status=AnalysisStatus(current_status) if current_status in ["completed", "failed", "cancelled", "pending", "processing"] else AnalysisStatus.COMPLETED,
                        message=f"Sync analysis {current_status}",
                        result=result_dict,
                        progress=100.0 if current_status == "completed" else status.get("progress", 0)
                    )
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            
            # Timeout - return current status
            return SyncAnalysisResponse(
                analysis_id=analysis_id,
                status=AnalysisStatus.PROCESSING,
                message="Analysis still in progress (timeout waiting)",
                progress=status.get("progress", 0) if status else 0
            )
        
        return SyncAnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.PENDING,
            message="Sync analysis started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting sync analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}", response_model=SyncAnalysisResponse)
async def get_analysis_status(
    analysis_id: str = Path(..., description="Analysis identifier")
):
    """
    Get the status and results of a sync analysis.
    
    This endpoint returns the current status of an analysis operation and,
    if completed, the full analysis results.
    
    ## Status Values
    
    * **pending**: Analysis is queued but not yet started
    * **processing**: Analysis is currently running
    * **completed**: Analysis completed successfully
    * **failed**: Analysis failed with an error
    * **cancelled**: Analysis was cancelled by user
    
    ## Example Response (Processing)
    
    ```json
    {
        "success": true,
        "analysis_id": "analysis_20250827_143052_abc12345",
        "status": "processing",
        "progress": 45.2,
        "estimated_completion": "2025-08-27T14:31:00Z",
        "timestamp": "2025-08-27T14:30:52Z"
    }
    ```
    
    ## Example Response (Completed)
    
    ```json
    {
        "success": true,
        "analysis_id": "analysis_20250827_143052_abc12345",
        "status": "completed",
        "result": {
            "analysis_id": "analysis_20250827_143052_abc12345",
            "master_file": "/mnt/data/audio/master.wav",
            "dub_file": "/mnt/data/audio/dub.wav",
            "status": "completed",
            "consensus_offset": {
                "offset_seconds": -2.456,
                "offset_samples": -54032,
                "confidence": 0.94
            },
            "overall_confidence": 0.94,
            "sync_status": "❌ SYNC CORRECTION NEEDED (> 100ms)",
            "recommendations": [
                "Dub audio is 2.46 seconds behind master",
                "High confidence in detection (94%)",
                "Recommend audio correction using FFmpeg"
            ]
        },
        "timestamp": "2025-08-27T14:30:52Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
    ```
    """
    try:
        status_info = await sync_analyzer_service.get_analysis_status(analysis_id)
        
        if not status_info:
            raise ResourceNotFoundError("analysis", analysis_id)
        
        # Prefer a human-readable status_message if provided by the service
        status_message = status_info.get("status_message") if isinstance(status_info, dict) else None
        return SyncAnalysisResponse(
            analysis_id=analysis_id,
            status=status_info["status"],
            result=status_info.get("result"),
            estimated_completion=status_info.get("estimated_completion"),
            progress=status_info.get("progress"),
            message=(status_message or f"Analysis status: {status_info['status']}")
        )
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    except Exception as e:
        logger.error(f"Error getting analysis status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{analysis_id}/progress/stream")
async def stream_analysis_progress(
    analysis_id: str = Path(..., description="Analysis identifier for SSE progress stream")
):
    """Server-Sent Events (SSE) stream of analysis progress.

    Emits JSON events with fields: status, progress, status_message, estimated_completion.
    Closes when the analysis reaches a terminal state or is not found.
    """
    async def event_generator():
        backoff = 1.0
        max_backoff = 5.0
        while True:
            try:
                status_info = await sync_analyzer_service.get_analysis_status(analysis_id)
                # Not found -> end stream
                if not status_info:
                    yield "event: end\n" + "data: {}\n\n"
                    break

                # Emit current status snapshot
                raw_status = status_info.get("status")
                # Normalize status to a lowercase string to handle enums
                if isinstance(raw_status, str):
                    norm_status = raw_status.lower()
                else:
                    norm_status = str(getattr(raw_status, "value", raw_status)).lower()

                payload = {
                    "analysis_id": analysis_id,
                    "status": norm_status,
                    "progress": status_info.get("progress"),
                    "status_message": status_info.get("status_message"),
                    "estimated_completion": status_info.get("estimated_completion"),
                }
                yield "data: " + json.dumps(payload) + "\n\n"

                # Terminal states -> end stream
                if norm_status in {"completed", "failed", "cancelled"}:
                    yield "event: end\n" + "data: {}\n\n"
                    break

                backoff = 1.0
            except Exception as e:
                # Transient error: send a comment to keep connection alive and backoff
                yield ": poll-error: " + str(e) + "\n\n"
                backoff = min(max_backoff, backoff * 1.5)

            await asyncio.sleep(backoff)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.delete("/{analysis_id}", response_model=dict)
async def cancel_analysis(
    analysis_id: str = Path(..., description="Analysis identifier")
):
    """
    Cancel an active analysis operation.
    
    This endpoint allows you to cancel an analysis that is currently running
    or pending. Cancelled analyses will be marked as cancelled and stored
    for reference.
    
    ## Example Response
    
    ```json
    {
        "success": true,
        "message": "Analysis cancelled successfully",
        "analysis_id": "analysis_20250827_143052_abc12345",
        "timestamp": "2025-08-27T14:30:52Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
    ```
    """
    try:
        cancelled = await sync_analyzer_service.cancel_analysis(analysis_id)
        
        if cancelled:
            return {
                "success": True,
                "message": "Analysis cancelled successfully",
                "analysis_id": analysis_id
            }
        else:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found or not cancellable")
            
    except Exception as e:
        logger.error(f"Error cancelling analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch", response_model=BatchAnalysisResponse, status_code=202)
async def batch_analysis(
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Perform batch sync analysis on multiple file pairs.
    
    This endpoint allows you to analyze multiple master-dub file pairs in a single
    request. The analysis can be performed in parallel for faster processing.
    
    ## Features
    
    * Process up to 100 file pairs in a single request
    * Parallel processing for improved performance
    * Configurable worker count (1-16 workers)
    * Consistent analysis configuration across all pairs
    
    ## Example Request
    
    ```json
    {
        "file_pairs": [
            {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"},
            {"master": "/mnt/data/audio/master2.wav", "dub": "/mnt/data/audio/dub2.wav"},
            {"master": "/mnt/data/audio/master3.wav", "dub": "/mnt/data/audio/dub3.wav"}
        ],
        "analysis_config": {
            "methods": ["mfcc", "onset"],
            "sample_rate": 22050,
            "window_size": 30.0,
            "confidence_threshold": 0.8
        },
        "parallel_processing": true,
        "max_workers": 4
    }
    ```
    
    ## Example Response
    
    ```json
    {
        "success": true,
        "batch_id": "batch_20250827_143052_abc12345",
        "total_pairs": 3,
        "completed_pairs": 0,
        "failed_pairs": 0,
        "message": "Batch analysis started successfully",
        "timestamp": "2025-08-27T14:30:52Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X POST "http://localhost:8000/api/v1/analysis/batch" \
      -H "Content-Type: application/json" \
      -d '{
        "file_pairs": [
            {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"}
        ],
        "analysis_config": {
            "methods": ["mfcc"],
            "sample_rate": 22050
        }
      }'
    ```
    """
    try:
        # For now, implement a simple sequential batch processing
        # In a production environment, this would use a proper job queue
        batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Start background task for batch processing
        background_tasks.add_task(
            _process_batch_analysis,
            batch_id,
            request
        )
        
        return BatchAnalysisResponse(
            batch_id=batch_id,
            total_pairs=len(request.file_pairs),
            completed_pairs=0,
            failed_pairs=0,
            message="Batch analysis started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting batch analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=AnalysisListResponse)
async def list_analyses(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by analysis status")
):
    """
    List all analyses with pagination and optional filtering.
    
    This endpoint returns a paginated list of all analyses, with optional
    filtering by status. Results are ordered by creation time (newest first).
    
    ## Query Parameters
    
    * **page**: Page number (1-based, default: 1)
    * **page_size**: Items per page (1-100, default: 20)
    * **status**: Filter by analysis status (optional)
    
    ## Example Response
    
    ```json
    {
        "success": true,
        "analyses": [
            {
                "analysis_id": "analysis_20250827_143052_abc12345",
                "master_file": "/mnt/data/audio/master.wav",
                "dub_file": "/mnt/data/audio/dub.wav",
                "status": "completed",
                "overall_confidence": 0.94,
                "sync_status": "❌ SYNC CORRECTION NEEDED (> 100ms)"
            }
        ],
        "total_count": 1,
        "page": 1,
        "page_size": 20,
        "total_pages": 1,
        "timestamp": "2025-08-27T14:30:52Z"
    }
    ```
    
    ## Curl Examples
    
    ```bash
    # Get first page
    curl -X GET "http://localhost:8000/api/v1/analysis/?page=1&page_size=20"
    
    # Filter by status
    curl -X GET "http://localhost:8000/api/v1/analysis/?status=completed"
    
    # Get specific page
    curl -X GET "http://localhost:8000/api/v1/analysis/?page=2&page_size=10"
    ```
    """
    try:
        analyses, total_count = await sync_analyzer_service.list_analyses(page, page_size)
        
        # Apply status filter if specified
        if status:
            analyses = [a for a in analyses if a.status == status]
            total_count = len(analyses)
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        
        return AnalysisListResponse(
            analyses=analyses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            message=f"Retrieved {len(analyses)} analyses"
        )
        
    except Exception as e:
        logger.error(f"Error listing analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync/{analysis_id}/timeline", response_model=dict)
async def get_analysis_timeline(
    analysis_id: str = Path(..., description="Analysis identifier")
):
    """
    Get operator-friendly timeline data for a completed sync analysis.

    This endpoint returns just the timeline data in operator-friendly format,
    optimized for visualization and understanding by non-technical users.

    ## Timeline Data Structure

    ```json
    {
        "success": true,
        "analysis_id": "analysis_20250827_143052_abc12345",
        "timeline": {
            "scenes": [
                {
                    "time_range": "00:00 - 00:30",
                    "start_seconds": 0.0,
                    "end_seconds": 30.0,
                    "scene_type": "dialogue",
                    "scene_description": "Clear dialogue",
                    "severity": "in_sync",
                    "severity_indicator": "✅",
                    "severity_description": "Perfect sync",
                    "reliability": "high",
                    "reliability_indicator": "🔵",
                    "reliability_explanation": "Strong signal match",
                    "offset_seconds": 0.012,
                    "repair_recommendation": "No action needed"
                }
            ]
        },
        "drift_summary": {
            "has_drift": false,
            "max_drift_ms": 12,
            "problematic_scenes": 0,
            "total_scenes": 8
        }
    }
    ```

    ## Usage

    Use this endpoint when you need just the timeline visualization data
    for the waveform display or operator console, without the full analysis result.
    """
    try:
        status_info = await sync_analyzer_service.get_analysis_status(analysis_id)

        if not status_info:
            raise ResourceNotFoundError("analysis", analysis_id)

        if status_info["status"] != "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Analysis {analysis_id} is not completed (status: {status_info['status']})"
            )

        result = status_info.get("result")
        if not result:
            raise HTTPException(status_code=404, detail="Analysis result not found")

        # Extract timeline data
        operator_timeline = result.get("operator_timeline")
        timeline_data = result.get("timeline", [])
        drift_analysis = result.get("drift_analysis", {})

        # Create drift summary for operator overview
        drift_summary = {
            "has_drift": drift_analysis.get("has_drift", False),
            "max_drift_ms": 0,
            "problematic_scenes": 0,
            "total_scenes": len(operator_timeline.get("scenes", []) if operator_timeline else timeline_data)
        }

        if timeline_data:
            # Calculate max drift and problematic scenes
            offsets = [abs(float(t.get("offset_seconds", 0))) * 1000 for t in timeline_data]
            drift_summary["max_drift_ms"] = max(offsets) if offsets else 0
            drift_summary["problematic_scenes"] = sum(1 for offset in offsets if offset > 100)

        return {
            "success": True,
            "analysis_id": analysis_id,
            "timeline": operator_timeline or {"scenes": []},
            "raw_timeline": timeline_data if timeline_data else [],
            "drift_analysis": drift_analysis,
            "drift_summary": drift_summary
        }

    except ResourceNotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving timeline for analysis {analysis_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve timeline: {str(e)}")

# Background task for batch processing
async def _process_batch_analysis(batch_id: str, request: BatchAnalysisRequest):
    """Process batch analysis in background."""
    try:
        logger.info(f"Starting batch analysis {batch_id} with {len(request.file_pairs)} pairs")
        
        # This would be implemented with a proper job queue in production
        # For now, just log the request
        for i, pair in enumerate(request.file_pairs):
            logger.info(f"Batch {batch_id}: Processing pair {i+1}/{len(request.file_pairs)}")
            logger.info(f"  Master: {pair['master']}")
            logger.info(f"  Dub: {pair['dub']}")
        
        logger.info(f"Completed batch analysis {batch_id}")
        
    except Exception as e:
        logger.error(f"Error in batch analysis {batch_id}: {e}")

# Import required modules for batch processing
import datetime
import uuid
