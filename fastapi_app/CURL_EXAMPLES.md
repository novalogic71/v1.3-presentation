# Professional Audio Sync Analyzer API - Curl Examples

This document provides comprehensive curl examples for all API endpoints, making it easy to test and integrate with the API.

## Base URL
All examples use `http://localhost:8000` as the base URL. Adjust this for your deployment.

## Authentication
Currently, the API doesn't require authentication. In production, you may need to add appropriate headers.

---

## Health and Status Endpoints

### 1. Basic Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

### 2. API Help
```bash
curl -X GET "http://localhost:8000/api/help"
```

### 3. Comprehensive System Health Status
```bash
curl -X GET "http://localhost:8000/api/v1/health/status"
```

### 4. FFmpeg Health
```bash
curl -X GET "http://localhost:8000/api/v1/health/ffmpeg"
```

### 5. AI Models Health
```bash
curl -X GET "http://localhost:8000/api/v1/health/ai-models"
```

### 6. File System Health
```bash
curl -X GET "http://localhost:8000/api/v1/health/filesystem"
```

### 7. System Resources Health
```bash
curl -X GET "http://localhost:8000/api/v1/health/system"
```

---

## File Management Endpoints

### 1. List Files

#### List Mount Directory
```bash
curl -X GET "http://localhost:8000/api/v1/files/"
```

#### List Specific Directory
```bash
curl -X GET "http://localhost:8000/api/v1/files/?path=/mnt/data/audio"
```

#### List Subdirectory
```bash
curl -X GET "http://localhost:8000/api/v1/files/?path=/mnt/data/audio/master_files"
```

### 2. Upload File

#### Basic Upload
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/local/audio.wav"
```

#### Upload with Metadata
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/local/master_audio.wav" \
  -F "file_type=audio" \
  -F "description=Master audio track for sync analysis" \
  -F "tags=master,audio,sync,professional"
```

#### Upload Video File
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/local/video.mov" \
  -F "file_type=video" \
  -F "description=Master video file" \
  -F "tags=master,video,sync"
```

### 3. Probe File (FFprobe)

Get detailed codec/container information:
```bash
curl -X GET "http://localhost:8000/api/v1/files/probe?path=/mnt/data/audio/master.mov"
```

### 4. Proxy Audio Stream

Stream audio in browser-friendly format:
```bash
# Default WAV output
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov" --output preview.wav

# AAC output for smaller size
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov&format=mp4" --output preview.m4a

# WebM/Opus output
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov&format=webm" --output preview.webm

# With duration limit (10 minutes max)
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/master.mov&max_duration=600" --output preview.wav

# With role-based loudness (dub gets +5dB boost)
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/dub.mov&role=dub" --output dub_preview.wav
```

### 5. Get Raw File
```bash
curl -X GET "http://localhost:8000/api/v1/files/raw?path=/mnt/data/audio/master.wav" --output master.wav
```

### 6. Get File Information
```bash
curl -X GET "http://localhost:8000/api/v1/files/file_abc123"
```

### 7. Delete File
```bash
curl -X DELETE "http://localhost:8000/api/v1/files/file_abc123"
```

---

## Analysis Endpoints

### 1. Start Sync Analysis

#### Basic Analysis (MFCC only)
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "methods": ["mfcc"],
    "sample_rate": 22050,
    "window_size": 30.0,
    "confidence_threshold": 0.8
  }'
```

#### Advanced Analysis (Multiple Methods)
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "methods": ["mfcc", "onset", "spectral"],
    "enable_ai": true,
    "ai_model": "wav2vec2",
    "sample_rate": 22050,
    "window_size": 30.0,
    "confidence_threshold": 0.8,
    "generate_plots": true,
    "output_format": "json"
  }'
```

#### AI-Enhanced Analysis
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "methods": ["ai"],
    "enable_ai": true,
    "ai_model": "wav2vec2",
    "sample_rate": 16000,
    "window_size": 60.0,
    "confidence_threshold": 0.9
  }'
```

### 2. Get Analysis Status
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
```

### 3. Monitor Analysis Progress (SSE Stream)

Connect to real-time progress stream:
```bash
# Using curl with streaming
curl -N "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345/progress/stream"

# Monitor with watch (polling alternative)
watch -n 2 'curl -s "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345" | jq ".progress, .message"'
```

### 4. Get Analysis Timeline
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/sync/analysis_20250827_143052_abc12345/timeline"
```

### 5. Cancel Analysis
```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
```

### 6. Batch Analysis

#### Simple Batch
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "file_pairs": [
      {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"},
      {"master": "/mnt/data/audio/master2.wav", "dub": "/mnt/data/audio/dub2.wav"},
      {"master": "/mnt/data/audio/master3.wav", "dub": "/mnt/data/audio/dub3.wav"}
    ],
    "analysis_config": {
      "methods": ["mfcc", "onset"],
      "sample_rate": 22050,
      "window_size": 30.0,
      "confidence_threshold": 0.8
    },
    "parallel_processing": true,
    "max_workers": 4
  }'
```

#### Large Batch with AI
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "file_pairs": [
      {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"},
      {"master": "/mnt/data/audio/master2.wav", "dub": "/mnt/data/audio/dub2.wav"},
      {"master": "/mnt/data/audio/master3.wav", "dub": "/mnt/data/audio/dub3.wav"},
      {"master": "/mnt/data/audio/master4.wav", "dub": "/mnt/data/audio/dub4.wav"},
      {"master": "/mnt/data/audio/master5.wav", "dub": "/mnt/data/audio/dub5.wav"}
    ],
    "analysis_config": {
      "methods": ["mfcc", "ai"],
      "enable_ai": true,
      "ai_model": "wav2vec2",
      "sample_rate": 16000,
      "window_size": 45.0,
      "confidence_threshold": 0.85
    },
    "parallel_processing": true,
    "max_workers": 6
  }'
```

### 7. List Analyses

#### Get First Page
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/?page=1&page_size=20"
```

#### Filter by Status
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/?status=completed&page=1&page_size=10"
```

#### Get Specific Page
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/?page=3&page_size=15"
```

---

## Batch Processing Endpoints (CSV Upload)

### 1. Upload Batch CSV
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
  -F "file=@batch_analysis.csv" \
  -F "description=Daily sync analysis batch" \
  -F "priority=normal"
```

### 2. Start Batch Processing
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/start" \
  -H "Content-Type: application/json" \
  -d '{
    "parallel_jobs": 4,
    "priority": "high",
    "notification_webhook": "https://your-server.com/webhook/batch-complete"
  }'
```

### 3. Get Batch Status
```bash
# Basic status
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/status"

# With detailed item status
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/status?include_details=true"
```

### 4. Get Batch Results
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600/results"
```

### 5. Cancel Batch
```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600"
```

---

## Analyze-and-Repair Workflow Endpoints

### 1. Start Analyze-and-Repair Workflow

#### Basic Workflow
```bash
curl -X POST "http://localhost:8000/api/v1/workflows/analyze-and-repair" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/master.mov",
    "dub_file": "/mnt/data/dub.mov",
    "episode_name": "Episode 101",
    "auto_repair": true,
    "create_package": true
  }'
```

#### Full Configuration
```bash
curl -X POST "http://localhost:8000/api/v1/workflows/analyze-and-repair" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/master.mov",
    "dub_file": "/mnt/data/dub.mov",
    "episode_name": "Episode 101 - Pilot",
    "chunk_size": 30.0,
    "enable_gpu": true,
    "auto_repair": true,
    "repair_threshold": 100.0,
    "repair_output_path": null,
    "create_package": true,
    "include_visualization": true,
    "create_zip": true,
    "output_directory": "./repair_workflows"
  }'
```

### 2. Get Workflow Status
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_20250828_140600_abc12345/status"
```

### 3. Download Workflow Files

#### Download Complete Package (ZIP)
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/package" \
  --output package.zip
```

#### Download Repaired File
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/repaired" \
  --output repaired.mov
```

#### Download Analysis JSON
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/analysis" \
  --output analysis.json
```

#### Download Report
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/report" \
  --output report.md
```

#### Download Visualization
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123/download/visualization" \
  --output visualization.png
```

### 4. List All Workflows
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflows"
```

### 5. Cleanup Workflow
```bash
curl -X DELETE "http://localhost:8000/api/v1/workflows/analyze-and-repair/workflow_123"
```

---

## Per-Channel Repair Endpoint

### Apply Per-Channel Offsets

#### 5.1 Surround (Multichannel)
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

#### Multi-Mono MOV (Multiple Audio Streams)
```bash
curl -X POST "http://localhost:8000/api/v1/repair/repair/per-channel" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/mnt/data/audio/dub_multi_mono.mov",
    "per_channel_results": {
      "S0": {"offset_seconds": -0.023},
      "S1": {"offset_seconds": -0.021},
      "S2": {"offset_seconds": -0.025},
      "S3": {"offset_seconds": -0.018}
    },
    "keep_duration": true
  }'
```

---

## AI Endpoints

### 1. List AI Models
```bash
curl -X GET "http://localhost:8000/api/v1/ai/models"
```

### 2. Get AI Model Information
```bash
curl -X GET "http://localhost:8000/api/v1/ai/models/wav2vec2"
```

```bash
curl -X GET "http://localhost:8000/api/v1/ai/models/yamnet"
```

```bash
curl -X GET "http://localhost:8000/api/v1/ai/models/spectral"
```

---

## Reports Endpoints

### 1. Get Analysis Report
```bash
curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345"
```

### 2. Get Formatted Report (HTML/Markdown)
```bash
curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345/formatted?episode_name=Episode%20101"
```

### 3. Search Reports by File Pair
```bash
curl -X GET "http://localhost:8000/api/v1/reports/search?master_file=/mnt/data/master.wav&dub_file=/mnt/data/dub.wav"

# Prefer highest confidence match
curl -X GET "http://localhost:8000/api/v1/reports/search?master_file=/mnt/data/master.wav&dub_file=/mnt/data/dub.wav&prefer_high_confidence=true"
```

### 4. List Reports

#### Get First Page
```bash
curl -X GET "http://localhost:8000/api/v1/reports/?page=1&page_size=20"
```

#### Get Specific Page
```bash
curl -X GET "http://localhost:8000/api/v1/reports/?page=2&page_size=15"
```

### 5. Debug Report Data
```bash
curl -X GET "http://localhost:8000/api/v1/reports/debug/analysis_20250827_143052_abc12345"
```

### 6. Upload Batch CSV (Reports Endpoint)
```bash
curl -X POST "http://localhost:8000/api/v1/reports/batch/csv" \
  -F "file=@batch_episodes.csv" \
  -F "output_dir=batch_results"
```

### 7. Start Batch Processing (Reports)
```bash
curl -X POST "http://localhost:8000/api/v1/reports/batch/batch_abc123/process?max_workers=4&generate_plots=true"
```

### 8. Get Batch Status (Reports)
```bash
curl -X GET "http://localhost:8000/api/v1/reports/batch/batch_abc123/status"
```

---

## UI State Endpoints

### 1. Get Batch Queue State
```bash
curl -X GET "http://localhost:8000/api/v1/ui/state/batch-queue"
```

### 2. Save Batch Queue State
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
      },
      {
        "id": "2",
        "master": {"name": "master2.wav", "path": "/mnt/data/master2.wav"},
        "dub": {"name": "dub2.wav", "path": "/mnt/data/dub2.wav"},
        "status": "completed",
        "progress": 100,
        "result": {
          "offset_seconds": -0.023,
          "confidence": 0.95,
          "method_used": "mfcc"
        }
      }
    ]
  }'
```

### 3. Clear Batch Queue State
```bash
curl -X DELETE "http://localhost:8000/api/v1/ui/state/batch-queue"
```

---

## Advanced Usage Examples

### 1. Complete Workflow

#### Step 1: Upload Master File
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/master.wav" \
  -F "file_type=audio" \
  -F "description=Master audio track" \
  -F "tags=master,audio"
```

#### Step 2: Upload Dub File
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/dub.wav" \
  -F "file_type=audio" \
  -F "description=Dub audio track" \
  -F "tags=dub,audio"
```

#### Step 3: Start Analysis
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/uploads/file_abc123_master.wav",
    "dub_file": "/mnt/data/uploads/file_def456_dub.wav",
    "methods": ["mfcc", "onset", "ai"],
    "enable_ai": true,
    "ai_model": "wav2vec2",
    "sample_rate": 22050,
    "window_size": 30.0,
    "confidence_threshold": 0.8
  }'
```

#### Step 4: Monitor Progress (SSE)
```bash
curl -N "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345/progress/stream"
```

#### Step 5: Get Results
```bash
curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345"
```

### 2. Complete Analyze-and-Repair Flow

#### Step 1: Start Workflow
```bash
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/workflows/analyze-and-repair" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/master.mov",
    "dub_file": "/mnt/data/dub.mov",
    "episode_name": "Episode 101",
    "auto_repair": true,
    "create_package": true
  }')

WORKFLOW_ID=$(echo $RESPONSE | jq -r '.workflow_id')
echo "Started workflow: $WORKFLOW_ID"
```

#### Step 2: Poll Until Complete
```bash
while true; do
  STATUS=$(curl -s "http://localhost:8000/api/v1/workflows/analyze-and-repair/$WORKFLOW_ID/status" | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 5
done
```

#### Step 3: Download Package
```bash
curl -X GET "http://localhost:8000/api/v1/workflows/analyze-and-repair/$WORKFLOW_ID/download/package" \
  --output "episode_101_package.zip"
```

### 3. Batch Processing Workflow

#### Step 1: Prepare File List
Create a JSON file `batch_files.json`:
```json
{
  "file_pairs": [
    {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"},
    {"master": "/mnt/data/audio/master2.wav", "dub": "/mnt/data/audio/dub2.wav"},
    {"master": "/mnt/data/audio/master3.wav", "dub": "/mnt/data/audio/dub3.wav"}
  ],
  "analysis_config": {
    "methods": ["mfcc", "onset"],
    "sample_rate": 22050,
    "window_size": 30.0,
    "confidence_threshold": 0.8
  },
  "parallel_processing": true,
  "max_workers": 4
}
```

#### Step 2: Submit Batch
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch" \
  -H "Content-Type: application/json" \
  -d @batch_files.json
```

#### Step 3: Monitor Batch Progress
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/?status=processing"
```

---

## Health Monitoring Examples

### Comprehensive Health Check Script
```bash
#!/bin/bash
API_URL="http://localhost:8000"

echo "=== System Health Check ==="

# Basic health
echo -n "Basic Health: "
curl -s "$API_URL/health" | jq -r '.status'

# Detailed health
echo -e "\n=== Component Status ==="
curl -s "$API_URL/api/v1/health/status" | jq '.components | to_entries[] | "\(.key): \(.value.status)"'

# FFmpeg
echo -e "\n=== FFmpeg ==="
curl -s "$API_URL/api/v1/health/ffmpeg" | jq '{status, version: .details.version}'

# AI Models
echo -e "\n=== AI Models ==="
curl -s "$API_URL/api/v1/health/ai-models" | jq '{status, gpu_available: .details.gpu_available, models: .details.available_models}'

# System Resources
echo -e "\n=== System Resources ==="
curl -s "$API_URL/api/v1/health/system" | jq '{cpu: .details.cpu_usage_percent, memory: .details.memory_usage_percent, disk: .details.disk_usage_percent}'
```

---

## Error Handling Examples

### 1. File Not Found
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/nonexistent_id"
# Returns: {"detail": "Analysis nonexistent_id not found"}
```

### 2. Invalid File Path
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "relative/path.wav",
    "dub_file": "/mnt/data/audio/dub.wav"
  }'
# Returns error about unsafe path
```

### 3. Unsupported File Type
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/document.txt"
# Returns: {"detail": "File type not supported"}
```

---

## Performance Testing

### 1. Health Endpoint Load Test
```bash
# Test with Apache Bench
ab -n 1000 -c 10 http://localhost:8000/health

# Test with curl in loop
for i in {1..100}; do
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
    "http://localhost:8000/health"
done
```

### 2. Analysis Endpoint Timing
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{"master_file": "...", "dub_file": "...", "methods": ["mfcc"]}' \
  -w "\nTotal time: %{time_total}s\n"
```

---

## Notes

- All file paths in examples use `/mnt/data` as the mount point. Adjust this for your system.
- The API returns JSON responses by default.
- Analysis operations are asynchronous - you'll get an analysis ID to track progress.
- File uploads support multipart/form-data format.
- Health checks provide detailed component status information.
- Rate limiting is enabled by default (60 requests per minute per IP).
- All timestamps are in ISO 8601 format (UTC).
- Use the SSE endpoint `/analysis/{id}/progress/stream` for real-time progress updates.

For more information, see the API documentation at `http://localhost:8000/docs` or `http://localhost:8000/redoc`.
