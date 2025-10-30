#!/usr/bin/env python3
"""
Logging configuration for the FastAPI application.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from app.core.config import settings

def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
):
    """Setup logging configuration."""
    
    # Use settings if not provided
    log_level = log_level or settings.LOG_LEVEL
    log_file = log_file or settings.LOG_FILE
    log_format = log_format or settings.LOG_FORMAT
    
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log file specified)
    if log_file:
        try:
            # Resolve absolute paths and relocate if inside code dir during reload/dev
            code_dir = Path(__file__).resolve().parents[2]  # fastapi_app directory
            log_path = Path(log_file)
            if not log_path.is_absolute():
                log_path = (Path.cwd() / log_path)
            # If the log path is inside the code directory and DEBUG is on, relocate outside
            try:
                # raises ValueError if not under code_dir
                log_path.resolve().relative_to(code_dir)
                if settings.DEBUG:
                    safe_dir = code_dir.parent / "logs"
                    safe_dir.mkdir(parents=True, exist_ok=True)
                    log_path = safe_dir / log_path.name
                    logging.warning(
                        f"Relocating LOG_FILE to avoid reload loops: {log_path}"
                    )
            except Exception:
                # Not under code_dir or resolution failed; keep as-is
                pass
            # Ensure directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                str(log_path),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            logging.info(f"Logging to file: {log_path}")
            
        except Exception as e:
            logging.warning(f"Could not setup file logging: {e}")
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    # Log startup message
    logging.info(f"Logging configured - Level: {log_level}, File: {log_file or 'console only'}")
    
    return root_logger
