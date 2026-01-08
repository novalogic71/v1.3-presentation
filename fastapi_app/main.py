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
import socket
from contextlib import asynccontextmanager
from typing import Dict, Any
from pathlib import Path

# Add parent directory to Python path for sync_analyzer imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
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

def _local_ipv4_addresses() -> list[str]:
    """Best-effort discovery of local IPv4s for same-host UI CORS."""
    ips: set[str] = set()
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ips.add(sock.getsockname()[0])
        sock.close()
    except Exception:
        pass
    return [ip for ip in ips if ip and ":" not in ip]

def _extend_allowed_origins(origins: list[str]) -> list[str]:
    """Add same-host UI origins (ports 3000/3002) to the allow list."""
    allowed = list(origins or [])
    for ip in _local_ipv4_addresses():
        for port in (3000, 3002):
            origin = f"http://{ip}:{port}"
            if origin not in allowed:
                allowed.append(origin)
    return allowed

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
    # CORS: in DEBUG, open up for easier local/dev usage
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
        cors_origins = _extend_allowed_origins(settings.ALLOWED_ORIGINS)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    app.add_middleware(RequestLoggingMiddleware)
    
    if settings.ENABLE_RATE_LIMITING:
        app.add_middleware(RateLimitMiddleware)
    
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
    
    # Web UI directory path (relative to fastapi_app/)
    web_ui_dir = Path(__file__).parent.parent / "web_ui"
    
    # Mount web_ui static assets
    if web_ui_dir.exists():
        # Mount styles directory
        styles_dir = web_ui_dir / "styles"
        if styles_dir.exists():
            app.mount("/styles", StaticFiles(directory=str(styles_dir)), name="styles")
        
        # Mount images directory  
        images_dir = web_ui_dir / "images"
        if images_dir.exists():
            app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")
    
    # Serve main UI pages
    @app.get("/", response_class=HTMLResponse, tags=["ui"])
    @app.get("/splash", response_class=HTMLResponse, tags=["ui"])
    async def serve_splash():
        """Serve the splash/landing page."""
        splash_path = web_ui_dir / "splash.html"
        if splash_path.exists():
            return FileResponse(splash_path, media_type="text/html")
        # Fallback: redirect to app
        return HTMLResponse('<meta http-equiv="refresh" content="0; url=/app">')
    
    @app.get("/app", response_class=HTMLResponse, tags=["ui"])
    async def serve_app():
        """Serve the main application page."""
        app_path = web_ui_dir / "app.html"
        if app_path.exists():
            return FileResponse(app_path, media_type="text/html")
        raise HTTPException(status_code=404, detail="App UI not found")
    
    @app.get("/qc", response_class=HTMLResponse, tags=["ui"])
    @app.get("/qc-interface.html", response_class=HTMLResponse, tags=["ui"])
    async def serve_qc():
        """Serve the QC interface page."""
        qc_path = web_ui_dir / "qc-interface.html"
        if qc_path.exists():
            return FileResponse(qc_path, media_type="text/html")
        raise HTTPException(status_code=404, detail="QC interface not found")
    
    @app.get("/repair", response_class=HTMLResponse, tags=["ui"])
    @app.get("/repair-preview-interface.html", response_class=HTMLResponse, tags=["ui"])
    async def serve_repair():
        """Serve the repair preview interface page."""
        repair_path = web_ui_dir / "repair-preview-interface.html"
        if repair_path.exists():
            return FileResponse(repair_path, media_type="text/html")
        raise HTTPException(status_code=404, detail="Repair interface not found")
    
    # Health check endpoint (MUST be before wildcard route)
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint for monitoring."""
        return {
            "status": "healthy",
            "service": "Professional Audio Sync Analyzer API",
            "version": "2.0.0",
            "timestamp": "2025-08-27T19:00:00"
        }
    
    # API help endpoint (MUST be before wildcard route)
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
                        "POST /api/v1/analysis/componentized - Componentized analysis",
                        "POST /api/v1/analysis/componentized/async - Async componentized analysis"
                    ]
                },
                "files": {
                    "description": "File management operations",
                    "endpoints": [
                        "GET /api/v1/files - List files in directory",
                        "GET /api/v1/files/probe - Probe media file info"
                    ]
                },
                "jobs": {
                    "description": "Background job management",
                    "endpoints": [
                        "GET /api/v1/jobs - List all jobs",
                        "GET /api/v1/jobs/{job_id} - Get job status"
                    ]
                },
                "proxy": {
                    "description": "Audio proxy creation",
                    "endpoints": [
                        "POST /api/v1/proxy/prepare - Prepare audio proxy",
                        "GET /api/v1/proxy/{filename} - Serve proxy file"
                    ]
                }
            },
            "documentation": {
                "swagger_ui": "/docs",
                "redoc": "/redoc",
                "openapi_spec": "/openapi.json"
            }
        }
    
    # Serve JS/CSS files from web_ui root (MUST be last - catch-all route)
    @app.get("/{filename:path}", tags=["ui"])
    async def serve_web_ui_files(filename: str):
        """Serve static files from web_ui directory."""
        # Security: only serve certain file types
        allowed_extensions = {'.js', '.css', '.html', '.ico', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ttf'}
        ext = Path(filename).suffix.lower()
        
        if ext not in allowed_extensions:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = web_ui_dir / filename
        if file_path.exists() and file_path.is_file():
            # Determine content type
            content_types = {
                '.js': 'application/javascript',
                '.css': 'text/css',
                '.html': 'text/html',
                '.ico': 'image/x-icon',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.svg': 'image/svg+xml',
                '.woff': 'font/woff',
                '.woff2': 'font/woff2',
                '.ttf': 'font/ttf',
            }
            media_type = content_types.get(ext, 'application/octet-stream')
            return FileResponse(file_path, media_type=media_type)
        
        raise HTTPException(status_code=404, detail="File not found")
    
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
                "*.log",
            ],
        })
        logger.info("🔧 DEBUG mode enabled - hot reload active")
    else:
        # Production mode - no reload, optimized settings
        logger.info("🏭 Production mode - hot reload disabled")

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=debug_flag,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        workers=1 if debug_flag else 4,  # Multiple workers in production
        **reload_kwargs,
    )
