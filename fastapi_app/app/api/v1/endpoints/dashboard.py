"""
System Dashboard API Endpoints

Provides real-time system monitoring data including:
- GPU status and utilization
- CPU and memory usage
- Celery worker status
- Redis queue stats
- Process information
"""

import os
import subprocess
import psutil
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


def get_gpu_processes() -> List[Dict[str, Any]]:
    """Get processes running on GPU."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,name,used_memory",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        processes = []
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if line and '[Not Found]' not in line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        processes.append({
                            "pid": int(parts[0]) if parts[0].isdigit() else 0,
                            "name": parts[1] if len(parts) > 1 else "unknown",
                            "memory_mb": float(parts[2]) if len(parts) > 2 and parts[2].replace('.', '').isdigit() else 0,
                        })
        return processes
    except Exception:
        return []


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU information using nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return {"available": False, "error": "nvidia-smi failed"}
        
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 8:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_total_mb": float(parts[2]),
                        "memory_used_mb": float(parts[3]),
                        "memory_free_mb": float(parts[4]),
                        "memory_percent": round(float(parts[3]) / float(parts[2]) * 100, 1) if float(parts[2]) > 0 else 0,
                        "utilization_percent": float(parts[5]) if parts[5] != '[N/A]' else 0,
                        "temperature_c": float(parts[6]) if parts[6] != '[N/A]' else 0,
                        "power_draw_w": float(parts[7]) if parts[7] != '[N/A]' else 0,
                    })
        
        # Get GPU processes
        gpu_processes = get_gpu_processes()
        
        return {
            "available": True,
            "gpu_count": len(gpus),
            "gpus": gpus,
            "processes": gpu_processes,
            "process_count": len(gpu_processes),
        }
    except FileNotFoundError:
        return {"available": False, "error": "nvidia-smi not found", "processes": [], "process_count": 0}
    except Exception as e:
        return {"available": False, "error": str(e), "processes": [], "process_count": 0}


def get_system_info() -> Dict[str, Any]:
    """Get system CPU, memory, and disk info."""
    try:
        # CPU info
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Memory info
        memory = psutil.virtual_memory()
        
        # Disk info
        disk = psutil.disk_usage('/')
        
        # Load average (Unix only)
        try:
            load_avg = os.getloadavg()
        except (OSError, AttributeError):
            load_avg = (0, 0, 0)
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "frequency_mhz": cpu_freq.current if cpu_freq else 0,
                "load_avg_1m": round(load_avg[0], 2),
                "load_avg_5m": round(load_avg[1], 2),
                "load_avg_15m": round(load_avg[2], 2),
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": round(disk.percent, 1),
            }
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {"error": str(e)}


def get_celery_info() -> Dict[str, Any]:
    """Get Celery worker status."""
    try:
        from fastapi_app.app.core.celery_app import celery_app
        
        # Get registered workers
        inspect = celery_app.control.inspect()
        
        # Get active tasks
        active = inspect.active() or {}
        
        # Get reserved tasks (queued on workers)
        reserved = inspect.reserved() or {}
        
        # Get worker stats
        stats = inspect.stats() or {}
        
        workers = []
        for worker_name, worker_stats in stats.items():
            worker_active = active.get(worker_name, [])
            worker_reserved = reserved.get(worker_name, [])
            
            workers.append({
                "name": worker_name,
                "status": "online",
                "active_tasks": len(worker_active),
                "reserved_tasks": len(worker_reserved),
                "processed": worker_stats.get('total', {}).get('analysis.componentized', 0),
                "pool": worker_stats.get('pool', {}).get('max-concurrency', 0),
                "pid": worker_stats.get('pid', 0),
            })

        # Fallback: if stats are empty, try a lightweight ping so the dashboard can still show "online"
        if not workers:
            try:
                ping_results = celery_app.control.ping(timeout=1) or []
            except Exception:
                ping_results = []
            for result in ping_results:
                if isinstance(result, dict):
                    for worker_name in result.keys():
                        workers.append({
                            "name": worker_name,
                            "status": "online",
                            "active_tasks": len(active.get(worker_name, [])),
                            "reserved_tasks": len(reserved.get(worker_name, [])),
                            "processed": 0,
                            "pool": 0,
                            "pid": 0,
                        })
        
        # Get queue length from Redis
        queue_length = 0
        try:
            import redis
            import os
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(redis_url)
            queue_length = r.llen('celery')
        except Exception:
            pass
        
        return {
            "workers": workers,
            "worker_count": len(workers),
            "total_active": sum(w["active_tasks"] for w in workers),
            "total_reserved": sum(w["reserved_tasks"] for w in workers),
            "queue_length": queue_length,
        }
    except Exception as e:
        logger.error(f"Error getting Celery info: {e}")
        return {"workers": [], "worker_count": 0, "error": str(e)}


def get_process_info() -> List[Dict[str, Any]]:
    """Get information about THIS APPLICATION's backend processes only."""
    # Only show processes from our application directory
    base_dir = os.environ.get(
        "APP_ROOT",
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(
                            os.path.dirname(__file__)
                        )
                    )
                )
            )
        )
    )
    app_path = os.path.abspath(base_dir)
    
    processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent', 'create_time', 'status']):
            try:
                info = proc.info
                name = info['name'].lower()
                cmdline = ' '.join(info['cmdline'] or [])
                
                # Skip non-relevant processes
                if name in ['bash', 'sh', 'grep', 'cat', 'ps', 'supervisord']:
                    continue
                
                # Only include processes running from our app path
                if app_path not in cmdline:
                    continue
                
                # Determine process type and display name
                if 'celery' in cmdline.lower() and 'worker' in cmdline.lower():
                    process_type = "Celery Worker"
                    display_name = "celery"
                elif 'uvicorn' in cmdline.lower() or 'fastapi' in cmdline.lower():
                    process_type = "FastAPI Server"
                    display_name = "uvicorn"
                elif name == 'ffmpeg':
                    # Extract filename being processed
                    parts = cmdline.split()
                    filename = "audio conversion"
                    for i, p in enumerate(parts):
                        if p == '-i' and i + 1 < len(parts):
                            filename = os.path.basename(parts[i + 1])[:40]
                            break
                    process_type = f"FFmpeg: {filename}"
                    display_name = "ffmpeg"
                elif name == 'ffprobe':
                    process_type = "FFprobe: audio analysis"
                    display_name = "ffprobe"
                elif name == 'fpcalc':
                    process_type = "Chromaprint: fingerprinting"
                    display_name = "fpcalc"
                else:
                    # Generic Python process from our app
                    if 'python' in name:
                        process_type = "Python Worker"
                        display_name = "python"
                    else:
                        continue  # Skip unknown processes
                
                processes.append({
                    "pid": info['pid'],
                    "name": display_name,
                    "cmdline": process_type,
                    "cpu_percent": round(info['cpu_percent'] or 0, 1),
                    "memory_percent": round(info['memory_percent'] or 0, 1),
                    "status": info['status'],
                    "uptime_seconds": int(datetime.now().timestamp() - info['create_time']) if info['create_time'] else 0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort by CPU usage, then by type
        processes.sort(key=lambda x: (-x['cpu_percent'], x['cmdline']))
        return processes[:15]  # Top 15 app processes
        
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        return []


def get_redis_info() -> Dict[str, Any]:
    """Get Redis server information."""
    try:
        import redis
        import os
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        info = r.info()
        
        return {
            "connected": True,
            "version": info.get('redis_version', 'unknown'),
            "uptime_seconds": info.get('uptime_in_seconds', 0),
            "connected_clients": info.get('connected_clients', 0),
            "used_memory_mb": round(info.get('used_memory', 0) / (1024**2), 2),
            "used_memory_peak_mb": round(info.get('used_memory_peak', 0) / (1024**2), 2),
            "total_commands_processed": info.get('total_commands_processed', 0),
            "keyspace_hits": info.get('keyspace_hits', 0),
            "keyspace_misses": info.get('keyspace_misses', 0),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/stats")
async def get_dashboard_stats() -> Dict[str, Any]:
    """
    Get all dashboard statistics.
    
    Returns comprehensive system monitoring data including GPU, CPU,
    memory, Celery workers, Redis, and process information.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "gpu": get_gpu_info(),
        "system": get_system_info(),
        "celery": get_celery_info(),
        "redis": get_redis_info(),
        "processes": get_process_info(),
    }


@router.get("/gpu")
async def get_gpu_stats() -> Dict[str, Any]:
    """Get GPU statistics only."""
    return {
        "timestamp": datetime.now().isoformat(),
        "gpu": get_gpu_info(),
    }


def get_console_logs(lines: int = 100) -> List[str]:
    """Get recent console logs from Celery and FastAPI."""
    # Get log directory from environment or use relative path
    base_dir = os.environ.get("APP_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))))
    logs_dir = os.path.join(base_dir, "logs")
    
    log_files = [
        os.path.join(logs_dir, "celery.log"),
        os.path.join(logs_dir, "celery_error.log"),
        os.path.join(logs_dir, "fastapi.log"),
    ]
    
    all_logs = []
    
    for log_file in log_files:
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    # Read last N lines efficiently
                    file_lines = f.readlines()
                    recent = file_lines[-lines:] if len(file_lines) > lines else file_lines
                    source = os.path.basename(log_file).replace('.log', '')
                    for line in recent:
                        line = line.strip()
                        if line:
                            all_logs.append({
                                "source": source,
                                "message": line[:500],  # Truncate long lines
                            })
        except Exception as e:
            logger.warning(f"Could not read {log_file}: {e}")
    
    # Return most recent logs (combined and sorted by position)
    return all_logs[-lines:] if len(all_logs) > lines else all_logs


@router.get("/logs")
async def get_logs(lines: int = 100) -> Dict[str, Any]:
    """
    Get recent console logs from all services.
    
    Args:
        lines: Number of log lines to return (default 100)
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "logs": get_console_logs(lines),
        "log_count": len(get_console_logs(lines)),
    }


@router.get("/health")
async def get_health_status() -> Dict[str, Any]:
    """Quick health check for all services."""
    gpu = get_gpu_info()
    system = get_system_info()
    celery = get_celery_info()
    redis = get_redis_info()
    
    # Determine overall health
    issues = []
    
    if not gpu.get("available"):
        issues.append("GPU not available")
    
    if system.get("memory", {}).get("percent", 0) > 90:
        issues.append("Memory usage critical (>90%)")
    
    if system.get("disk", {}).get("percent", 0) > 90:
        issues.append("Disk usage critical (>90%)")
    
    if celery.get("worker_count", 0) == 0:
        issues.append("No Celery workers online")
    
    if not redis.get("connected"):
        issues.append("Redis not connected")
    
    status = "healthy" if len(issues) == 0 else "degraded" if len(issues) < 3 else "critical"
    
    return {
        "status": status,
        "issues": issues,
        "timestamp": datetime.now().isoformat(),
    }
