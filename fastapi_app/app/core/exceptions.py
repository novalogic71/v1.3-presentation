#!/usr/bin/env python3
"""
Custom exception classes for the Professional Audio Sync Analyzer API.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SyncAnalyzerException(Exception):
    """Base exception for sync analyzer errors."""
    
    def __init__(
        self,
        detail: str,
        error_code: str = "UNKNOWN_ERROR",
        status_code: int = 500,
        timestamp: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.timestamp = timestamp or datetime.utcnow()
        self.context = context or {}
        
        # Log the exception
        logger.error(
            f"SyncAnalyzerException: {error_code} - {detail}",
            extra={
                "error_code": error_code,
                "status_code": status_code,
                "context": context
            }
        )
        
        super().__init__(detail)

class FileValidationError(SyncAnalyzerException):
    """Raised when file validation fails."""
    
    def __init__(self, detail: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="FILE_VALIDATION_ERROR",
            status_code=400,
            context={"file_path": file_path},
            **kwargs
        )

class FileNotFoundError(SyncAnalyzerException):
    """Raised when a file is not found."""
    
    def __init__(self, file_path: str, **kwargs):
        super().__init__(
            detail=f"File not found: {file_path}",
            error_code="FILE_NOT_FOUND",
            status_code=404,
            context={"file_path": file_path},
            **kwargs
        )

class FileTypeNotSupportedError(SyncAnalyzerException):
    """Raised when file type is not supported."""
    
    def __init__(self, file_path: str, file_type: str, supported_types: list, **kwargs):
        super().__init__(
            detail=f"File type '{file_type}' not supported. Supported types: {', '.join(supported_types)}",
            error_code="FILE_TYPE_NOT_SUPPORTED",
            status_code=400,
            context={
                "file_path": file_path,
                "file_type": file_type,
                "supported_types": supported_types
            },
            **kwargs
        )

class FileSizeExceededError(SyncAnalyzerException):
    """Raised when file size exceeds maximum allowed size."""
    
    def __init__(self, file_path: str, file_size: int, max_size: int, **kwargs):
        super().__init__(
            detail=f"File size {file_size} bytes exceeds maximum allowed size {max_size} bytes",
            error_code="FILE_SIZE_EXCEEDED",
            status_code=400,
            context={
                "file_path": file_path,
                "file_size": file_size,
                "max_size": max_size
            },
            **kwargs
        )

class AnalysisError(SyncAnalyzerException):
    """Raised when sync analysis fails."""
    
    def __init__(self, detail: str, analysis_id: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="ANALYSIS_ERROR",
            status_code=500,
            context={"analysis_id": analysis_id},
            **kwargs
        )

class AnalysisMethodNotSupportedError(SyncAnalyzerException):
    """Raised when requested analysis method is not supported."""
    
    def __init__(self, method: str, supported_methods: list, **kwargs):
        super().__init__(
            detail=f"Analysis method '{method}' not supported. Supported methods: {', '.join(supported_methods)}",
            error_code="ANALYSIS_METHOD_NOT_SUPPORTED",
            status_code=400,
            context={
                "method": method,
                "supported_methods": supported_methods
            },
            **kwargs
        )

class AIModelError(SyncAnalyzerException):
    """Raised when AI model operations fail."""
    
    def __init__(self, detail: str, model_name: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="AI_MODEL_ERROR",
            status_code=500,
            context={"model_name": model_name},
            **kwargs
        )

class AIModelNotAvailableError(SyncAnalyzerException):
    """Raised when requested AI model is not available."""
    
    def __init__(self, model_name: str, available_models: list, **kwargs):
        super().__init__(
            detail=f"AI model '{model_name}' not available. Available models: {', '.join(available_models)}",
            error_code="AI_MODEL_NOT_AVAILABLE",
            status_code=400,
            context={
                "model_name": model_name,
                "available_models": available_models
            },
            **kwargs
        )

class FFmpegError(SyncAnalyzerException):
    """Raised when FFmpeg operations fail."""
    
    def __init__(self, detail: str, command: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="FFMPEG_ERROR",
            status_code=500,
            context={"command": command},
            **kwargs
        )

class ReportGenerationError(SyncAnalyzerException):
    """Raised when report generation fails."""
    
    def __init__(self, detail: str, analysis_id: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="REPORT_GENERATION_ERROR",
            status_code=500,
            context={"analysis_id": analysis_id},
            **kwargs
        )

class RateLimitExceededError(SyncAnalyzerException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, detail: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            context={"retry_after": retry_after},
            **kwargs
        )

class AuthenticationError(SyncAnalyzerException):
    """Raised when authentication fails."""
    
    def __init__(self, detail: str = "Authentication failed", **kwargs):
        super().__init__(
            detail=detail,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            **kwargs
        )

class AuthorizationError(SyncAnalyzerException):
    """Raised when authorization fails."""
    
    def __init__(self, detail: str = "Insufficient permissions", **kwargs):
        super().__init__(
            detail=detail,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            **kwargs
        )

class ValidationError(SyncAnalyzerException):
    """Raised when request validation fails."""
    
    def __init__(self, detail: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="VALIDATION_ERROR",
            status_code=422,
            context={"field": field},
            **kwargs
        )

class ResourceNotFoundError(SyncAnalyzerException):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        super().__init__(
            detail=f"{resource_type} with id '{resource_id}' not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            context={
                "resource_type": resource_type,
                "resource_id": resource_id
            },
            **kwargs
        )

class ResourceConflictError(SyncAnalyzerException):
    """Raised when there's a conflict with an existing resource."""
    
    def __init__(self, detail: str, resource_type: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="RESOURCE_CONFLICT",
            status_code=409,
            context={"resource_type": resource_type},
            **kwargs
        )

class ServiceUnavailableError(SyncAnalyzerException):
    """Raised when a required service is unavailable."""
    
    def __init__(self, detail: str, service_name: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
            context={"service_name": service_name},
            **kwargs
        )

class BatchProcessingError(SyncAnalyzerException):
    """Raised when batch processing operations fail."""
    
    def __init__(self, detail: str, batch_id: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail,
            error_code="BATCH_PROCESSING_ERROR",
            status_code=500,
            context={"batch_id": batch_id},
            **kwargs
        )

# Exception to HTTP exception conversion
def sync_analyzer_exception_to_http(exc: SyncAnalyzerException) -> HTTPException:
    """Convert SyncAnalyzerException to FastAPI HTTPException."""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": exc.detail,
            "error_code": exc.error_code,
            "timestamp": exc.timestamp.isoformat(),
            "context": exc.context
        }
    )
