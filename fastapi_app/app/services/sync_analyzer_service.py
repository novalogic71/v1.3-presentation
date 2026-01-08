#!/usr/bin/env python3
"""
Core sync analyzer service for the FastAPI application.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import traceback
import sys
import os
import subprocess

from app.core.config import settings, get_analysis_methods, get_ai_models
from app.core.exceptions import (
    FileNotFoundError, FileTypeNotSupportedError, AnalysisError,
    AnalysisMethodNotSupportedError, AIModelNotAvailableError
)
from app.models.sync_models import (
    SyncAnalysisRequest, SyncAnalysisResult, SyncOffset, MethodResult,
    AIAnalysisResult, AnalysisStatus, AnalysisMethod, AIModel
)

logger = logging.getLogger(__name__)

class SyncAnalyzerService:
    """Service for performing sync analysis operations."""
    
    def __init__(self):
        """Initialize the sync analyzer service."""
        self.analysis_cache: Dict[str, SyncAnalysisResult] = {}
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=settings.AI_BATCH_SIZE)

        # Initialize database for job persistence
        from sync_analyzer.db.job_db import migrate_database, mark_orphaned_jobs
        migrate_database()

        # Mark any jobs from previous server instances as orphaned
        orphaned_count = mark_orphaned_jobs()
        if orphaned_count > 0:
            logger.warning(f"Marked {orphaned_count} orphaned job(s) from previous server instance")

        # Restore incomplete jobs from database to memory
        self._restore_incomplete_jobs()

        # Initialize sync detector instances
        self._init_sync_detectors()

        logger.info("SyncAnalyzerService initialized successfully")

    def _console_progress(self, analysis_id: str, progress: float, message: str, done: bool = False):
        """Emit a single-line console progress indicator when running in a TTY.

        - If stderr/stdout is a TTY and DEBUG: update the same line with \r.
        - Otherwise: rate-limit regular logs to avoid spam (every >=5% or on message change),
          and always log once when done.
        """
        try:
            is_tty = (sys.stderr.isatty() or sys.stdout.isatty())
            single_line_ok = is_tty and bool(str(os.environ.get("SINGLE_LINE_PROGRESS", "1")).lower() in {"1", "true", "yes"}) and bool(settings.DEBUG)
            record = self.active_analyses.get(analysis_id, {})
            if single_line_ok:
                # Render a fixed-width single line with carriage return
                short_id = analysis_id.split("_")[-1]
                msg = (message or "").strip().replace("\n", " ")
                line = f"\r[{short_id}] {progress:6.1f}% {msg[:70]:<70}"
                print(line, end="", flush=True)
                if done:
                    print("", flush=True)  # newline
            else:
                last_p = float(record.get("_last_log_p", -10.0))
                last_m = record.get("_last_log_m")
                should_log = done or (progress - last_p >= 5.0) or (message and message != last_m)
                if should_log:
                    logger.info(f"Analysis Progress ({analysis_id}): {progress:.1f}% - {message}")
                    record["_last_log_p"] = progress
                    record["_last_log_m"] = message
                    self.active_analyses[analysis_id] = record
        except Exception:
            # Never let progress printing break analysis
            pass
    
    def _init_sync_detectors(self):
        """Initialize sync detector instances."""
        try:
            import torch
            # Import sync analyzer modules
            from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector
            from sync_analyzer.ai.embedding_sync_detector import AISyncDetector, EmbeddingConfig
            # Proactive hint if transformers is missing when AI is enabled/default
            try:
                import transformers  # noqa: F401
            except Exception:
                logger.warning(
                    "Transformers not installed; AI wav2vec2 will fall back to spectral. "
                    "Install with 'pip install transformers' or 'pip install -r fastapi_app/requirements.txt'"
                )
            
            # Initialize core detector
            gpu_available = torch.cuda.is_available()
            self.core_detector = ProfessionalSyncDetector(
                sample_rate=settings.DEFAULT_SAMPLE_RATE,
                window_size_seconds=settings.DEFAULT_WINDOW_SIZE,
                confidence_threshold=settings.DEFAULT_CONFIDENCE_THRESHOLD,
                use_gpu=(settings.USE_GPU and gpu_available)
            )
            
            # Initialize AI detector
            self.ai_detector = AISyncDetector(
                config=EmbeddingConfig(
                    model_name="wav2vec2",
                    use_gpu=(settings.USE_GPU and gpu_available),
                    sample_rate=16000
                )
            )
            
            device_msg = "GPU" if (settings.USE_GPU and gpu_available) else "CPU"
            if settings.USE_GPU and not gpu_available:
                logger.warning("GPU requested but not available; AI will run on CPU")
            logger.info(f"Sync detectors initialized successfully (AI device: {device_msg})")
        
        except ImportError as e:
            logger.warning(f"Could not import sync analyzer modules: {e}")
            self.core_detector = None
            self.ai_detector = None
        except Exception as e:
            logger.error(f"Error initializing sync detectors: {e}")
            self.core_detector = None
            self.ai_detector = None

    def _restore_incomplete_jobs(self):
        """
        Restore incomplete jobs from database to active_analyses.

        This allows clients to reconnect to jobs that were in progress
        when the page was refreshed or the server restarted (though
        restarted jobs will be marked as orphaned).
        """
        try:
            from sync_analyzer.db.job_db import list_jobs

            # Get jobs in processing or pending state
            incomplete = list_jobs(status='processing') + list_jobs(status='pending')

            for job_record in incomplete:
                job_id = job_record['job_id']
                request_params = json.loads(job_record['request_params'])

                # Reconstruct analysis record
                self.active_analyses[job_id] = {
                    "id": job_id,
                    "request": SyncAnalysisRequest(**request_params),
                    "status": AnalysisStatus(job_record['status']),
                    "created_at": datetime.fromisoformat(job_record['created_at']),
                    "progress": job_record.get('progress', 0.0),
                    "status_message": job_record.get('status_message'),
                    "restored_from_db": True  # Flag to indicate this was restored
                }

            if incomplete:
                logger.info(f"Restored {len(incomplete)} incomplete job(s) from database")

        except Exception as e:
            logger.warning(f"Could not restore incomplete jobs: {e}")

    async def analyze_sync(self, request: SyncAnalysisRequest) -> str:
        """
        Start a sync analysis operation.
        
        Args:
            request: Sync analysis request
            
        Returns:
            Analysis ID for tracking
        """
        analysis_id = f"analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Validate files exist
        await self._validate_files(request.master_file, request.dub_file)
        
        # Validate analysis methods (include AI if enabled)
        effective_methods = list(request.methods)
        try:
            from app.models.sync_models import AnalysisMethod
        except Exception:
            # Fallback import path
            from fastapi_app.app.models.sync_models import AnalysisMethod  # type: ignore

        if request.enable_ai and AnalysisMethod.AI not in effective_methods:
            effective_methods.append(AnalysisMethod.AI)

        await self._validate_methods(effective_methods)
        
        # Validate AI settings
        if request.enable_ai:
            await self._validate_ai_model(request.ai_model)
        
        # Create analysis record
        analysis_record = {
            "id": analysis_id,
            "request": request,
            "status": AnalysisStatus.PENDING,
            "created_at": datetime.utcnow(),
            "progress": 0.0
        }

        self.active_analyses[analysis_id] = analysis_record

        # Persist job to database
        try:
            from sync_analyzer.db.job_db import create_job
            create_job(
                job_id=analysis_id,
                job_type='single',
                request_params=request.model_dump()
            )
            logger.debug(f"Job {analysis_id} persisted to database")
        except Exception as e:
            logger.warning(f"Could not persist job to database: {e}")

        # Start analysis in background
        asyncio.create_task(self._perform_analysis(analysis_id, request))

        logger.info(f"Started sync analysis {analysis_id} for {request.master_file} vs {request.dub_file}")

        return analysis_id
    
    async def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of an analysis operation.
        
        Args:
            analysis_id: Analysis identifier
            
        Returns:
            Analysis status information
        """
        if analysis_id in self.active_analyses:
            return self.active_analyses[analysis_id]
        elif analysis_id in self.analysis_cache:
            result = self.analysis_cache[analysis_id]
            return {
                "id": analysis_id,
                "status": result.status,
                "result": result,
                "created_at": result.created_at,
                "completed_at": result.completed_at,
                "progress": 100.0
            }
        else:
            return None
    
    async def get_analysis_result(self, analysis_id: str) -> Optional[SyncAnalysisResult]:
        """
        Get the completed analysis result.
        
        Args:
            analysis_id: Analysis identifier
            
        Returns:
            Analysis result if completed
        """
        # First check cache
        cached_result = self.analysis_cache.get(analysis_id)
        if cached_result:
            return cached_result
            
        # If not in cache, check database
        try:
            from sync_analyzer.db.report_db import get_by_analysis_id
            from pathlib import Path
            # Use correct database path relative to project root
            db_path = Path("../sync_reports/sync_reports.db")
            db_result = get_by_analysis_id(analysis_id, db_path)
            
            if db_result:
                # Convert database result to SyncAnalysisResult
                # Calculate offset_samples assuming 22050 Hz (standard analysis sample rate)
                sample_rate = 22050
                offset_samples = int(db_result["consensus_offset_seconds"] * sample_rate)
                
                sync_result = SyncAnalysisResult(
                    analysis_id=db_result["analysis_id"],
                    status=AnalysisStatus.COMPLETED,
                    consensus_offset=SyncOffset(
                        offset_seconds=db_result["consensus_offset_seconds"],
                        offset_milliseconds=db_result["consensus_offset_seconds"] * 1000.0,
                        offset_samples=offset_samples,
                        confidence=db_result["confidence_score"]
                    ),
                    master_file=db_result["master_file"],
                    dub_file=db_result["dub_file"],
                    created_at=datetime.fromisoformat(db_result["created_at"].replace('Z', '+00:00')) if isinstance(db_result["created_at"], str) else db_result["created_at"],
                    completed_at=datetime.fromisoformat(db_result["created_at"].replace('Z', '+00:00')) if isinstance(db_result["created_at"], str) else db_result["created_at"]
                )
                
                # Cache the result for future requests
                self.analysis_cache[analysis_id] = sync_result
                return sync_result
                
        except Exception as e:
            logger.error(f"Error retrieving analysis from database: {e}")
            
        return None
    
    async def cancel_analysis(self, analysis_id: str) -> bool:
        """
        Cancel an active analysis operation.
        
        Args:
            analysis_id: Analysis identifier
            
        Returns:
            True if cancelled successfully
        """
        if analysis_id in self.active_analyses:
            analysis_record = self.active_analyses[analysis_id]
            analysis_record["status"] = AnalysisStatus.CANCELLED
            analysis_record["cancelled_at"] = datetime.utcnow()
            
            # Move to cache
            self.analysis_cache[analysis_id] = self._create_cancelled_result(analysis_record)
            del self.active_analyses[analysis_id]
            
            logger.info(f"Cancelled analysis {analysis_id}")
            return True
        
        return False
    
    async def list_analyses(self, page: int = 1, page_size: int = 20) -> Tuple[List[SyncAnalysisResult], int]:
        """
        List all analyses with pagination.
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Tuple of (analyses, total_count)
        """
        all_results = list(self.analysis_cache.values())
        total_count = len(all_results)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        page_results = all_results[start_idx:end_idx]
        
        return page_results, total_count
    
    async def _validate_files(self, master_file: str, dub_file: str):
        """Validate that files exist and are accessible."""
        for file_path in [master_file, dub_file]:
            if not Path(file_path).exists():
                raise FileNotFoundError(file_path)
            
            # Check file type
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in settings.ALLOWED_EXTENSIONS:
                raise FileTypeNotSupportedError(
                    file_path, file_ext, settings.ALLOWED_EXTENSIONS
                )
    
    async def _validate_methods(self, methods: List[AnalysisMethod]):
        """Validate requested analysis methods."""
        for method in methods:
            if method not in settings.ENABLED_METHODS:
                raise AnalysisMethodNotSupportedError(
                    method.value, settings.ENABLED_METHODS
                )
    
    async def _validate_ai_model(self, model: AIModel):
        """Validate requested AI model."""
        if model.value not in settings.ENABLED_AI_MODELS:
            raise AIModelNotAvailableError(
                model.value, settings.ENABLED_AI_MODELS
            )
    
    async def _perform_analysis(self, analysis_id: str, request: SyncAnalysisRequest):
        """Perform the actual sync analysis."""
        from sync_analyzer.db.job_db import update_job_status, complete_job, fail_job

        try:
            analysis_record = self.active_analyses[analysis_id]
            analysis_record["status"] = AnalysisStatus.PROCESSING
            analysis_record["progress"] = 10.0

            # Update job status to processing in database
            try:
                update_job_status(analysis_id, status='processing', progress=10.0, status_message="Starting analysis")
            except Exception as e:
                logger.warning(f"Could not update job status in database: {e}")

            logger.info(f"Starting analysis {analysis_id}")
            
            # Perform analysis using thread pool executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._run_sync_analysis,
                request,
                analysis_id
            )
            
            # Build operator timeline if raw timeline data exists
            operator_timeline = None
            try:
                raw_tl = {
                    'combined_chunks': result.get("chunk_details") or result.get("combined_chunks") or [],
                    'timeline': result.get("timeline") or []
                }
                if raw_tl['combined_chunks'] or raw_tl['timeline']:
                    from sync_analyzer.ui.operator_timeline import OperatorTimeline
                    op = OperatorTimeline()
                    scenes = op.create_scene_timeline(raw_tl)
                    operator_timeline = { 'scenes': scenes }
            except Exception as _op_err:
                logger.warning(f"Operator timeline build failed: {_op_err}")

            # Create analysis result
            analysis_result = SyncAnalysisResult(
                analysis_id=analysis_id,
                master_file=request.master_file,
                dub_file=request.dub_file,
                status=AnalysisStatus.COMPLETED,
                consensus_offset=result["consensus_offset"],
                method_results=result["method_results"],
                ai_result=result.get("ai_result"),
                analysis_config=request,
                processing_time=result["processing_time"],
                created_at=analysis_record["created_at"],
                completed_at=datetime.utcnow(),
                frame_rate=request.frame_rate,
                overall_confidence=result["overall_confidence"],
                method_agreement=result["method_agreement"],
                sync_status=result["sync_status"],
                recommendations=result["recommendations"],
                timeline=result.get("timeline"),
                chunk_details=result.get("chunk_details"),
                combined_chunks=result.get("combined_chunks"),
                drift_analysis=result.get("drift_analysis"),
                operator_timeline=operator_timeline
            )
            
            # Store result
            self.analysis_cache[analysis_id] = analysis_result

            # Persist to reports database (lightweight SQLite store)
            try:
                from sync_analyzer.db.report_db import save_report_from_model
                save_report_from_model(analysis_result)
                logger.info(f"Report persisted to SQLite store for {analysis_id}")
            except Exception as _db_err:
                logger.warning(f"Could not persist report to DB: {_db_err}")

            # Persist job completion to jobs database
            try:
                complete_job(analysis_id, result_data=analysis_result.model_dump())
                logger.debug(f"Job {analysis_id} marked as completed in database")
            except Exception as e:
                logger.warning(f"Could not complete job in database: {e}")

            # Update analysis record
            analysis_record["status"] = AnalysisStatus.COMPLETED
            analysis_record["result"] = analysis_result
            analysis_record["progress"] = 100.0
            analysis_record["completed_at"] = datetime.utcnow()
            # Ensure we terminate any single-line console progress neatly
            self._console_progress(analysis_id, 100.0, "Completed", done=True)

            logger.info(f"Completed analysis {analysis_id} successfully")
            
        except Exception as e:
            logger.error(f"Analysis {analysis_id} failed: {e}")
            traceback.print_exc()

            # Persist job failure to database
            try:
                fail_job(analysis_id, error_message=str(e))
                logger.debug(f"Job {analysis_id} marked as failed in database")
            except Exception as db_err:
                logger.warning(f"Could not fail job in database: {db_err}")

            # Update analysis record with error
            analysis_record["status"] = AnalysisStatus.FAILED
            analysis_record["error"] = str(e)
            analysis_record["progress"] = 0.0
            self._console_progress(analysis_id, 0.0, f"Failed: {e}", done=True)

            # Create failed result
            failed_result = self._create_failed_result(analysis_record, str(e))
            self.analysis_cache[analysis_id] = failed_result
            
        finally:
            # Clean up active analysis
            if analysis_id in self.active_analyses:
                del self.active_analyses[analysis_id]
    
    def _run_sync_analysis(self, request: SyncAnalysisRequest, analysis_id: str) -> Dict[str, Any]:
        """Run sync analysis in a separate thread."""
        start_time = datetime.utcnow()
        
        try:
            if not self.core_detector:
                raise AnalysisError("Core sync detector not available")
            
            # Large-file handling (chunked vs. direct). Threshold configurable.
            LARGE_FILE_THRESHOLD_SECONDS = float(getattr(settings, 'LONG_FILE_THRESHOLD_SECONDS', 180.0))
            def _probe_duration_seconds(path: str) -> float:
                try:
                    pr = subprocess.run(
                        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                        capture_output=True, text=True, timeout=10
                    )
                    if pr.returncode == 0:
                        return float((pr.stdout or '0').strip() or 0.0)
                except Exception:
                    pass
                return 0.0

            m_dur = _probe_duration_seconds(request.master_file)
            d_dur = _probe_duration_seconds(request.dub_file)
            max_dur = max(m_dur, d_dur)
            
            # Decide whether to use the chunked analyzer
            use_chunked = (max_dur >= LARGE_FILE_THRESHOLD_SECONDS)
            # Request-level overrides
            prefer_gpu = getattr(request, 'prefer_gpu', None)
            prefer_bypass = getattr(request, 'prefer_gpu_bypass_chunked', None)
            force_chunked = bool(getattr(request, 'force_chunked', False))
            enable_drift = bool(getattr(request, 'enable_drift_detection', False))
            # If GPU is available and policy allows, bypass chunked up to a cap
            try:
                sys_gpu_available = torch.cuda.is_available()
            except Exception:
                sys_gpu_available = False
            # Compute effective GPU preference
            if prefer_gpu is None:
                gpu_available = (settings.USE_GPU and sys_gpu_available)
            else:
                gpu_available = (bool(prefer_gpu) and sys_gpu_available)

            if force_chunked:
                use_chunked = True
            elif not enable_drift:
                # If drift detection is disabled, NEVER use chunked analyzer
                # Chunked analyzer is only for drift detection across the file
                # For simple offset detection (bars/tone, dubbed content), use standard methods
                use_chunked = False
                try:
                    if analysis_id in self.active_analyses:
                        self.active_analyses[analysis_id]["status_message"] = "Drift detection disabled: using standard analysis"
                        self._console_progress(analysis_id, 15.0, "Standard analysis (drift detection OFF)")
                except Exception:
                    pass
            elif use_chunked and gpu_available and (
                (prefer_bypass is True) or (prefer_bypass is None and bool(getattr(settings, 'LONG_FILE_GPU_BYPASS', True)))
            ):
                cap = getattr(settings, 'LONG_FILE_GPU_BYPASS_MAX_SECONDS', None)
                if (cap is None) or (max_dur <= float(cap)):
                    use_chunked = False
                    try:
                        if analysis_id in self.active_analyses:
                            self.active_analyses[analysis_id]["status_message"] = "GPU available: bypassing chunked analyzer"
                            self._console_progress(analysis_id, 15.0, "Bypassing chunked analyzer due to GPU")
                    except Exception:
                        pass

            if use_chunked:
                # Coarse progress updates for UI/SSE
                try:
                    if analysis_id in self.active_analyses:
                        self.active_analyses[analysis_id]["status_message"] = "Using chunked analyzer for large files"
                        self.active_analyses[analysis_id]["progress"] = 20.0
                        self._console_progress(analysis_id, 20.0, "Chunked analysis: extracting audio")
                except Exception:
                    pass
                
                from sync_analyzer.core.optimized_large_file_detector import OptimizedLargeFileDetector
                # Use request.window_size as chunk_size to ensure measurable offsets up to window_size
                req_chunk = float(getattr(request, 'window_size', 30.0) or 30.0)
                chunked = OptimizedLargeFileDetector(gpu_enabled=True, chunk_size=req_chunk)
                chunk_result = chunked.analyze_sync_chunked(request.master_file, request.dub_file)
                
                # Build a MethodResult-like entry based on chunked result
                offset_seconds = float(chunk_result.get('offset_seconds') or 0.0)
                confidence = float(chunk_result.get('confidence') or 0.0)
                
                # Progress near completion
                try:
                    if analysis_id in self.active_analyses:
                        self.active_analyses[analysis_id]["status_message"] = "Aggregating chunk results"
                        self.active_analyses[analysis_id]["progress"] = 95.0
                        self._console_progress(analysis_id, 95.0, "Chunked analysis: aggregating")
                except Exception:
                    pass
                
                # Convert to our models
                frame_rates = [23.976, 24.0, 25.0, 29.97, 30.0]
                offset_frames = {str(fps): offset_seconds * fps for fps in frame_rates}
                offset = SyncOffset(
                    offset_seconds=offset_seconds,
                    offset_milliseconds=offset_seconds * 1000.0,
                    offset_samples=int(offset_seconds * request.sample_rate),
                    offset_frames=offset_frames,
                    confidence=confidence,
                )
                method_result = MethodResult(
                    method=AnalysisMethod.CORRELATION,  # reuse enum; denote chunked in metadata
                    offset=offset,
                    processing_time=(datetime.utcnow() - start_time).total_seconds(),
                    quality_score=confidence,
                    metadata={
                        "chunked": True,
                        "chunks_analyzed": int(chunk_result.get('chunks_analyzed') or 0),
                        "chunks_reliable": int(chunk_result.get('chunks_reliable') or 0),
                        "similarity_score": float(chunk_result.get('similarity_score') or 0.0),
                    }
                )
                
                method_results = [method_result]
                consensus_offset = offset
                overall_confidence = confidence
                method_agreement = 1.0
                sync_status = chunk_result.get('sync_status') or "Analysis Complete"
                rec = chunk_result.get('recommendation') or []
                recommendations = rec if isinstance(rec, list) else [rec] if rec else []
                
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                return {
                    "consensus_offset": consensus_offset,
                    "method_results": method_results,
                    "ai_result": None,
                    "processing_time": processing_time,
                    "overall_confidence": overall_confidence,
                    "method_agreement": method_agreement,
                    "sync_status": sync_status,
                    "recommendations": recommendations,
                }

            # Perform analysis using core detector
            results = {}
            method_results = []
            
            # Build effective methods for execution (ensure AI added when enabled)
            effective_methods = list(request.methods)
            if request.enable_ai and (AnalysisMethod.AI not in effective_methods):
                effective_methods.append(AnalysisMethod.AI)

            for method in effective_methods:
                if method == AnalysisMethod.AI and request.enable_ai:
                    # AI-based analysis
                    if self.ai_detector:
                        ai_result = self._run_ai_analysis(request, analysis_id)
                        results["ai_result"] = ai_result
                        
                        # Convert AI result to MethodResult for consensus calculation
                        ai_method_result = self._convert_ai_to_method_result(ai_result, request)
                        method_results.append(ai_method_result)
                        results[method.value] = ai_method_result
                    else:
                        logger.warning("AI detector not available, skipping AI analysis")
                elif method != AnalysisMethod.AI:
                    # Traditional method analysis
                    # Update progress for traditional methods
                    if analysis_id in self.active_analyses:
                        self.active_analyses[analysis_id]["progress"] = 20.0 + (len(method_results) * 15.0)
                        self.active_analyses[analysis_id]["status_message"] = f"Running {method.value} analysis..."
                    
                    method_result = self._run_traditional_analysis(request, method)
                    method_results.append(method_result)
                    results[method.value] = method_result
            
            # Calculate consensus offset
            consensus_offset = self._calculate_consensus_offset(method_results)
            
            # Calculate overall metrics
            overall_confidence = self._calculate_overall_confidence(method_results)
            method_agreement = self._calculate_method_agreement(method_results)
            
            # Generate recommendations
            sync_status, recommendations = self._generate_recommendations(consensus_offset, overall_confidence)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "consensus_offset": consensus_offset,
                "method_results": method_results,
                "ai_result": results.get("ai_result"),
                "processing_time": processing_time,
                "overall_confidence": overall_confidence,
                "method_agreement": method_agreement,
                "sync_status": sync_status,
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Error in sync analysis: {e}")
            raise AnalysisError(f"Sync analysis failed: {e}")
    
    def _run_traditional_analysis(self, request: SyncAnalysisRequest, method: AnalysisMethod) -> MethodResult:
        """Run traditional analysis method."""
        method_start = datetime.utcnow()
        
        try:
            # Convert method to sync analyzer method
            method_map = {
                AnalysisMethod.MFCC: "mfcc",
                AnalysisMethod.ONSET: "onset",
                AnalysisMethod.SPECTRAL: "spectral",
                AnalysisMethod.CORRELATION: "correlation"
            }
            
            # Skip AI method in traditional analysis (it should be handled separately)
            if method == AnalysisMethod.AI:
                raise AnalysisError("AI method should not be processed as traditional analysis")
            
            sync_method = method_map.get(method, "mfcc")
            
            # Build a detector configured for this request (so sample_rate/window_size are honored)
            try:
                from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector
                detector = ProfessionalSyncDetector(
                    sample_rate=request.sample_rate,
                    window_size_seconds=request.window_size,
                    confidence_threshold=request.confidence_threshold,
                    use_gpu=(settings.USE_GPU and torch.cuda.is_available())
                )
            except Exception:
                # Fallback to the shared detector if import fails
                detector = self.core_detector

            # Run analysis with request-specific detector
            results_dict = detector.analyze_sync(
                Path(request.master_file),
                Path(request.dub_file),
                methods=[sync_method]
            )
            
            # Extract the specific method result
            result = results_dict.get(sync_method)
            if not result:
                raise AnalysisError(f"No result returned for method {sync_method}")
            
            # Extract offset information from SyncResult object
            offset_seconds = result.offset_seconds
            confidence = result.confidence
            
            # Calculate frame offsets for common frame rates
            frame_rates = [23.976, 24.0, 25.0, 29.97, 30.0]
            offset_frames = {str(fps): offset_seconds * fps for fps in frame_rates}

            offset = SyncOffset(
                offset_seconds=offset_seconds,
                offset_milliseconds=offset_seconds * 1000.0,
                offset_samples=int(offset_seconds * request.sample_rate),
                offset_frames=offset_frames,
                confidence=confidence
            )
            
            processing_time = (datetime.utcnow() - method_start).total_seconds()
            
            return MethodResult(
                method=method,
                offset=offset,
                processing_time=processing_time,
                quality_score=confidence,
                metadata={
                    "method": sync_method,
                    "sample_rate": request.sample_rate,
                    "window_size": request.window_size,
                    "confidence_threshold": request.confidence_threshold
                }
            )
            
        except Exception as e:
            logger.error(f"Error in {method.value} analysis: {e}")
            raise AnalysisError(f"{method.value} analysis failed: {e}")
    
    def _run_ai_analysis(self, request: SyncAnalysisRequest, analysis_id: str) -> AIAnalysisResult:
        """Run AI-based analysis."""
        
        ai_start = datetime.utcnow()
        
        try:
            # Load audio with request-specific sample rate (avoid default SR from shared detector)
            from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector
            loader = ProfessionalSyncDetector(
                sample_rate=request.sample_rate,
                window_size_seconds=request.window_size,
                confidence_threshold=request.confidence_threshold,
                use_gpu=(settings.USE_GPU)
            )
            master_audio, _ = loader.load_and_preprocess_audio(Path(request.master_file))
            dub_audio, _ = loader.load_and_preprocess_audio(Path(request.dub_file))
            
            # Determine requested AI model (default to wav2vec2)
            try:
                model_name = request.ai_model.value if request.ai_model else "wav2vec2"
            except Exception:
                model_name = "wav2vec2"

            # Build/choose detector for requested model
            try:
                import torch  # noqa: F401
                sys_gpu = bool(torch.cuda.is_available())
            except Exception:
                sys_gpu = False
            # Honor request-level GPU preference if provided
            prefer_gpu = getattr(request, 'prefer_gpu', None)
            if prefer_gpu is None:
                gpu_ok = bool(settings.USE_GPU and sys_gpu)
            else:
                gpu_ok = bool(prefer_gpu and sys_gpu)

            # Create a fresh detector for the requested model to honor selection
            from sync_analyzer.ai.embedding_sync_detector import AISyncDetector, EmbeddingConfig
            requested_ai = AISyncDetector(
                config=EmbeddingConfig(
                    model_name=model_name,
                    use_gpu=gpu_ok,
                    sample_rate=16000,
                )
            )

            # Inform front-end of the active AI model/device
            try:
                if analysis_id in self.active_analyses:
                    dev = 'GPU' if gpu_ok else 'CPU'
                    self.active_analyses[analysis_id]["status_message"] = f"AI: {model_name} on {dev}"
                    self._console_progress(analysis_id, 10.0, f"AI: {model_name} on {dev}")
            except Exception:
                pass

            # Create progress callback for AI analysis
            def ai_progress_callback(progress, message):
                if analysis_id in self.active_analyses:
                    self.active_analyses[analysis_id]["progress"] = max(10.0, min(95.0, 10.0 + (progress * 0.85)))
                    self.active_analyses[analysis_id]["status_message"] = message
                    # Update server console in-place instead of spamming lines
                    scaled = self.active_analyses[analysis_id]["progress"]
                    self._console_progress(analysis_id, float(scaled), message)
            
            # Run AI analysis
            ai_result = requested_ai.detect_sync(
                master_audio,
                dub_audio,
                # IMPORTANT: Use the ACTUAL audio sample rate, not the embedding rate
                # The AI detector will resample internally, but offset calculations
                # must be based on the audio sample rate we loaded
                sr=request.sample_rate,
                progress_callback=ai_progress_callback
            )
            
            processing_time = (datetime.utcnow() - ai_start).total_seconds()
            
            return AIAnalysisResult(
                model=request.ai_model,
                embedding_similarity=ai_result.embedding_similarity,
                temporal_consistency=ai_result.temporal_consistency,
                model_confidence=ai_result.confidence,
                processing_time=processing_time,
                model_metadata={
                    "model": model_name,
                    "sample_rate": request.sample_rate,
                    "offset_samples": ai_result.offset_samples,
                    "offset_seconds": ai_result.offset_seconds
                }
            )
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            raise AnalysisError(f"AI analysis failed: {e}")
    
    def _convert_ai_to_method_result(self, ai_result: AIAnalysisResult, request: SyncAnalysisRequest) -> MethodResult:
        """Convert AI analysis result to MethodResult for consensus calculation."""
        # For AI results, we need to extract offset information from the model_metadata
        offset_seconds = ai_result.model_metadata.get("offset_seconds", 0.0)
        offset_samples = ai_result.model_metadata.get("offset_samples", 0)
        
        # Calculate frame offsets for common frame rates
        frame_rates = [23.976, 24.0, 25.0, 29.97, 30.0]
        offset_frames = {str(fps): offset_seconds * fps for fps in frame_rates}

        offset = SyncOffset(
            offset_seconds=offset_seconds,
            offset_milliseconds=offset_seconds * 1000.0,
            offset_samples=offset_samples,
            offset_frames=offset_frames,
            confidence=ai_result.model_confidence
        )
        
        return MethodResult(
            method=AnalysisMethod.AI,
            offset=offset,
            processing_time=ai_result.processing_time,
            quality_score=ai_result.model_confidence,
            metadata={
                "model": ai_result.model.value,
                "embedding_similarity": ai_result.embedding_similarity,
                "temporal_consistency": ai_result.temporal_consistency,
                "ai_analysis": True
            }
        )
    
    def _calculate_consensus_offset(self, method_results: List[MethodResult]) -> SyncOffset:
        """Calculate consensus offset across all methods.

        IMPORTANT: Prioritizes CORRELATION method for sample-accurate results.
        AI has ±500ms precision (hop_size), so it's excluded from consensus.
        """
        if not method_results:
            raise AnalysisError("No method results available for consensus calculation")

        # Exclude AI from consensus unless it's the only available result
        non_ai_results = [r for r in method_results if r.method != AnalysisMethod.AI]
        if not non_ai_results:
            logger.warning("Only AI results available - using AI despite low precision")
            non_ai_results = method_results

        # Mirror ProfessionalSyncDetector consensus: prefer correlation, otherwise best confidence
        threshold = None
        for result in non_ai_results:
            threshold = result.metadata.get("confidence_threshold")
            if threshold is not None:
                break
        if threshold is None:
            threshold = 0.3

        high_confidence = [r for r in non_ai_results if r.offset.confidence >= threshold]
        if high_confidence:
            correlation = next((r for r in high_confidence if r.method == AnalysisMethod.CORRELATION), None)
            best_result = correlation or max(high_confidence, key=lambda r: r.offset.confidence)
        else:
            best_result = max(non_ai_results, key=lambda r: r.offset.confidence)

        logger.info(
            f"Consensus using {best_result.method.value} "
            f"({best_result.offset.confidence:.3f}): {best_result.offset.offset_seconds:.4f}s"
        )

        return SyncOffset(
            offset_seconds=best_result.offset.offset_seconds,
            offset_milliseconds=best_result.offset.offset_seconds * 1000.0,
            offset_samples=best_result.offset.offset_samples,
            offset_frames=best_result.offset.offset_frames,
            confidence=best_result.offset.confidence
        )
    
    def _calculate_overall_confidence(self, method_results: List[MethodResult]) -> float:
        """Calculate overall confidence score."""
        if not method_results:
            return 0.0
        
        # Average confidence across methods
        return sum(r.offset.confidence for r in method_results) / len(method_results)
    
    def _calculate_method_agreement(self, method_results: List[MethodResult]) -> float:
        """Calculate agreement between methods."""
        if len(method_results) < 2:
            return 1.0
        
        # Calculate standard deviation of offsets
        offsets = [r.offset.offset_seconds for r in method_results]
        mean_offset = sum(offsets) / len(offsets)
        variance = sum((o - mean_offset) ** 2 for o in offsets) / len(offsets)
        std_dev = variance ** 0.5
        
        # Convert to agreement score (lower std dev = higher agreement)
        # Normalize to 0-1 range, where 1 = perfect agreement
        max_expected_deviation = 5.0  # 5 seconds
        agreement = max(0.0, 1.0 - (std_dev / max_expected_deviation))
        
        return agreement
    
    def _generate_recommendations(self, offset: SyncOffset, confidence: float) -> Tuple[str, List[str]]:
        """Generate sync status and recommendations."""
        offset_abs = abs(offset.offset_seconds)
        
        # Determine sync status
        if offset_abs < 0.040:  # Less than 40ms
            status = "✅ EXCELLENT SYNC (< 40ms)"
        elif offset_abs < 0.100:  # Less than 100ms
            status = "⚠️ MINOR SYNC ISSUE (< 100ms)"
        else:
            status = "❌ SYNC CORRECTION NEEDED (> 100ms)"
        
        # Generate recommendations
        recommendations = []
        
        if offset.offset_seconds > 0:
            recommendations.append(f"Dub audio is {offset.offset_seconds:.3f} seconds ahead of master")
        elif offset.offset_seconds < 0:
            recommendations.append(f"Dub audio is {abs(offset.offset_seconds):.3f} seconds behind master")
        else:
            recommendations.append("Audio files are perfectly synchronized")
        
        # Confidence-based recommendations
        if confidence >= 0.9:
            recommendations.append(f"Very high confidence in detection ({confidence:.1%})")
        elif confidence >= 0.7:
            recommendations.append(f"High confidence in detection ({confidence:.1%})")
        elif confidence >= 0.5:
            recommendations.append(f"Moderate confidence in detection ({confidence:.1%})")
        else:
            recommendations.append(f"Low confidence in detection ({confidence:.1%}) - consider re-analysis")
        
        # Technical recommendations
        if offset_abs > 0.1:
            recommendations.append("Recommend audio correction using FFmpeg")
            recommendations.append("Consider using multiple analysis methods for validation")
        
        # Frame rate information
        if offset.offset_frames:
            recommendations.append("Frame offset equivalents provided for common frame rates")
        
        return status, recommendations
    
    def _create_cancelled_result(self, analysis_record: Dict[str, Any]) -> SyncAnalysisResult:
        """Create a cancelled analysis result."""
        request = analysis_record["request"]
        
        return SyncAnalysisResult(
            analysis_id=analysis_record["id"],
            master_file=request.master_file,
            dub_file=request.dub_file,
            status=AnalysisStatus.CANCELLED,
            consensus_offset=SyncOffset(
                offset_seconds=0.0,
                offset_milliseconds=0.0,
                offset_samples=0,
                offset_frames={},
                confidence=0.0
            ),
            method_results=[],
            ai_result=None,
            analysis_config=request,
            processing_time=0.0,
            created_at=analysis_record["created_at"],
            completed_at=analysis_record.get("cancelled_at"),
            overall_confidence=0.0,
            method_agreement=0.0,
            sync_status="ANALYSIS CANCELLED",
            recommendations=["Analysis was cancelled by user"]
        )
    
    def _create_failed_result(self, analysis_record: Dict[str, Any], error: str) -> SyncAnalysisResult:
        """Create a failed analysis result."""
        request = analysis_record["request"]
        
        return SyncAnalysisResult(
            analysis_id=analysis_record["id"],
            master_file=request.master_file,
            dub_file=request.dub_file,
            status=AnalysisStatus.FAILED,
            consensus_offset=SyncOffset(
                offset_seconds=0.0,
                offset_milliseconds=0.0,
                offset_samples=0,
                offset_frames={},
                confidence=0.0
            ),
            method_results=[],
            ai_result=None,
            analysis_config=request,
            processing_time=0.0,
            created_at=analysis_record["created_at"],
            completed_at=datetime.utcnow(),
            overall_confidence=0.0,
            method_agreement=0.0,
            sync_status="ANALYSIS FAILED",
            recommendations=[f"Analysis failed with error: {error}"]
        )
    
    async def cleanup(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)
        logger.info("SyncAnalyzerService cleaned up")

# Global service instance
sync_analyzer_service = SyncAnalyzerService()
