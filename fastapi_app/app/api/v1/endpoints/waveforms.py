"""
Waveform API endpoints for serving pre-generated waveform data.

Pre-generated waveforms enable instant QC visualization without needing
to decode audio files in the browser. Waveforms are automatically generated
after analysis completes and cached for fast retrieval.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["waveforms"])

# Waveform cache directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
WAVEFORM_CACHE_DIR = PROJECT_ROOT / "waveform_cache"


class WaveformData(BaseModel):
    """Waveform visualization data for a single audio file."""
    source_path: str = Field(..., description="Original file path")
    source_name: str = Field(..., description="File name")
    duration: float = Field(..., description="Audio duration in seconds")
    sample_rate: int = Field(..., description="Sample rate used for extraction")
    width: int = Field(..., description="Number of data points (typically 2000)")
    peaks: List[float] = Field(..., description="Peak amplitude values for visualization")
    rms: List[float] = Field(..., description="RMS values for visualization")
    generated_at: str = Field(..., description="ISO timestamp when waveform was generated")

    class Config:
        json_schema_extra = {
            "example": {
                "source_path": "/mnt/data/audio/master.wav",
                "source_name": "master.wav",
                "duration": 120.5,
                "sample_rate": 22050,
                "width": 2000,
                "peaks": [0.1, 0.2, 0.15],
                "rms": [0.05, 0.1, 0.08],
                "generated_at": "2025-01-09T12:00:00Z"
            }
        }


class WaveformPairData(BaseModel):
    """Combined master/dub waveform data for QC interface."""
    analysis_id: Optional[str] = Field(None, description="Associated analysis ID")
    master: WaveformData = Field(..., description="Master file waveform data")
    dub: WaveformData = Field(..., description="Dub file waveform data")
    generated_at: str = Field(..., description="Generation timestamp")


class GenerateWaveformRequest(BaseModel):
    """Request to generate waveform data for a file pair."""
    master_path: str = Field(..., description="Absolute path to master audio/video file")
    dub_path: str = Field(..., description="Absolute path to dub audio/video file")
    analysis_id: Optional[str] = Field(None, description="Analysis ID for cache naming")
    force_regenerate: bool = Field(False, description="Force regeneration even if cached")

    class Config:
        json_schema_extra = {
            "example": {
                "master_path": "/mnt/data/project/master.mp4",
                "dub_path": "/mnt/data/project/dub.mxf",
                "analysis_id": "analysis_20250109_120000_abc123",
                "force_regenerate": False
            }
        }


@router.get("/analysis/{analysis_id}", response_model=WaveformPairData)
async def get_waveforms_by_analysis(analysis_id: str):
    """
    Get pre-generated waveforms for an analysis.
    
    Returns cached waveform peak data that can be rendered instantly in the QC interface
    without needing to decode audio files in the browser.
    
    ## Response
    
    Returns master and dub waveform data with:
    - **peaks**: Peak amplitude values (2000 points)
    - **rms**: RMS values for fill display
    - **duration**: Audio duration in seconds
    
    ## Example
    
    ```bash
    curl http://localhost:8000/api/v1/waveforms/analysis/analysis_20250109_120000_abc123
    ```
    
    ## Notes
    
    - Waveforms are automatically generated after analysis completes
    - If waveforms don't exist, returns 404 - call POST /generate to create them
    - Cache files are stored in `waveform_cache/` directory
    """
    # Check for combined waveform file
    combined_file = WAVEFORM_CACHE_DIR / f"{analysis_id}_waveforms.json"
    
    if combined_file.exists():
        try:
            with open(combined_file, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to read waveform cache: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read waveform data: {e}")
    
    # Check for individual files
    master_file = WAVEFORM_CACHE_DIR / f"{analysis_id}_master.json"
    dub_file = WAVEFORM_CACHE_DIR / f"{analysis_id}_dub.json"
    
    if master_file.exists() and dub_file.exists():
        try:
            with open(master_file, 'r') as f:
                master_data = json.load(f)
            with open(dub_file, 'r') as f:
                dub_data = json.load(f)
            
            return {
                "analysis_id": analysis_id,
                "master": master_data,
                "dub": dub_data
            }
        except Exception as e:
            logger.error(f"Failed to read waveform files: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read waveform data: {e}")
    
    raise HTTPException(
        status_code=404, 
        detail=f"No waveform data found for analysis {analysis_id}. Waveforms may need to be generated."
    )


class ComponentizedTrackData(BaseModel):
    """Waveform data for a single track in componentized analysis."""
    name: str = Field(..., description="Track name/label")
    type: str = Field(..., description="Track type: 'master' or 'component'")
    peaks: List[float] = Field(..., description="Peak amplitude values")
    rms: Optional[List[float]] = Field(None, description="RMS values")
    duration: float = Field(..., description="Duration in seconds")
    sample_rate: int = Field(22050, description="Sample rate")
    width: int = Field(..., description="Number of data points")


class ComponentizedWaveformResponse(BaseModel):
    """Response for componentized waveform data with multiple tracks."""
    analysis_id: str = Field(..., description="Analysis ID")
    tracks: List[ComponentizedTrackData] = Field(..., description="List of track waveforms")
    generated_at: str = Field(..., description="Generation timestamp")


@router.get("/componentized/{analysis_id}", response_model=ComponentizedWaveformResponse)
async def get_componentized_waveforms(analysis_id: str):
    """
    Get waveform data for componentized analyses with multiple dub tracks.
    
    Returns master waveform plus all component waveforms for multi-track QC view.
    
    ## Response
    
    Returns array of track waveforms:
    - First track is always master (type: 'master')
    - Remaining tracks are dub components (type: 'component')
    
    ## Example
    
    ```bash
    curl http://localhost:8000/api/v1/waveforms/componentized/analysis_20250109_120000_abc123
    ```
    
    ## Notes
    
    - Automatically detects component files by naming pattern
    - Falls back to standard 2-track if no components found
    """
    from datetime import datetime
    
    tracks = []
    
    # Look for componentized waveform files
    # Pattern: {analysis_id}_component_{N}.json or {analysis_id}_{trackname}.json
    
    # First, check for master
    master_file = WAVEFORM_CACHE_DIR / f"{analysis_id}_master.json"
    if master_file.exists():
        try:
            with open(master_file, 'r') as f:
                master_data = json.load(f)
            tracks.append({
                "name": "Master",
                "type": "master",
                "peaks": master_data.get("peaks", []),
                "rms": master_data.get("rms"),
                "duration": master_data.get("duration", 0),
                "sample_rate": master_data.get("sample_rate", 22050),
                "width": master_data.get("width", len(master_data.get("peaks", [])))
            })
        except Exception as e:
            logger.warning(f"Failed to read master waveform: {e}")
    
    # Look for component files
    # Try multiple patterns
    component_patterns = [
        f"{analysis_id}_component_*.json",
        f"{analysis_id}_dub_*.json",
        f"{analysis_id}_track_*.json"
    ]
    
    component_files = []
    for pattern in component_patterns:
        component_files.extend(WAVEFORM_CACHE_DIR.glob(pattern))
    
    # Also check for single dub file
    dub_file = WAVEFORM_CACHE_DIR / f"{analysis_id}_dub.json"
    if dub_file.exists() and dub_file not in component_files:
        component_files.insert(0, dub_file)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in component_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    
    for idx, comp_file in enumerate(sorted(unique_files)):
        try:
            with open(comp_file, 'r') as f:
                comp_data = json.load(f)
            
            # Extract track name from filename
            track_name = comp_file.stem.replace(f"{analysis_id}_", "")
            track_name = track_name.replace("_", " ").title()
            if track_name.lower() == "dub":
                track_name = "Dub"
            
            tracks.append({
                "name": track_name,
                "type": "component",
                "peaks": comp_data.get("peaks", []),
                "rms": comp_data.get("rms"),
                "duration": comp_data.get("duration", 0),
                "sample_rate": comp_data.get("sample_rate", 22050),
                "width": comp_data.get("width", len(comp_data.get("peaks", [])))
            })
        except Exception as e:
            logger.warning(f"Failed to read component waveform {comp_file}: {e}")
    
    if not tracks:
        raise HTTPException(
            status_code=404,
            detail=f"No componentized waveform data found for analysis {analysis_id}"
        )
    
    return {
        "analysis_id": analysis_id,
        "tracks": tracks,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/file", response_model=WaveformData)
async def get_waveform_by_path(path: str = Query(..., description="Absolute path to audio/video file")):
    """
    Get cached waveform for a specific file path.
    
    Looks up waveform data by file path hash. Returns 404 if not cached.
    
    ## Example
    
    ```bash
    curl "http://localhost:8000/api/v1/waveforms/file?path=/mnt/data/audio/master.wav"
    ```
    """
    import hashlib
    
    file_path = Path(path)
    path_hash = hashlib.md5(str(file_path.resolve()).encode()).hexdigest()[:12]
    cache_name = f"{file_path.stem}_{path_hash}"
    cache_file = WAVEFORM_CACHE_DIR / f"{cache_name}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read waveform cache: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read waveform data: {e}")
    
    raise HTTPException(
        status_code=404,
        detail=f"No cached waveform found for {path}"
    )


@router.post("/generate")
async def generate_waveforms(
    request: GenerateWaveformRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate waveform data for a master/dub pair (synchronous).
    
    Extracts audio from the files using ffmpeg, calculates peak/RMS data,
    and saves to the waveform cache. This runs synchronously and blocks
    until complete.
    
    ## Use Cases
    
    - Generate waveforms for existing analyses that don't have cached data
    - Force regeneration after file changes
    - Manual waveform generation for testing
    
    ## Example
    
    ```bash
    curl -X POST http://localhost:8000/api/v1/waveforms/generate \\
      -H "Content-Type: application/json" \\
      -d '{
        "master_path": "/mnt/data/project/master.mp4",
        "dub_path": "/mnt/data/project/dub.mxf",
        "analysis_id": "analysis_20250109_120000_abc123"
      }'
    ```
    
    ## Processing Time
    
    - Typical: 1-5 seconds per file depending on duration
    - For long files, consider using `/generate-async` instead
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    
    try:
        from sync_analyzer.utils.waveform_generator import WaveformGenerator
        
        generator = WaveformGenerator(output_dir=WAVEFORM_CACHE_DIR)
        
        # Generate waveforms
        result = generator.generate_pair(
            request.master_path,
            request.dub_path,
            request.analysis_id,
            request.force_regenerate
        )
        
        return {
            "status": "success",
            "analysis_id": request.analysis_id,
            "master_width": result["master"]["width"],
            "master_duration": result["master"]["duration"],
            "dub_width": result["dub"]["width"],
            "dub_duration": result["dub"]["duration"]
        }
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Waveform generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@router.post("/generate-async")
async def generate_waveforms_async(
    request: GenerateWaveformRequest,
    background_tasks: BackgroundTasks
):
    """
    Queue waveform generation as a background task (non-blocking).
    
    Returns immediately while waveform generation runs in the background.
    Use this for long files or when you don't need to wait for completion.
    
    ## Example
    
    ```bash
    curl -X POST http://localhost:8000/api/v1/waveforms/generate-async \\
      -H "Content-Type: application/json" \\
      -d '{
        "master_path": "/mnt/data/project/master.mp4",
        "dub_path": "/mnt/data/project/dub.mxf",
        "analysis_id": "analysis_20250109_120000_abc123"
      }'
    ```
    
    ## Checking Status
    
    Poll `GET /analysis/{analysis_id}` to check if waveforms are ready.
    """
    def generate_in_background():
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        
        try:
            from sync_analyzer.utils.waveform_generator import WaveformGenerator
            generator = WaveformGenerator(output_dir=WAVEFORM_CACHE_DIR)
            generator.generate_pair(
                request.master_path,
                request.dub_path,
                request.analysis_id,
                request.force_regenerate
            )
            logger.info(f"Background waveform generation completed for {request.analysis_id}")
        except Exception as e:
            logger.error(f"Background waveform generation failed: {e}")
    
    background_tasks.add_task(generate_in_background)
    
    return {
        "status": "queued",
        "analysis_id": request.analysis_id,
        "message": "Waveform generation queued as background task"
    }


@router.get("/list")
async def list_cached_waveforms(
    limit: int = Query(100, ge=1, le=1000, description="Max items to return")
):
    """
    List all cached waveform files.
    
    Returns metadata about cached waveform files including size and modification time.
    Useful for monitoring cache usage and debugging.
    
    ## Example
    
    ```bash
    curl "http://localhost:8000/api/v1/waveforms/list?limit=50"
    ```
    """
    WAVEFORM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    files = []
    for cache_file in sorted(WAVEFORM_CACHE_DIR.glob("*.json"))[:limit]:
        try:
            stat = cache_file.stat()
            files.append({
                "name": cache_file.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": stat.st_mtime
            })
        except Exception:
            pass
    
    return {
        "cache_dir": str(WAVEFORM_CACHE_DIR),
        "count": len(files),
        "files": files
    }


@router.delete("/clear")
async def clear_waveform_cache(
    older_than_days: Optional[int] = Query(None, description="Only clear files older than N days")
):
    """
    Clear the waveform cache.
    
    Deletes cached waveform files to free disk space. Optionally filter
    by age to keep recent waveforms.
    
    ## Examples
    
    ```bash
    # Clear all waveforms
    curl -X DELETE "http://localhost:8000/api/v1/waveforms/clear"
    
    # Clear waveforms older than 30 days
    curl -X DELETE "http://localhost:8000/api/v1/waveforms/clear?older_than_days=30"
    ```
    
    ## Warning
    
    Cleared waveforms will need to be regenerated when the QC interface is opened.
    """
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    
    try:
        from sync_analyzer.utils.waveform_generator import WaveformGenerator
        generator = WaveformGenerator(output_dir=WAVEFORM_CACHE_DIR)
        count = generator.clear_cache(older_than_days)
        
        return {
            "status": "success",
            "files_deleted": count
        }
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {e}")

