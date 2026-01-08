#!/usr/bin/env python3
"""
UI state endpoints to persist lightweight client state (e.g., batch queue)
in the shared SQLite store so it survives browser refresh.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class BatchFile(BaseModel):
    name: str
    path: str
    type: Optional[str] = None
    label: Optional[str] = None
    index: Optional[int] = None


class BatchResult(BaseModel):
    offset_seconds: Optional[float] = None
    confidence: Optional[float] = None
    method_used: Optional[str] = None
    quality_score: Optional[float] = None


class BatchQueueItem(BaseModel):
    id: Union[str, int]
    master: BatchFile
    # For standard single-dub analysis
    dub: Optional[BatchFile] = None
    # For componentized analysis (multiple components per master)
    type: Optional[str] = None  # 'componentized' or None for standard
    components: Optional[List[BatchFile]] = None
    componentResults: Optional[List[Dict[str, Any]]] = None
    offsetMode: Optional[str] = None
    # Common fields
    status: str = Field(default="queued")
    progress: float = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    frameRate: Optional[float] = None
    analysisId: Optional[str] = None
    autoRepair: Optional[bool] = None
    keepDuration: Optional[bool] = None
    restoredFromDb: Optional[bool] = None
    statusMessage: Optional[str] = None


class BatchQueueState(BaseModel):
    items: List[BatchQueueItem] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


STATE_KEY = "ui_batch_queue"


@router.get("/batch-queue")
async def get_batch_queue_state():
    """Return the persisted batch queue (if any)."""
    try:
        from sync_analyzer.db.ui_state_db import get_state

        state = get_state(STATE_KEY) or {"items": [], "updated_at": datetime.utcnow().isoformat()}
        return {"success": True, "state": state}
    except Exception as e:
        logger.error(f"get_batch_queue_state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-queue")
async def set_batch_queue_state(state: BatchQueueState):
    """Persist the provided batch queue state."""
    try:
        from sync_analyzer.db.ui_state_db import set_state

        payload = state.model_dump()
        payload["updated_at"] = datetime.utcnow().isoformat()
        set_state(STATE_KEY, payload)
        return {"success": True}
    except Exception as e:
        logger.error(f"set_batch_queue_state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/batch-queue")
async def clear_batch_queue_state():
    """Clear the persisted batch queue state."""
    try:
        from sync_analyzer.db.ui_state_db import delete_state

        delete_state(STATE_KEY)
        return {"success": True}
    except Exception as e:
        logger.error(f"clear_batch_queue_state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
