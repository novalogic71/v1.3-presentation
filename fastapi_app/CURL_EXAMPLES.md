# Professional Audio Sync Analyzer API - Curl Examples

This document provides comprehensive curl examples for all API endpoints, making it easy to test and integrate with the API.

## Base URL
All examples use `http://localhost:8000` as the base URL. Adjust this for your deployment.

## Authentication
Currently, the API doesn't require authentication. In production, you may need to add appropriate headers.

## Health and Status Endpoints

### 1. Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

### 2. API Help
```bash
curl -X GET "http://localhost:8000/api/help"
```

### 3. System Health Status
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

### 3. Cancel Analysis
```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
```

### 4. Batch Analysis

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

### 5. List Analyses

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

### 3. Get File Information
```bash
curl -X GET "http://localhost:8000/api/v1/files/file_abc123"
```

### 4. Delete File
```bash
curl -X DELETE "http://localhost:8000/api/v1/files/file_abc123"
```

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

## Reports Endpoints

### 1. Get Analysis Report
```bash
curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345"
```

### 2. List Reports

#### Get First Page
```bash
curl -X GET "http://localhost:8000/api/v1/reports/?page=1&page_size=20"
```

#### Get Specific Page
```bash
curl -X GET "http://localhost:8000/api/v1/reports/?page=2&page_size=15"
```

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

#### Step 4: Monitor Progress
```bash
# Replace with actual analysis ID from step 3
curl -X GET "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
```

#### Step 5: Get Results
```bash
# Once analysis is complete
curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345"
```

### 2. Batch Processing Workflow

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
# Check all analyses
curl -X GET "http://localhost:8000/api/v1/analysis/?status=processing"
```

### 3. Health Monitoring

#### Comprehensive Health Check
```bash
curl -X GET "http://localhost:8000/api/v1/health/status"
```

#### Component-Specific Checks
```bash
# Check FFmpeg
curl -X GET "http://localhost:8000/api/v1/health/ffmpeg"

# Check AI models
curl -X GET "http://localhost:8000/api/v1/health/ai-models"

# Check file system
curl -X GET "http://localhost:8000/api/v1/health/filesystem"

# Check system resources
curl -X GET "http://localhost:8000/api/v1/health/system"
```

## Error Handling Examples

### 1. File Not Found
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/nonexistent_id"
```

### 2. Invalid File Path
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "relative/path.wav",
    "dub_file": "/mnt/data/audio/dub.wav"
  }'
```

### 3. Unsupported File Type
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/document.txt"
```

### 4. File Too Large
```bash
# This will fail if the file exceeds MAX_FILE_SIZE
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/very_large_file.wav"
```

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

### 2. Analysis Endpoint Load Test
```bash
# Create test payload
cat > test_analysis.json << EOF
{
  "master_file": "/mnt/data/audio/test_master.wav",
  "dub_file": "/mnt/data/audio/test_dub.wav",
  "methods": ["mfcc"],
  "sample_rate": 22050
}
EOF

# Test with multiple concurrent requests
for i in {1..10}; do
  curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
    -H "Content-Type: application/json" \
    -d @test_analysis.json &
done
wait
```

## Scripts and Automation

### 1. Health Check Script
```bash
#!/bin/bash
# health_check.sh

API_URL="http://localhost:8000"
LOG_FILE="/var/log/sync_analyzer_health.log"

echo "$(date): Starting health check..." >> $LOG_FILE

# Check basic health
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
if [ "$HEALTH_RESPONSE" = "200" ]; then
    echo "$(date): Basic health check passed" >> $LOG_FILE
else
    echo "$(date): Basic health check failed: $HEALTH_RESPONSE" >> $LOG_FILE
    exit 1
fi

# Check detailed health
DETAILED_HEALTH=$(curl -s "$API_URL/api/v1/health/status")
echo "$(date): Detailed health: $DETAILED_HEALTH" >> $LOG_FILE

echo "$(date): Health check completed" >> $LOG_FILE
```

### 2. Batch Analysis Script
```bash
#!/bin/bash
# batch_analysis.sh

API_URL="http://localhost:8000"
INPUT_DIR="/mnt/data/audio"
OUTPUT_DIR="/mnt/data/reports"

# Find all master-dub pairs
find "$INPUT_DIR" -name "*master*" -type f | while read master_file; do
    # Generate corresponding dub filename
    dub_file=$(echo "$master_file" | sed 's/master/dub/g')
    
    if [ -f "$dub_file" ]; then
        echo "Analyzing: $master_file vs $dub_file"
        
        # Submit analysis
        ANALYSIS_ID=$(curl -s -X POST "$API_URL/api/v1/analysis/sync" \
          -H "Content-Type: application/json" \
          -d "{
            \"master_file\": \"$master_file\",
            \"dub_file\": \"$dub_file\",
            \"methods\": [\"mfcc\", \"onset\"],
            \"sample_rate\": 22050
          }" | jq -r '.analysis_id')
        
        echo "Analysis started: $ANALYSIS_ID"
        
        # Wait for completion
        while true; do
            STATUS=$(curl -s "$API_URL/api/v1/analysis/$ANALYSIS_ID" | jq -r '.status')
            if [ "$STATUS" = "completed" ]; then
                echo "Analysis completed: $ANALYSIS_ID"
                break
            elif [ "$STATUS" = "failed" ]; then
                echo "Analysis failed: $ANALYSIS_ID"
                break
            fi
            sleep 5
        done
    fi
done
```

## Troubleshooting

### 1. Check API Status
```bash
# Basic connectivity
curl -v "http://localhost:8000/health"

# Check if service is running
ps aux | grep uvicorn
netstat -tlnp | grep :8000
```

### 2. Check Logs
```bash
# Application logs
tail -f logs/app.log

# System logs
journalctl -u sync-analyzer-api -f
```

### 3. Test Individual Components
```bash
# Test FFmpeg
ffmpeg -version

# Test file system access
ls -la /mnt/data/

# Test Python environment
python -c "import fastapi, uvicorn; print('Dependencies OK')"
```

## Batch Queue Endpoints (Cross-Browser Sync)

### 1. Get Batch Queue
```bash
curl -X GET "http://localhost:8000/api/v1/batch-queue"
```

### 2. Save Batch Queue
```bash
curl -X POST "http://localhost:8000/api/v1/batch-queue" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "id": 1234567890,
        "type": "componentized",
        "status": "queued",
        "master": {"path": "/mnt/data/master.mov", "name": "master.mov"},
        "components": [
          {"path": "/mnt/data/comp_a0.wav", "label": "a0", "name": "comp_a0.wav"}
        ]
      }
    ],
    "clientId": "browser-session-123"
  }'
```

### 3. Update Single Item
```bash
curl -X PUT "http://localhost:8000/api/v1/batch-queue/item/1234567890" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "progress": 100,
    "result": {"offset_seconds": -0.5, "confidence": 0.95}
  }'
```

### 4. Delete Single Item
```bash
curl -X DELETE "http://localhost:8000/api/v1/batch-queue/item/1234567890"
```

### 5. Clear Batch Queue
```bash
curl -X DELETE "http://localhost:8000/api/v1/batch-queue"
```

## Job Registry Endpoints (API Job Discovery)

### 1. Get All Jobs
```bash
curl -X GET "http://localhost:8000/api/v1/job-registry"
```

### 2. Get Jobs by Status
```bash
curl -X GET "http://localhost:8000/api/v1/job-registry?status=completed"
```

### 3. Get Recent Jobs (Last 6 Hours)
```bash
curl -X GET "http://localhost:8000/api/v1/job-registry?since_hours=6"
```

### 4. Get New Jobs Since Timestamp
```bash
curl -X GET "http://localhost:8000/api/v1/job-registry/new?since=2026-01-09T12:00:00"
```

### 5. Get Specific Job
```bash
curl -X GET "http://localhost:8000/api/v1/job-registry/abc123-task-id"
```

### 6. Remove Job from Registry
```bash
curl -X DELETE "http://localhost:8000/api/v1/job-registry/abc123-task-id"
```

## GPU Analysis Examples

### 1. GPU-Accelerated Componentized Analysis
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/componentized/async" \
  -H "Content-Type: application/json" \
  -d '{
    "master": "/mnt/data/master.mov",
    "components": [
      {"path": "/mnt/data/Lt.wav", "label": "Lt"},
      {"path": "/mnt/data/Rt.wav", "label": "Rt"},
      {"path": "/mnt/data/C.wav", "label": "C"},
      {"path": "/mnt/data/LFE.wav", "label": "LFE"}
    ],
    "methods": ["gpu"],
    "offset_mode": "channel_aware",
    "frameRate": 23.976
  }'
```

Response:
```json
{
  "success": true,
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "message": "Analysis queued in Celery. Poll /api/v1/jobs/<task_id> for status."
}
```

### 2. Check Job Status
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/abc123-def456-ghi789"
```

## Dashboard Endpoints

### 1. Get System Info
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/system-info"
```

### 2. Get GPU Info
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/gpu-info"
```

### 3. Get Celery Workers Info
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/celery-info"
```

### 4. Get Console Logs
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/console-logs?lines=100"
```

## Notes

- All file paths in examples use `/mnt/data` as the mount point. Adjust this for your system.
- The API returns JSON responses by default.
- Analysis operations are asynchronous - you'll get an analysis ID to track progress.
- File uploads support multipart/form-data format.
- Health checks provide detailed component status information.
- Rate limiting is enabled by default (60 requests per minute per IP).
- All timestamps are in ISO 8601 format (UTC).
- **Cross-Browser Sync**: Batch queue is stored in Redis - all browsers see the same state.
- **API Job Discovery**: Jobs submitted via API automatically appear in the UI.

For more information, see the API documentation at `http://localhost:8000/docs` or `http://localhost:8000/redoc`.
