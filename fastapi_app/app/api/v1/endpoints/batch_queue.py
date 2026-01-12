"""
Batch Queue API - Server-side storage for batch queue state
Ensures all browser sessions see the same job status
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import redis
import json
import logging
from datetime import datetime

import os

logger = logging.getLogger(__name__)
router = APIRouter()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
BATCH_QUEUE_KEY = "sync_analyzer:batch_queue"
BATCH_QUEUE_TTL = 60 * 60 * 24 * 7  # 7 days


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


class BatchQueueItem(BaseModel):
    """Single batch queue item"""
    id: int
    type: str  # 'standard' or 'componentized'
    status: str  # 'queued', 'processing', 'completed', 'failed', 'cancelled'
    progress: int = 0
    master: Dict[str, Any]
    dub: Optional[Dict[str, Any]] = None
    components: Optional[List[Dict[str, Any]]] = None
    componentResults: Optional[List[Dict[str, Any]]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    analysisId: Optional[str] = None
    offsetMode: Optional[str] = None
    progressMessage: Optional[str] = None
    masterFindings: Optional[List[str]] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class BatchQueueState(BaseModel):
    """Full batch queue state"""
    items: List[Dict[str, Any]]
    lastUpdated: Optional[str] = None
    clientId: Optional[str] = None


class BatchQueueResponse(BaseModel):
    """Response for batch queue operations"""
    success: bool
    items: List[Dict[str, Any]] = []
    lastUpdated: Optional[str] = None
    message: Optional[str] = None


@router.get("", response_model=BatchQueueResponse)
async def get_batch_queue():
    """Get the current batch queue state"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        data = r.get(BATCH_QUEUE_KEY)
        if data:
            state = json.loads(data)
            return BatchQueueResponse(
                success=True,
                items=state.get("items", []),
                lastUpdated=state.get("lastUpdated")
            )
        return BatchQueueResponse(
            success=True,
            items=[],
            lastUpdated=None,
            message="No batch queue found"
        )
    except Exception as e:
        logger.error(f"Failed to get batch queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=BatchQueueResponse)
async def save_batch_queue(state: BatchQueueState):
    """Save the batch queue state"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        state_dict = {
            "items": state.items,
            "lastUpdated": datetime.utcnow().isoformat(),
            "clientId": state.clientId
        }
        r.setex(BATCH_QUEUE_KEY, BATCH_QUEUE_TTL, json.dumps(state_dict))
        return BatchQueueResponse(
            success=True,
            items=state.items,
            lastUpdated=state_dict["lastUpdated"],
            message=f"Saved {len(state.items)} items"
        )
    except Exception as e:
        logger.error(f"Failed to save batch queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/item/{item_id}", response_model=BatchQueueResponse)
async def update_batch_item(item_id: int, item: Dict[str, Any]):
    """Update a single batch queue item"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        data = r.get(BATCH_QUEUE_KEY)
        if not data:
            raise HTTPException(status_code=404, detail="Batch queue not found")
        
        state = json.loads(data)
        items = state.get("items", [])
        
        # Find and update the item
        found = False
        for i, existing in enumerate(items):
            if existing.get("id") == item_id:
                # Merge the update
                items[i] = {**existing, **item, "updatedAt": datetime.utcnow().isoformat()}
                found = True
                break
        
        if not found:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        
        state["items"] = items
        state["lastUpdated"] = datetime.utcnow().isoformat()
        r.setex(BATCH_QUEUE_KEY, BATCH_QUEUE_TTL, json.dumps(state))
        
        return BatchQueueResponse(
            success=True,
            items=items,
            lastUpdated=state["lastUpdated"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update batch item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/item/{item_id}", response_model=BatchQueueResponse)
async def delete_batch_item(item_id: int):
    """Delete a single batch queue item"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        data = r.get(BATCH_QUEUE_KEY)
        if not data:
            return BatchQueueResponse(success=True, items=[], message="Queue already empty")
        
        state = json.loads(data)
        items = state.get("items", [])
        items = [item for item in items if item.get("id") != item_id]
        
        state["items"] = items
        state["lastUpdated"] = datetime.utcnow().isoformat()
        r.setex(BATCH_QUEUE_KEY, BATCH_QUEUE_TTL, json.dumps(state))
        
        return BatchQueueResponse(
            success=True,
            items=items,
            lastUpdated=state["lastUpdated"]
        )
    except Exception as e:
        logger.error(f"Failed to delete batch item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("", response_model=BatchQueueResponse)
async def clear_batch_queue():
    """Clear the entire batch queue"""
    r = get_redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    
    try:
        r.delete(BATCH_QUEUE_KEY)
        return BatchQueueResponse(
            success=True,
            items=[],
            lastUpdated=datetime.utcnow().isoformat(),
            message="Batch queue cleared"
        )
    except Exception as e:
        logger.error(f"Failed to clear batch queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

