# Quick Start Guide

This guide will get you up and running with the Professional Audio Sync Analyzer in under 5 minutes.

## 📋 Prerequisites

Before you begin, ensure you have:
- **Python 3.9 or higher** installed
- **FFmpeg** installed and accessible from command line
- At least **2 GB of free disk space**
- Two audio/video files to test with

### Verify Prerequisites

```bash
# Check Python version
python --version  # Should be 3.9+

# Check FFmpeg installation
ffmpeg -version

# Check pip
pip --version
```

## 🚀 Installation

### Method 1: Direct Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/professional-audio-sync-analyzer.git
cd professional-audio-sync-analyzer

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Method 2: Development Installation

```bash
# After cloning and setting up venv (as above)
pip install -e .

# This installs the package in development mode
# You can now use `sync-analyzer` command from anywhere
```

## 🎯 First Analysis

### Option A: Command Line (Quick Test)

```bash
# Basic analysis with MFCC method (fastest)
python -m sync_analyzer.cli.sync_cli master_file.mov dub_file.mov

# Advanced analysis with multiple methods
python -m sync_analyzer.cli.sync_cli \
  --methods mfcc correlation \
  --output-dir ./my_reports \
  master_file.mov dub_file.mov
```

**Expected Output:**
```
🎵 Professional Audio Sync Analyzer v2.0
📁 Master: master_file.mov (120.5s)
📁 Dub: dub_file.mov (120.8s)
🔍 Analyzing with methods: ['mfcc']
✅ Sync Analysis Complete!
   📊 Offset: -2.456 seconds
   🎯 Confidence: 94.2%
   📋 Report: ./reports/sync_report_20250827_143052.json
```

### Option B: Web Interface (Recommended)

1. **Start all services (FastAPI + Celery):**
   ```bash
   ./start_all.sh
   ```

2. **Open your browser:**
   Navigate to: http://localhost:8000/app

3. **Analyze files:**
   - Use the file browser to navigate to your media files
   - For **Standard** mode: Select master and dub files
   - For **Componentized** mode: Select master and multiple component files
   - Enable **GPU Fast** for AI-accelerated analysis (recommended)
   - Click "Add to Batch" then "Process Batch"
   - View results in the batch processing queue

4. **Repair sync issues:**
   - Click on a completed job to view details
   - Use "QC" to review the sync visually
   - Click "Repair" for automatic correction

### Option C: Backend Dashboard (NEW)

Monitor GPU, system resources, and job status:

```bash
# Open the dashboard
http://localhost:8000/dashboard
```

## 🚀 GPU-Accelerated Analysis (NEW)

The system now supports AI-powered GPU analysis using Wav2Vec2:

### Enable GPU Fast Mode
1. In the web UI, go to **Config** tab
2. Enable **🚀 GPU Fast** toggle (enabled by default)
3. Process your batch as normal

### GPU Features
- **10-50x faster** than CPU methods
- **Smart Hybrid**: Automatically verifies results if inconsistent
- **Bars/Tone Detection**: Skips test patterns at file head
- **Cross-Browser Sync**: Jobs visible in all browser sessions

### Fallback Behavior
If GPU is unavailable, the system automatically falls back to CPU-based MFCC+Onset analysis.

## 📊 Understanding Results

### Sync Offset Interpretation

| Offset Range | Status | Action Needed |
|--------------|--------|---------------|
| **< ±25ms** | ✅ Excellent | No action needed |
| **±25ms to ±100ms** | ⚠️ Minor issue | Consider correction for critical content |
| **> ±100ms** | ❌ Correction needed | Repair recommended |

### Confidence Score

- **90-100%**: Very reliable result
- **70-89%**: Good result, likely accurate
- **50-69%**: Moderate confidence, verify manually
- **< 50%**: Low confidence, check audio quality

## 🔧 Common Issues & Solutions

### Issue: "FFmpeg not found"
```bash
# Install FFmpeg
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
```

### Issue: "No audio track found"
- Verify your files contain audio streams
- Check file isn't corrupted:
  ```bash
  ffprobe your_file.mov
  ```

### Issue: "Port 3001 already in use"
```bash
# Find and kill process using port 3001
lsof -ti:3001 | xargs kill -9

# Or use a different port
python server.py --port 3002
```

### Issue: Analysis takes too long
- Use only MFCC method for speed: `--methods mfcc`
- Reduce analysis window: `--window 15`
- Check available system memory

## 🎬 Example Workflows

### Workflow 1: Broadcast TV Dubbing
```bash
# Analyze all language pairs in a directory
python -m sync_analyzer.cli.batch_processor \
  --input-dir ./dubbing_files \
  --pattern "*_EN.mov,*_ES.mov" \
  --output-dir ./sync_reports
```

### Workflow 2: Film Post-Production
```bash
# High-precision analysis for film
python -m sync_analyzer.cli.sync_cli \
  --methods mfcc correlation \
  --window 60 \
  --precision high \
  original_mix.wav adr_track.wav
```

### Workflow 3: Batch Repair
1. Use web interface to analyze multiple files
2. Queue them in the batch processor
3. Use "Process All" to repair automatically
4. Check results in the completed section

## 📈 Next Steps

Once you're comfortable with basic usage:

1. **Explore Advanced Features:**
   - Custom analysis parameters
   - Batch processing scripts
   - API integration

2. **Check Documentation:**
   - `docs/API_REFERENCE.md` - Full API documentation
   - `docs/ADVANCED_USAGE.md` - Advanced features and scripting
   - `examples/` - More example scripts

3. **Join the Community:**
   - Report issues on GitHub
   - Share your use cases
   - Contribute improvements

## 🆘 Getting Help

- **Documentation**: Check the `docs/` directory
- **Examples**: See `examples/` for working code
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Ask questions in GitHub Discussions

---

**You're now ready to analyze audio sync professionally!** 🎵✨
