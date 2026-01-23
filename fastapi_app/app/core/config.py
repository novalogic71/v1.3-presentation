#!/usr/bin/env python3
"""
Configuration management for the Professional Audio Sync Analyzer API.
"""

import os
import logging
from typing import List, Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import validator, Field

class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    APP_NAME: str = "Professional Audio Sync Analyzer API"
    VERSION: str = "2.0.0"
    BUILD_ID: Optional[str] = Field(default=None, env="BUILD_ID")
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # Security settings
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    ALLOWED_HOSTS: List[str] = Field(default=["*"], env="ALLOWED_HOSTS")
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:8000",
            "http://10.124.201.10:3002",
        ],
        env="ALLOWED_ORIGINS"
    )
    CORS_ORIGIN_REGEX: str = Field(
        default=(
            r"^https?://(localhost|127\.0\.0\.1|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?$"
        ),
        env="CORS_ORIGIN_REGEX"
    )
    
    # File system settings
    MOUNT_PATH: str = Field(default="/mnt/data", env="MOUNT_PATH")
    UPLOAD_DIR: str = Field(default="./uploads", env="UPLOAD_DIR")
    MAX_FILE_SIZE: int = Field(default=1024 * 1024 * 1024, env="MAX_FILE_SIZE")  # 1GB
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=[
            ".wav",
            ".mp3",
            ".flac",
            ".m4a",
            ".aiff",
            ".ogg",
            ".mov",
            ".mp4",
            ".avi",
            ".mkv",
            ".mxf",
            ".ec3",
            ".eac3",
            ".adm",
            ".iab",
        ],
        env="ALLOWED_EXTENSIONS"
    )
    
    # Analysis settings
    ENABLED_METHODS: List[str] = Field(
        # Include "ai" by default so AI can be triggered when enabled
        default=["mfcc", "onset", "spectral", "correlation", "ai"],
        env="ENABLED_METHODS"
    )
    ENABLED_AI_MODELS: List[str] = Field(
        default=["wav2vec2", "yamnet", "spectral"],
        env="ENABLED_AI_MODELS"
    )
    DEFAULT_SAMPLE_RATE: int = Field(default=22050, env="DEFAULT_SAMPLE_RATE")
    DEFAULT_WINDOW_SIZE: float = Field(default=30.0, env="DEFAULT_WINDOW_SIZE")
    DEFAULT_CONFIDENCE_THRESHOLD: float = Field(default=0.7, env="DEFAULT_CONFIDENCE_THRESHOLD")
    # Long-file handling
    LONG_FILE_THRESHOLD_SECONDS: float = Field(default=180.0, env="LONG_FILE_THRESHOLD_SECONDS")
    LONG_FILE_GPU_BYPASS: bool = Field(default=True, env="LONG_FILE_GPU_BYPASS")
    LONG_FILE_GPU_BYPASS_MAX_SECONDS: Optional[float] = Field(default=900.0, env="LONG_FILE_GPU_BYPASS_MAX_SECONDS")
    
    # AI settings
    AI_MODEL_CACHE_DIR: str = Field(default="./ai_models", env="AI_MODEL_CACHE_DIR")
    AI_WAV2VEC2_MODEL_PATH: Optional[str] = Field(default=None, env="AI_WAV2VEC2_MODEL_PATH")
    YAMNET_MODEL_PATH: Optional[str] = Field(default=None, env="YAMNET_MODEL_PATH")
    HF_LOCAL_ONLY: bool = Field(default=True, env="HF_LOCAL_ONLY")
    AI_ALLOW_ONLINE_MODELS: bool = Field(default=False, env="AI_ALLOW_ONLINE_MODELS")
    USE_GPU: bool = Field(default=True, env="USE_GPU")
    AI_BATCH_SIZE: int = Field(default=4, env="AI_BATCH_SIZE")
    DISABLE_AI_BATCH: bool = Field(default=False, env="DISABLE_AI_BATCH")
    
    # Database settings (for future use)
    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Rate limiting
    ENABLE_RATE_LIMITING: bool = Field(default=True, env="ENABLE_RATE_LIMITING")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # Caching
    ENABLE_CACHING: bool = Field(default=True, env="ENABLE_CACHING")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 1 hour
    
    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")
    
    @validator("MOUNT_PATH")
    def validate_mount_path(cls, v):
        """Validate mount path exists and is accessible."""
        path = Path(v)
        try:
            if not path.exists():
                logging.warning(f"MOUNT_PATH does not exist: {v} — continuing; related features may be degraded")
                return str(path)
            if not path.is_dir():
                logging.warning(f"MOUNT_PATH is not a directory: {v} — continuing; related features may be degraded")
                return str(path)
            return str(path.resolve())
        except Exception:
            # Never fail app startup due to MOUNT_PATH issues
            logging.warning(f"Could not validate MOUNT_PATH: {v} — continuing with provided value")
            return str(path)
    
    @validator("UPLOAD_DIR")
    def validate_upload_dir(cls, v):
        """Create upload directory if it doesn't exist."""
        path = Path(v)
        # Relocate outside code dir in DEBUG to avoid reload loops on file writes
        try:
            code_dir = Path(__file__).resolve().parents[2]
            if not path.is_absolute():
                abs_path = (Path.cwd() / path)
            else:
                abs_path = path
            try:
                abs_path.resolve().relative_to(code_dir)
                if str(os.getenv("DEBUG", str(False))).lower() in {"1", "true", "yes"}:
                    safe_dir = code_dir.parent / abs_path.name
                    logging.warning(f"Relocating UPLOAD_DIR to {safe_dir} to avoid reload loops")
                    path = safe_dir
            except Exception:
                pass
        except Exception:
            pass
        path.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())
    
    @validator("AI_MODEL_CACHE_DIR")
    def validate_ai_cache_dir(cls, v):
        """Create AI model cache directory if it doesn't exist."""
        path = Path(v)
        # Relocate outside code dir in DEBUG to avoid reload loops on model cache writes
        try:
            code_dir = Path(__file__).resolve().parents[2]
            if not path.is_absolute():
                abs_path = (Path.cwd() / path)
            else:
                abs_path = path
            try:
                abs_path.resolve().relative_to(code_dir)
                if str(os.getenv("DEBUG", str(False))).lower() in {"1", "true", "yes"}:
                    safe_dir = code_dir.parent / abs_path.name
                    logging.warning(f"Relocating AI_MODEL_CACHE_DIR to {safe_dir} to avoid reload loops")
                    path = safe_dir
            except Exception:
                pass
        except Exception:
            pass
        path.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())
    
    @validator("ALLOWED_EXTENSIONS")
    def validate_extensions(cls, v):
        """Validate file extensions start with dot."""
        for ext in v:
            if not ext.startswith("."):
                raise ValueError(f"Extension must start with dot: {ext}")
        return v
    
    @validator("ENABLED_METHODS")
    def validate_methods(cls, v):
        """Validate analysis methods."""
        valid_methods = ["mfcc", "onset", "spectral", "correlation", "ai"]
        for method in v:
            if method not in valid_methods:
                raise ValueError(f"Invalid method: {method}")
        return v
    
    @validator("ENABLED_AI_MODELS")
    def validate_ai_models(cls, v):
        """Validate AI models."""
        valid_models = ["wav2vec2", "yamnet", "spectral"]
        for model in v:
            if model not in valid_models:
                raise ValueError(f"Invalid AI model: {model}")
        return v
    
    class Config:
        # Resolve the .env relative to the fastapi_app root regardless of cwd
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Additional computed settings
def get_file_type_info() -> dict:
    """Get file type information for validation."""
    return {
        "audio": [".wav", ".mp3", ".flac", ".m4a", ".aiff", ".ogg"],
        "video": [".mov", ".mp4", ".avi", ".mkv", ".wmv"],
        "all": settings.ALLOWED_EXTENSIONS
    }

def get_analysis_methods() -> dict:
    """Get available analysis methods with descriptions."""
    return {
        "mfcc": {
            "name": "MFCC (Mel-Frequency Cepstral Coefficients)",
            "description": "Fast, reliable method for most content. Excellent for speech and music.",
            "analysis_time": "2-5 seconds",
            "accuracy": "High",
            "best_for": ["Speech", "Music", "General audio"]
        },
        "onset": {
            "name": "Onset Detection",
            "description": "Detects audio onset points for precise timing analysis.",
            "analysis_time": "3-7 seconds",
            "accuracy": "Medium-High",
            "best_for": ["Music", "Percussion", "Sharp sounds"]
        },
        "spectral": {
            "name": "Spectral Analysis",
            "description": "Frequency domain analysis for complex audio content.",
            "analysis_time": "5-10 seconds",
            "accuracy": "Medium",
            "best_for": ["Complex audio", "Background noise", "Mixed content"]
        },
        "correlation": {
            "name": "Cross-Correlation",
            "description": "Raw audio waveform analysis for pure audio content.",
            "analysis_time": "10-20 seconds",
            "accuracy": "Very High",
            "best_for": ["Pure audio", "Simple content", "High precision"]
        },
        "ai": {
            "name": "AI-Enhanced Detection",
            "description": "Machine learning-based detection using audio embeddings.",
            "analysis_time": "15-30 seconds",
            "accuracy": "Highest",
            "best_for": ["Complex scenarios", "Adaptive detection", "Professional use"]
        }
    }

def get_ai_models() -> dict:
    """Get available AI models with descriptions."""
    return {
        "wav2vec2": {
            "name": "Wav2Vec2",
            "description": "Facebook's self-supervised speech representation model",
            "embedding_dim": 768,
            "sample_rate": 16000,
            "best_for": ["Speech", "Voice content", "General audio"],
            "model_size": "~95MB"
        },
        "yamnet": {
            "name": "YAMNet",
            "description": "Google's audio event detection model",
            "embedding_dim": 1024,
            "sample_rate": 16000,
            "best_for": ["Audio events", "Sound classification", "Complex audio"],
            "model_size": "~15MB"
        },
        "spectral": {
            "name": "Spectral Embeddings",
            "description": "Custom spectral-based audio embeddings",
            "embedding_dim": 512,
            "sample_rate": 22050,
            "best_for": ["Music", "Instrumental content", "Fast analysis"],
            "model_size": "~5MB"
        }
    }
