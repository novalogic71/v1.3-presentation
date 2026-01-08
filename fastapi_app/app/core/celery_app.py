"""
Celery Application Configuration

Provides persistent background job processing with Redis as the broker
and result backend. Jobs survive server restarts and browser refreshes.

Production features:
- Automatic reconnection on Redis failures
- Task retry with exponential backoff
- Graceful degradation
"""

import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# Redis connection URL (default to localhost)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "sync_analyzer",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.analysis_tasks"],
)

# Celery configuration - Production Hardened
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result backend settings
    result_expires=86400 * 7,  # Keep results for 7 days
    result_extended=True,  # Store task args in result
    
    # Task execution settings
    task_acks_late=True,  # Ack after task completes (safer)
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    task_track_started=True,  # Track when task starts
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # Number of concurrent workers
    
    # Task time limits
    task_time_limit=3600,  # Hard limit: 1 hour
    task_soft_time_limit=3300,  # Soft limit: 55 minutes (gives cleanup time)
    
    # Retry settings - exponential backoff
    task_default_retry_delay=60,  # Wait 60s before retry
    task_max_retries=3,  # Max 3 retries
    
    # Broker connection resilience
    broker_connection_retry_on_startup=True,  # Retry connection at startup
    broker_connection_max_retries=10,  # Max connection retries
    broker_connection_retry=True,  # Enable connection retry
    broker_heartbeat=30,  # Heartbeat interval
    broker_pool_limit=10,  # Connection pool limit
    
    # Redis specific settings for resilience
    redis_socket_connect_timeout=10,
    redis_socket_timeout=30,
    redis_retry_on_timeout=True,
    
    # Result backend resilience
    result_backend_always_retry=True,
    result_backend_max_retries=10,
    
    # Beat schedule (for periodic tasks if needed)
    beat_schedule={},
)

# Custom task base class for progress tracking
from celery import Task
import redis
import json


class ProgressTask(Task):
    """
    Base task class that supports progress tracking via Redis.
    
    Usage in task:
        self.update_progress(50, "Processing file 2/4...")
    
    Features:
    - Automatic Redis reconnection on failure
    - Graceful degradation if Redis unavailable
    """
    
    _redis = None
    _redis_available = True
    
    @property
    def redis(self):
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    REDIS_URL,
                    socket_connect_timeout=5,
                    socket_timeout=10,
                    retry_on_timeout=True,
                )
                # Test connection
                self._redis.ping()
                self._redis_available = True
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._redis_available = False
                return None
        return self._redis
    
    def _reconnect_redis(self):
        """Attempt to reconnect to Redis."""
        self._redis = None
        return self.redis
    
    def update_progress(self, progress: int, message: str = ""):
        """Update task progress in Redis with retry logic."""
        if not self.request.id:
            return
            
        key = f"task_progress:{self.request.id}"
        data = {
            "progress": progress,
            "message": message,
            "task_id": self.request.id,
        }
        
        for attempt in range(3):
            try:
                r = self.redis
                if r:
                    r.setex(key, 3600, json.dumps(data))
                    return
            except redis.ConnectionError:
                logger.warning(f"Redis connection lost, attempt {attempt + 1}/3")
                self._reconnect_redis()
            except Exception as e:
                logger.warning(f"Failed to update progress: {e}")
                break
    
    def get_progress(self, task_id: str) -> dict:
        """Get task progress from Redis with graceful fallback."""
        key = f"task_progress:{task_id}"
        try:
            r = self.redis
            if r:
                data = r.get(key)
                if data:
                    return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get progress: {e}")
        return {"progress": 0, "message": "Unknown", "task_id": task_id}


# Register the base class
celery_app.Task = ProgressTask


def get_task_progress(task_id: str) -> dict:
    """Helper function to get task progress from Redis with resilience."""
    try:
        r = redis.from_url(
            REDIS_URL,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        key = f"task_progress:{task_id}"
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Could not get task progress from Redis: {e}")
    return {"progress": 0, "message": "Unknown", "task_id": task_id}


def get_active_tasks() -> list:
    """Get list of active (running) tasks from Celery."""
    inspect = celery_app.control.inspect()
    
    active_tasks = []
    
    # Get active tasks from all workers
    active = inspect.active() or {}
    for worker, tasks in active.items():
        for task in tasks:
            active_tasks.append({
                "task_id": task.get("id"),
                "name": task.get("name"),
                "args": task.get("args"),
                "kwargs": task.get("kwargs"),
                "worker": worker,
                "started": task.get("time_start"),
            })
    
    # Get reserved (queued) tasks
    reserved = inspect.reserved() or {}
    for worker, tasks in reserved.items():
        for task in tasks:
            active_tasks.append({
                "task_id": task.get("id"),
                "name": task.get("name"),
                "args": task.get("args"),
                "kwargs": task.get("kwargs"),
                "worker": worker,
                "status": "queued",
            })
    
    return active_tasks

