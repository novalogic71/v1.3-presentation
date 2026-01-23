"""
Celery Tasks for Audio Sync Analysis

These tasks run in background workers and persist across server restarts.
Progress is tracked via Redis for real-time updates.
"""

import os
import sys
import logging
from typing import Dict, Any, List
from pathlib import Path

# Ensure fastapi_app is importable (so "app.*" resolves reliably in workers)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.celery_app import celery_app, ProgressTask

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=ProgressTask, name="analysis.componentized")
def run_componentized_analysis_task(
    self,
    master_path: str,
    components: List[Dict[str, Any]],
    offset_mode: str = "mixdown",
    methods: List[str] = None,
    hop_seconds: float = 0.2,
    anchor_window_seconds: float = 10.0,
    refine_window_seconds: float = 8.0,
    refine_pad_seconds: float = 2.0,
    frame_rate: float = 23.976,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run componentized sync analysis as a background Celery task.
    
    This task survives server restarts and browser refreshes.
    Progress is tracked via Redis.
    
    Args:
        master_path: Path to master audio/video file
        components: List of component dicts with 'path', 'label', 'name'
        offset_mode: 'mixdown', 'anchor', or 'channel_aware'
        ...other analysis parameters
    
    Returns:
        Analysis results dict
    """
    task_id = self.request.id
    logger.info(f"Starting componentized analysis task {task_id}")
    
    # Set logging level based on verbose flag
    if verbose:
        logging.getLogger("sync_analyzer").setLevel(logging.DEBUG)
        logging.getLogger("app").setLevel(logging.DEBUG)
        logger.info(f"Verbose logging enabled for task {task_id}")
    
    try:
        self.update_progress(5, "Initializing analysis...")
        
        # Import here to avoid circular imports and ensure fresh imports in worker
        from app.services.componentized_service import (
            run_componentized_analysis,
            _json_safe,
        )
        
        # Create a wrapper to update progress from within the service
        original_progress_fn = None
        
        def progress_callback(progress: int, message: str):
            self.update_progress(progress, message)
        
        # Run the analysis with progress tracking
        # The componentized service uses job_manager.update_progress internally
        # We'll inject our task_id as the job_id
        result = run_componentized_analysis(
            master_path=master_path,
            components=components,
            offset_mode=offset_mode,
            methods=methods,
            hop_seconds=hop_seconds,
            anchor_window_seconds=anchor_window_seconds,
            refine_window_seconds=refine_window_seconds,
            refine_pad_seconds=refine_pad_seconds,
            frame_rate=frame_rate,
            job_id=task_id,  # Use Celery task_id for progress tracking
            verbose=verbose,
        )

        # Generate waveforms for QC interface (background, non-blocking)
        try:
            from sync_analyzer.utils.waveform_generator import generate_componentized_waveforms
            component_paths = [comp["path"] for comp in components]
            generate_componentized_waveforms(
                master_path=master_path,
                component_paths=component_paths,
                analysis_id=task_id
            )
            logger.info(f"Generated waveforms for task {task_id}")
        except Exception as wf_err:
            logger.warning(f"Waveform generation failed (non-critical): {wf_err}")

        self.update_progress(100, "Analysis complete!")
        logger.info(f"Componentized analysis task {task_id} completed successfully")
        
        # Update job registry with completion
        try:
            from app.api.v1.endpoints.job_registry import update_job_status
            update_job_status(task_id, "completed", progress=100, result=_json_safe(result))
        except Exception as reg_err:
            logger.warning(f"Failed to update job registry: {reg_err}")
        
        return _json_safe(result)
    
    except Exception as e:
        logger.error(f"Componentized analysis task {task_id} failed: {e}")
        self.update_progress(0, f"Failed: {str(e)}")
        
        # Update job registry with failure
        try:
            from app.api.v1.endpoints.job_registry import update_job_status
            update_job_status(task_id, "failed", error=str(e))
        except Exception as reg_err:
            logger.warning(f"Failed to update job registry: {reg_err}")
        
        raise


@celery_app.task(bind=True, base=ProgressTask, name="analysis.single")
def run_single_analysis_task(
    self,
    master_path: str,
    dub_path: str,
    methods: List[str] = None,
    ai_model: str = "wav2vec2",
    enable_gpu: bool = True,
    channel_strategy: str = "mono_downmix",
    target_channels: List[str] = None,
    frame_rate: float = 23.976,
) -> Dict[str, Any]:
    """
    Run single file sync analysis as a background Celery task.
    
    Args:
        master_path: Path to master audio/video file
        dub_path: Path to dub audio/video file
        methods: Analysis methods to use
        ...other analysis parameters
    
    Returns:
        Analysis results dict
    """
    task_id = self.request.id
    logger.info(f"Starting single analysis task {task_id}")
    
    try:
        self.update_progress(5, "Initializing analysis...")
        
        # Import sync_analyzer
        from sync_analyzer.analysis import analyze
        
        if methods is None:
            methods = ["mfcc", "onset", "spectral", "correlation"]
        
        self.update_progress(10, "Running sync detection...")
        
        consensus, sync_results, ai_result = analyze(
            Path(master_path),
            Path(dub_path),
            methods=methods,
        )
        
        self.update_progress(90, "Processing results...")
        
        # Build result
        method_results = []
        for method_name, method_result in sync_results.items():
            method_results.append({
                "method": method_name,
                "offset_seconds": getattr(method_result, 'offset_seconds', 0),
                "confidence": getattr(method_result, 'confidence', 0),
                "quality_score": getattr(method_result, 'quality_score', 0),
            })
        
        result = {
            "success": True,
            "offset_seconds": consensus.offset_seconds,
            "confidence": consensus.confidence,
            "method_used": getattr(consensus, 'method_used', 'unknown'),
            "method_results": method_results,
            "consensus_offset": {
                "offset_seconds": consensus.offset_seconds,
                "confidence": consensus.confidence,
            },
        }
        
        self.update_progress(100, "Analysis complete!")
        logger.info(f"Single analysis task {task_id} completed successfully")
        
        return result
    
    except Exception as e:
        logger.error(f"Single analysis task {task_id} failed: {e}")
        self.update_progress(0, f"Failed: {str(e)}")
        raise


@celery_app.task(name="analysis.cleanup_old_results")
def cleanup_old_results(max_age_days: int = 7):
    """
    Periodic task to clean up old task results from Redis.
    
    This is called by Celery Beat if configured.
    """
    import redis
    from app.core.celery_app import REDIS_URL
    
    r = redis.from_url(REDIS_URL)
    
    # Clean up old progress keys
    pattern = "task_progress:*"
    cursor = 0
    deleted = 0
    
    while True:
        cursor, keys = r.scan(cursor, match=pattern, count=100)
        for key in keys:
            ttl = r.ttl(key)
            if ttl == -1:  # No expiry set
                r.expire(key, 86400)  # Set 24 hour expiry
            elif ttl < 0:  # Key doesn't exist
                continue
        if cursor == 0:
            break
    
    logger.info(f"Cleanup task completed, processed progress keys")
    return {"status": "completed"}
