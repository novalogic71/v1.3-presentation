# Professional Audio Sync Analyzer - End-to-End API Workflow

This document provides complete end-to-end API request schemas and workflows for the Professional Audio Sync Analyzer system.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [File Management Workflow](#file-management-workflow)
4. [Single Analysis Workflow](#single-analysis-workflow)
5. [Batch Processing Workflow](#batch-processing-workflow)
6. [Analyze-and-Repair Workflow](#analyze-and-repair-workflow)
7. [Per-Channel Repair Endpoint](#per-channel-repair-endpoint)
8. [Reports Workflow](#reports-workflow)
9. [UI State Management](#ui-state-management)
10. [Complete API Schema Reference](#complete-api-schema-reference)
11. [Error Handling](#error-handling)
12. [Best Practices](#best-practices)

---

## 🚀 Quick Start

### Base URL
```
http://localhost:8000/api/v1
```

### Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health/status"
```

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

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

### 3. Probe File with FFprobe

**Endpoint:** `GET /files/probe`

Returns detailed codec/container information for debugging playback issues.

```bash
curl -X GET "http://localhost:8000/api/v1/files/probe?path=/mnt/data/audio/master.mov"
```

**Response Schema:**
```json
{
  "success": true,
  "path": "/mnt/data/audio/master.mov",
  "format": {
    "filename": "/mnt/data/audio/master.mov",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "duration": "120.500000"
  },
  "streams": [...],
  "audio_summary": {
    "codec_name": "aac",
    "sample_rate": "48000",
    "channels": 2,
    "channel_layout": "stereo"
  },
  "video_summary": {
    "codec_name": "h264",
    "width": 1920,
    "height": 1080,
    "frame_rate": 23.976
  }
}
```

### 4. Proxy Audio Stream

**Endpoint:** `GET /files/proxy-audio`

Transcodes audio to browser-friendly format for playback. Supports Dolby Atmos files.

```bash
# Default WAV output (best compatibility)
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov&format=wav"

# AAC output for smaller size
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov&format=mp4"

# With role-based loudness adjustment
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov&role=dub"
```

**Parameters:**
- `path` (required): Absolute path to file under mount
- `format`: Output format - `wav` (default), `mp4`, `webm`, `opus`, `aac`
- `max_duration`: Max duration in seconds (default: 600)
- `role`: `master` or `dub` (dub gets +5dB boost for balance)

### 5. Get Raw File

**Endpoint:** `GET /files/raw`

Serves raw file for direct download/streaming.

```bash
curl -X GET "http://localhost:8000/api/v1/files/raw?path=/mnt/data/audio/master.wav"
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
  "status": "pending",
  "message": "Sync analysis started successfully",
  "timestamp": "2025-08-28T14:05:30Z"
}
```

### 2. Get Analysis Status

**Endpoint:** `GET /analysis/{analysis_id}`

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/20250828_140530"
```

**Response Schema (Processing):**
```json
{
  "success": true,
  "analysis_id": "20250828_140530",
  "status": "processing",
  "progress": 45.2,
  "message": "AI Analysis: Processing window 23/45",
  "estimated_completion": "2025-08-28T14:06:00Z",
  "timestamp": "2025-08-28T14:05:45Z"
}
```

**Response Schema (Completed):**
```json
{
  "success": true,
  "analysis_id": "20250828_140530",
  "status": "completed",
  "result": {
    "analysis_id": "20250828_140530",
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "consensus_offset": {
      "offset_seconds": -15.023,
      "offset_samples": -54032,
      "offset_frames": {
        "23.976": -58.9,
        "24.0": -58.9,
        "25.0": -61.4
      },
      "confidence": 0.981
    },
    "method_results": [...],
    "overall_confidence": 0.95,
    "sync_status": "❌ SYNC CORRECTION NEEDED (> 100ms)",
    "recommendations": [...]
  },
  "timestamp": "2025-08-28T14:05:52Z"
}
```

### 3. Stream Analysis Progress (SSE)

**Endpoint:** `GET /analysis/{analysis_id}/progress/stream`

Server-Sent Events stream for real-time progress updates.

```bash
curl -N "http://localhost:8000/api/v1/analysis/20250828_140530/progress/stream"
```

**Event Format:**
```
data: {"analysis_id": "20250828_140530", "status": "processing", "progress": 67.5, "status_message": "AI Analysis: Dub embeddings - Processing window 23/45"}

data: {"analysis_id": "20250828_140530", "status": "completed", "progress": 100}

event: end
data: {}
```

### 4. Get Analysis Timeline

**Endpoint:** `GET /analysis/sync/{analysis_id}/timeline`

Returns operator-friendly timeline data for visualization.

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/sync/20250828_140530/timeline"
```

**Response Schema:**
```json
{
  "success": true,
  "analysis_id": "20250828_140530",
  "timeline": {
    "scenes": [
      {
        "time_range": "00:00 - 00:30",
        "start_seconds": 0.0,
        "end_seconds": 30.0,
        "scene_type": "dialogue",
        "severity": "in_sync",
        "severity_indicator": "✅",
        "offset_seconds": 0.012,
        "reliability": "high",
        "repair_recommendation": "No action needed"
      }
    ]
  },
  "drift_summary": {
    "has_drift": false,
    "max_drift_ms": 12,
    "problematic_scenes": 0,
    "total_scenes": 8
  }
}
```

### 5. Cancel Analysis

**Endpoint:** `DELETE /analysis/{analysis_id}`

```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/20250828_140530"
```

---

## 📊 Batch Processing Workflow

### 1. Upload Batch CSV

**Endpoint:** `POST /analysis/batch/upload-csv`

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
  -F "file=@batch_analysis.csv" \
  -F "description=Daily sync analysis batch" \
  -F "priority=normal"
```

**CSV Format:**
```csv
master_file,dub_file,methods,ai_model,description,tags
/mnt/data/audio/master1.wav,/mnt/data/audio/dub1.wav,"mfcc,ai",wav2vec2,Daily batch item 1,"daily,batch"
/mnt/data/audio/master2.wav,/mnt/data/audio/dub2.wav,"onset,spectral",,"Daily batch item 2","daily,batch"
```

**Response Schema:**
```json
{
  "success": true,
  "batch_id": "batch_20250828_140600",
  "items_count": 3,
  "items": [...],
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

### 3. Monitor Batch Progress

**Endpoint:** `GET /analysis/batch/{batch_id}/status`

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/status?include_details=true"
```

### 4. Download Batch Results

**Endpoint:** `GET /analysis/batch/{batch_id}/results`

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/results"
```

### 5. Cancel Batch

**Endpoint:** `DELETE /analysis/batch/{batch_id}`

```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600"
```

---

## 🔧 Analyze-and-Repair Workflow

Complete end-to-end workflow that performs analysis, intelligent repair, and packaging.

### 1. Start Analyze-and-Repair Workflow

**Endpoint:** `POST /workflows/analyze-and-repair`

```bash
curl -X POST "http://localhost:8000/api/v1/workflows/analyze-and-repair" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/master.mov",
    "dub_file": "/mnt/data/dub.mov",
    "episode_name": "Episode 101",
    "chunk_size": 30.0,
    "enable_gpu": true,
    "auto_repair": true,
    "repair_threshold": 100.0,
    "create_package": true,
    "include_visualization": true,
    "create_zip": true,
    "output_directory": "./repair_workflows"
  }'
```

**Request Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `master_file` | string | required | Path to master/reference file |
| `dub_file` | string | required | Path to dub file to analyze and repair |
| `episode_name` | string | "Episode" | Name for the episode/content |
| `chunk_size` | float | 30.0 | Chunk size in seconds for analysis |
| `enable_gpu` | bool | true | Enable GPU acceleration |
| `auto_repair` | bool | true | Automatically apply repair if needed |
| `repair_threshold` | float | 100.0 | Offset threshold in ms for repair |
| `repair_output_path` | string | null | Custom path for repaired file |
| `create_package` | bool | true | Create comprehensive repair package |
| `include_visualization` | bool | true | Include sync visualization in package |
| `create_zip` | bool | true | Create ZIP archive of package |
| `output_directory` | string | "./repair_workflows" | Base output directory |

**Response Schema:**
```json
{
  "success": true,
  "workflow_id": "workflow_20250828_140600_abc12345",
  "status": "processing",
  "current_step": "initialized"
}
```

### 2. Get Workflow Status

**Endpoint:** `GET /workflows/analyze-and-repair/{workflow_id}/status`

```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_20250828_140600_abc12345/status"
```

**Response Schema:**
```json
{
  "success": true,
  "workflow_id": "workflow_20250828_140600_abc12345",
  "status": "completed",
  "current_step": "completed",
  
  "analysis_completed": true,
  "sync_status": "❌ SYNC CORRECTION NEEDED",
  "offset_ms": -2456.0,
  "confidence": 0.94,
  
  "repair_needed": true,
  "repair_applied": true,
  "repair_type": "global_offset",
  "repaired_file_path": "/path/to/repaired.mov",
  
  "package_created": true,
  "package_directory": "/path/to/package",
  "package_zip_file": "/path/to/package.zip",
  
  "analysis_file": "/path/to/analysis.json",
  "repair_report": "/path/to/report.md",
  "visualization_file": "/path/to/visualization.png",
  
  "processing_time": 45.2
}
```

**Workflow Steps:**
- `initialized` - Workflow started
- `analysis` - Running sync analysis
- `analysis_complete` - Analysis finished
- `repair` - Applying sync repair
- `repair_complete` - Repair finished
- `repair_skipped` - No repair needed (offset < threshold)
- `packaging` - Creating output package
- `package_complete` - Package created
- `completed` - All steps finished

### 3. Download Workflow Files

**Endpoint:** `GET /workflows/analyze-and-repair/{workflow_id}/download/{file_type}`

Available file types:
- `analysis` - JSON analysis results
- `repaired` - Repaired audio/video file
- `report` - Markdown repair report
- `visualization` - Sync visualization PNG
- `package` - ZIP package containing all outputs

```bash
# Download the complete package
curl -O "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/package"

# Download just the repaired file
curl -O "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/repaired"
```

### 4. List All Workflows

**Endpoint:** `GET /workflows/analyze-and-repair/workflows`

```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflows"
```

### 5. Cleanup Workflow

**Endpoint:** `DELETE /workflows/analyze-and-repair/{workflow_id}`

```bash
curl -X DELETE "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123"
```

---

## 🔊 Per-Channel Repair Endpoint

Apply per-channel offsets to multichannel or multi-mono audio files.

**Endpoint:** `POST /repair/repair/per-channel`

```bash
curl -X POST "http://localhost:8000/api/v1/repair/repair/per-channel" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/mnt/data/audio/dub_5.1.mov",
    "per_channel_results": {
      "FL": {"offset_seconds": -0.023},
      "FR": {"offset_seconds": -0.021},
      "FC": {"offset_seconds": -0.025},
      "LFE": {"offset_seconds": 0.0},
      "SL": {"offset_seconds": -0.019},
      "SR": {"offset_seconds": -0.020}
    },
    "output_path": "/mnt/data/audio/dub_5.1_repaired.mov",
    "keep_duration": true
  }'
```

**Request Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | string | Absolute path to dub file under mount |
| `per_channel_results` | object | Per-channel offsets: `{ role: {offset_seconds: float} }` |
| `output_path` | string | Output path (auto-generated if omitted) |
| `keep_duration` | bool | Pad/trim to keep original duration (default: true) |

**Channel Roles:**
- For 5.1 multichannel: `FL`, `FR`, `FC`, `LFE`, `SL`, `SR`
- For multi-mono MOVs: `S0`, `S1`, `S2`, etc.

**Response Schema:**
```json
{
  "success": true,
  "output_file": "/mnt/data/audio/dub_5.1_repaired.mov",
  "output_size": 10485760,
  "keep_duration": true
}
```

---

## 📄 Reports Workflow

### 1. Get Analysis Report

**Endpoint:** `GET /reports/{analysis_id}`

```bash
curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345"
```

### 2. Get Formatted Report

**Endpoint:** `GET /reports/{analysis_id}/formatted`

Returns professionally formatted HTML and Markdown versions.

```bash
curl -X GET "http://localhost:8000/api/v1/reports/analysis_123/formatted?episode_name=Episode%20101"
```

### 3. Search Reports by File Pair

**Endpoint:** `GET /reports/search`

```bash
curl -X GET "http://localhost:8000/api/v1/reports/search?master_file=/mnt/data/master.wav&dub_file=/mnt/data/dub.wav&prefer_high_confidence=true"
```

### 4. List All Reports

**Endpoint:** `GET /reports/`

```bash
curl -X GET "http://localhost:8000/api/v1/reports/?page=1&page_size=20"
```

### 5. Debug Report Data

**Endpoint:** `GET /reports/debug/{analysis_id}`

Returns raw database result for debugging.

```bash
curl -X GET "http://localhost:8000/api/v1/reports/debug/analysis_123"
```

---

## 💾 UI State Management

Persist UI state (e.g., batch queue) across browser sessions.

### 1. Get Batch Queue State

**Endpoint:** `GET /ui/state/batch-queue`

```bash
curl -X GET "http://localhost:8000/api/v1/ui/state/batch-queue"
```

### 2. Save Batch Queue State

**Endpoint:** `POST /ui/state/batch-queue`

```bash
curl -X POST "http://localhost:8000/api/v1/ui/state/batch-queue" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "id": "1",
        "master": {"name": "master.wav", "path": "/mnt/data/master.wav"},
        "dub": {"name": "dub.wav", "path": "/mnt/data/dub.wav"},
        "status": "queued",
        "progress": 0
      }
    ]
  }'
```

### 3. Clear Batch Queue State

**Endpoint:** `DELETE /ui/state/batch-queue`

```bash
curl -X DELETE "http://localhost:8000/api/v1/ui/state/batch-queue"
```

---

## 📋 Complete API Schema Reference

### File Types
```typescript
enum FileType {
  AUDIO = "audio"
  VIDEO = "video"
  ATMOS = "atmos"
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
  YAMNET = "yamnet"
  SPECTRAL = "spectral"
}
```

### Analysis Status
```typescript
enum AnalysisStatus {
  PENDING = "pending"
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

### Workflow Status
```typescript
enum WorkflowStatus {
  PROCESSING = "processing"
  COMPLETED = "completed"
  FAILED = "failed"
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
- `WORKFLOW_NOT_FOUND` - Workflow ID not found
- `UNSAFE_PATH` - Path is outside allowed mount directory

---

## 💡 Best Practices

### 1. File Management
- Upload files before analysis for better performance
- Use descriptive filenames and tags
- Use `/files/probe` to check codec compatibility before playback
- Use `/files/proxy-audio` for browser-friendly playback of Atmos/E-AC-3 files

### 2. Analysis Configuration
- Start with default methods, then customize based on content type
- Use AI methods for highest accuracy when available
- Set appropriate confidence thresholds based on use case
- Use the `/analysis/{id}/progress/stream` SSE endpoint for real-time progress

### 3. Batch Processing
- Group related files in batches for efficiency
- Use parallel processing for large batches
- Monitor progress and handle failures gracefully
- Use webhook notifications for long-running batches

### 4. Analyze-and-Repair Workflow
- Use this for complete end-to-end sync correction
- Set appropriate repair threshold (100ms default)
- Download the package ZIP for complete deliverables
- Check workflow status before downloading files

### 5. Error Handling
- Always check `success` field in responses
- Implement retry logic for transient failures
- Log request_id for debugging
- Handle SSE stream disconnections gracefully

### 6. Performance Optimization
- Cache frequently accessed file information
- Use streaming for large file uploads
- Use GPU acceleration when available
- Implement pagination for large result sets

---

## 🔗 Related Documentation

- [API Reference](./README.md) - Complete API documentation
- [CURL Examples](./CURL_EXAMPLES.md) - Ready-to-use CURL commands
- [Docker Setup](./Dockerfile) - Containerization guide
- [Batch Processing Examples](./BATCH_PROCESSING_EXAMPLES.md) - Batch workflow examples

---

## 📞 Support

For technical support or questions:
- GitHub Issues: [Submit an issue](https://github.com/novalogic71/Sync_dub_final/issues)
- Documentation: [Full API Docs](http://localhost:8000/docs)

---

*Generated on November 2025 | Version 1.3.0*
