#!/usr/bin/env python3
"""
Health endpoints for system monitoring and status.
"""

import logging
import subprocess
import psutil
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.sync_models import HealthStatus, ComponentHealth

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status", response_model=HealthStatus)
async def get_health_status():
    """
    Get comprehensive system health status.
    
    This endpoint provides detailed information about the health of all system
    components, including FFmpeg, AI models, and file system.
    
    ## Example Response
    
    ```json
    {
      "status": "healthy",
      "service": "Professional Audio Sync Analyzer API",
      "version": "2.0.0",
      "timestamp": "2025-08-27T19:00:00Z",
      "components": {
        "ffmpeg": {
          "status": "healthy",
          "version": "5.1.6",
          "last_check": "2025-08-27T19:00:00Z"
        },
        "ai_models": {
          "status": "healthy",
          "loaded_models": 3,
          "last_check": "2025-08-27T19:00:00Z"
        },
        "file_system": {
          "status": "healthy",
          "mount_path": "/mnt/data",
          "last_check": "2025-08-27T19:00:00Z"
        },
        "system_resources": {
          "status": "healthy",
          "cpu_usage": 15.2,
          "memory_usage": 45.8,
          "disk_usage": 23.1,
          "last_check": "2025-08-27T19:00:00Z"
        }
      }
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/health/status"
    ```
    """
    try:
        components = {}
        overall_status = "healthy"
        
        # Check FFmpeg
        ffmpeg_health = await _check_ffmpeg_health()
        components["ffmpeg"] = ffmpeg_health
        if ffmpeg_health["status"] != "healthy":
            overall_status = "degraded"
        
        # Check AI models
        ai_models_health = await _check_ai_models_health()
        components["ai_models"] = ai_models_health
        if ai_models_health["status"] != "healthy":
            overall_status = "degraded"
        
        # Check file system
        filesystem_health = await _check_filesystem_health()
        components["filesystem"] = filesystem_health
        if filesystem_health["status"] != "healthy":
            overall_status = "degraded"
        
        # Check system resources
        system_health = await _check_system_health()
        components["system_resources"] = system_health
        if system_health["status"] != "healthy":
            overall_status = "degraded"
        
        return HealthStatus(
            status=overall_status,
            service=settings.APP_NAME,
            version=settings.VERSION,
            build_id=settings.BUILD_ID,
            timestamp=datetime.utcnow(),
            components=components
        )
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ffmpeg", response_model=ComponentHealth)
async def get_ffmpeg_health():
    """
    Get FFmpeg health status.
    
    ## Example Response
    
    ```json
    {
      "status": "healthy",
      "message": "FFmpeg is working correctly",
      "details": {
        "version": "5.1.6",
        "codecs": ["h264", "aac", "mp3"],
        "formats": ["mp4", "avi", "wav"]
      },
      "last_check": "2025-08-27T19:00:00Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/health/ffmpeg"
    ```
    """
    try:
        return await _check_ffmpeg_health()
    except Exception as e:
        logger.error(f"Error getting FFmpeg health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ai-models", response_model=ComponentHealth)
async def get_ai_models_health():
    """
    Get AI models health status.
    
    ## Example Response
    
    {
      "status": "healthy",
      "message": "All AI models are available",
      "details": {
        "loaded_models": 3,
        "available_models": ["wav2vec2", "yamnet", "spectral"],
        "gpu_available": true
      },
      "last_check": "2025-08-27T19:00:00Z"
    }
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/health/ai-models"
    ```
    """
    try:
        return await _check_ai_models_health()
    except Exception as e:
        logger.error(f"Error getting AI models health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filesystem", response_model=ComponentHealth)
async def get_filesystem_health():
    """
    Get file system health status.
    
    ## Example Response
    
    ```json
    {
      "status": "healthy",
      "message": "File system is accessible",
      "details": {
        "mount_path": "/mnt/data",
        "free_space_gb": 45.2,
        "total_space_gb": 1000.0,
        "permissions": "rw"
      },
      "last_check": "2025-08-27T19:00:00Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/health/filesystem"
    ```
    """
    try:
        return await _check_filesystem_health()
    except Exception as e:
        logger.error(f"Error getting filesystem health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system", response_model=ComponentHealth)
async def get_system_health():
    """
    Get system resources health status.
    
    ## Example Response
    
    ```json
    {
      "status": "healthy",
      "message": "System resources are within normal limits",
      "details": {
        "cpu_usage_percent": 15.2,
        "memory_usage_percent": 45.8,
        "disk_usage_percent": 23.1,
        "load_average": [0.5, 0.8, 1.2]
      },
      "last_check": "2025-08-27T19:00:00Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/health/system"
    ```
    """
    try:
        return await _check_system_health()
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def _check_ffmpeg_health() -> ComponentHealth:
    """Check FFmpeg health status."""
    try:
        # Check FFmpeg version
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Extract version from output
            version_line = result.stdout.split('\n')[0]
            version = version_line.split(' ')[2] if ' ' in version_line else "unknown"
            
            return ComponentHealth(
                status="healthy",
                message="FFmpeg is working correctly",
                details={
                    "version": version,
                    "codecs": ["h264", "aac", "mp3", "flac", "wav"],
                    "formats": ["mp4", "avi", "wav", "mp3", "flac"]
                },
                last_check=datetime.utcnow()
            )
        else:
            return ComponentHealth(
                status="unhealthy",
                message="FFmpeg command failed",
                details={"error": result.stderr},
                last_check=datetime.utcnow()
            )
            
    except subprocess.TimeoutExpired:
        return ComponentHealth(
            status="unhealthy",
            message="FFmpeg command timed out",
            details={"error": "Command execution timeout"},
            last_check=datetime.utcnow()
        )
    except FileNotFoundError:
        return ComponentHealth(
            status="unhealthy",
            message="FFmpeg not found in PATH",
            details={"error": "FFmpeg executable not found"},
            last_check=datetime.utcnow()
        )
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"FFmpeg health check failed: {e}",
            details={"error": str(e)},
            last_check=datetime.utcnow()
        )

async def _check_ai_models_health() -> ComponentHealth:
    """Check AI models health status."""
    try:
        from app.core.config import get_ai_models
        
        ai_models = get_ai_models()
        available_models = list(ai_models.keys())
        
        # Check GPU availability
        gpu_available = False
        try:
            import torch
            gpu_available = torch.cuda.is_available()
        except ImportError:
            pass
        
        return ComponentHealth(
            status="healthy",
            message="AI models are available",
            details={
                "available_models": available_models,
                "total_models": len(available_models),
                "gpu_available": gpu_available,
                "models": ai_models
            },
            last_check=datetime.utcnow()
        )
        
    except Exception as e:
        return ComponentHealth(
            status="degraded",
            message=f"AI models health check failed: {e}",
            details={"error": str(e)},
            last_check=datetime.utcnow()
        )

async def _check_filesystem_health() -> ComponentHealth:
    """Check file system health status."""
    try:
        import os
        from pathlib import Path
        
        mount_path = Path(settings.MOUNT_PATH)
        
        if not mount_path.exists():
            return ComponentHealth(
                status="unhealthy",
                message="Mount path does not exist",
                details={"mount_path": str(mount_path)},
                last_check=datetime.utcnow()
            )
        
        if not mount_path.is_dir():
            return ComponentHealth(
                status="unhealthy",
                message="Mount path is not a directory",
                details={"mount_path": str(mount_path)},
                last_check=datetime.utcnow()
            )
        
        # Check disk usage
        try:
            stat = os.statvfs(mount_path)
            total_space = stat.f_blocks * stat.f_frsize
            free_space = stat.f_bavail * stat.f_frsize
            used_space = total_space - free_space
            
            disk_usage_percent = (used_space / total_space) * 100 if total_space > 0 else 0
            
            # Check permissions
            permissions = "rw" if os.access(mount_path, os.R_OK | os.W_OK) else "r"
            
            return ComponentHealth(
                status="healthy",
                message="File system is accessible",
                details={
                    "mount_path": str(mount_path),
                    "free_space_gb": round(free_space / (1024**3), 2),
                    "total_space_gb": round(total_space / (1024**3), 2),
                    "used_space_gb": round(used_space / (1024**3), 2),
                    "disk_usage_percent": round(disk_usage_percent, 1),
                    "permissions": permissions
                },
                last_check=datetime.utcnow()
            )
            
        except OSError as e:
            return ComponentHealth(
                status="degraded",
                message="Could not get disk usage information",
                details={"error": str(e), "mount_path": str(mount_path)},
                last_check=datetime.utcnow()
            )
            
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"File system health check failed: {e}",
            details={"error": str(e)},
            last_check=datetime.utcnow()
        )

async def _check_system_health() -> ComponentHealth:
    """Check system resources health status."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # Load average
        load_avg = psutil.getloadavg()
        
        # Determine status based on thresholds
        status = "healthy"
        message = "System resources are within normal limits"
        
        if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
            status = "unhealthy"
            message = "System resources are critically high"
        elif cpu_percent > 80 or memory_percent > 80 or disk_percent > 80:
            status = "degraded"
            message = "System resources are elevated"
        
        return ComponentHealth(
            status=status,
            message=message,
            details={
                "cpu_usage_percent": round(cpu_percent, 1),
                "memory_usage_percent": round(memory_percent, 1),
                "disk_usage_percent": round(disk_percent, 1),
                "load_average": [round(load, 2) for load in load_avg],
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2)
            },
            last_check=datetime.utcnow()
        )
        
    except Exception as e:
        return ComponentHealth(
            status="unhealthy",
            message=f"System health check failed: {e}",
            details={"error": str(e)},
            last_check=datetime.utcnow()
        )
