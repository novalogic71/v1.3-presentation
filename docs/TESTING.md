# Professional Audio Sync Analyzer - Testing Guide

## System Testing Overview

This document provides comprehensive testing procedures and performance benchmarks for the Professional Audio Sync Analyzer system, including batch processing capacity and multi-GPU performance testing.

## Batch Processing Capacity Testing

### Hardware Configuration
- **GPUs**: 3x NVIDIA RTX 2080 Ti (11GB each)
- **Total GPU Memory**: 33,792 MB
- **Multi-GPU Load Balancing**: Round-robin assignment based on process ID

### Current GPU Status
```bash
# Check current GPU memory usage
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits

# Example output:
# GPU 0: 76 MB used / 11,264 MB total (0.7% used, 11,188 MB free)
# GPU 1: 8 MB used / 11,264 MB total (0.1% used, 11,256 MB free) 
# GPU 2: 4,720 MB used / 11,264 MB total (41.9% used, 6,544 MB free)
```

### Concurrent Job Capacity

#### Memory Requirements per Analysis Type
| Analysis Method | Memory per Job | Processing Time | GPU Utilization |
|----------------|----------------|-----------------|-----------------|
| **MFCC Analysis** | ~500-600 MB | 2-5 seconds | Low |
| **Onset Detection** | ~600-700 MB | 3-7 seconds | Low |
| **Spectral Analysis** | ~700-800 MB | 5-10 seconds | Medium |
| **AI Analysis (Wav2Vec2)** | ~1,500-2,000 MB | 15-30 seconds | High |
| **Chunked Analysis** | ~800-1,200 MB | 10-20 seconds | Medium |

#### Recommended Concurrent Jobs
| Workload Type | Memory per Job | Max Theoretical | **Recommended** | **Conservative** | Notes |
|---------------|----------------|-----------------|-----------------|------------------|-------|
| **Traditional Only** | ~500-800 MB | 36+ jobs | **12-15 jobs** | **8-10 jobs** | MFCC, Onset, Spectral |
| **AI Analysis** | ~1,500-2,000 MB | 16+ jobs | **4-6 jobs** | **2-3 jobs** | Wav2Vec2 heavy - prone to hanging |
| **Mixed Workload** | ~800-1,200 MB | 24+ jobs | **6-8 jobs** | **4-6 jobs** | Balanced approach |

⚠️ **Important**: AI analysis (Wav2Vec2) is currently prone to hanging at low percentages (3-10%) during batch processing. Use conservative job counts until this is resolved.

### Current API Limits
```python
# In sync_models.py:655
parallel_jobs: int = Field(default=2, ge=1, le=8, description="Number of parallel jobs")
```

- **Default**: 2 parallel jobs
- **Maximum**: 8 parallel jobs (current hard limit)
- **Recommended Update**: Increase to 12 for optimal throughput

## Performance Testing Procedures

### 1. Basic Functionality Test
```bash
# Test service initialization and GPU detection
cd fastapi_app
python -c "
from app.services.sync_analyzer_service import SyncAnalyzerService
import torch
service = SyncAnalyzerService()
print(f'✅ Service initialized with {torch.cuda.device_count()} GPUs')
"
```

### 2. Multi-GPU Load Balancing Test
```bash
# Start multiple processes to verify GPU distribution
for i in {1..6}; do
  python -c "
import sys, os
sys.path.append('..')
from sync_analyzer.ai.embedding_sync_detector import AISyncDetector, EmbeddingConfig
detector = AISyncDetector(EmbeddingConfig(use_gpu=True))
print(f'Process {os.getpid()}: {detector.device}')
" &
done
wait

# Expected output: Processes distributed across cuda:0, cuda:1, cuda:2
```

### 3. Batch Processing Load Test
```bash
# Create test batch with varying job counts
curl -X POST "http://localhost:8000/api/v1/analysis/batch/test_batch/start" \
  -H "Content-Type: application/json" \
  -d '{
    "parallel_jobs": 8,
    "priority": "normal"
  }'

# Monitor GPU usage during processing
watch -n 1 nvidia-smi
```

### 4. Memory Usage Monitoring
```bash
# Monitor GPU memory during batch processing
nvidia-smi --query-gpu=memory.used,memory.total --format=csv --loop=1

# Expected behavior:
# - Memory usage should be distributed across all 3 GPUs
# - No single GPU should exceed 90% utilization
# - Memory should be freed after job completion
```

## Recent Fixes Validation

### Offset Calculation Accuracy Test
```bash
# Test with known 15-second offset
# Expected result: ~14.7-15.3 seconds (within 0.3s accuracy)

# Before fix: 22,297ms (7+ second error)
# After fix: 14,700ms (~0.3 second error)
```

### Multi-GPU Distribution Test
```bash
# Verify round-robin GPU assignment
# Check logs for messages like:
# "Using GPU 0 of 3 available GPUs"
# "Using GPU 1 of 3 available GPUs" 
# "Using GPU 2 of 3 available GPUs"

tail -f logs/app.log | grep "GPU"
```

### Batch Processing Hang Prevention
```bash
# Test that AI analysis no longer hangs at 90%
# Previous issue: Batch processing stuck at "AI Analysis: Finding optimal alignment... (90%)"
# Fixed: Should complete successfully with multi-GPU memory management
```

## Performance Benchmarks

### Expected Processing Times (per file pair)
| Analysis Type | Small Files (<5 min) | Medium Files (5-30 min) | Large Files (>30 min) |
|---------------|---------------------|-------------------------|----------------------|
| **MFCC** | 2-5 seconds | 5-15 seconds | 15-30 seconds |
| **Onset** | 3-7 seconds | 7-20 seconds | 20-45 seconds |
| **Spectral** | 5-10 seconds | 10-30 seconds | 30-60 seconds |
| **AI Analysis** | 15-30 seconds | 30-90 seconds | 90-180 seconds |
| **All Methods** | 20-40 seconds | 40-120 seconds | 120-240 seconds |

### Throughput Estimates
| Job Count | Traditional Methods | Mixed Workload | AI-Heavy |
|-----------|-------------------|----------------|----------|
| **2 jobs** | 180-360 pairs/hour | 120-180 pairs/hour | 60-90 pairs/hour |
| **8 jobs** | 720-1440 pairs/hour | 480-720 pairs/hour | 240-360 pairs/hour |
| **12 jobs** | 1080-2160 pairs/hour | 720-1080 pairs/hour | 360-540 pairs/hour |

## Troubleshooting Guide

### GPU Memory Issues
```bash
# Check for memory leaks
nvidia-smi --query-gpu=memory.used --format=csv --loop=1

# Clear GPU cache if needed
python -c "import torch; torch.cuda.empty_cache()"

# Force CPU mode if GPU issues persist
export USE_GPU=false
```

### Batch Processing Failures

#### Common Issue: AI Analysis Hanging at Low Percentages
**Symptoms**: 
```
INFO:sync_analyzer.ai.embedding_sync_detector:Processed 10/273 audio windows (3.7%)
```
Job gets stuck and never progresses beyond early percentage.

**Root Cause**: GPU memory fragmentation or insufficient memory for large audio files during AI embedding extraction.

**Solutions**:
```bash
# 1. Reduce parallel jobs for AI analysis
curl -X POST "http://localhost:8000/api/v1/analysis/batch/{batch_id}/start" \
  -H "Content-Type: application/json" \
  -d '{"parallel_jobs": 4, "priority": "normal"}'  # Reduced from 8 to 4

# 2. Clear GPU cache before batch processing
python -c "import torch; torch.cuda.empty_cache()"

# 3. Restart the FastAPI server to clear accumulated memory
sudo systemctl restart sync-analyzer  # or manual restart

# 4. Use CPU mode for AI analysis if issues persist
export USE_GPU=false
```

#### Debugging Commands
```bash
# Check batch status
curl "http://localhost:8000/api/v1/analysis/batch/{batch_id}/status"

# Cancel stuck batch
curl -X DELETE "http://localhost:8000/api/v1/analysis/batch/{batch_id}"

# Monitor server logs with filtering
tail -f logs/app.log | grep -E "(ERROR|WARN|Processed.*audio windows)"

# Monitor GPU memory during AI processing
watch -n 5 'nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader'
```

#### Emergency Recovery
```bash
# Kill stuck processes
pkill -f "python.*sync_analyzer"

# Clear all GPU memory
nvidia-smi --gpu-reset

# Restart service
cd fastapi_app && python main.py
```

### Performance Optimization
```bash
# Increase batch job count for better throughput
# Edit sync_models.py to increase parallel job limits:
parallel_jobs: int = Field(default=8, ge=1, le=12)

# Monitor system resources
htop
iotop
nvidia-smi
```

## Test Scenarios

### Scenario 1: Maximum Throughput Test
- **Job Count**: 12 parallel jobs
- **Methods**: MFCC, Onset, Spectral only (no AI)
- **Expected**: 1000+ file pairs per hour
- **GPU Usage**: Distributed across all 3 GPUs

### Scenario 2: AI-Heavy Workload Test
- **Job Count**: 6 parallel jobs  
- **Methods**: All methods including AI
- **Expected**: 300-400 file pairs per hour
- **GPU Memory**: ~75% utilization per GPU

### Scenario 3: Memory Stress Test
- **Job Count**: 15 parallel jobs (above recommended)
- **Expected**: Some jobs may fail with OOM errors
- **Purpose**: Validate memory management and error handling

### Scenario 4: Long-Running Stability Test
- **Duration**: 4+ hours continuous processing
- **Job Count**: 8 parallel jobs
- **Expected**: No memory leaks, consistent performance
- **Monitor**: GPU memory usage should remain stable

## Known Issues

### AI Analysis Batch Processing Hang
**Issue**: AI analysis gets stuck at low percentages (3-10%) during embedding extraction
```
INFO:sync_analyzer.ai.embedding_sync_detector:Processed 10/273 audio windows (3.7%)
```

**Status**: Under Investigation  
**Workarounds**: 
- Use conservative parallel job counts (2-3 for AI workloads)
- Restart server between large batches
- Consider disabling AI analysis for large batch jobs
- Monitor GPU memory usage during processing

**Error Message Pattern**:
```
Batch analysis failed: Analysis failed: ...
INFO:sync_analyzer.ai.embedding_sync_detector:Processed X/Y audio windows (low %)
```

### Multi-GPU Memory Management
**Issue**: Occasional memory fragmentation across GPUs during sustained processing  
**Workaround**: Periodic server restart or GPU cache clearing

## Validation Checklist

- [ ] Service starts without errors
- [ ] All 3 GPUs detected and used
- [ ] Multi-GPU load balancing working
- [ ] Offset calculations within 0.3s accuracy
- [ ] Traditional methods (MFCC/Onset/Spectral) batch processing works
- [ ] AI analysis works for single files
- [ ] AI batch processing works with conservative job counts (2-3)
- [ ] Memory usage distributed across GPUs
- [ ] No memory leaks after job completion
- [ ] Performance meets throughput expectations (traditional methods)
- [ ] Error handling works for failed jobs
- [ ] System stable under sustained load (traditional methods)

## System Requirements Verification

### Minimum Requirements
- **GPU Memory**: 6GB per active analysis job
- **System RAM**: 16GB minimum, 32GB recommended  
- **CPU**: 8+ cores for optimal performance
- **Storage**: SSD for temp files and logs

### Optimal Configuration
- **GPU Memory**: 11GB+ per GPU (current: 3x 11GB ✅)
- **System RAM**: 64GB+ for large batch processing
- **CPU**: 16+ cores with high single-thread performance
- **Storage**: NVMe SSD for maximum I/O performance

---

**Last Updated**: September 2025
**System Version**: Professional Audio Sync Analyzer v2.0.0
**Multi-GPU Support**: Active
**Recent Fixes**: Offset calculation accuracy, batch processing stability