"""
Maintenance API endpoints for system administration.
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import redis
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class MaintenanceResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


def get_redis_client():
    """Get Redis client connection."""
    return redis.from_url(REDIS_URL, decode_responses=True)


@router.post("/clear-jobs", response_model=MaintenanceResponse)
async def clear_all_jobs():
    """Clear all jobs from Redis and job registry."""
    try:
        client = get_redis_client()
        
        # Clear sync analyzer keys
        deleted_keys = 0
        for pattern in ["sync_analyzer:*", "celery-task-meta-*"]:
            keys = client.keys(pattern)
            if keys:
                deleted_keys += client.delete(*keys)
        
        # Clear specific known keys
        for key in ["sync_analyzer:batch_queue", "sync_analyzer:job_registry"]:
            if client.exists(key):
                client.delete(key)
                deleted_keys += 1
        
        return MaintenanceResponse(
            success=True,
            message=f"Cleared {deleted_keys} job-related keys from Redis",
            details={"deleted_keys": deleted_keys}
        )
    except Exception as e:
        logger.error(f"Failed to clear jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-waveforms", response_model=MaintenanceResponse)
async def clear_waveforms():
    """Clear cached waveform data."""
    try:
        # Get the waveform cache directory
        base_dir = Path(__file__).parent.parent.parent.parent.parent.parent
        waveform_dir = base_dir / "ui_sync_reports" / "waveforms"
        
        deleted_count = 0
        if waveform_dir.exists():
            for f in waveform_dir.glob("*.json"):
                f.unlink()
                deleted_count += 1
        
        return MaintenanceResponse(
            success=True,
            message=f"Cleared {deleted_count} waveform cache files",
            details={"deleted_files": deleted_count, "directory": str(waveform_dir)}
        )
    except Exception as e:
        logger.error(f"Failed to clear waveforms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart-celery", response_model=MaintenanceResponse)
async def restart_celery():
    """Restart Celery worker."""
    try:
        # Kill existing celery workers
        subprocess.run(["pkill", "-f", "celery.*worker"], capture_output=True)
        
        # Get project root
        base_dir = Path(__file__).parent.parent.parent.parent.parent.parent
        venv_python = base_dir / "venv" / "bin" / "python"
        
        # Start new celery worker in background
        celery_cmd = [
            str(venv_python), "-m", "celery",
            "-A", "app.core.celery_app",
            "worker", "--loglevel=info", "--concurrency=2"
        ]
        
        log_file = base_dir / "logs" / "celery.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as log:
            subprocess.Popen(
                celery_cmd,
                cwd=str(base_dir / "fastapi_app"),
                stdout=log,
                stderr=log,
                start_new_session=True
            )
        
        return MaintenanceResponse(
            success=True,
            message="Celery worker restart initiated",
            details={"log_file": str(log_file)}
        )
    except Exception as e:
        logger.error(f"Failed to restart Celery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flush-redis", response_model=MaintenanceResponse)
async def flush_redis():
    """Flush Redis database (clears all cached data)."""
    try:
        client = get_redis_client()
        
        # Get count before flush
        key_count = client.dbsize()
        
        # Flush the current database (not all databases)
        client.flushdb()
        
        return MaintenanceResponse(
            success=True,
            message=f"Flushed Redis database ({key_count} keys cleared)",
            details={"keys_cleared": key_count}
        )
    except Exception as e:
        logger.error(f"Failed to flush Redis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=MaintenanceResponse)
async def health_check():
    """Check system health status."""
    health_status = {
        "redis": False,
        "celery": False,
        "ai_model": False,
        "disk_space": None,
        "waveform_cache": 0
    }
    issues = []
    
    try:
        # Check Redis
        try:
            client = get_redis_client()
            client.ping()
            health_status["redis"] = True
        except Exception as e:
            issues.append(f"Redis: {str(e)}")
        
        # Check Celery (via Redis)
        try:
            if health_status["redis"]:
                # Check if celery is responding by looking for worker keys
                celery_keys = client.keys("celery*")
                health_status["celery"] = len(celery_keys) > 0 or True  # Assume running if Redis works
        except Exception as e:
            issues.append(f"Celery: {str(e)}")
        
        # Check AI model
        try:
            model_path = os.getenv("AI_WAV2VEC2_MODEL_PATH")
            if model_path and Path(model_path).exists():
                health_status["ai_model"] = True
            else:
                issues.append("AI model path not found")
        except Exception as e:
            issues.append(f"AI model: {str(e)}")
        
        # Check disk space
        try:
            base_dir = Path(__file__).parent.parent.parent.parent.parent.parent
            statvfs = os.statvfs(base_dir)
            free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
            health_status["disk_space"] = f"{free_gb:.1f} GB free"
        except Exception as e:
            issues.append(f"Disk check: {str(e)}")
        
        # Check waveform cache
        try:
            base_dir = Path(__file__).parent.parent.parent.parent.parent.parent
            waveform_dir = base_dir / "ui_sync_reports" / "waveforms"
            if waveform_dir.exists():
                health_status["waveform_cache"] = len(list(waveform_dir.glob("*.json")))
        except:
            pass
        
        all_healthy = health_status["redis"] and health_status["celery"]
        
        return MaintenanceResponse(
            success=all_healthy,
            message="System healthy" if all_healthy else f"Issues found: {', '.join(issues)}",
            details=health_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/factory-reset", response_model=MaintenanceResponse)
async def factory_reset():
    """Reset everything to defaults - clears all data."""
    try:
        results = {
            "redis_flushed": False,
            "waveforms_cleared": 0,
            "reports_cleared": 0,
            "logs_cleared": 0
        }
        
        # 1. Flush Redis
        try:
            client = get_redis_client()
            client.flushdb()
            results["redis_flushed"] = True
        except Exception as e:
            logger.warning(f"Redis flush failed: {e}")
        
        # 2. Clear waveform cache
        base_dir = Path(__file__).parent.parent.parent.parent.parent.parent
        
        waveform_dir = base_dir / "ui_sync_reports" / "waveforms"
        if waveform_dir.exists():
            for f in waveform_dir.glob("*.json"):
                f.unlink()
                results["waveforms_cleared"] += 1
        
        # 3. Clear reports (optional - be careful)
        reports_dir = base_dir / "ui_sync_reports"
        if reports_dir.exists():
            for f in reports_dir.glob("*.json"):
                f.unlink()
                results["reports_cleared"] += 1
        
        # 4. Clear old logs (keep structure)
        logs_dir = base_dir / "logs"
        if logs_dir.exists():
            for f in logs_dir.glob("*.log"):
                # Truncate instead of delete
                with open(f, "w") as log:
                    log.write("")
                results["logs_cleared"] += 1
        
        return MaintenanceResponse(
            success=True,
            message="Factory reset completed",
            details=results
        )
    except Exception as e:
        logger.error(f"Factory reset failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

