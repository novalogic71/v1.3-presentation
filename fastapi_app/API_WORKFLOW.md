# Professional Audio Sync Analyzer - End-to-End API Workflow

This document provides complete end-to-end API request schemas and workflows for the Professional Audio Sync Analyzer system.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [File Management Workflow](#file-management-workflow)
4. [Single Analysis Workflow](#single-analysis-workflow)
5. [Batch Processing Workflow](#batch-processing-workflow)
6. [Waveform API Workflow](#-waveform-api-workflow-new)
7. [Backend Monitoring Workflow](#-backend-monitoring-workflow-new)
8. [Complete API Schema Reference](#complete-api-schema-reference)
9. [Error Handling](#error-handling)
10. [Best Practices](#best-practices)

---

## 🚀 Quick Start

### Base URL
```
http://localhost:8000/api/v1
```

### Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

---

## 🔐 Authentication

Currently, the API does not require authentication. In production environments, implement API key authentication:

```bash
# Future authentication header
Authorization: Bearer <your_api_key>
```

---

## 📁 File Management Workflow

### 1. List Available Files

**Endpoint:** `GET /files/`

```bash
curl -X GET "http://localhost:8000/api/v1/files/?path=/mnt/data/audio"
```

**Response Schema:**
```json
{
  "success": true,
  "files": [
    {
      "id": "file_abc123",
      "name": "master_audio.wav",
      "path": "/mnt/data/audio/master_audio.wav",
      "type": "audio",
      "size": 10485760,
      "extension": ".wav",
      "created_at": "2025-08-28T10:00:00Z",
      "modified_at": "2025-08-28T10:00:00Z",
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
      "item_count": 25,
      "created_at": "2025-08-28T09:00:00Z",
      "modified_at": "2025-08-28T10:00:00Z"
    }
  ],
  "current_path": "/mnt/data/audio",
  "parent_path": "/mnt/data",
  "total_count": 26,
  "timestamp": "2025-08-28T10:00:00Z"
}
```

### 2. Upload Files

**Endpoint:** `POST /files/upload`

```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/audio.wav" \
  -F "file_type=audio" \
  -F "description=Master audio track for sync analysis" \
  -F "tags=master,audio,sync"
```

**Response Schema:**
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
    "extension": ".wav",
    "duration_seconds": 120.5,
    "sample_rate": 48000,
    "bit_depth": 24,
    "channels": 2
  },
  "message": "File uploaded successfully",
  "timestamp": "2025-08-28T10:00:00Z"
}
```

---

## 🎯 Single Analysis Workflow

### 1. Start Sync Analysis

**Endpoint:** `POST /analysis/sync`

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "methods": ["mfcc", "onset", "spectral", "ai"],
    "ai_model": "wav2vec2",
    "confidence_threshold": 0.5,
    "max_offset_seconds": 60.0,
    "analysis_options": {
      "enable_quality_metrics": true,
      "enable_detailed_report": true,
      "frame_rate": null,
      "window_size": 2.0
    }
  }'
```

**Request Schema:**
```json
{
  "master_file": "string (required) - Path to master file",
  "dub_file": "string (required) - Path to dub file", 
  "methods": ["string"] (optional) - Analysis methods: mfcc, onset, spectral, ai",
  "ai_model": "string (optional) - AI model: wav2vec2, hubert, wavlm",
  "confidence_threshold": "number (optional) - Minimum confidence (0.0-1.0)",
  "max_offset_seconds": "number (optional) - Maximum offset to detect",
  "analysis_options": {
    "enable_quality_metrics": "boolean (optional)",
    "enable_detailed_report": "boolean (optional)", 
    "frame_rate": "number (optional) - Custom frame rate",
    "window_size": "number (optional) - Analysis window size"
  }
}
```

**Response Schema:**
```json
{
  "success": true,
  "analysis_id": "20250828_140530",
  "result": {
    "offset_seconds": -15.023,
    "confidence": 0.981,
    "quality_score": 0.972,
    "method_used": "AI (Wav2Vec2)",
    "analysis_methods": ["mfcc", "onset", "spectral", "ai"],
    "recommendations": [
      "High confidence result - offset is reliable",
      "Consider applying sync correction"
    ],
    "technical_details": {
      "all_methods": ["mfcc", "onset", "spectral", "ai"],
      "primary_method": "AI (Wav2Vec2)",
      "method_agreement": 0.95,
      "processing_time_seconds": 12.5
    }
  },
  "report_path": "/path/to/detailed/report.json",
  "timestamp": "2025-08-28T14:05:30Z"
}
```

### 2. Get Analysis Status

**Endpoint:** `GET /analysis/{analysis_id}/status`

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/20250828_140530/status"
```

**Response Schema:**
```json
{
  "success": true,
  "analysis_id": "20250828_140530",
  "status": "completed",
  "progress": 100,
  "result": {
    "offset_seconds": -15.023,
    "confidence": 0.981,
    "quality_score": 0.972,
    "method_used": "AI (Wav2Vec2)"
  },
  "timestamp": "2025-08-28T14:05:45Z"
}
```

---

## 📊 Batch Processing Workflow

### 1. Upload Batch CSV

**Endpoint:** `POST /analysis/batch/upload-csv`

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
  -F "file=@batch_analysis.csv" \
  -F "description=Daily sync analysis batch"
```

**CSV Format:**
```csv
master_file,dub_file,methods,ai_model,description,tags
/mnt/data/audio/master1.wav,/mnt/data/audio/dub1.wav,"mfcc,ai",wav2vec2,Daily batch item 1,"daily,batch"
/mnt/data/audio/master2.wav,/mnt/data/audio/dub2.wav,"onset,spectral",,"Daily batch item 2","daily,batch"
/mnt/data/audio/master3.wav,/mnt/data/audio/dub3.wav,ai,wav2vec2,Daily batch item 3,"daily,batch,priority"
```

**Response Schema:**
```json
{
  "success": true,
  "batch_id": "batch_20250828_140600",
  "items_count": 3,
  "items": [
    {
      "item_id": "item_001",
      "master_file": "/mnt/data/audio/master1.wav",
      "dub_file": "/mnt/data/audio/dub1.wav",
      "methods": ["mfcc", "ai"],
      "status": "queued"
    }
  ],
  "message": "Batch uploaded successfully",
  "timestamp": "2025-08-28T14:06:00Z"
}
```

### 2. Start Batch Processing

**Endpoint:** `POST /analysis/batch/{batch_id}/start`

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/start" \
  -H "Content-Type: application/json" \
  -d '{
    "parallel_jobs": 2,
    "priority": "normal",
    "notification_webhook": "https://your-server.com/webhook/batch-complete"
  }'
```

**Response Schema:**
```json
{
  "success": true,
  "batch_id": "batch_20250828_140600", 
  "status": "processing",
  "items_total": 3,
  "items_completed": 0,
  "items_failed": 0,
  "estimated_completion": "2025-08-28T14:20:00Z",
  "timestamp": "2025-08-28T14:06:15Z"
}
```

### 3. Monitor Batch Progress

**Endpoint:** `GET /analysis/batch/{batch_id}/status`

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/status"
```

**Response Schema:**
```json
{
  "success": true,
  "batch_id": "batch_20250828_140600",
  "status": "processing",
  "progress": 66.7,
  "items_total": 3,
  "items_completed": 2,
  "items_processing": 1,
  "items_failed": 0,
  "items_details": [
    {
      "item_id": "item_001",
      "status": "completed",
      "result": {
        "offset_seconds": -15.023,
        "confidence": 0.981,
        "method_used": "AI (Wav2Vec2)"
      }
    },
    {
      "item_id": "item_002", 
      "status": "processing",
      "progress": 45
    },
    {
      "item_id": "item_003",
      "status": "queued"
    }
  ],
  "estimated_completion": "2025-08-28T14:18:00Z",
  "timestamp": "2025-08-28T14:10:00Z"
}
```

### 4. Download Batch Results

**Endpoint:** `GET /analysis/batch/{batch_id}/results`

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/results" \
  -H "Accept: application/json"
```

**Response Schema:**
```json
{
  "success": true,
  "batch_id": "batch_20250828_140600",
  "status": "completed",
  "summary": {
    "items_total": 3,
    "items_completed": 3, 
    "items_failed": 0,
    "average_confidence": 0.923,
    "processing_time_seconds": 847
  },
  "results": [
    {
      "item_id": "item_001",
      "master_file": "/mnt/data/audio/master1.wav",
      "dub_file": "/mnt/data/audio/dub1.wav",
      "result": {
        "offset_seconds": -15.023,
        "confidence": 0.981,
        "quality_score": 0.972,
        "method_used": "AI (Wav2Vec2)"
      }
    }
  ],
  "download_links": {
    "json_report": "/api/v1/reports/batch_20250828_140600.json",
    "csv_export": "/api/v1/reports/batch_20250828_140600.csv",
    "detailed_report": "/api/v1/reports/batch_20250828_140600_detailed.pdf"
  },
  "timestamp": "2025-08-28T14:20:30Z"
}
```

---

## 📋 Complete API Schema Reference

### File Types
```typescript
enum FileType {
  AUDIO = "audio"
  VIDEO = "video" 
  UNKNOWN = "unknown"
}
```

### Analysis Methods
```typescript
enum AnalysisMethod {
  MFCC = "mfcc"           // Mel-frequency cepstral coefficients
  ONSET = "onset"         // Onset-based alignment
  SPECTRAL = "spectral"   // Spectral feature correlation
  AI = "ai"              // AI-based analysis
}
```

### AI Models
```typescript
enum AIModel {
  WAV2VEC2 = "wav2vec2"
  HUBERT = "hubert"
  WAVLM = "wavlm"
}
```

### Analysis Status
```typescript
enum AnalysisStatus {
  QUEUED = "queued"
  PROCESSING = "processing"
  COMPLETED = "completed"
  FAILED = "failed"
  CANCELLED = "cancelled"
}
```

### Batch Status  
```typescript
enum BatchStatus {
  UPLOADED = "uploaded"
  PROCESSING = "processing"
  COMPLETED = "completed" 
  FAILED = "failed"
  CANCELLED = "cancelled"
}
```

---

## ⚠️ Error Handling

### Standard Error Response
```json
{
  "success": false,
  "error": "Detailed error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2025-08-28T14:00:00Z",
  "request_id": "req_abc123"
}
```

### Common Error Codes
- `FILE_NOT_FOUND` - Specified file does not exist
- `INVALID_FILE_TYPE` - File type not supported
- `ANALYSIS_FAILED` - Sync analysis failed
- `INSUFFICIENT_CONFIDENCE` - Result below confidence threshold
- `TIMEOUT_EXCEEDED` - Analysis timed out
- `BATCH_NOT_FOUND` - Batch ID not found
- `INVALID_CSV_FORMAT` - CSV format validation failed

---

## 💡 Best Practices

### 1. File Management
- Upload files before analysis for better performance
- Use descriptive filenames and tags
- Check file compatibility with `/files/validate` endpoint

### 2. Analysis Configuration
- Start with default methods, then customize based on content type
- Use AI methods for highest accuracy when available
- Set appropriate confidence thresholds based on use case

### 3. Batch Processing
- Group related files in batches for efficiency
- Use parallel processing for large batches
- Monitor progress and handle failures gracefully

### 4. Error Handling
- Always check `success` field in responses
- Implement retry logic for transient failures
- Log request_id for debugging

### 5. Performance Optimization
- Cache frequently accessed file information
- Use streaming for large file uploads
- Implement pagination for large result sets

---

## 🔄 Cross-Browser Sync Workflow (NEW)

The batch queue is stored server-side in Redis, enabling real-time sync across all browser sessions.

### 1. Get Current Batch Queue

**Endpoint:** `GET /batch-queue`

```bash
curl -X GET "http://localhost:8000/api/v1/batch-queue"
```

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": 1234567890,
      "type": "componentized",
      "status": "completed",
      "master": {"path": "/mnt/data/master.mov", "name": "master.mov"},
      "components": [...],
      "result": {...}
    }
  ],
  "updated_at": "2026-01-09T12:00:00Z"
}
```

### 2. Save Batch Queue (Auto-synced from UI)

**Endpoint:** `POST /batch-queue`

```bash
curl -X POST "http://localhost:8000/api/v1/batch-queue" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [...],
    "clientId": "browser-abc123"
  }'
```

---

## 🔍 API Job Discovery Workflow (NEW)

Jobs submitted via API automatically appear in the UI batch queue.

### 1. Submit Job via API

**Endpoint:** `POST /analysis/componentized/async`

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/componentized/async" \
  -H "Content-Type: application/json" \
  -d '{
    "master": "/mnt/data/master.mov",
    "components": [
      {"path": "/mnt/data/Lt.wav", "label": "Lt"}
    ],
    "methods": ["gpu"],
    "offset_mode": "channel_aware"
  }'
```

**Response:**
```json
{
  "success": true,
  "job_id": "abc123-def456",
  "status": "queued"
}
```

### 2. Job Automatically Appears in UI

The UI polls `/api/v1/job-registry` every 10 seconds and adds new jobs to the batch queue.

### 3. Query Job Registry

**Endpoint:** `GET /job-registry`

```bash
curl -X GET "http://localhost:8000/api/v1/job-registry?since_hours=24"
```

**Response:**
```json
{
  "success": true,
  "jobs": [
    {
      "job_id": "abc123-def456",
      "type": "componentized",
      "status": "completed",
      "master_file": "/mnt/data/master.mov",
      "master_name": "master.mov",
      "component_count": 4,
      "progress": 100,
      "result": {...},
      "created_at": "2026-01-09T12:00:00Z",
      "source": "api"
    }
  ],
  "total": 1
}
```

---

## 📊 Backend Monitoring Workflow (NEW)

Monitor GPU, system resources, and job status via the dashboard API.

### 1. Get GPU Status

**Endpoint:** `GET /dashboard/gpu-info`

```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/gpu-info"
```

### 2. Get System Info

**Endpoint:** `GET /dashboard/system-info`

```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/system-info"
```

### 3. Get Celery Worker Status

**Endpoint:** `GET /dashboard/celery-info`

```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/celery-info"
```

---

## 🎵 Waveform API Workflow (NEW)

Pre-generated waveforms enable instant QC visualization without needing to decode audio files in the browser.

### 1. Get Waveforms by Analysis ID

**Endpoint:** `GET /waveforms/analysis/{analysis_id}`

```bash
curl -X GET "http://localhost:8000/api/v1/waveforms/analysis/analysis_20250109_120000_abc123"
```

**Response:**
```json
{
  "analysis_id": "analysis_20250109_120000_abc123",
  "master": {
    "source_path": "/mnt/data/master.mp4",
    "source_name": "master.mp4",
    "duration": 120.5,
    "sample_rate": 22050,
    "width": 2000,
    "peaks": [0.1, 0.2, 0.15, ...],
    "rms": [0.05, 0.1, 0.08, ...],
    "generated_at": "2025-01-09T12:00:00Z"
  },
  "dub": {
    "source_path": "/mnt/data/dub.mxf",
    "source_name": "dub.mxf",
    "duration": 120.5,
    "sample_rate": 22050,
    "width": 2000,
    "peaks": [0.12, 0.18, 0.14, ...],
    "rms": [0.06, 0.09, 0.07, ...],
    "generated_at": "2025-01-09T12:00:00Z"
  },
  "generated_at": "2025-01-09T12:00:00Z"
}
```

### 2. Generate Waveforms Manually

**Endpoint:** `POST /waveforms/generate`

```bash
curl -X POST "http://localhost:8000/api/v1/waveforms/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "master_path": "/mnt/data/project/master.mp4",
    "dub_path": "/mnt/data/project/dub.mxf",
    "analysis_id": "analysis_20250109_120000_abc123",
    "force_regenerate": false
  }'
```

### 3. Generate Waveforms (Background)

**Endpoint:** `POST /waveforms/generate-async`

Returns immediately while waveform generation runs in background.

```bash
curl -X POST "http://localhost:8000/api/v1/waveforms/generate-async" \
  -H "Content-Type: application/json" \
  -d '{
    "master_path": "/mnt/data/project/master.mp4",
    "dub_path": "/mnt/data/project/dub.mxf",
    "analysis_id": "analysis_20250109_120000_abc123"
  }'
```

### 4. List Cached Waveforms

**Endpoint:** `GET /waveforms/list`

```bash
curl -X GET "http://localhost:8000/api/v1/waveforms/list?limit=50"
```

### 5. Clear Waveform Cache

**Endpoint:** `DELETE /waveforms/clear`

```bash
# Clear all waveforms
curl -X DELETE "http://localhost:8000/api/v1/waveforms/clear"

# Clear waveforms older than 30 days
curl -X DELETE "http://localhost:8000/api/v1/waveforms/clear?older_than_days=30"
```

### Waveform Notes

- Waveforms are automatically generated after analysis completes
- Cache files are small (~50-100KB each) and load instantly
- Stored in `waveform_cache/` directory
- Use `generate_all_waveforms.py` to batch-generate for existing analyses

---

## 🔗 Related Documentation

- [API Reference](./README.md) - Complete API documentation
- [CURL Examples](./CURL_EXAMPLES.md) - Ready-to-use CURL commands
- [Docker Setup](./Dockerfile) - Containerization guide

---

## 📞 Support

For technical support or questions:
- GitHub Issues: [Submit an issue](https://github.com/novalogic71/Sync_dub_final/issues)
- Email: support@sync-analyzer.com
- Documentation: [Full API Docs](http://localhost:8000/docs)

---

*Generated on 2026-01-09 | Version 1.3.0*