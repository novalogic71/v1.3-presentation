#!/usr/bin/env python3
"""
Professional Audio Sync Analyzer - FastAPI Application
=====================================================

A production-ready FastAPI application that provides RESTful API access to the
Professional Audio Sync Analyzer system with comprehensive documentation,
validation, and error handling.

Author: AI Audio Engineer
Version: 2.0.0
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from pathlib import Path

# Add parent directory to Python path for sync_analyzer imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.core.exceptions import SyncAnalyzerException
from app.core.middleware import RequestLoggingMiddleware, RateLimitMiddleware

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("🚀 Starting Professional Audio Sync Analyzer API...")
    logger.info(f"📁 Mount path: {settings.MOUNT_PATH}")
    logger.info(f"🔧 Analysis methods: {settings.ENABLED_METHODS}")
    logger.info(f"🤖 AI models: {settings.ENABLED_AI_MODELS}")
    
    # Verify FFmpeg availability
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("✅ FFmpeg is available")
        else:
            logger.warning("⚠️ FFmpeg may not be working correctly")
    except Exception as e:
        logger.error(f"❌ FFmpeg not available: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Professional Audio Sync Analyzer API...")

def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Use a relative server in DEBUG to avoid cross-origin issues in Swagger
    debug_servers = [{"url": ""}]
    app = FastAPI(
        title="Professional Audio Sync Analyzer API",
        description="""
## 🎬 Professional Audio Sync Analyzer API v1.3.0

A comprehensive RESTful API for professional audio synchronization analysis, repair, and packaging.

### ✨ Key Features
- **Multi-method detection**: MFCC, onset, spectral, correlation, and AI (Wav2Vec2, YAMNet)
- **Sub-frame accuracy**: Millisecond-level offset detection with confidence scoring
- **End-to-end workflows**: Analyze → Repair → Package in a single API call
- **Real-time progress**: Server-Sent Events (SSE) for live progress updates
- **Batch processing**: CSV upload for processing multiple file pairs
- **Per-channel repair**: Individual offset correction for multichannel/multi-mono audio
- **Proxy streaming**: Transcode Atmos/E-AC-3 to browser-friendly formats

### 🚀 Quick Start
1. **Browse files**: `GET /api/v1/files/?path=/mnt/data`
2. **Probe media**: `GET /api/v1/files/probe?path=/path/to/file`
3. **Analyze sync**: `POST /api/v1/analysis/sync` with master/dub paths
4. **Monitor progress**: `GET /api/v1/analysis/{id}/progress/stream` (SSE)
5. **Complete workflow**: `POST /api/v1/workflows/analyze-and-repair`

### 📡 Using Swagger
- In `DEBUG=true` mode, this docs page uses relative URLs for Try-it-out
- CORS is open in DEBUG for easier local testing
- Use the **Servers** dropdown to select your deployment
        """,
        version="1.3.0",
        contact={
            "name": "AI Audio Engineer",
            "email": "support@sync-analyzer.com",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        servers=(debug_servers if os.environ.get("DEBUG", str(settings.DEBUG)).lower() in {"1", "true", "yes"}
                 else [
                    {"url": "http://localhost:8000", "description": "Development server"},
                    {"url": "https://api.sync-analyzer.com", "description": "Production server"},
                 ]),
        tags_metadata=[
            {
                "name": "analysis",
                "description": "Core sync analysis operations. Start analysis, monitor progress via SSE, get timeline data.",
                "externalDocs": {
                    "description": "Analysis Documentation",
                    "url": "https://docs.sync-analyzer.com/analysis",
                },
            },
            {
                "name": "batch",
                "description": "Batch processing via CSV upload. Upload CSV files and process multiple file pairs in parallel.",
            },
            {
                "name": "workflows",
                "description": "Complete end-to-end workflows. Analyze-and-repair combines analysis, repair, and packaging.",
            },
            {
                "name": "repair",
                "description": "Audio repair operations. Apply per-channel offsets to multichannel/multi-mono files.",
            },
            {
                "name": "files",
                "description": "File management and playback helpers. Browse, probe, upload, and proxy-stream audio/video.",
                "externalDocs": {
                    "description": "FFprobe Documentation",
                    "url": "https://ffmpeg.org/ffprobe.html",
                }
            },
            {
                "name": "reports",
                "description": "Report generation and retrieval. Get formatted reports, search by file pair.",
            },
            {
                "name": "ai",
                "description": "AI-powered sync detection using Wav2Vec2, YAMNet, and spectral embeddings.",
            },
            {
                "name": "health",
                "description": "Health checks and system status. Monitor FFmpeg, AI models, filesystem, and system resources.",
            },
            {
                "name": "ui-state",
                "description": "UI state persistence. Save and restore batch queue state across browser sessions.",
            },
        ],
    )
    
    # Add middleware
    # IMPORTANT: Middleware executes in REVERSE order of how it's added
    # Add CORS LAST so it executes FIRST to handle OPTIONS preflight requests

    # Rate limiting (if enabled)
    if settings.ENABLE_RATE_LIMITING:
        app.add_middleware(RateLimitMiddleware)

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Trusted host validation
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # CORS - added LAST to execute FIRST
    # In DEBUG mode, open up for easier local/dev usage
    debug_flag = os.environ.get("DEBUG", str(settings.DEBUG)).lower() in {"1", "true", "yes"}
    if debug_flag:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Add exception handlers
    @app.exception_handler(SyncAnalyzerException)
    async def sync_analyzer_exception_handler(request: Request, exc: SyncAnalyzerException):
        """Handle custom sync analyzer exceptions."""
        logger.error(f"SyncAnalyzerException: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_code": exc.error_code,
                "timestamp": exc.timestamp.isoformat(),
                "path": str(request.url),
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        from datetime import datetime
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url),
            }
        )
    
    # Include API router
    app.include_router(api_router, prefix="/api/v1")
    
    # Mount static files
    if os.path.exists("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint for monitoring."""
        from datetime import datetime
        return {
            "status": "healthy",
            "service": "Professional Audio Sync Analyzer API",
            "version": "1.3.0",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # API help endpoint
    @app.get("/api/help", tags=["health"])
    async def api_help():
        """Get API usage information and examples."""
        return {
            "message": "Professional Audio Sync Analyzer API Help",
            "version": "1.3.0",
            "endpoints": {
                "analysis": {
                    "description": "Core sync analysis operations",
                    "endpoints": [
                        "POST /api/v1/analysis/sync - Start sync analysis",
                        "GET /api/v1/analysis/{analysis_id} - Get analysis status/results",
                        "GET /api/v1/analysis/{analysis_id}/progress/stream - SSE progress stream",
                        "GET /api/v1/analysis/sync/{analysis_id}/timeline - Get timeline data",
                        "DELETE /api/v1/analysis/{analysis_id} - Cancel analysis",
                        "GET /api/v1/analysis/ - List all analyses"
                    ]
                },
                "batch": {
                    "description": "Batch processing via CSV upload",
                    "endpoints": [
                        "POST /api/v1/analysis/batch/upload-csv - Upload batch CSV",
                        "POST /api/v1/analysis/batch/{batch_id}/start - Start batch processing",
                        "GET /api/v1/analysis/batch/{batch_id}/status - Get batch status",
                        "GET /api/v1/analysis/batch/{batch_id}/results - Get batch results",
                        "DELETE /api/v1/analysis/batch/{batch_id} - Cancel batch"
                    ]
                },
                "workflows": {
                    "description": "Complete end-to-end workflows",
                    "endpoints": [
                        "POST /api/v1/workflows/analyze-and-repair - Start complete workflow",
                        "GET /api/v1/workflows/analyze-and-repair/{workflow_id}/status - Get workflow status",
                        "GET /api/v1/workflows/analyze-and-repair/{workflow_id}/download/{file_type} - Download outputs",
                        "GET /api/v1/workflows/analyze-and-repair/workflows - List all workflows",
                        "DELETE /api/v1/workflows/analyze-and-repair/{workflow_id} - Cleanup workflow"
                    ]
                },
                "repair": {
                    "description": "Audio repair operations",
                    "endpoints": [
                        "POST /api/v1/repair/repair/per-channel - Apply per-channel offsets"
                    ]
                },
                "files": {
                    "description": "File management and streaming",
                    "endpoints": [
                        "GET /api/v1/files/ - List files in directory",
                        "POST /api/v1/files/upload - Upload audio/video files",
                        "GET /api/v1/files/probe - FFprobe file analysis",
                        "GET /api/v1/files/proxy-audio - Transcode to browser-friendly audio",
                        "GET /api/v1/files/raw - Get raw file",
                        "GET /api/v1/files/{file_id} - Get file information",
                        "DELETE /api/v1/files/{file_id} - Delete file"
                    ]
                },
                "reports": {
                    "description": "Report generation and retrieval",
                    "endpoints": [
                        "GET /api/v1/reports/{analysis_id} - Get analysis report",
                        "GET /api/v1/reports/{analysis_id}/formatted - Get formatted HTML/Markdown report",
                        "GET /api/v1/reports/search - Search reports by file pair",
                        "GET /api/v1/reports/ - List all reports"
                    ]
                },
                "ai": {
                    "description": "AI model information",
                    "endpoints": [
                        "GET /api/v1/ai/models - List available AI models",
                        "GET /api/v1/ai/models/{model_name} - Get model details"
                    ]
                },
                "health": {
                    "description": "System health monitoring",
                    "endpoints": [
                        "GET /api/v1/health/status - Comprehensive health status",
                        "GET /api/v1/health/ffmpeg - FFmpeg availability",
                        "GET /api/v1/health/ai-models - AI models status",
                        "GET /api/v1/health/filesystem - File system health",
                        "GET /api/v1/health/system - System resources"
                    ]
                },
                "ui_state": {
                    "description": "UI state persistence",
                    "endpoints": [
                        "GET /api/v1/ui/state/batch-queue - Get batch queue state",
                        "POST /api/v1/ui/state/batch-queue - Save batch queue state",
                        "DELETE /api/v1/ui/state/batch-queue - Clear batch queue"
                    ]
                }
            },
            "curl_examples": {
                "basic_sync_analysis": "curl -X POST 'http://localhost:8000/api/v1/analysis/sync' -H 'Content-Type: application/json' -d '{\"master_file\": \"/path/to/master.wav\", \"dub_file\": \"/path/to/dub.wav\"}'",
                "monitor_progress_sse": "curl -N 'http://localhost:8000/api/v1/analysis/{analysis_id}/progress/stream'",
                "analyze_and_repair": "curl -X POST 'http://localhost:8000/api/v1/workflows/analyze-and-repair' -H 'Content-Type: application/json' -d '{\"master_file\": \"/path/to/master.mov\", \"dub_file\": \"/path/to/dub.mov\", \"auto_repair\": true}'",
                "file_probe": "curl 'http://localhost:8000/api/v1/files/probe?path=/path/to/media.mov'",
                "proxy_audio": "curl 'http://localhost:8000/api/v1/files/proxy-audio?path=/path/to/media.mov&format=wav' --output preview.wav",
                "per_channel_repair": "curl -X POST 'http://localhost:8000/api/v1/repair/repair/per-channel' -H 'Content-Type: application/json' -d '{\"file_path\": \"/path/to/dub.mov\", \"per_channel_results\": {\"FL\": {\"offset_seconds\": -0.023}}}'"
            },
            "documentation": {
                "swagger_ui": "/docs",
                "redoc": "/redoc",
                "openapi_spec": "/openapi.json",
                "api_workflow": "See API_WORKFLOW.md",
                "curl_examples": "See CURL_EXAMPLES.md"
            }
        }
    
    return app

# Create the application instance
app = create_application()

if __name__ == "__main__":
    debug_flag = os.environ.get("DEBUG", str(settings.DEBUG)).lower() in {"1", "true", "yes"}
    reload_kwargs: Dict[str, Any] = {}
    if debug_flag:
        # Restrict reload watcher to code dirs and exclude volatile dirs
        app_dir = str(Path(__file__).parent)
        reload_kwargs.update({
            "reload_dirs": [app_dir],
            "reload_includes": ["*.py"],
            "reload_excludes": [
                "logs/*",
                "uploads/*",
                "reports/*",
                "ai_models/*",
                "static/*",
            ],
        })

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=debug_flag,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        **reload_kwargs,
    )
