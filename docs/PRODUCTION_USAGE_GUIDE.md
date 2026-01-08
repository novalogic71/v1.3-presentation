# 🚀 Sync Dub Production Usage Guide
*Comprehensive API and CLI Reference for Continuous Production Use*

## 📋 Table of Contents
- [Quick Start](#quick-start)
- [Core Scripts Overview](#core-scripts-overview)
- [Production Workflows](#production-workflows)
- [API Endpoints](#api-endpoints)
- [CLI Tools Reference](#cli-tools-reference)
- [Batch Processing](#batch-processing)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Prerequisites
```bash
# Ensure project root is in Python path
export PYTHONPATH=/path/to/Sync_dub_final:$PYTHONPATH

# Start all services
./start_all.sh
```

### Basic Sync Analysis
```bash
# Quick sync check at specific timestamps
PYTHONPATH=. python scripts/monitoring/quick_sync_check.py master.mov dub.mov 0 60 120 300

# Comprehensive continuous monitoring
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py master.mov dub.mov

# Check for sync drift patterns
PYTHONPATH=. python scripts/monitoring/check_sync_drift.py master.mov dub.mov
```

---

## 🔧 Core Scripts Overview

### 📊 Monitoring Scripts (`scripts/monitoring/`)

#### `continuous_sync_monitor.py` ⭐ **PRIMARY TOOL**
**Purpose**: Comprehensive multi-pass sync analysis with operator-friendly timeline

```bash
# Basic usage
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py master.mov dub.mov

# Features:
# ✅ Multi-pass analysis with intelligent refinement
# ✅ CUDA GPU acceleration (auto-detects all GPUs)
# ✅ Content-aware classification (dialogue/music/mixed)
# ✅ Operator-friendly timeline display
# ✅ Detailed repair recommendations
# ✅ Scene-by-scene breakdown
```

#### `quick_sync_check.py`
**Purpose**: Fast spot-checks at specific timestamps

```bash
# Check sync at specific times (in seconds)
PYTHONPATH=. python scripts/monitoring/quick_sync_check.py master.mov dub.mov 0 60 120 300
```

#### `check_sync_drift.py`
**Purpose**: Simple drift detection

```bash
PYTHONPATH=. python scripts/monitoring/check_sync_drift.py master.mov dub.mov
```

### 🔄 Batch Processing (`scripts/batch/`)

#### `csv_batch_processor.py` ⭐ **BATCH ANALYSIS**
**Purpose**: Process multiple file pairs with comprehensive analysis + optional auto-repair

```bash
# Analyze multiple files from CSV
PYTHONPATH=. python scripts/batch/csv_batch_processor.py files.csv --output-dir results/

# Full workflow: analyze + auto-repair + package
PYTHONPATH=. python scripts/batch/csv_batch_processor.py batch.csv \
  --output-dir results/ \
  --auto-repair \
  --repair-threshold 100 \
  --repair-output-dir ./repaired_sync_files \
  --create-package \
  --package-dir ./repair_packages \
  --plot \
  --max-workers 3
```

**CSV Format**:
```csv
master_file,dub_file,episode_name,chunk_size
/path/master1.mov,/path/dub1.mov,Episode 101,45
/path/master2.mov,/path/dub2.mov,Episode 102,30
```

#### `batch_sync_processor.py`
**Purpose**: Multi-GPU batch processing without repair

```bash
# Process specific file pairs
PYTHONPATH=. python scripts/batch/batch_sync_processor.py \
  --pairs master1.mov dub1.mov master2.mov dub2.mov \
  --output-dir results/

# Auto-find pairs in directory
PYTHONPATH=. python scripts/batch/batch_sync_processor.py \
  --directory /path/to/files \
  --patterns "*Original*.mov:*v1.1*.mov" \
  --output-dir results/
```

#### `batch_sync_repair.py`
**Purpose**: Repair multiple files based on batch analysis

```bash
PYTHONPATH=. python scripts/batch/batch_sync_repair.py \
  --batch-summary results/batch_processing_summary.json \
  --csv original.csv \
  --output-dir repaired/ \
  --validate \
  --max-workers 4
```

### 🔧 Repair Scripts (`scripts/repair/`)

#### `intelligent_sync_repair.py` ⭐ **REPAIR ENGINE**
**Purpose**: Apply intelligent sync corrections

```bash
# Basic repair
PYTHONPATH=. python scripts/repair/intelligent_sync_repair.py \
  input.mov analysis.json --output repaired.mov

# With validation and quality preservation
PYTHONPATH=. python scripts/repair/intelligent_sync_repair.py \
  input.mov analysis.json \
  --output repaired.mov \
  --validate-with master.mov \
  --preserve-quality
```

#### `sync_repair_packager.py`
**Purpose**: Create comprehensive repair packages

```bash
PYTHONPATH=. python scripts/repair/sync_repair_packager.py \
  analysis.json original.mov \
  --repaired repaired.mov \
  --episode "Episode 101" \
  --output-dir ./packages
```

#### `sync_report_analyzer.py`
**Purpose**: Generate formatted analysis reports

```bash
PYTHONPATH=. python scripts/repair/sync_report_analyzer.py \
  analysis.json \
  --name "Episode 101" \
  --output report.txt
```

#### `llm_report_formatter.py`
**Purpose**: AI-enhanced report formatting

```bash
PYTHONPATH=. python scripts/repair/llm_report_formatter.py \
  analysis.json \
  --name "Episode 101" \
  --output enhanced_report.md \
  --model llama3.2
```

### 🧪 Testing Scripts (`scripts/testing/`)

#### `test_enhanced_sync.py`
**Purpose**: Validate enhanced sync detection features

```bash
PYTHONPATH=. python scripts/testing/test_enhanced_sync.py
```

#### `test_operator_timeline.py`
**Purpose**: Test operator-friendly timeline display

```bash
PYTHONPATH=. python scripts/testing/test_operator_timeline.py
```

---

## 🏭 Production Workflows

### Workflow 1: Single File Analysis & Repair
```bash
# 1. Analyze sync issues
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py \
  master.mov dub.mov > analysis_output.txt

# 2. Extract JSON for repair (look for JSON in output)
# analysis.json is generated automatically

# 3. Apply intelligent repair
PYTHONPATH=. python scripts/repair/intelligent_sync_repair.py \
  dub.mov analysis.json --output repaired_dub.mov --validate-with master.mov

# 4. Create comprehensive package
PYTHONPATH=. python scripts/repair/sync_repair_packager.py \
  analysis.json dub.mov --repaired repaired_dub.mov --episode "Show S01E01"
```

### Workflow 2: Batch Processing
```bash
# 1. Create CSV file (see format above)
# 2. Run comprehensive batch analysis + auto-repair
PYTHONPATH=. python scripts/batch/csv_batch_processor.py batch.csv \
  --output-dir batch_results/ \
  --auto-repair --repair-threshold 100 \
  --repair-output-dir repaired_files/ \
  --create-package --package-dir packages/ \
  --plot --max-workers 4 --use-optimized-cli --gpu

# This single command provides:
# ✅ Multi-GPU accelerated analysis for all files
# ✅ Automatic repair for files with sync issues
# ✅ Comprehensive repair packages
# ✅ Visualization plots
# ✅ Detailed reports
```

### Workflow 3: Quality Control Pipeline
```bash
# 1. Quick spot check
PYTHONPATH=. python scripts/monitoring/quick_sync_check.py master.mov dub.mov 0 300 600 900

# 2. Full analysis if issues found
PYTHONPATH=. python scripts/monitoring/continuous_sync_monitor.py master.mov dub.mov

# 3. Generate professional report
PYTHONPATH=. python scripts/repair/llm_report_formatter.py analysis.json \
  --name "Quality Control Report" --output qc_report.md
```

---

## 🌐 API Endpoints

### FastAPI Server (Port 8000)
Start with: `./start_all.sh` or `uvicorn fastapi_app.app.main:app --host 0.0.0.0 --port 8000`

#### Analysis Endpoints

**POST /api/v1/analyze**
```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/path/to/master.mov",
    "dub_file": "/path/to/dub.mov",
    "chunk_size": 30.0
  }'
```

**POST /api/v1/batch-analyze**
```bash
curl -X POST "http://localhost:8000/api/v1/batch-analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "file_pairs": [
      {"master": "/path/master1.mov", "dub": "/path/dub1.mov"},
      {"master": "/path/master2.mov", "dub": "/path/dub2.mov"}
    ],
    "max_workers": 4
  }'
```

#### Repair Endpoints

**POST /api/v1/repair**
```bash
curl -X POST "http://localhost:8000/api/v1/repair" \
  -H "Content-Type: application/json" \
  -d '{
    "input_file": "/path/to/dub.mov",
    "analysis_data": {...},
    "output_file": "/path/to/repaired.mov"
  }'
```

#### File Management

**GET /api/v1/files**
```bash
curl "http://localhost:8000/api/v1/files?directory=/path/to/files"
```

**POST /api/v1/files/upload**
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@video.mov"
```

#### Reports

**GET /api/v1/reports/{analysis_id}**
```bash
curl "http://localhost:8000/api/v1/reports/12345"
```

### Web UI (Port 3000)
Access at: `http://localhost:3000`

Features:
- 📊 Interactive sync visualization
- 🎛️ Operator console for batch operations
- 🔄 Real-time processing status
- 📈 Waveform analysis tools
- 🛠️ Repair preview interface

---

## 🎯 CLI Tools Reference

### Environment Setup
```bash
# Always set Python path
export PYTHONPATH=/path/to/Sync_dub_final:$PYTHONPATH

# Or prefix each command
PYTHONPATH=. python scripts/...
```

### GPU Configuration
- **Auto-detection**: System automatically detects all available GPUs
- **Load balancing**: Round-robin assignment prevents memory exhaustion
- **Multi-GPU batch**: Use `--max-workers` to control parallel processes

### Key Parameters

#### Chunk Size
- **Default**: 30 seconds for monitoring, 45 seconds for batch
- **Dialogue-heavy**: Use 15-30 seconds
- **Music/Action**: Use 45-60 seconds

#### Quality Settings
- **Fast analysis**: Default settings
- **High precision**: `--refinement-chunk-size 5`
- **Quality repair**: `--preserve-quality`

---

## 📊 Batch Processing

### CSV Format Requirements
```csv
master_file,dub_file,episode_name,chunk_size,notes
/path/master1.mov,/path/dub1.mov,Episode 101,45,Optional notes
/path/master2.mov,/path/dub2.mov,Episode 102,30,Dialogue heavy
```

### Batch Workflow Options

#### Option 1: Analysis Only
```bash
PYTHONPATH=. python scripts/batch/csv_batch_processor.py files.csv --output-dir results/
```

#### Option 2: Analysis + Auto-Repair
```bash
PYTHONPATH=. python scripts/batch/csv_batch_processor.py files.csv \
  --output-dir results/ \
  --auto-repair \
  --repair-threshold 100
```

#### Option 3: Complete Pipeline
```bash
PYTHONPATH=. python scripts/batch/csv_batch_processor.py files.csv \
  --output-dir results/ \
  --auto-repair \
  --repair-threshold 100 \
  --repair-output-dir repaired/ \
  --create-package \
  --package-dir packages/ \
  --plot \
  --use-optimized-cli \
  --gpu
```

---

## 🔍 Troubleshooting

### Common Issues

#### Module Import Errors
```bash
# Solution: Always set PYTHONPATH
export PYTHONPATH=/path/to/Sync_dub_final:$PYTHONPATH
```

#### GPU Memory Issues
```bash
# Solution: Reduce max workers
--max-workers 2

# Or disable GPU
# Remove --gpu flag
```

#### File Path Issues
```bash
# Solution: Use absolute paths in CSV
/full/path/to/master.mov,/full/path/to/dub.mov
```

#### Analysis Timeout
```bash
# Solution: Increase chunk size for large files
--chunk-size 60
```

### Performance Optimization

#### For Large Files (>1 hour)
- Use `chunk_size: 60` in CSV
- Enable `--use-optimized-cli --gpu`
- Set `--max-workers` to number of GPUs

#### For Batch Processing
- Use SSD storage for temporary files
- Enable `--use-optimized-cli --gpu`
- Monitor GPU memory usage

#### For Quality Control
- Use `continuous_sync_monitor.py` for detailed analysis
- Enable `--preserve-quality` for final repairs
- Generate reports with `llm_report_formatter.py`

---

## 📈 Performance Metrics

### Analysis Speed (with GPU acceleration)
- **Quick check**: ~2-5 seconds per timestamp
- **Continuous monitor**: ~15-20 seconds per minute of content
- **Batch processing**: Scales linearly with GPU count

### Accuracy
- **Typical accuracy**: ±0.3 seconds
- **Best case**: ±0.1 seconds (clear dialogue)
- **Challenging**: ±0.5 seconds (music/action heavy)

### Repair Success Rate
- **Simple offsets**: 95%+ success
- **Complex drift**: 85%+ success
- **Manual review**: Required for large gaps (>5 seconds)

---

## 🚀 Production Recommendations

### Daily Operations
1. Use `csv_batch_processor.py` for bulk analysis
2. Enable auto-repair for offsets <500ms
3. Manual review for larger issues
4. Generate reports for quality tracking

### Quality Assurance
1. Spot-check with `quick_sync_check.py`
2. Full analysis with `continuous_sync_monitor.py`
3. Professional reports with `llm_report_formatter.py`

### Monitoring
1. Track repair success rates
2. Monitor GPU utilization
3. Review analysis accuracy metrics
4. Archive repair packages for reference

---

*Last updated: September 2025*
*For technical support, see TROUBLESHOOTING.md*