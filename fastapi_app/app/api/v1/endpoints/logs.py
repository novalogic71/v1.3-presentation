"""
Real-Time Log Streaming API
===========================

Provides endpoints to fetch and stream Celery worker logs
for the dashboard log viewer.
"""

import os
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from collections import deque
import re
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Path to Celery log file
# logs.py is in fastapi_app/app/api/v1/endpoints/, need to go up 6 levels to project root
LOG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
    "logs", "celery.log"
)

# In-memory log buffer for fast access (last 500 lines)
log_buffer: deque = deque(maxlen=500)
last_read_position: int = 0


class LogEntry(BaseModel):
    """A single log entry."""
    timestamp: str
    level: str
    process: str
    message: str
    raw: str


class LogResponse(BaseModel):
    """Response containing log entries."""
    entries: List[LogEntry]
    total_lines: int
    log_file: str
    has_more: bool


def parse_celery_log_line(line: str) -> Optional[LogEntry]:
    """Parse a Celery log line into structured format."""
    # Celery log format: [2026-01-10 23:25:42,209: INFO/MainProcess] message
    pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+): (\w+)/(\w+)\] (.+)'
    match = re.match(pattern, line.strip())
    
    if match:
        return LogEntry(
            timestamp=match.group(1),
            level=match.group(2),
            process=match.group(3),
            message=match.group(4),
            raw=line.strip()
        )
    
    # Fallback for non-standard lines (tracebacks, etc.)
    if line.strip():
        return LogEntry(
            timestamp="",
            level="INFO",
            process="",
            message=line.strip(),
            raw=line.strip()
        )
    
    return None


def read_log_tail(lines: int = 100, level_filter: Optional[str] = None) -> List[LogEntry]:
    """Read the last N lines from the log file."""
    entries = []
    
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return []
        
        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            # Read all lines and get the last N
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            for line in recent_lines:
                entry = parse_celery_log_line(line)
                if entry:
                    # Apply level filter
                    if level_filter:
                        if level_filter.upper() == "ERROR" and entry.level not in ["ERROR", "CRITICAL"]:
                            continue
                        elif level_filter.upper() == "WARNING" and entry.level not in ["ERROR", "CRITICAL", "WARNING"]:
                            continue
                        elif level_filter.upper() == "DEBUG":
                            pass  # Show all
                    entries.append(entry)
    
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
    
    return entries


def read_new_logs() -> List[LogEntry]:
    """Read only new log lines since last check (for polling)."""
    global last_read_position
    entries = []
    
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return []
        
        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            # Check file size
            f.seek(0, 2)  # Go to end
            current_size = f.tell()
            
            # If file was truncated, reset position
            if current_size < last_read_position:
                last_read_position = 0
            
            # Read from last position
            f.seek(last_read_position)
            new_lines = f.readlines()
            last_read_position = f.tell()
            
            for line in new_lines:
                entry = parse_celery_log_line(line)
                if entry:
                    entries.append(entry)
                    log_buffer.append(entry)
    
    except Exception as e:
        logger.error(f"Error reading new logs: {e}")
    
    return entries


@router.get("/tail", response_model=LogResponse)
async def get_log_tail(
    lines: int = Query(100, ge=10, le=500, description="Number of lines to return"),
    level: Optional[str] = Query(None, description="Filter by level: DEBUG, INFO, WARNING, ERROR")
):
    """
    Get the last N lines from the Celery log file.
    
    Use this for initial load of the log viewer.
    """
    entries = read_log_tail(lines, level)
    
    return LogResponse(
        entries=entries,
        total_lines=len(entries),
        log_file=LOG_FILE_PATH,
        has_more=True
    )


@router.get("/poll")
async def poll_new_logs(
    level: Optional[str] = Query(None, description="Filter by level")
):
    """
    Poll for new log entries since last check.
    
    Use this for real-time updates (call every 1-2 seconds).
    """
    entries = read_new_logs()
    
    # Apply level filter
    if level:
        level_upper = level.upper()
        if level_upper == "ERROR":
            entries = [e for e in entries if e.level in ["ERROR", "CRITICAL"]]
        elif level_upper == "WARNING":
            entries = [e for e in entries if e.level in ["ERROR", "CRITICAL", "WARNING"]]
    
    return {
        "entries": [e.dict() for e in entries],
        "count": len(entries),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def get_log_status():
    """
    Get log file status and statistics.
    """
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return {
                "exists": False,
                "path": LOG_FILE_PATH,
                "error": "Log file not found"
            }
        
        stat = os.stat(LOG_FILE_PATH)
        
        # Count lines and get level distribution
        level_counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0}
        total_lines = 0
        
        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                total_lines += 1
                for level in level_counts:
                    if f": {level}/" in line:
                        level_counts[level] += 1
                        break
        
        return {
            "exists": True,
            "path": LOG_FILE_PATH,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "total_lines": total_lines,
            "level_counts": level_counts,
            "buffer_size": len(log_buffer)
        }
    
    except Exception as e:
        return {
            "exists": False,
            "path": LOG_FILE_PATH,
            "error": str(e)
        }


@router.post("/clear-buffer")
async def clear_log_buffer():
    """
    Clear the in-memory log buffer.
    
    Note: This doesn't clear the actual log file.
    """
    global last_read_position
    log_buffer.clear()
    last_read_position = 0
    
    return {"status": "cleared", "message": "Log buffer cleared"}

