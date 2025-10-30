#!/usr/bin/env python3
"""
File management endpoints for browsing and uploading files.
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path as PathLib
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends, Path
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import mimetypes

from app.core.config import settings, get_file_type_info
from app.core.exceptions import FileValidationError, FileNotFoundError, FileTypeNotSupportedError
from app.models.sync_models import (
    FileListResponse, FileInfo, FileType, FileUploadRequest, FileUploadResponse, DirectoryInfo
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=FileListResponse)
async def list_files(
    path: str = Query(settings.MOUNT_PATH, description="Directory path to list")
):
    """
    List files and directories in the specified path.
    
    This endpoint provides a file browser interface for navigating the file system
    and discovering audio/video files for sync analysis.
    
    ## Query Parameters
    
    * **path**: Directory path to list (default: mount path)
    
    ## Supported File Types
    
    * **Audio**: .wav, .mp3, .flac, .m4a, .aiff, .ogg
    * **Video**: .mov, .mp4, .avi, .mkv, .wmv
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "files": [
        {
          "id": "file_123",
          "name": "master_audio.wav",
          "path": "/mnt/data/audio/master_audio.wav",
          "type": "audio",
          "size": 10485760,
          "extension": ".wav",
          "created_at": "2025-08-27T19:00:00Z",
          "modified_at": "2025-08-27T19:00:00Z",
          "duration_seconds": 120.5,
          "sample_rate": 48000,
          "bit_depth": 24,
          "channels": 2
        }
      ],
      "directories": [
        {
          "name": "audio_files",
          "path": "/mnt/data/audio_files",
          "item_count": 25
        }
      ],
      "current_path": "/mnt/data/audio",
      "parent_path": "/mnt/data",
      "total_count": 26,
      "timestamp": "2025-08-27T19:00:00Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/files/?path=/mnt/data/audio"
    ```
    """
    try:
        # Validate path is safe
        if not _is_safe_path(path):
            raise FileValidationError("Invalid or unsafe path", file_path=path)
        
        # Check if path exists
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        
        if not os.path.isdir(path):
            raise FileValidationError("Path is not a directory", file_path=path)
        
        # Get file type information
        file_types = get_file_type_info()
        
        files = []
        directories = []
        
        # List directory contents
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            
            try:
                if os.path.isdir(item_path):
                    # Directory
                    try:
                        item_count = len(os.listdir(item_path))
                    except (OSError, PermissionError):
                        item_count = 0
                    
                    directories.append(DirectoryInfo(
                        name=item,
                        path=item_path,
                        item_count=item_count,
                        created_at=datetime.fromtimestamp(os.path.getctime(item_path)),
                        modified_at=datetime.fromtimestamp(os.path.getmtime(item_path))
                    ))
                elif os.path.isfile(item_path):
                    # File
                    file_ext = PathLib(item).suffix.lower()
                    if file_ext in settings.ALLOWED_EXTENSIONS:
                        file_info = await _get_file_info(item_path, item, file_ext)
                        files.append(file_info)
            except (OSError, PermissionError) as e:
                logger.warning(f"Error accessing {item_path}: {e}")
                continue
        
        # Calculate parent path
        parent_path = str(PathLib(path).parent) if PathLib(path).parent != PathLib(path) else None
        
        # Sort results
        files.sort(key=lambda x: x.name.lower())
        directories.sort(key=lambda x: x.name.lower())
        
        return FileListResponse(
            files=files,
            directories=directories,
            current_path=path,
            parent_path=parent_path,
            total_count=len(files) + len(directories),
            message=f"Retrieved {len(files)} files and {len(directories)} directories"
        )
        
    except (FileValidationError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    file_type: Optional[FileType] = Form(None, description="File type (auto-detected if not specified)"),
    description: Optional[str] = Form(None, description="File description"),
    tags: Optional[str] = Form(None, description="Comma-separated tags")
):
    """
    Upload an audio or video file for sync analysis.
    
    This endpoint allows you to upload audio/video files to the system for
    later use in sync analysis operations.
    
    ## Supported Formats
    
    * **Audio**: WAV, MP3, FLAC, M4A, AIFF, OGG
    * **Video**: MOV, MP4, AVI, MKV, WMV
    
    ## File Size Limits
    
    * Maximum file size: 1GB (configurable)
    * Recommended: Under 500MB for optimal performance
    
    ## Example Request
    
    ```bash
    curl -X POST "http://localhost:8000/api/v1/files/upload" \
      -F "file=@/path/to/audio.wav" \
      -F "file_type=audio" \
      -F "description=Master audio track for sync analysis" \
      -F "tags=master,audio,sync"
    ```
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "file_id": "file_abc123",
      "file_info": {
        "id": "file_abc123",
        "name": "master_audio.wav",
        "path": "/mnt/data/uploads/master_audio.wav",
        "type": "audio",
        "size": 10485760,
        "extension": ".wav"
      },
      "message": "File uploaded successfully",
      "timestamp": "2025-08-27T19:00:00Z"
    }
    ```
    """
    try:
        # Validate file
        if not file.filename:
            raise FileValidationError("No filename provided")
        
        # Check file size
        if file.size and file.size > settings.MAX_FILE_SIZE:
            raise FileValidationError(
                f"File size {file.size} bytes exceeds maximum allowed size {settings.MAX_FILE_SIZE} bytes",
                file_path=file.filename
            )
        
        # Determine file type
        file_ext = PathLib(file.filename).suffix.lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise FileTypeNotSupportedError(
                file.filename, file_ext, settings.ALLOWED_EXTENSIONS
            )
        
        # Auto-detect file type if not specified
        if not file_type:
            file_type = _detect_file_type(file_ext)
        
        # Generate unique filename
        file_id = f"file_{uuid.uuid4().hex[:8]}"
        safe_filename = f"{file_id}_{PathLib(file.filename).name}"
        upload_path = PathLib(settings.UPLOAD_DIR) / safe_filename
        
        # Ensure upload directory exists
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(upload_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Get file information
        file_info = await _get_file_info(str(upload_path), safe_filename, file_ext)
        
        # Store metadata (in production, this would go to a database)
        metadata = {
            "file_id": file_id,
            "original_filename": file.filename,
            "description": description,
            "tags": tags.split(",") if tags else [],
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_type": file_type.value if file_type else "unknown"
        }
        
        logger.info(f"File uploaded successfully: {file.filename} -> {upload_path}")
        
        return FileUploadResponse(
            file_id=file_id,
            file_info=file_info,
            message="File uploaded successfully"
        )
        
    except (FileValidationError, FileTypeNotSupportedError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/probe")
async def probe_file(path: str = Query(..., description="Absolute path under mount to probe with ffprobe")):
    """Run ffprobe on a file and return detailed codec/container info.

    Returns a JSON payload including `format` and `streams` from ffprobe. This is
    useful to determine why browser playback fails (e.g., AC-3/E-AC-3 in MOV/MP4).
    """
    if not _is_safe_path(path):
        raise HTTPException(status_code=400, detail="Invalid or unsafe path")
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        import subprocess, json, shutil
        ffprobe_bin = shutil.which("ffprobe") or "/home/linuxbrew/.linuxbrew/bin/ffprobe"
        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"ffprobe failed: {proc.stderr.strip()}")
        data = json.loads(proc.stdout)
        # Convenience summary of first audio stream, if present
        audio = None
        video = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "audio" and audio is None:
                audio = {
                    "codec_name": s.get("codec_name"),
                    "codec_long_name": s.get("codec_long_name"),
                    "sample_rate": s.get("sample_rate"),
                    "channels": s.get("channels"),
                    "channel_layout": s.get("channel_layout"),
                    "bit_rate": s.get("bit_rate"),
                    "profile": s.get("profile"),
                    "codec_tag": s.get("codec_tag_string"),
                }
            elif s.get("codec_type") == "video" and video is None:
                # Extract frame rate from r_frame_rate or avg_frame_rate
                fps_str = s.get("r_frame_rate") or s.get("avg_frame_rate") or "0/1"
                try:
                    num, den = map(int, fps_str.split('/'))
                    fps = round(num / den, 3) if den != 0 else 0
                except:
                    fps = 0
                video = {
                    "codec_name": s.get("codec_name"),
                    "width": s.get("width"),
                    "height": s.get("height"),
                    "frame_rate": fps,
                    "r_frame_rate": s.get("r_frame_rate"),
                    "avg_frame_rate": s.get("avg_frame_rate"),
                }
        return JSONResponse({
            "success": True,
            "path": path,
            "format": data.get("format"),
            "streams": data.get("streams"),
            "audio_summary": audio,
            "video_summary": video,
        })
    except Exception as e:
        logger.error(f"Error probing file {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/proxy-audio")
async def proxy_audio(
    path: str = Query(..., description="Absolute path under mount to transcode/stream as browser-friendly audio"),
    format: str = Query("wav", description="Output format: wav|mp4|webm|opus|aac")
):
    """Transcode source file's audio track to a browser-friendly audio stream.

    Defaults to WAV (PCM) for maximum compatibility. For compressed output:
    - format=mp4 (AAC in fragmented MP4)
    - format=aac (raw ADTS AAC)
    - format=webm or opus (Opus in WebM)
    """
    if not _is_safe_path(path):
        raise HTTPException(status_code=400, detail="Invalid or unsafe path")
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    fmt = format.lower()
    if fmt not in {"wav", "mp4", "webm", "opus", "aac"}:
        raise HTTPException(status_code=400, detail="Unsupported target format")
    try:
        import subprocess, shutil
        ffmpeg_bin = shutil.which("ffmpeg") or "/home/linuxbrew/.linuxbrew/bin/ffmpeg"
        args = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "2", "-ar", "48000"]
        media_type = "audio/wav"
        if fmt == "wav":
            args += ["-f", "wav", "-acodec", "pcm_s16le", "pipe:1"]
            media_type = "audio/wav"
        elif fmt == "mp4":
            args += ["-c:a", "aac", "-b:a", "192k", "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1"]
            media_type = "audio/mp4"
        elif fmt == "aac":
            args += ["-c:a", "aac", "-b:a", "192k", "-f", "adts", "pipe:1"]
            media_type = "audio/aac"
        elif fmt in {"webm", "opus"}:
            args += ["-c:a", "libopus", "-b:a", "128k", "-f", "webm", "pipe:1"]
            media_type = "audio/webm"

        proc = subprocess.Popen(args, stdout=subprocess.PIPE)

        def _iter():
            try:
                while True:
                    chunk = proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                try:
                    proc.terminate()
                except Exception:
                    pass

        return StreamingResponse(_iter(), media_type=media_type)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffmpeg not found in PATH")
    except Exception as e:
        logger.error(f"Error proxying audio for {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/raw")
async def get_raw_file(path: str = Query(..., description="Absolute path under mount to stream")):
    """Serve a raw file from the mounted data directory (read-only).

    Security: the path must resolve under settings.MOUNT_PATH. This is intended for
    local development or trusted environments to let the web UI fetch audio/video
    for playback/visualization.
    """
    try:
        if not _is_safe_path(path):
            raise FileValidationError("Invalid or unsafe path", file_path=path)
        if not os.path.exists(path) or not os.path.isfile(path):
            raise FileNotFoundError(path)
        media_type, _ = mimetypes.guess_type(path)
        return FileResponse(path, media_type=media_type or 'application/octet-stream', filename=os.path.basename(path))
    except (FileValidationError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error serving raw file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(
    file_id: str = Path(..., description="File identifier")
):
    """
    Get detailed information about a specific file.
    
    This endpoint returns comprehensive information about a file, including
    audio/video metadata if available.
    
    ## Example Response
    
    ```json
    {
      "id": "file_abc123",
      "name": "master_audio.wav",
      "path": "/mnt/data/uploads/master_audio.wav",
      "type": "audio",
      "size": 10485760,
      "extension": ".wav",
      "created_at": "2025-08-27T19:00:00Z",
      "modified_at": "2025-08-27T19:00:00Z",
      "duration_seconds": 120.5,
      "sample_rate": 48000,
      "bit_depth": 24,
      "channels": 2
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/files/file_abc123"
    ```
    """
    try:
        # In production, this would query a database
        # For now, search in upload directory
        upload_dir = PathLib(settings.UPLOAD_DIR)
        
        for file_path in upload_dir.glob(f"*_{file_id}_*"):
            if file_path.is_file():
                file_info = await _get_file_info(
                    str(file_path),
                    file_path.name,
                    file_path.suffix.lower()
                )
                return file_info
        
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{file_id}", response_model=dict)
async def delete_file(
    file_id: str = Path(..., description="File identifier")
):
    """
    Delete a file from the system.
    
    This endpoint removes a file and its associated metadata from the system.
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "message": "File deleted successfully",
      "file_id": "file_abc123",
      "timestamp": "2025-08-27T19:00:00Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/files/file_abc123"
    ```
    """
    try:
        # In production, this would query a database
        # For now, search in upload directory
        upload_dir = PathLib(settings.UPLOAD_DIR)
        
        for file_path in upload_dir.glob(f"*_{file_id}_*"):
            if file_path.is_file():
                file_path.unlink()
                logger.info(f"File deleted: {file_path}")
                
                return {
                    "success": True,
                    "message": "File deleted successfully",
                    "file_id": file_id
                }
        
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
def _is_safe_path(path: str) -> bool:
    """Check if path is safe and within allowed directory."""
    try:
        resolved = PathLib(path).resolve()
        mount_resolved = PathLib(settings.MOUNT_PATH).resolve()
        return str(resolved).startswith(str(mount_resolved))
    except:
        return False

def _detect_file_type(file_ext: str) -> FileType:
    """Detect file type from extension."""
    audio_exts = [".wav", ".mp3", ".flac", ".m4a", ".aiff", ".ogg"]
    video_exts = [".mov", ".mp4", ".avi", ".mkv", ".wmv"]
    
    if file_ext in audio_exts:
        return FileType.AUDIO
    elif file_ext in video_exts:
        return FileType.VIDEO
    else:
        return FileType.UNKNOWN

async def _get_file_info(file_path: str, filename: str, file_ext: str) -> FileInfo:
    """Get comprehensive file information."""
    try:
        stat = os.stat(file_path)
        
        # Basic file info
        file_info = FileInfo(
            id=filename,  # In production, this would be a proper ID
            name=filename,
            path=file_path,
            type=_detect_file_type(file_ext),
            size=stat.st_size,
            extension=file_ext,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime)
        )
        
        # Try to extract audio/video metadata
        if file_info.type in [FileType.AUDIO, FileType.VIDEO]:
            metadata = await _extract_media_metadata(file_path)
            if metadata:
                file_info.duration_seconds = metadata.get("duration")
                file_info.sample_rate = metadata.get("sample_rate")
                file_info.bit_depth = metadata.get("bit_depth")
                file_info.channels = metadata.get("channels")
        
        return file_info
        
    except Exception as e:
        logger.warning(f"Error getting file info for {file_path}: {e}")
        # Return basic info if metadata extraction fails
        stat = os.stat(file_path)
        return FileInfo(
            id=filename,
            name=filename,
            path=file_path,
            type=_detect_file_type(file_ext),
            size=stat.st_size,
            extension=file_ext,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime)
        )

async def _extract_media_metadata(file_path: str) -> Optional[dict]:
    """Extract comprehensive media metadata including SMPTE timecode information."""
    try:
        # Import SMPTE utilities
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        from smpte_utils import SMPTEUtils
        
        # Use enhanced SMPTE-aware metadata extraction
        metadata = SMPTEUtils.extract_media_metadata(file_path)
        
        if "error" in metadata:
            logger.debug(f"SMPTE metadata extraction failed for {file_path}: {metadata['error']}")
            return None
        
        # Convert to format expected by API
        api_metadata = {}
        
        # Basic metadata
        if "duration" in metadata:
            api_metadata["duration"] = metadata["duration"]
        if "size" in metadata:
            api_metadata["file_size"] = metadata["size"]
        if "bit_rate" in metadata:
            api_metadata["bit_rate"] = metadata["bit_rate"]
        if "format_name" in metadata:
            api_metadata["format"] = metadata["format_name"]
        
        # Audio metadata
        if "audio_codec" in metadata:
            api_metadata["codec_name"] = metadata["audio_codec"]
        if "sample_rate" in metadata:
            api_metadata["sample_rate"] = metadata["sample_rate"]
        if "channels" in metadata:
            api_metadata["channels"] = metadata["channels"]
        if "channel_layout" in metadata:
            api_metadata["channel_layout"] = metadata["channel_layout"]
        
        # Video metadata (if available)
        if "video_codec" in metadata:
            api_metadata["video_codec"] = metadata["video_codec"]
        if "width" in metadata:
            api_metadata["width"] = metadata["width"]
        if "height" in metadata:
            api_metadata["height"] = metadata["height"]
        if "frame_rate" in metadata:
            api_metadata["frame_rate"] = metadata["frame_rate"]
        if "frame_rate_description" in metadata:
            api_metadata["frame_rate_description"] = metadata["frame_rate_description"]
        
        # SMPTE timecode information
        if "source_timecode" in metadata:
            api_metadata["source_timecode"] = metadata["source_timecode"]
        if "source_start_seconds" in metadata:
            api_metadata["source_start_seconds"] = metadata["source_start_seconds"]
        if "source_timecode_parsed" in metadata:
            tc = metadata["source_timecode_parsed"]
            api_metadata["smpte_timecode"] = {
                "hours": tc.hours,
                "minutes": tc.minutes,
                "seconds": tc.seconds,
                "frames": tc.frames,
                "frame_rate": tc.frame_rate,
                "drop_frame": tc.drop_frame,
                "formatted": str(tc)
            }
        
        return api_metadata
        
    except Exception as e:
        logger.debug(f"Could not extract metadata for {file_path}: {e}")
        return None
