# Batch Processing API Examples

This document provides comprehensive examples for using the batch processing functionality of the Professional Audio Sync Analyzer API.

## 📋 Table of Contents

1. [CSV Format](#csv-format)
2. [Upload Batch CSV](#upload-batch-csv)
3. [Start Batch Processing](#start-batch-processing)
4. [Monitor Progress](#monitor-progress)
5. [Get Results](#get-results)
6. [Complete Workflow Example](#complete-workflow-example)
7. [Python Script Examples](#python-script-examples)

---

## 📄 CSV Format

### Required Columns
- `master_file`: Path to master audio/video file
- `dub_file`: Path to dub audio/video file

### Optional Columns
- `methods`: Comma-separated analysis methods (mfcc,onset,spectral,ai)
- `ai_model`: AI model to use (wav2vec2, yamnet, spectral)
- `description`: Item description
- `tags`: Comma-separated tags

### Sample CSV Content

```csv
master_file,dub_file,methods,ai_model,description,tags
/mnt/data/audio/master1.wav,/mnt/data/audio/dub1.wav,"mfcc,ai",wav2vec2,Daily batch item 1,"daily,batch"
/mnt/data/audio/master2.wav,/mnt/data/audio/dub2.wav,"onset,spectral",,Daily batch item 2,"daily,batch"
/mnt/data/audio/master3.wav,/mnt/data/audio/dub3.wav,ai,wav2vec2,Daily batch item 3,"daily,batch,priority"
```

### Using Your Test Files

```csv
master_file,dub_file,methods,ai_model,description,tags
/mnt/data/amcmurray/_insync_master_files/DunkirkEC_InsideTheCockpit_ProRes.mov,/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_InsideTheCockpit_ProRes_15sec.mov,"mfcc,ai",wav2vec2,Dunkirk Inside Cockpit sync test,"test,dunkirk,cockpit"
/mnt/data/amcmurray/_insync_master_files/DunkirkEC_TakingToTheAir2_ProRes.mov,/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_TakingToTheAir2_ProRes_15sec.mov,"onset,spectral",,Dunkirk Taking to Air sync test,"test,dunkirk,air"
/mnt/data/amcmurray/_insync_master_files/DunkirkEC_TheInCameraApproach1_ProRes.mov,/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_TheInCameraApproach1_ProRes_15sec.mov,ai,wav2vec2,Dunkirk In Camera Approach sync test,"test,dunkirk,camera"
```

---

## 📤 Upload Batch CSV

### Basic Upload

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
  -F "file=@sample_batch.csv" \
  -F "description=Daily sync analysis batch" \
  -F "priority=normal"
```

### With Webhook Notification

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
  -F "file=@sample_batch.csv" \
  -F "description=Priority batch with webhook" \
  -F "priority=high" \
  -F "notification_webhook=https://your-server.com/webhook/batch-complete"
```

### Expected Response

```json
{
  "success": true,
  "batch_id": "batch_20250828_140600_a1b2c3d4",
  "items_count": 3,
  "items": [
    {
      "item_id": "item_001",
      "master_file": "/mnt/data/audio/master1.wav",
      "dub_file": "/mnt/data/audio/dub1.wav",
      "methods": ["mfcc", "ai"],
      "ai_model": "wav2vec2",
      "description": "Daily batch item 1",
      "tags": ["daily", "batch"],
      "status": "pending"
    }
  ],
  "message": "Batch uploaded successfully with 3 items",
  "timestamp": "2025-08-28T14:06:00Z"
}
```

---

## 🚀 Start Batch Processing

### Basic Start

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4/start" \
  -H "Content-Type: application/json" \
  -d '{
    "parallel_jobs": 2,
    "priority": "normal"
  }'
```

### High Priority with Webhook

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4/start" \
  -H "Content-Type: application/json" \
  -d '{
    "parallel_jobs": 4,
    "priority": "high",
    "notification_webhook": "https://your-server.com/webhook/batch-status"
  }'
```

### Expected Response

```json
{
  "success": true,
  "batch_id": "batch_20250828_140600_a1b2c3d4",
  "status": "processing",
  "progress": 0.0,
  "items_total": 3,
  "items_completed": 0,
  "items_processing": 2,
  "items_failed": 0,
  "estimated_completion": "2025-08-28T14:20:00Z",
  "message": "Batch processing started with 2 parallel jobs",
  "timestamp": "2025-08-28T14:06:15Z"
}
```

---

## 📊 Monitor Progress

### Basic Status Check

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4/status"
```

### Detailed Status with Item Details

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4/status?include_details=true"
```

### Expected Response

```json
{
  "success": true,
  "batch_id": "batch_20250828_140600_a1b2c3d4",
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
      "status": "processing"
    },
    {
      "item_id": "item_003", 
      "status": "pending"
    }
  ],
  "estimated_completion": "2025-08-28T14:18:00Z",
  "timestamp": "2025-08-28T14:10:00Z"
}
```

---

## 📥 Get Results

### JSON Results

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4/results" \
  -H "Accept: application/json"
```

### CSV Export

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4/results?export_format=csv" \
  -H "Accept: text/csv" \
  -o batch_results.csv
```

### Expected Response

```json
{
  "success": true,
  "batch_id": "batch_20250828_140600_a1b2c3d4",
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
      "status": "completed",
      "result": {
        "offset_seconds": -15.023,
        "confidence": 0.981,
        "method_used": "AI (Wav2Vec2)",
        "analysis_id": "20250828_140605"
      }
    }
  ],
  "download_links": {
    "json_report": "/api/v1/reports/batch_20250828_140600_a1b2c3d4.json",
    "csv_export": "/api/v1/reports/batch_20250828_140600_a1b2c3d4.csv"
  },
  "timestamp": "2025-08-28T14:20:30Z"
}
```

---

## 🔄 Complete Workflow Example

### Step 1: Upload CSV
```bash
# Save batch CSV file
cat > dunkirk_batch.csv << 'EOF'
master_file,dub_file,methods,ai_model,description,tags
/mnt/data/amcmurray/_insync_master_files/DunkirkEC_InsideTheCockpit_ProRes.mov,/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_InsideTheCockpit_ProRes_15sec.mov,"mfcc,ai",wav2vec2,Dunkirk Inside Cockpit sync test,"test,dunkirk,cockpit"
/mnt/data/amcmurray/_insync_master_files/DunkirkEC_TakingToTheAir2_ProRes.mov,/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_TakingToTheAir2_ProRes_15sec.mov,"onset,spectral",,Dunkirk Taking to Air sync test,"test,dunkirk,air"
/mnt/data/amcmurray/_insync_master_files/DunkirkEC_TheInCameraApproach1_ProRes.mov,/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_TheInCameraApproach1_ProRes_15sec.mov,ai,wav2vec2,Dunkirk In Camera Approach sync test,"test,dunkirk,camera"
EOF

# Upload batch
BATCH_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/analysis/batch/upload-csv" \
  -F "file=@dunkirk_batch.csv" \
  -F "description=Dunkirk test batch" \
  -F "priority=normal")

echo "Upload Response: $BATCH_RESPONSE"

# Extract batch ID
BATCH_ID=$(echo $BATCH_RESPONSE | jq -r '.batch_id')
echo "Batch ID: $BATCH_ID"
```

### Step 2: Start Processing
```bash
# Start batch processing
START_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/analysis/batch/$BATCH_ID/start" \
  -H "Content-Type: application/json" \
  -d '{
    "parallel_jobs": 2,
    "priority": "normal"
  }')

echo "Start Response: $START_RESPONSE"
```

### Step 3: Monitor Progress
```bash
# Monitor progress (run in loop)
while true; do
  STATUS_RESPONSE=$(curl -s -X GET "http://localhost:8000/api/v1/analysis/batch/$BATCH_ID/status")
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
  PROGRESS=$(echo $STATUS_RESPONSE | jq -r '.progress')
  
  echo "$(date): Batch Status: $STATUS, Progress: $PROGRESS%"
  
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    break
  fi
  
  sleep 10  # Check every 10 seconds
done
```

### Step 4: Get Results
```bash
# Get final results
RESULTS_RESPONSE=$(curl -s -X GET "http://localhost:8000/api/v1/analysis/batch/$BATCH_ID/results")
echo "Results: $RESULTS_RESPONSE" | jq '.'

# Save results to file
echo $RESULTS_RESPONSE | jq '.' > batch_results_${BATCH_ID}.json
echo "Results saved to batch_results_${BATCH_ID}.json"
```

---

## 🐍 Python Script Examples

### Simple Batch Processing Script

```python
#!/usr/bin/env python3
import requests
import json
import time
import sys

API_BASE = "http://localhost:8000/api/v1"

def upload_batch_csv(csv_file_path, description="Batch processing"):
    """Upload a batch CSV file."""
    url = f"{API_BASE}/analysis/batch/upload-csv"
    
    with open(csv_file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'description': description,
            'priority': 'normal'
        }
        
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        return response.json()

def start_batch_processing(batch_id, parallel_jobs=2):
    """Start batch processing."""
    url = f"{API_BASE}/analysis/batch/{batch_id}/start"
    
    data = {
        'parallel_jobs': parallel_jobs,
        'priority': 'normal'
    }
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()

def monitor_batch_progress(batch_id, check_interval=10):
    """Monitor batch processing progress."""
    url = f"{API_BASE}/analysis/batch/{batch_id}/status"
    
    print(f"Monitoring batch {batch_id}...")
    
    while True:
        response = requests.get(url)
        response.raise_for_status()
        status_data = response.json()
        
        status = status_data['status']
        progress = status_data['progress']
        completed = status_data['items_completed']
        total = status_data['items_total']
        
        print(f"Status: {status}, Progress: {progress}%, Items: {completed}/{total}")
        
        if status in ['completed', 'failed', 'cancelled']:
            return status_data
        
        time.sleep(check_interval)

def get_batch_results(batch_id):
    """Get batch processing results."""
    url = f"{API_BASE}/analysis/batch/{batch_id}/results"
    
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_processor.py <csv_file_path>")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    
    try:
        # Upload CSV
        print(f"Uploading batch CSV: {csv_file_path}")
        upload_result = upload_batch_csv(csv_file_path)
        batch_id = upload_result['batch_id']
        print(f"Batch uploaded successfully. Batch ID: {batch_id}")
        
        # Start processing
        print("Starting batch processing...")
        start_result = start_batch_processing(batch_id)
        print(f"Batch processing started with {start_result['items_processing']} parallel jobs")
        
        # Monitor progress
        final_status = monitor_batch_progress(batch_id)
        print(f"Batch processing finished with status: {final_status['status']}")
        
        # Get results
        if final_status['status'] == 'completed':
            print("Getting batch results...")
            results = get_batch_results(batch_id)
            
            # Save results
            results_file = f"batch_results_{batch_id}.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {results_file}")
            
            # Print summary
            summary = results['summary']
            print(f"\nBatch Summary:")
            print(f"  Total Items: {summary['items_total']}")
            print(f"  Completed: {summary['items_completed']}")
            print(f"  Failed: {summary['items_failed']}")
            print(f"  Average Confidence: {summary['average_confidence']:.3f}")
            print(f"  Processing Time: {summary['processing_time_seconds']:.1f} seconds")
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Usage
```bash
# Make script executable
chmod +x batch_processor.py

# Run with your CSV file
python batch_processor.py dunkirk_batch.csv
```

---

## 🔧 Advanced Features

### Cancel Batch Processing
```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/batch/batch_20250828_140600_a1b2c3d4"
```

### Health Check Before Batch Processing
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

### List Available Analysis Methods
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/methods"
```

---

## 📈 Performance Tips

1. **Optimal Parallel Jobs**: Start with 2-4 parallel jobs, increase based on CPU cores
2. **File Size**: Smaller files (< 100MB) process faster
3. **Method Selection**: AI methods are slower but more accurate
4. **Batch Size**: Keep batches under 50 items for optimal performance
5. **Monitoring**: Check status every 10-30 seconds to avoid overwhelming the API

---

## 🚨 Error Handling

### Common Error Responses

```json
{
  "success": false,
  "error": "Batch batch_12345 not found",
  "timestamp": "2025-08-28T14:00:00Z"
}
```

### Error Codes
- `404`: Batch not found
- `400`: Invalid CSV format or request data
- `500`: Internal server error
- `408`: Analysis timeout

---

## 📞 Support

For help with batch processing:
- Check API status: `GET /api/v1/health`
- View API docs: `http://localhost:8000/docs`
- Monitor logs for detailed error messages

---

*Generated on 2025-08-28 | Version 1.0.0*