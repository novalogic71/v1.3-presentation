"""
Proxy Endpoints

Provides API endpoints for audio proxy creation and serving.
Proxies are cached transcoded versions of audio files optimized for browser playback.
"""

import os
import mimetypes
import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ....services.proxy_service import (
    ensure_wav_proxy,
    transcode_to_format,
    get_proxy_path,
    is_safe_path,
    hash_for_proxy,
    PROXY_CACHE_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class PrepareProxyRequest(BaseModel):
    """Request for preparing audio proxy."""
    path: str = Field(default=None, description="Path to source audio/video file")
    role: str = Field(default="audio", description="Role identifier (master, component, audio)")
    # Legacy combined format support
    master: Optional[str] = Field(default=None, description="Legacy: Master file path")
    dub: Optional[str] = Field(default=None, description="Legacy: Dub file path")


class PrepareProxyResponse(BaseModel):
    """Response for proxy preparation."""
    success: bool
    proxy_path: Optional[str] = None
    proxy_url: Optional[str] = None
    # Legacy combined format fields
    master_url: Optional[str] = None
    dub_url: Optional[str] = None
    format: Optional[str] = None
    error: Optional[str] = None


@router.post("/prepare", response_model=PrepareProxyResponse)
async def prepare_proxy(request: PrepareProxyRequest):
    """
    Prepare audio proxy(s) for browser playback.
    
    Supports two formats:
    
    ## New Format (single file)
    
    ```json
    {
      "path": "/mnt/data/audio/master.mxf",
      "role": "master"
    }
    ```
    
    Response:
    ```json
    {
      "success": true,
      "proxy_path": "abc123_master.wav",
      "proxy_url": "/api/v1/proxy/abc123_master.wav"
    }
    ```
    
    ## Legacy Format (master + dub)
    
    ```json
    {
      "master": "/mnt/data/audio/master.mxf",
      "dub": "/mnt/data/audio/dub.wav"
    }
    ```
    
    Response:
    ```json
    {
      "success": true,
      "master_url": "/api/v1/proxy/abc123_master.wav",
      "dub_url": "/api/v1/proxy/def456_dub.wav",
      "format": "wav"
    }
    ```
    """
    try:
        # Legacy format: master + dub
        if request.master and request.dub:
            # Validate paths
            if not is_safe_path(request.master):
                raise HTTPException(status_code=400, detail="Invalid or unsafe master path")
            if not is_safe_path(request.dub):
                raise HTTPException(status_code=400, detail="Invalid or unsafe dub path")
            if not os.path.exists(request.master):
                raise HTTPException(status_code=404, detail="Master file not found")
            if not os.path.exists(request.dub):
                raise HTTPException(status_code=404, detail="Dub file not found")
            
            # Create proxies for both
            master_proxy = ensure_wav_proxy(request.master, "master")
            dub_proxy = ensure_wav_proxy(request.dub, "dub")
            
            master_filename = os.path.basename(master_proxy)
            dub_filename = os.path.basename(dub_proxy)
            
            return PrepareProxyResponse(
                success=True,
                master_url=f"/api/v1/proxy/{master_filename}",
                dub_url=f"/api/v1/proxy/{dub_filename}",
                format="wav",
            )
        
        # New format: single path
        if not request.path:
            raise HTTPException(status_code=400, detail="Path is required (or master+dub for legacy format)")
        
        if not is_safe_path(request.path):
            raise HTTPException(status_code=400, detail="Invalid or unsafe path")
        
        if not os.path.exists(request.path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Create proxy
        proxy_path = ensure_wav_proxy(request.path, request.role)
        proxy_filename = os.path.basename(proxy_path)
        
        return PrepareProxyResponse(
            success=True,
            proxy_path=proxy_filename,
            proxy_url=f"/api/v1/proxy/{proxy_filename}",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Proxy preparation error: {e}")
        return PrepareProxyResponse(
            success=False,
            error=str(e),
        )


@router.get("/{filename}")
async def serve_proxy(filename: str):
    """
    Serve a proxy audio file.
    
    Retrieves and streams a previously created proxy file.
    
    ## Example
    
    ```bash
    curl -O "http://localhost:8000/api/v1/proxy/abc123_master.wav"
    ```
    """
    try:
        # Security: only serve files from proxy cache
        proxy_path = get_proxy_path(filename)
        
        if not proxy_path:
            raise HTTPException(status_code=404, detail="Proxy file not found")
        
        # Determine media type
        media_type = mimetypes.guess_type(proxy_path)[0] or "application/octet-stream"
        
        return FileResponse(
            proxy_path,
            media_type=media_type,
            filename=filename,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving proxy {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/stream")
async def stream_proxy_audio(
    path: str = Query(..., description="Path to source audio/video file"),
    format: str = Query(default="wav", description="Target format (wav, mp4, webm, opus, aac)"),
    max_duration: int = Query(default=600, description="Maximum duration in seconds"),
):
    """
    Stream transcoded audio for browser playback.
    
    Transcodes the source file to a browser-friendly format and streams it.
    
    ## Supported Formats
    - **wav**: PCM audio (best quality, largest size)
    - **mp4/aac**: AAC audio in MP4 container (good quality, small size)
    - **webm/opus**: Opus audio (efficient, good for streaming)
    
    ## Example
    
    ```bash
    curl "http://localhost:8000/api/v1/proxy/audio/stream?path=/mnt/data/audio/file.mxf&format=mp4"
    ```
    """
    try:
        if not path:
            raise HTTPException(status_code=400, detail="Path is required")
        
        if not is_safe_path(path):
            raise HTTPException(status_code=400, detail="Invalid or unsafe path")
        
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")
        
        format = format.lower()
        if format not in {"wav", "mp4", "webm", "opus", "aac"}:
            raise HTTPException(status_code=400, detail="Unsupported format")
        
        # Transcode and get path
        transcoded_path = transcode_to_format(path, format, max_duration)
        
        # Determine media type
        media_types = {
            "wav": "audio/wav",
            "mp4": "audio/mp4",
            "aac": "audio/mp4",
            "webm": "audio/webm",
            "opus": "audio/opus",
        }
        media_type = media_types.get(format, "application/octet-stream")
        
        return FileResponse(
            transcoded_path,
            media_type=media_type,
            filename=os.path.basename(transcoded_path),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup")
async def cleanup_proxy_cache(
    max_age_hours: int = Query(default=24, description="Remove files older than this many hours"),
):
    """
    Clean up old proxy files.
    
    Removes proxy files older than the specified age.
    
    ## Example
    
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/proxy/cleanup?max_age_hours=12"
    ```
    """
    try:
        from ....services.proxy_service import cleanup_old_proxies
        
        removed = cleanup_old_proxies(max_age_hours)
        
        return {
            "success": True,
            "removed_count": removed,
            "message": f"Removed {removed} old proxy files",
        }
    
    except Exception as e:
        logger.error(f"Proxy cleanup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

