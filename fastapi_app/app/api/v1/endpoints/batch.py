#!/usr/bin/env python3
"""
Batch processing endpoints for sync analysis.
"""

import csv
import io
import logging
import uuid
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import JSONResponse, FileResponse

from app.core.config import settings
from app.core.exceptions import FileValidationError, FileNotFoundError, BatchProcessingError, AnalysisError
from app.models.sync_models import (
    BatchUploadResponse, BatchUploadRequest, BatchStartRequest, BatchStatusResponse,
    BatchResultsResponse, BatchItem, BatchStatus, AnalysisMethod, AIModel, AnalysisStatus,
    BatchResultSummary
)
from app.services.sync_analyzer_service import SyncAnalyzerService

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory batch storage (in production, use a database)
BATCH_STORAGE: Dict[str, Dict[str, Any]] = {}
BATCH_RESULTS: Dict[str, List[BatchItem]] = {}

@router.post("/upload-csv", response_model=BatchUploadResponse)
async def upload_batch_csv(
    file: UploadFile = File(..., description="CSV file with batch analysis items"),
    description: Optional[str] = Form(None, description="Batch description"),
    priority: str = Form("normal", description="Batch priority: low, normal, high")
):
    """
    Upload a CSV file for batch sync analysis.
    
    ## CSV Format
    
    The CSV file should have the following columns:
    - `master_file`: Path to master audio/video file
    - `dub_file`: Path to dub audio/video file  
    - `methods`: Comma-separated analysis methods (mfcc,onset,spectral,ai)
    - `ai_model`: AI model to use (wav2vec2, yamnet, spectral) - optional
    - `description`: Item description - optional
    - `tags`: Comma-separated tags - optional
    
    ## Example CSV Content
    
    ```csv
    master_file,dub_file,methods,ai_model,description,tags
    /mnt/data/audio/master1.wav,/mnt/data/audio/dub1.wav,"mfcc,ai",wav2vec2,Daily batch item 1,"daily,batch"
    /mnt/data/audio/master2.wav,/mnt/data/audio/dub2.wav,"onset,spectral",,Daily batch item 2,"daily,batch"
    ```
    
    ## Response
    
    Returns a batch ID and list of parsed items ready for processing.
    
    ## Curl Example
    
    ```bash
    curl -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
      -F "file=@batch_analysis.csv" \
      -F "description=Daily sync analysis batch" \
      -F "priority=normal"
    ```
    """
    try:
        # Validate file
        if not file.filename or not file.filename.endswith('.csv'):
            raise FileValidationError("File must be a CSV file", file_path=file.filename or "unknown")
        
        # Read and parse CSV
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Parse CSV
        batch_items = await _parse_batch_csv(csv_content)
        
        if not batch_items:
            raise HTTPException(status_code=400, detail="No valid batch items found in CSV")
        
        # Generate batch ID
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Store batch information
        BATCH_STORAGE[batch_id] = {
            'batch_id': batch_id,
            'description': description,
            'priority': priority,
            'status': BatchStatus.UPLOADED,
            'items_count': len(batch_items),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        BATCH_RESULTS[batch_id] = batch_items
        
        logger.info(f"Batch uploaded successfully: {batch_id} with {len(batch_items)} items")
        
        return BatchUploadResponse(
            batch_id=batch_id,
            items_count=len(batch_items),
            items=batch_items,
            message=f"Batch uploaded successfully with {len(batch_items)} items"
        )
        
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading batch CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{batch_id}/start", response_model=BatchStatusResponse)
async def start_batch_processing(
    batch_id: str,
    background_tasks: BackgroundTasks,
    request: BatchStartRequest = BatchStartRequest()
):
    """
    Start processing a batch of sync analysis items.
    
    Begins asynchronous processing of all items in the batch using the specified
    number of parallel workers.
    
    ## Parameters
    
    - **batch_id**: The batch identifier from upload
    - **parallel_jobs**: Number of parallel processing jobs (1-8)
    - **priority**: Processing priority (low, normal, high)
    - **notification_webhook**: Optional webhook for completion notifications
    
    ## Response
    
    Returns the current batch status and estimated completion time.
    
    ## Curl Example
    
    ```bash
    curl -X POST "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/start" \
      -H "Content-Type: application/json" \
      -d '{
        "parallel_jobs": 2,
        "priority": "normal",
        "notification_webhook": "https://your-server.com/webhook"
      }'
    ```
    """
    try:
        # Check if batch exists
        if batch_id not in BATCH_STORAGE:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        batch_info = BATCH_STORAGE[batch_id]
        batch_items = BATCH_RESULTS[batch_id]
        
        # Check if batch is in correct state
        if batch_info['status'] != BatchStatus.UPLOADED:
            raise HTTPException(
                status_code=400, 
                detail=f"Batch is in {batch_info['status']} state, cannot start processing"
            )
        
        # Update batch status
        batch_info['status'] = BatchStatus.PROCESSING
        batch_info['parallel_jobs'] = request.parallel_jobs
        batch_info['started_at'] = datetime.now(timezone.utc)
        batch_info['updated_at'] = datetime.now(timezone.utc)
        
        # Estimate completion time (rough estimate: 30 seconds per item per job)
        estimated_minutes = (len(batch_items) * 30) / (request.parallel_jobs * 60)
        batch_info['estimated_completion'] = datetime.now(timezone.utc).replace(
            microsecond=0
        ).replace(second=0) + timedelta(minutes=int(estimated_minutes))
        
        # Start background processing
        background_tasks.add_task(
            _process_batch_background, 
            batch_id, 
            batch_items, 
            request.parallel_jobs,
            request.notification_webhook
        )
        
        logger.info(f"Started batch processing: {batch_id} with {request.parallel_jobs} parallel jobs")
        
        return BatchStatusResponse(
            batch_id=batch_id,
            status=BatchStatus.PROCESSING,
            progress=0.0,
            items_total=len(batch_items),
            items_completed=0,
            items_processing=min(request.parallel_jobs, len(batch_items)),
            items_failed=0,
            estimated_completion=batch_info.get('estimated_completion'),
            message=f"Batch processing started with {request.parallel_jobs} parallel jobs"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    include_details: bool = Query(False, description="Include detailed item status")
):
    """
    Get the current status of a batch processing job.
    
    Returns progress information, completion status, and optionally detailed
    item-level status for each analysis in the batch.
    
    ## Parameters
    
    - **batch_id**: The batch identifier
    - **include_details**: Whether to include detailed item status (optional)
    
    ## Response
    
    Returns current batch status, progress percentage, and item counts.
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/status?include_details=true"
    ```
    """
    try:
        # Check if batch exists
        if batch_id not in BATCH_STORAGE:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        batch_info = BATCH_STORAGE[batch_id]
        batch_items = BATCH_RESULTS[batch_id]
        
        # Calculate status counts
        items_completed = sum(1 for item in batch_items if item.status == AnalysisStatus.COMPLETED)
        items_processing = sum(1 for item in batch_items if item.status == AnalysisStatus.PROCESSING)
        items_failed = sum(1 for item in batch_items if item.status == AnalysisStatus.FAILED)
        items_pending = sum(1 for item in batch_items if item.status == AnalysisStatus.PENDING)
        
        # Calculate progress
        progress = (items_completed + items_failed) / len(batch_items) * 100 if batch_items else 0
        
        # Determine overall status
        if items_completed == len(batch_items):
            batch_status = BatchStatus.COMPLETED
        elif items_failed == len(batch_items):
            batch_status = BatchStatus.FAILED
        elif items_processing > 0 or batch_info['status'] == BatchStatus.PROCESSING:
            batch_status = BatchStatus.PROCESSING
        else:
            batch_status = BatchStatus(batch_info['status'])
        
        # Update batch info
        batch_info['status'] = batch_status
        batch_info['updated_at'] = datetime.now(timezone.utc)
        
        return BatchStatusResponse(
            batch_id=batch_id,
            status=batch_status,
            progress=round(progress, 1),
            items_total=len(batch_items),
            items_completed=items_completed,
            items_processing=items_processing,
            items_failed=items_failed,
            items_details=batch_items if include_details else None,
            estimated_completion=batch_info.get('estimated_completion'),
            message=f"Batch status: {batch_status.value}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{batch_id}/results", response_model=BatchResultsResponse)
async def get_batch_results(
    batch_id: str,
    export_format: str = Query("json", description="Export format: json, csv")
):
    """
    Get the final results of a completed batch processing job.
    
    Returns comprehensive results including individual analysis results,
    summary statistics, and download links for detailed reports.
    
    ## Parameters
    
    - **batch_id**: The batch identifier
    - **export_format**: Response format (json, csv)
    
    ## Response
    
    Returns batch results with summary statistics and individual item results.
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/results" \
      -H "Accept: application/json"
    ```
    """
    try:
        # Check if batch exists
        if batch_id not in BATCH_STORAGE:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        batch_info = BATCH_STORAGE[batch_id]
        batch_items = BATCH_RESULTS[batch_id]
        
        # Calculate summary statistics
        items_completed = [item for item in batch_items if item.status == AnalysisStatus.COMPLETED]
        items_failed = [item for item in batch_items if item.status == AnalysisStatus.FAILED]
        
        # Calculate average confidence from completed items
        confidences = []
        for item in items_completed:
            if item.result and 'confidence' in item.result:
                confidences.append(item.result['confidence'])
        
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Calculate processing time
        start_time = batch_info.get('started_at')
        end_time = batch_info.get('completed_at', datetime.now(timezone.utc))
        processing_time = (end_time - start_time).total_seconds() if start_time else 0
        
        summary = BatchResultSummary(
            items_total=len(batch_items),
            items_completed=len(items_completed),
            items_failed=len(items_failed),
            average_confidence=round(average_confidence, 3),
            processing_time_seconds=round(processing_time, 1)
        )
        
        # Generate download links
        download_links = {
            "json_report": f"/api/v1/reports/{batch_id}.json",
            "csv_export": f"/api/v1/reports/{batch_id}.csv"
        }
        
        # Add PDF report if available
        if len(items_completed) > 0:
            download_links["detailed_report"] = f"/api/v1/reports/{batch_id}_detailed.pdf"
        
        return BatchResultsResponse(
            batch_id=batch_id,
            status=BatchStatus(batch_info['status']),
            summary=summary,
            results=batch_items,
            download_links=download_links,
            message=f"Batch results: {len(items_completed)}/{len(batch_items)} completed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{batch_id}")
async def cancel_batch(batch_id: str):
    """
    Cancel a batch processing job.
    
    Stops processing and marks the batch as cancelled. Items already completed
    will retain their results.
    
    ## Parameters
    
    - **batch_id**: The batch identifier to cancel
    
    ## Response
    
    Returns success confirmation with cancellation details.
    
    ## Curl Example
    
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600"
    ```
    """
    try:
        # Check if batch exists
        if batch_id not in BATCH_STORAGE:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        batch_info = BATCH_STORAGE[batch_id]
        batch_items = BATCH_RESULTS[batch_id]
        
        # Update batch status
        batch_info['status'] = BatchStatus.CANCELLED
        batch_info['cancelled_at'] = datetime.now(timezone.utc)
        batch_info['updated_at'] = datetime.now(timezone.utc)
        
        # Cancel pending items
        for item in batch_items:
            if item.status == AnalysisStatus.PENDING:
                item.status = AnalysisStatus.CANCELLED
        
        logger.info(f"Batch cancelled: {batch_id}")
        
        return {
            "success": True,
            "message": f"Batch {batch_id} cancelled successfully",
            "batch_id": batch_id,
            "timestamp": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def _parse_batch_csv(csv_content: str) -> List[BatchItem]:
    """Parse CSV content into batch items."""
    items = []
    reader = csv.DictReader(io.StringIO(csv_content))
    
    for i, row in enumerate(reader):
        try:
            # Generate item ID
            item_id = f"item_{i+1:03d}"
            
            # Parse methods
            methods_str = row.get('methods', 'mfcc').strip()
            if methods_str:
                method_names = [m.strip() for m in methods_str.split(',')]
                methods = []
                for method_name in method_names:
                    if method_name in [m.value for m in AnalysisMethod]:
                        methods.append(AnalysisMethod(method_name))
            else:
                methods = [AnalysisMethod.MFCC]
            
            # Parse AI model
            ai_model = None
            ai_model_str = row.get('ai_model', '').strip()
            if ai_model_str and ai_model_str in [m.value for m in AIModel]:
                ai_model = AIModel(ai_model_str)
            
            # Parse tags
            tags_str = row.get('tags', '').strip()
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
            
            # Create batch item
            item = BatchItem(
                item_id=item_id,
                master_file=row.get('master_file', '').strip(),
                dub_file=row.get('dub_file', '').strip(),
                methods=methods,
                ai_model=ai_model,
                description=row.get('description', '').strip() or None,
                tags=tags,
                status=AnalysisStatus.PENDING
            )
            
            # Validate required fields
            if not item.master_file or not item.dub_file:
                logger.warning(f"Skipping row {i+1}: missing master_file or dub_file")
                continue
            
            items.append(item)
            
        except Exception as e:
            logger.warning(f"Error parsing row {i+1}: {e}")
            continue
    
    return items

async def _process_batch_background(
    batch_id: str, 
    batch_items: List[BatchItem], 
    parallel_jobs: int,
    notification_webhook: Optional[str] = None
):
    """Process batch items in the background."""
    try:
        from datetime import timedelta
        
        logger.info(f"Starting background processing for batch {batch_id}")
        
        # Create semaphore to limit concurrent jobs
        semaphore = asyncio.Semaphore(parallel_jobs)
        sync_service = SyncAnalyzerService()
        
        async def process_item(item: BatchItem):
            async with semaphore:
                try:
                    # Update item status
                    item.status = AnalysisStatus.PROCESSING
                    item.started_at = datetime.now(timezone.utc)
                    
                    logger.info(f"Processing item {item.item_id}: {item.master_file} + {item.dub_file}")
                    
                    # Create analysis request
                    from app.models.sync_models import SyncAnalysisRequest, AnalysisConfig
                    from app.core.config import settings
                    
                    # Check if AI should be disabled for batch processing
                    enable_ai = item.ai_model is not None
                    if settings.DISABLE_AI_BATCH:
                        enable_ai = False
                        # Filter out AI from methods if disabled
                        filtered_methods = [m for m in item.methods if m.lower() != 'ai']
                        if filtered_methods != item.methods:
                            logger.warning(f"AI disabled for batch processing, using methods: {filtered_methods}")
                    else:
                        filtered_methods = item.methods
                    
                    analysis_request = SyncAnalysisRequest(
                        master_file=item.master_file,
                        dub_file=item.dub_file,
                        analysis_config=AnalysisConfig(
                            methods=filtered_methods,
                            ai_model=item.ai_model,
                            enable_ai=enable_ai
                        )
                    )
                    
                    # Perform sync analysis
                    analysis_id = await sync_service.analyze_sync(analysis_request)
                    
                    # Wait for analysis to complete
                    max_wait_time = 300  # 5 minutes timeout
                    start_time = datetime.now(timezone.utc)
                    
                    while True:
                        analysis_result = await sync_service.get_analysis_result(analysis_id)
                        if analysis_result and analysis_result.status != AnalysisStatus.PROCESSING:
                            break
                        
                        # Check timeout
                        if (datetime.now(timezone.utc) - start_time).total_seconds() > max_wait_time:
                            raise TimeoutError(f"Analysis timed out after {max_wait_time} seconds")
                        
                        await asyncio.sleep(2)  # Check every 2 seconds
                    
                    # Extract result data
                    if analysis_result and analysis_result.sync_offset:
                        result = {
                            "offset_seconds": analysis_result.sync_offset.offset_seconds,
                            "confidence": analysis_result.sync_offset.confidence,
                            "method_used": analysis_result.primary_method,
                            "analysis_id": analysis_id
                        }
                    else:
                        raise AnalysisError("Analysis completed but no valid result found")
                    
                    # Update item with results
                    item.result = result
                    item.status = AnalysisStatus.COMPLETED
                    item.completed_at = datetime.now(timezone.utc)
                    
                    logger.info(f"Completed item {item.item_id} successfully")
                    
                except Exception as e:
                    logger.error(f"Error processing item {item.item_id}: {e}")
                    item.error = str(e)
                    item.status = AnalysisStatus.FAILED
                    item.completed_at = datetime.now(timezone.utc)
        
        # Process all items concurrently
        tasks = [process_item(item) for item in batch_items]
        await asyncio.gather(*tasks)
        
        # Update batch status
        BATCH_STORAGE[batch_id]['status'] = BatchStatus.COMPLETED
        BATCH_STORAGE[batch_id]['completed_at'] = datetime.now(timezone.utc)
        BATCH_STORAGE[batch_id]['updated_at'] = datetime.now(timezone.utc)
        
        logger.info(f"Batch processing completed: {batch_id}")
        
        # Send webhook notification if configured
        if notification_webhook:
            await _send_webhook_notification(batch_id, notification_webhook)
        
    except Exception as e:
        logger.error(f"Error in background batch processing: {e}")
        BATCH_STORAGE[batch_id]['status'] = BatchStatus.FAILED
        BATCH_STORAGE[batch_id]['error'] = str(e)
        BATCH_STORAGE[batch_id]['updated_at'] = datetime.now(timezone.utc)

async def _send_webhook_notification(batch_id: str, webhook_url: str):
    """Send webhook notification for batch completion."""
    try:
        import httpx
        
        batch_info = BATCH_STORAGE[batch_id]
        batch_items = BATCH_RESULTS[batch_id]
        
        # Prepare notification payload
        payload = {
            "event": "batch_completed",
            "batch_id": batch_id,
            "status": batch_info['status'],
            "items_total": len(batch_items),
            "items_completed": sum(1 for item in batch_items if item.status == AnalysisStatus.COMPLETED),
            "items_failed": sum(1 for item in batch_items if item.status == AnalysisStatus.FAILED),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Webhook notification sent successfully for batch {batch_id}")
            else:
                logger.warning(f"Webhook notification failed with status {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error sending webhook notification: {e}")