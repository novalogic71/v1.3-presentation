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
        A comprehensive RESTful API for professional audio synchronization analysis.

        ### Highlights
        - Multi-method detection (MFCC, onset, spectral, correlation) and optional AI.
        - Sub-frame accuracy with millisecond offsets, production-ready reporting.
        - File browse/proxy helpers to enable browser playback during dev.

        ### Using Swagger (local/dev)
        - When `DEBUG=true`, this docs page uses a relative server so Try it out hits the current host.
        - CORS is open in DEBUG for easier testing (no credentials).
        - If you see CORS errors, ensure the Servers dropdown points to this host/port.

        ### Quick Start
        1) Browse files: `GET /api/v1/files/?path=/mnt/data`
        2) Probe media: `GET /api/v1/files/probe?path=/abs/video_or_audio`
        3) Stream proxy audio: `GET /api/v1/files/proxy-audio?path=/abs/media&format=wav`
        4) Analyze sync: `POST /api/v1/analysis/sync` with master/dub paths
        """,
        version="2.0.0",
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
                "description": "Core sync analysis operations. Upload files and analyze sync offsets.",
                "externalDocs": {
                    "description": "Analysis Documentation",
                    "url": "https://docs.sync-analyzer.com/analysis",
                },
            },
            {
                "name": "files",
                "description": "File management and playback helpers (browse, probe, raw/proxy streaming).",
                "externalDocs": {
                    "description": "File ops & troubleshooting",
                    "url": "https://ffmpeg.org/ffprobe.html",
                }
            },
            {
                "name": "reports",
                "description": "Report generation and retrieval. Get detailed sync analysis reports.",
            },
            {
                "name": "ai",
                "description": "AI-powered sync detection using deep learning embeddings.",
            },
            {
                "name": "health",
                "description": "Health checks and system status monitoring.",
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
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "timestamp": "2025-08-27T19:00:00",
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
        return {
            "status": "healthy",
            "service": "Professional Audio Sync Analyzer API",
            "version": "2.0.0",
            "timestamp": "2025-08-27T19:00:00"
        }
    
    # API help endpoint
    @app.get("/api/help", tags=["health"])
    async def api_help():
        """Get API usage information and examples."""
        return {
            "message": "Professional Audio Sync Analyzer API Help",
            "version": "2.0.0",
            "endpoints": {
                "analysis": {
                    "description": "Core sync analysis operations",
                    "endpoints": [
                        "POST /api/v1/analysis/sync - Analyze sync between master and dub files",
                        "POST /api/v1/analysis/batch - Batch sync analysis",
                        "GET /api/v1/analysis/{analysis_id} - Get analysis results",
                        "DELETE /api/v1/analysis/{analysis_id} - Delete analysis"
                    ]
                },
                "files": {
                    "description": "File management operations",
                    "endpoints": [
                        "GET /api/v1/files - List files in directory",
                        "POST /api/v1/files/upload - Upload audio/video files",
                        "GET /api/v1/files/{file_id} - Get file information",
                        "DELETE /api/v1/files/{file_id} - Delete file"
                    ]
                },
                "reports": {
                    "description": "Report generation and retrieval",
                    "endpoints": [
                        "GET /api/v1/reports/{analysis_id} - Get analysis report",
                        "POST /api/v1/reports/{analysis_id}/export - Export report",
                        "GET /api/v1/reports - List all reports"
                    ]
                },
                "ai": {
                    "description": "AI-powered sync detection",
                    "endpoints": [
                        "POST /api/v1/ai/embedding - Extract audio embeddings",
                        "POST /api/v1/ai/sync - AI-based sync detection",
                        "GET /api/v1/ai/models - List available AI models"
                    ]
                }
            },
            "curl_examples": {
                "basic_sync_analysis": "curl -X POST 'http://localhost:8000/api/v1/analysis/sync' \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"master_file\": \"/path/to/master.wav\", \"dub_file\": \"/path/to/dub.wav\"}'",
                "file_upload": "curl -X POST 'http://localhost:8000/api/v1/files/upload' \\\n  -F 'file=@/path/to/audio.wav' \\\n  -F 'file_type=audio'",
                "get_analysis": "curl -X GET 'http://localhost:8000/api/v1/analysis/{analysis_id}'"
            },
            "documentation": {
                "swagger_ui": "/docs",
                "redoc": "/redoc",
                "openapi_spec": "/openapi.json"
            },
            "curl_examples_extra": {
                "file_probe": "curl 'http://localhost:8000/api/v1/files/probe?path=/abs/media.mov' | jq",
                "audio_proxy_wav": "curl -L 'http://localhost:8000/api/v1/files/proxy-audio?path=/abs/media.mov&format=wav' --output preview.wav"
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
