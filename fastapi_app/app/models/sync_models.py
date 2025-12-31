#!/usr/bin/env python3
"""
Pydantic models for sync analysis requests and responses.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum

# Enums
class AnalysisMethod(str, Enum):
    """Available analysis methods."""
    MFCC = "mfcc"
    ONSET = "onset"
    SPECTRAL = "spectral"
    CORRELATION = "correlation"
    AI = "ai"

class ChannelStrategy(str, Enum):
    """How to handle multi-channel audio during analysis."""
    MONO_DOWNMIX = "mono_downmix"
    PER_CHANNEL = "per_channel"
    SELECTED = "selected"

class AIModel(str, Enum):
    """Available AI models."""
    WAV2VEC2 = "wav2vec2"
    YAMNET = "yamnet"
    SPECTRAL = "spectral"

class FileType(str, Enum):
    """File types."""
    AUDIO = "audio"
    VIDEO = "video"
    UNKNOWN = "unknown"

class AnalysisStatus(str, Enum):
    """Analysis status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Base Models
class BaseResponse(BaseModel):
    """Base response model."""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ErrorResponse(BaseResponse):
    """Error response model."""
    success: bool = False
    error: str
    error_code: str
    details: Optional[Dict[str, Any]] = None

# File Models
class FileInfo(BaseModel):
    """File information model."""
    id: str
    name: str
    path: str
    type: FileType
    size: int
    extension: str
    created_at: datetime
    modified_at: datetime
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    bit_depth: Optional[int] = None
    channels: Optional[int] = None
    
    class Config:
        json_json_schema_extra = {
            "example": {
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
        }

class FileUploadRequest(BaseModel):
    """File upload request model."""
    file_type: Optional[FileType] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    
    class Config:
        json_json_schema_extra = {
            "example": {
                "file_type": "audio",
                "description": "Master audio track for sync analysis",
                "tags": ["master", "audio", "sync"]
            }
        }

class FileUploadResponse(BaseResponse):
    """File upload response model."""
    file_id: str
    file_info: FileInfo
    upload_url: Optional[str] = None

# Analysis Models
class SyncAnalysisRequest(BaseModel):
    """Sync analysis request model."""
    master_file: str = Field(..., description="Path to master audio/video file")
    dub_file: str = Field(..., description="Path to dub audio/video file")
    methods: List[AnalysisMethod] = Field(
        default=[AnalysisMethod.MFCC],
        description="Analysis methods to use"
    )
    enable_ai: bool = Field(default=False, description="Enable AI-based detection")
    ai_model: Optional[AIModel] = Field(
        default=AIModel.WAV2VEC2,
        description="AI model to use for embedding extraction"
    )
    sample_rate: int = Field(
        default=22050,
        ge=8000,
        le=192000,
        description="Target sample rate for analysis"
    )
    window_size: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Analysis window size in seconds"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.1,
        le=1.0,
        description="Confidence threshold for reliable detection"
    )
    frame_rate: Optional[float] = Field(
        default=None,
        ge=1.0,
        description="Optional frame rate override for timecode conversions"
    )
    generate_plots: bool = Field(default=True, description="Generate visualization plots")
    output_format: str = Field(default="json", description="Output format (json, text, both)")
    # Multi-channel handling
    channel_strategy: ChannelStrategy = Field(
        default=ChannelStrategy.MONO_DOWNMIX,
        description="How to handle multi-channel audio"
    )
    channel_map: Optional[Dict[str, int]] = Field(
        default=None,
        description="Optional mapping of channel role to stream/channel index (e.g., {'FL':0,'FR':1})"
    )
    target_channels: Optional[List[str]] = Field(
        default=None,
        description="Subset of channel roles to analyze (e.g., ['FL','FR','FC'])"
    )
    # Optional runtime preferences (override server defaults)
    prefer_gpu: Optional[bool] = Field(
        default=None,
        description="If set, prefer enabling/disabling GPU for this request"
    )
    prefer_gpu_bypass_chunked: Optional[bool] = Field(
        default=None,
        description="If true and GPU available, bypass chunked analyzer up to server cap"
    )
    force_chunked: Optional[bool] = Field(
        default=None,
        description="If true, forces chunked analyzer regardless of GPU"
    )
    
    @validator('master_file', 'dub_file')
    def validate_file_paths(cls, v):
        """Validate file paths."""
        if not v:
            raise ValueError("File path cannot be empty")
        if not v.startswith('/'):
            raise ValueError("File path must be absolute")
        return v
    
    @validator('methods')
    def validate_methods(cls, v):
        """Validate analysis methods."""
        if not v:
            raise ValueError("At least one analysis method must be specified")
        return v
    
    @model_validator(mode='after')
    def validate_ai_settings(self):
        """Validate AI-related settings."""
        if self.enable_ai and not self.ai_model:
            raise ValueError("AI model must be specified when AI is enabled")
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "master_file": "/mnt/data/audio/master.wav",
                "dub_file": "/mnt/data/audio/dub.wav",
                "methods": ["mfcc", "onset"],
                "enable_ai": True,
                "ai_model": "wav2vec2",
                "sample_rate": 22050,
                "window_size": 30.0,
                "confidence_threshold": 0.8,
                "frame_rate": 23.976,
                "generate_plots": True,
                "output_format": "json",
                "channel_strategy": "mono_downmix"
            }
        }

class BatchAnalysisRequest(BaseModel):
    """Batch analysis request model."""
    file_pairs: List[Dict[str, str]] = Field(
        ...,
        description="List of master-dub file pairs",
        min_items=1,
        max_items=100
    )
    analysis_config: SyncAnalysisRequest = Field(
        ...,
        description="Analysis configuration for all pairs"
    )
    parallel_processing: bool = Field(
        default=True,
        description="Enable parallel processing of file pairs"
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum number of parallel workers"
    )
    
    @validator('file_pairs')
    def validate_file_pairs(cls, v):
        """Validate file pairs."""
        for pair in v:
            if 'master' not in pair or 'dub' not in pair:
                raise ValueError("Each file pair must have 'master' and 'dub' keys")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_pairs": [
                    {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"},
                    {"master": "/mnt/data/audio/master2.wav", "dub": "/mnt/data/audio/dub2.wav"}
                ],
                "analysis_config": {
                    "methods": ["mfcc"],
                    "sample_rate": 22050,
                    "window_size": 30.0
                },
                "parallel_processing": True,
                "max_workers": 4
            }
        }

# Analysis Result Models
class SyncOffset(BaseModel):
    """Sync offset information."""
    offset_seconds: float = Field(..., description="Offset in seconds")
    offset_samples: int = Field(..., description="Offset in samples")
    offset_frames: Dict[str, float] = Field(
        default_factory=dict,
        description="Offset in frames for different frame rates"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "offset_seconds": -2.456,
                "offset_samples": -54032,
                "offset_frames": {
                    "23.976": -58.9,
                    "24.0": -58.9,
                    "25.0": -61.4,
                    "29.97": -73.6,
                    "30.0": -73.7
                },
                "confidence": 0.94
            }
        }

class MethodResult(BaseModel):
    """Individual method analysis result."""
    method: AnalysisMethod
    offset: SyncOffset
    processing_time: float = Field(..., description="Processing time in seconds")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Method quality score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Method-specific metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "method": "mfcc",
                "offset": {
                    "offset_seconds": -2.456,
                    "offset_samples": -54032,
                    "confidence": 0.94
                },
                "processing_time": 3.2,
                "quality_score": 0.92,
                "metadata": {
                    "mfcc_coefficients": 13,
                    "window_size": 30.0
                }
            }
        }

class AIAnalysisResult(BaseModel):
    """AI-based analysis result."""
    model: AIModel
    embedding_similarity: float = Field(..., ge=0.0, le=1.0)
    temporal_consistency: float = Field(..., ge=0.0, le=1.0)
    model_confidence: float = Field(..., ge=0.0, le=1.0)
    processing_time: float = Field(..., description="Processing time in seconds")
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "model": "wav2vec2",
                "embedding_similarity": 0.87,
                "temporal_consistency": 0.91,
                "model_confidence": 0.89,
                "processing_time": 12.5,
                "model_metadata": {
                    "embedding_dim": 768,
                    "sample_rate": 16000
                }
            }
        }

class SyncAnalysisResult(BaseModel):
    """Complete sync analysis result."""
    analysis_id: str = Field(..., description="Unique analysis identifier")
    master_file: str = Field(..., description="Path to master file")
    dub_file: str = Field(..., description="Path to dub file")
    status: AnalysisStatus = Field(..., description="Analysis status")
    
    # Results
    consensus_offset: SyncOffset = Field(..., description="Consensus offset across all methods")
    method_results: List[MethodResult] = Field(..., description="Results from individual methods")
    ai_result: Optional[AIAnalysisResult] = Field(None, description="AI analysis result if enabled")
    
    # Metadata
    analysis_config: SyncAnalysisRequest = Field(..., description="Analysis configuration used")
    processing_time: float = Field(..., description="Total processing time in seconds")
    created_at: datetime = Field(..., description="Analysis creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Analysis completion timestamp")
    
    # Quality metrics
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    method_agreement: float = Field(..., ge=0.0, le=1.0, description="Agreement between methods")
    
    # Recommendations
    sync_status: str = Field(..., description="Human-readable sync status")
    recommendations: List[str] = Field(..., description="List of recommendations")
    
    # Timeline data for drift visualization (optional)
    timeline: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Per-segment timeline of offsets across the file"
    )
    chunk_details: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Raw per-chunk analysis details used to build the timeline"
    )
    combined_chunks: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Combined chunks when multi-pass refinement is used"
    )
    drift_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Aggregate drift metrics computed from the timeline"
    )
    operator_timeline: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Operator-friendly timeline view (contains 'scenes')"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "analysis_20250827_143052",
                "master_file": "/mnt/data/audio/master.wav",
                "dub_file": "/mnt/data/audio/dub.wav",
                "status": "completed",
                "consensus_offset": {
                    "offset_seconds": -2.456,
                    "offset_samples": -54032,
                    "confidence": 0.94
                },
                "method_results": [
                    {
                        "method": "mfcc",
                        "offset": {"offset_seconds": -2.456, "confidence": 0.94},
                        "processing_time": 3.2,
                        "quality_score": 0.92
                    }
                ],
                "overall_confidence": 0.94,
                "method_agreement": 0.95,
                "sync_status": "SYNC CORRECTION NEEDED",
                "recommendations": [
                    "Dub audio is 2.46 seconds behind master",
                    "High confidence in detection (94%)",
                    "Recommend audio correction using FFmpeg"
                ]
            }
        }

# Report Models
class AnalysisReport(BaseModel):
    """Analysis report model."""
    report_id: str = Field(..., description="Unique report identifier")
    analysis_result: SyncAnalysisResult = Field(..., description="Analysis result")
    report_format: str = Field(..., description="Report format (json, text, html)")
    generated_at: datetime = Field(..., description="Report generation timestamp")
    file_path: Optional[str] = Field(None, description="Path to saved report file")
    file_size: Optional[int] = Field(None, description="Report file size in bytes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "report_20250827_143052",
                "analysis_result": {
                    "analysis_id": "analysis_20250827_143052",
                    "status": "completed"
                },
                "report_format": "json",
                "generated_at": "2025-08-27T14:30:52Z",
                "file_path": "/reports/sync_report_20250827_143052.json",
                "file_size": 2048
            }
        }

# Response Models
class SyncAnalysisResponse(BaseResponse):
    """Sync analysis response model."""
    analysis_id: str
    status: AnalysisStatus
    result: Optional[SyncAnalysisResult] = None
    estimated_completion: Optional[datetime] = None
    progress: Optional[float] = Field(None, ge=0.0, le=100.0, description="Progress percentage")

class BatchAnalysisResponse(BaseResponse):
    """Batch analysis response model."""
    batch_id: str
    total_pairs: int
    completed_pairs: int
    failed_pairs: int
    results: List[SyncAnalysisResult] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

class AnalysisListResponse(BaseResponse):
    """Analysis list response model."""
    analyses: List[SyncAnalysisResult] = Field(default_factory=list)
    total_count: int
    page: int
    page_size: int
    total_pages: int

class ReportListResponse(BaseResponse):
    """Report list response model."""
    reports: List[AnalysisReport] = Field(default_factory=list)
    total_count: int
    page: int
    page_size: int
    total_pages: int

# File Management Models
class DirectoryInfo(BaseModel):
    """Directory information model."""
    name: str
    path: str
    item_count: int
    created_at: datetime
    modified_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "audio_files",
                "path": "/mnt/data/audio_files",
                "item_count": 25,
                "created_at": "2025-08-27T19:00:00Z",
                "modified_at": "2025-08-27T19:00:00Z"
            }
        }

class FileListResponse(BaseResponse):
    """File list response model."""
    files: List[FileInfo] = Field(default_factory=list)
    directories: List[DirectoryInfo] = Field(default_factory=list)
    current_path: str
    parent_path: Optional[str] = None
    total_count: int

# AI Models
class AIModelInfo(BaseModel):
    """AI model information."""
    name: AIModel
    display_name: str
    description: str
    embedding_dim: int
    sample_rate: int
    model_size: str
    best_for: List[str]
    is_available: bool
    load_time: Optional[float] = Field(None, description="Model load time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "wav2vec2",
                "display_name": "Wav2Vec2",
                "description": "Facebook's self-supervised speech representation model",
                "embedding_dim": 768,
                "sample_rate": 16000,
                "model_size": "~95MB",
                "best_for": ["Speech", "Voice content", "General audio"],
                "is_available": True,
                "load_time": 2.3
            }
        }

class AIAnalysisRequest(BaseModel):
    """AI analysis request model."""
    audio_file: str = Field(..., description="Path to audio file for analysis")
    model: AIModel = Field(..., description="AI model to use")
    extract_embeddings: bool = Field(default=True, description="Extract audio embeddings")
    analyze_sync: bool = Field(default=False, description="Perform sync analysis")
    reference_file: Optional[str] = Field(None, description="Reference file for sync analysis")
    
    @validator('audio_file')
    def validate_audio_file(cls, v):
        """Validate audio file path."""
        if not v:
            raise ValueError("Audio file path cannot be empty")
        if not v.startswith('/'):
            raise ValueError("Audio file path must be absolute")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_file": "/mnt/data/audio/sample.wav",
                "model": "wav2vec2",
                "extract_embeddings": True,
                "analyze_sync": False
            }
        }

# Health and Status Models
class HealthStatus(BaseModel):
    """Health status model."""
    status: str = Field(..., description="Overall health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component health status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "Professional Audio Sync Analyzer API",
                "version": "2.0.0",
                "timestamp": "2025-08-27T19:00:00Z",
                "components": {
                    "ffmpeg": {"status": "healthy", "version": "5.1.6"},
                    "ai_models": {"status": "healthy", "loaded_models": 3},
                    "file_system": {"status": "healthy", "mount_path": "/mnt/data"}
                }
            }
        }

class ComponentHealth(BaseModel):
    """Component health status."""
    status: str = Field(..., description="Component status")
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    last_check: datetime = Field(..., description="Last health check timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "Component is functioning normally",
                "details": {"version": "1.0.0", "uptime": "24h"},
                "last_check": "2025-08-27T19:00:00Z"
            }
        }

# Batch Processing Models
class BatchStatus(str, Enum):
    """Batch processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BatchItem(BaseModel):
    """Single batch analysis item."""
    item_id: str = Field(..., description="Unique item identifier")
    master_file: str = Field(..., description="Path to master file")
    dub_file: str = Field(..., description="Path to dub file")
    methods: List[AnalysisMethod] = Field(default=[AnalysisMethod.MFCC], description="Analysis methods")
    ai_model: Optional[AIModel] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: AnalysisStatus = Field(default=AnalysisStatus.PENDING)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "item_id": "item_001",
                "master_file": "/mnt/data/audio/master1.wav",
                "dub_file": "/mnt/data/audio/dub1.wav",
                "methods": ["mfcc", "ai"],
                "ai_model": "wav2vec2",
                "description": "Daily batch item 1",
                "tags": ["daily", "batch"],
                "status": "pending"
            }
        }

class BatchUploadRequest(BaseModel):
    """Batch CSV upload request."""
    description: Optional[str] = Field(None, description="Batch description")
    priority: str = Field(default="normal", description="Batch priority: low, normal, high")
    notification_webhook: Optional[str] = Field(None, description="Webhook URL for completion notifications")
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "Daily sync analysis batch",
                "priority": "normal",
                "notification_webhook": "https://your-server.com/webhook/batch-complete"
            }
        }

class BatchUploadResponse(BaseResponse):
    """Batch upload response."""
    batch_id: str = Field(..., description="Unique batch identifier")
    items_count: int = Field(..., description="Number of items in batch")
    items: List[BatchItem] = Field(..., description="Batch items")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "batch_id": "batch_20250828_140600",
                "items_count": 3,
                "message": "Batch uploaded successfully",
                "timestamp": "2025-08-28T14:06:00Z"
            }
        }

class BatchStartRequest(BaseModel):
    """Request to start batch processing."""
    parallel_jobs: int = Field(default=2, ge=1, le=8, description="Number of parallel jobs")
    priority: str = Field(default="normal", description="Processing priority")
    notification_webhook: Optional[str] = Field(None, description="Webhook URL for notifications")
    
    class Config:
        json_schema_extra = {
            "example": {
                "parallel_jobs": 2,
                "priority": "normal",
                "notification_webhook": "https://your-server.com/webhook/batch-complete"
            }
        }

class BatchStatusResponse(BaseResponse):
    """Batch status response."""
    batch_id: str = Field(..., description="Batch identifier")
    status: BatchStatus = Field(..., description="Current batch status")
    progress: float = Field(..., ge=0.0, le=100.0, description="Progress percentage")
    items_total: int = Field(..., description="Total number of items")
    items_completed: int = Field(..., description="Number of completed items")
    items_processing: int = Field(..., description="Number of items currently processing")
    items_failed: int = Field(..., description="Number of failed items")
    items_details: Optional[List[BatchItem]] = Field(None, description="Detailed item status")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "batch_id": "batch_20250828_140600",
                "status": "processing",
                "progress": 66.7,
                "items_total": 3,
                "items_completed": 2,
                "items_processing": 1,
                "items_failed": 0,
                "estimated_completion": "2025-08-28T14:18:00Z",
                "timestamp": "2025-08-28T14:10:00Z"
            }
        }

class BatchResultSummary(BaseModel):
    """Batch result summary."""
    items_total: int = Field(..., description="Total number of items")
    items_completed: int = Field(..., description="Successfully completed items")
    items_failed: int = Field(..., description="Failed items")
    average_confidence: float = Field(..., description="Average confidence score")
    processing_time_seconds: float = Field(..., description="Total processing time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "items_total": 3,
                "items_completed": 3,
                "items_failed": 0,
                "average_confidence": 0.923,
                "processing_time_seconds": 847
            }
        }

class BatchResultsResponse(BaseResponse):
    """Batch results response."""
    batch_id: str = Field(..., description="Batch identifier")
    status: BatchStatus = Field(..., description="Final batch status")
    summary: BatchResultSummary = Field(..., description="Results summary")
    results: List[BatchItem] = Field(..., description="Individual results")
    download_links: Dict[str, str] = Field(..., description="Download links for reports")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "batch_id": "batch_20250828_140600",
                "status": "completed",
                "summary": {
                    "items_total": 3,
                    "items_completed": 3,
                    "items_failed": 0,
                    "average_confidence": 0.923,
                    "processing_time_seconds": 847
                },
                "download_links": {
                    "json_report": "/api/v1/reports/batch_20250828_140600.json",
                    "csv_export": "/api/v1/reports/batch_20250828_140600.csv"
                },
                "timestamp": "2025-08-28T14:20:30Z"
            }
        }
