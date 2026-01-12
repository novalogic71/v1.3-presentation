"""
Job Registry API - Tracks all jobs submitted via any method (UI or API)
Allows the UI to discover and display jobs submitted directly to the API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import redis
import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
JOB_REGISTRY_KEY = "sync_analyzer:job_registry"
JOB_REGISTRY_TTL = 60 * 60 * 24  # 24 hours


def get_redis():
    """Get Redis connection"""
    try:
        r = redis.from_url(
            REDIS_URL,
            socket_connect_timeout=5,
            socket_timeout=10,
            decode_responses=True
        )
        r.ping()
        return r
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return None


class JobInfo(BaseModel):
    """Job information for registry"""
    job_id: str
    type: str  # 'standard' or 'componentized'
    status: str  # 'queued', 'processing', 'completed', 'failed'
    master_file: str
    master_name: str
    dub_file: Optional[str] = None
    dub_name: Optional[str] = None
    components: Optional[List[Dict[str, Any]]] = None
    component_count: int = 0
    progress: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    source: str = "api"  # 'api' or 'ui'


class JobRegistryResponse(BaseModel):
    """Response for job registry operations"""
    success: bool
    jobs: List[Dict[str, Any]] = []
    total: int = 0
    message: Optional[str] = None


def register_job(job_id: str, job_info: dict):
    """Register a new job in the registry (called by analysis endpoints)"""
    r = get_redis()
    if not r:
        logger.warning("Redis unavailable - job not registered")
        return False
    
    try:
        # Add timestamp
        job_info["created_at"] = datetime.utcnow().isoformat()
        job_info["updated_at"] = datetime.utcnow().isoformat()
        job_info["job_id"] = job_id
        
        # Store in hash
        r.hset(JOB_REGISTRY_KEY, job_id, json.dumps(job_info))
        r.expire(JOB_REGISTRY_KEY, JOB_REGISTRY_TTL)
        
        logger.info(f"Registered job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to register job: {e}")
        return False


def update_job_status(job_id: str, status: str, progress: int = None, 
                      result: dict = None, error: str = None):
    """Update job status in registry"""
    r = get_redis()
    if not r:
        return False
    
    try:
        data = r.hget(JOB_REGISTRY_KEY, job_id)
        if not data:
            return False
        
        job_info = json.loads(data)
        job_info["status"] = status
        job_info["updated_at"] = datetime.utcnow().isoformat()
        
        if progress is not None:
            job_info["progress"] = progress
        if result is not None:
            job_info["result"] = result
        if error is not None:
            job_info["error"] = error
        
        r.hset(JOB_REGISTRY_KEY, job_id, json.dumps(job_info))
        return True
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        return False


@router.get("", response_model=JobRegistryResponse)
async def get_all_jobs(
    status: Optional[str] = None,
    source: Optional[str] = None,
    since_hours: int = 24
):
    """Get all registered jobs, optionally filtered by status or source"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        all_jobs = r.hgetall(JOB_REGISTRY_KEY)
        jobs = []
        
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
        
        for job_id, job_data in all_jobs.items():
            try:
                job = json.loads(job_data)
                
                # Filter by age
                created = datetime.fromisoformat(job.get("created_at", "2000-01-01"))
                if created < cutoff:
                    continue
                
                # Filter by status
                if status and job.get("status") != status:
                    continue
                
                # Filter by source
                if source and job.get("source") != source:
                    continue
                
                jobs.append(job)
            except json.JSONDecodeError:
                continue
        
        # Sort by created_at descending (newest first)
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return JobRegistryResponse(
            success=True,
            jobs=jobs,
            total=len(jobs)
        )
    except Exception as e:
        logger.error(f"Failed to get jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/new", response_model=JobRegistryResponse)
async def get_new_jobs(since: Optional[str] = None):
    """Get jobs created after a certain timestamp (for polling)"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        all_jobs = r.hgetall(JOB_REGISTRY_KEY)
        jobs = []
        
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except:
                pass
        
        for job_id, job_data in all_jobs.items():
            try:
                job = json.loads(job_data)
                
                # Filter by timestamp if provided
                if since_dt:
                    created = datetime.fromisoformat(job.get("created_at", "2000-01-01"))
                    if created <= since_dt:
                        continue
                
                jobs.append(job)
            except json.JSONDecodeError:
                continue
        
        # Sort by created_at descending
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return JobRegistryResponse(
            success=True,
            jobs=jobs,
            total=len(jobs)
        )
    except Exception as e:
        logger.error(f"Failed to get new jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get a specific job by ID"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        data = r.hget(JOB_REGISTRY_KEY, job_id)
        if not data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return json.loads(data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def remove_job(job_id: str):
    """Remove a job from registry"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        r.hdel(JOB_REGISTRY_KEY, job_id)
        return {"success": True, "message": f"Job {job_id} removed"}
    except Exception as e:
        logger.error(f"Failed to remove job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def clear_registry():
    """Clear all jobs from registry"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        r.delete(JOB_REGISTRY_KEY)
        return {"success": True, "message": "Job registry cleared"}
    except Exception as e:
        logger.error(f"Failed to clear registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

