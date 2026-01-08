# 🏭 Production Workflows & Best Practices
*Recommended workflows for continuous production use*

## 📋 Quick Reference

| Workflow | Use Case | Time Required | Recommended Tool |
|----------|----------|---------------|------------------|
| **Single File QC** | Quick quality check | 2-5 minutes | `quick_sync_check.py` |
| **Detailed Analysis** | Full sync assessment | 5-15 minutes | `continuous_sync_monitor.py` |
| **Batch Processing** | Multiple files | 20-60 minutes | `csv_batch_processor.py` |
| **Auto-Repair Pipeline** | Production delivery | 30-90 minutes | `csv_batch_processor.py` with repair |

---

## 🚀 Workflow 1: Daily Quality Control

### Purpose
Quick assessment of incoming files for immediate sync issues.

### Process
```bash
# Step 1: Quick spot check at key timestamps
PYTHONPATH=. python scripts/monitoring/quick_sync_check.py \
  master.mov dub.mov 0 300 600 900 1200

# Step 2: If issues detected, run detailed analysis
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py \
  master.mov dub.mov

# Step 3: Generate summary report
PYTHONPATH=. python scripts/repair/sync_report_analyzer.py \
  analysis.json --name "QC Report $(date)" --output qc_report.txt
```

### Success Criteria
- ✅ All timestamps within ±300ms
- ✅ No major drift patterns detected
- ✅ Content classification accurate

### Escalation Path
- **Minor issues** (±100-300ms): Flag for batch repair
- **Major issues** (>±500ms): Immediate manual review
- **Drift patterns**: Full analysis and targeted repair

---

## 🏭 Workflow 2: Batch Production Processing

### Purpose
Process multiple episodes/files efficiently with automated repair.

### Setup Phase
```bash
# 1. Create batch CSV file
cat > batch_files.csv << EOF
master_file,dub_file,episode_name,chunk_size
/path/master_ep101.mov,/path/dub_ep101.mov,Episode 101,45
/path/master_ep102.mov,/path/dub_ep102.mov,Episode 102,30
/path/master_ep103.mov,/path/dub_ep103.mov,Episode 103,45
EOF

# 2. Create output directories
mkdir -p batch_results repaired_files repair_packages
```

### Processing Phase
```bash
# Single command for complete pipeline
PYTHONPATH=. python scripts/batch/csv_batch_processor.py batch_files.csv \
  --output-dir batch_results/ \
  --auto-repair \
  --repair-threshold 100 \
  --repair-output-dir repaired_files/ \
  --create-package \
  --package-dir repair_packages/ \
  --plot \
  --use-optimized-cli \
  --gpu \
  --max-workers 4
```

### Quality Assurance Phase
```bash
# Review batch summary
cat batch_results/batch_processing_summary.json | jq '.summary'

# Validate critical repairs
for file in repaired_files/*.mov; do
  echo "Validating: $file"
  PYTHONPATH=. python scripts/monitoring/quick_sync_check.py \
    master_file "$file" 0 300 600
done
```

### Delivery Phase
```bash
# Create delivery packages
for package in repair_packages/*; do
  echo "Package ready: $package"
  ls -la "$package"
done
```

---

## 🎯 Workflow 3: Critical Issue Resolution

### Purpose
Handle files with significant sync problems requiring manual intervention.

### Diagnosis Phase
```bash
# 1. Comprehensive analysis
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py \
  master.mov problematic_dub.mov > detailed_analysis.txt

# 2. Extract analysis data
grep -A 50 "SCENE BREAKDOWN" detailed_analysis.txt > scene_breakdown.txt

# 3. Generate technical report
PYTHONPATH=. python scripts/repair/llm_report_formatter.py \
  analysis.json \
  --name "Critical Issue Analysis" \
  --output technical_report.md
```

### Repair Planning Phase
```bash
# 1. Identify repair strategy
echo "=== REPAIR STRATEGY ==="
grep "IMMEDIATE ACTION" detailed_analysis.txt

# 2. Test repair on problematic sections
PYTHONPATH=. python scripts/repair/intelligent_sync_repair.py \
  problematic_dub.mov analysis.json \
  --output test_repair.mov \
  --temp-dir ./temp_repair

# 3. Validate repair
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py \
  master.mov test_repair.mov > validation_results.txt
```

### Resolution Phase
```bash
# 1. Apply final repair
PYTHONPATH=. python scripts/repair/intelligent_sync_repair.py \
  problematic_dub.mov analysis.json \
  --output final_repaired.mov \
  --validate-with master.mov \
  --preserve-quality

# 2. Create comprehensive package
PYTHONPATH=. python scripts/repair/sync_repair_packager.py \
  analysis.json problematic_dub.mov \
  --repaired final_repaired.mov \
  --episode "Critical Repair Case" \
  --output-dir critical_packages
```

---

## 📊 Workflow 4: Performance Monitoring

### Purpose
Track system performance and accuracy metrics over time.

### Daily Metrics Collection
```bash
#!/bin/bash
# daily_metrics.sh

DATE=$(date +%Y-%m-%d)
METRICS_DIR="metrics/$DATE"
mkdir -p "$METRICS_DIR"

# Collect processing stats
echo "=== Daily Processing Stats ===" > "$METRICS_DIR/daily_stats.txt"
echo "Date: $DATE" >> "$METRICS_DIR/daily_stats.txt"
echo "Files processed: $(ls batch_results/ | wc -l)" >> "$METRICS_DIR/daily_stats.txt"
echo "Repairs applied: $(ls repaired_files/ | wc -l)" >> "$METRICS_DIR/daily_stats.txt"

# GPU utilization
nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits > "$METRICS_DIR/gpu_usage.txt"

# Analysis accuracy (from validation results)
grep "Confidence:" batch_results/*.json | awk '{sum+=$2; count++} END {print "Average confidence:", sum/count}' >> "$METRICS_DIR/daily_stats.txt"
```

### Weekly Performance Review
```bash
#!/bin/bash
# weekly_review.sh

# Generate performance summary
echo "=== Weekly Performance Summary ===" > weekly_summary.md
echo "Week ending: $(date)" >> weekly_summary.md

# Processing volume
echo "## Processing Volume" >> weekly_summary.md
find batch_results/ -name "*.json" -mtime -7 | wc -l >> weekly_summary.md

# Success rates
echo "## Success Rates" >> weekly_summary.md
total_files=$(find batch_results/ -name "*.json" -mtime -7 | wc -l)
successful_repairs=$(find repaired_files/ -name "*.mov" -mtime -7 | wc -l)
echo "Repair success rate: $(($successful_repairs * 100 / $total_files))%" >> weekly_summary.md

# Average processing time
echo "## Performance Metrics" >> weekly_summary.md
echo "Average GPU utilization: $(cat metrics/*/gpu_usage.txt | awk '{sum+=$1; count++} END {print sum/count "%"}')" >> weekly_summary.md
```

---

## 🎛️ Workflow 5: Web UI Operations

### Purpose
Use the web interface for interactive analysis and monitoring.

### Setup
```bash
# Start all services
./start_all.sh

# Access interfaces
echo "Web UI: http://localhost:3000"
echo "API: http://localhost:8000"
echo "Operator Console: http://localhost:3000/operator-console"
```

### Interactive Analysis Workflow
1. **Upload files** via web interface
2. **Configure analysis** parameters in UI
3. **Monitor progress** in real-time
4. **Review results** in interactive timeline
5. **Apply repairs** with preview
6. **Download packages** when complete

### Batch Operations via UI
1. **Upload CSV** batch file
2. **Configure batch** settings
3. **Start processing** with progress monitoring
4. **Review summary** dashboard
5. **Download results** in bulk

---

## ⚙️ Environment Configuration

### Production Environment Setup
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
export PYTHONPATH=/path/to/Sync_dub_final:$PYTHONPATH
export SYNC_DUB_ENV=production
export CUDA_VISIBLE_DEVICES=0,1,2  # Available GPUs

# 3. Set up directories
mkdir -p {batch_results,repaired_files,repair_packages,temp_processing}

# 4. Configure logging
export SYNC_DUB_LOG_LEVEL=INFO
export SYNC_DUB_LOG_DIR=/var/log/sync_dub
```

### Performance Tuning
```bash
# GPU memory optimization
export CUDA_MEMORY_FRACTION=0.8

# CPU threading
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8

# Temporary storage (use SSD if available)
export TMPDIR=/fast/storage/temp
```

---

## 🚨 Error Handling & Recovery

### Common Error Recovery

#### "Module not found" Errors
```bash
# Verify Python path
echo $PYTHONPATH
export PYTHONPATH=/path/to/Sync_dub_final:$PYTHONPATH
```

#### GPU Memory Errors
```bash
# Reduce parallel workers
--max-workers 2

# Clear GPU memory
python -c "import torch; torch.cuda.empty_cache()"
```

#### File Processing Errors
```bash
# Check file permissions
chmod +r input_files/*

# Verify file integrity
ffmpeg -v error -i input.mov -f null -
```

### Automated Recovery Scripts
```bash
#!/bin/bash
# recovery.sh - Restart failed batch processing

# Find incomplete processing
for json_file in batch_results/*.json; do
  if ! grep -q "completed" "$json_file"; then
    echo "Reprocessing: $json_file"
    # Extract original parameters and retry
  fi
done
```

---

## 📈 Quality Metrics

### Key Performance Indicators

#### Processing Efficiency
- **Files per hour**: Target 15-20 files/hour (with 4 GPUs)
- **GPU utilization**: Target 70-85% average
- **Error rate**: Target <5% processing failures

#### Quality Metrics
- **Sync accuracy**: Target ±200ms for 95% of content
- **Repair success**: Target 90%+ for simple offsets
- **Manual review**: Target <10% of total files

#### Operational Metrics
- **Turnaround time**: Target <4 hours for batch processing
- **Storage efficiency**: Target 80% cleanup of temp files
- **Uptime**: Target 99% service availability

### Continuous Improvement
```bash
# Weekly quality review
PYTHONPATH=. python scripts/utils/quality_metrics.py \
  --batch-results batch_results/ \
  --period weekly \
  --output quality_report.json

# Performance optimization
PYTHONPATH=. python scripts/utils/performance_analyzer.py \
  --metrics-dir metrics/ \
  --recommendations performance_recommendations.txt
```

---

## 🔄 Maintenance Procedures

### Daily Maintenance
```bash
#!/bin/bash
# daily_maintenance.sh

# Clean temporary files
find /tmp -name "sync_analysis_*" -mtime +1 -delete

# Rotate logs
logrotate /etc/logrotate.d/sync_dub

# Check disk space
df -h | grep -E "(95%|96%|97%|98%|99%)" && echo "WARNING: Disk space low"

# GPU health check
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits | \
while read temp; do
  if [ "$temp" -gt 80 ]; then
    echo "WARNING: GPU temperature high: ${temp}°C"
  fi
done
```

### Weekly Maintenance
```bash
#!/bin/bash
# weekly_maintenance.sh

# Archive old results
tar -czf "archive/batch_results_$(date +%Y%m%d).tar.gz" batch_results/
rm -rf batch_results/*

# Update system
pip install --upgrade -r requirements.txt

# Performance analysis
PYTHONPATH=. python scripts/utils/system_health_check.py > weekly_health_report.txt
```

---

*For technical support and troubleshooting, refer to PRODUCTION_USAGE_GUIDE.md*