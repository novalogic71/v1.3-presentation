# Professional Audio Sync Analyzer

A comprehensive professional-grade audio synchronization analysis and repair system designed for broadcast television, film post-production, and media workflows. This system provides both command-line tools and a modern web interface for detecting and correcting audio-video sync issues.

## ✨ Features

### 🎯 Core Analysis Engine
- **Multi-Method Detection**: MFCC, onset detection, spectral analysis, and cross-correlation algorithms
- **AI-Powered GPU Analysis**: Wav2Vec2 neural network sync detection with full GPU acceleration (NEW)
- **Smart Hybrid Mode**: Automatic verification using MFCC when GPU results are inconsistent (NEW)
- **High Precision**: Sub-frame accuracy with millisecond-level offset detection
- **Multi-GPU Support**: Automatic workload distribution across available GPUs
- **Bars/Tone Detection**: Automatic detection and handling of test patterns at file head (NEW)
- **Audio Fingerprinting**: Chromaprint-based fingerprint sync detection (NEW)
- **Comprehensive Reporting**: Detailed JSON, CSV, and HTML reports with waveform visualizations

### 🌐 Modern Web Interface
- **Intuitive UI**: Professional dark-themed interface with real-time feedback
- **Cross-Browser Sync**: Jobs sync across all browser sessions via Redis (NEW)
- **API Job Discovery**: Jobs submitted via API automatically appear in UI (NEW)
- **Batch Processing**: Queue multiple file pairs for automated analysis
- **Visual Results**: Offset visualization with interactive waveforms
- **Componentized Analysis**: Analyze multichannel files with per-component results (NEW)
- **Integrated Repair**: One-click audio sync correction with FFmpeg integration
- **Export Options**: CSV, JSON, HTML Report, Table View, Waveform View exports (NEW)

### 🔧 Automated Repair
- **FFmpeg Integration**: Professional-quality audio offset correction
- **Quality Preservation**: Lossless video copying with precise audio adjustment
- **Backup Creation**: Automatic backup of original files before modification
- **Batch Repair**: Process multiple files efficiently with queue management

### 🤖 AI/GPU Analysis Methods (NEW)
- **Wav2Vec2 GPU**: Fast neural network-based sync detection using PyTorch
- **Smart Hybrid**: GPU analysis with automatic MFCC verification for multichannel
- **Fingerprint**: Chromaprint audio fingerprinting for content matching
- **Channel-Aware**: Per-channel analysis for discrete multichannel files

## 🚀 Quick Start

### Prerequisites
- Python 3.9+ (3.10 recommended)
- FFmpeg installed and accessible in PATH
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/professional-audio-sync-analyzer.git
   cd professional-audio-sync-analyzer
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Quick Test

**Command Line Analysis:**
```bash
python -m sync_analyzer.cli.sync_cli master_video.mov dub_video.mov --methods mfcc
```

**Web Interface:**
```bash
cd web_ui
python server.py
```
Then open http://localhost:3002 in your browser.

> **Note**: The application opens with a professional splash screen at the root URL (`/`). Click "Enter Application" or press Enter to access the main interface at `/app`. For presentations, see [PRESENTATION_GUIDE.md](PRESENTATION_GUIDE.md) for a complete walkthrough.

## ⚡ GPU & AI Analysis

### Wav2Vec2 GPU Mode (Recommended)
The default analysis mode uses Facebook's Wav2Vec2 neural network for fast, accurate sync detection:

- **Full GPU Acceleration**: All operations run on CUDA GPU
- **10-50x Faster**: Compared to CPU-based methods
- **Smart Verification**: Automatically uses MFCC to verify inconsistent results
- **Bars/Tone Detection**: Skips test patterns at file head

```bash
# Enable GPU mode (default in UI)
USE_GPU=true python -m fastapi_app.main
```

### Multi-GPU Support
- **Automatic Load Balancing**: Distributes workload across all available GPUs
- **Round-robin Distribution**: Based on process ID prevents memory exhaustion
- **Memory Management**: Automatic GPU memory cleanup between jobs

### Configuration
```bash
# GPU Settings
USE_GPU=true                           # Enable GPU acceleration
LONG_FILE_THRESHOLD_SECONDS=180        # Files longer than this use chunked analysis
LONG_FILE_GPU_BYPASS=true              # Bypass chunking for GPU analysis
LONG_FILE_GPU_BYPASS_MAX_SECONDS=900   # Max file length for GPU bypass

# AI Model Settings
AI_WAV2VEC2_MODEL_PATH=/path/to/model  # Custom model path (optional)
HF_LOCAL_ONLY=1                        # Use local models only (no downloads)
```

## 🔄 Cross-Browser Sync & API Integration

### Server-Side Job Storage (NEW)
Jobs are stored in Redis, enabling real-time sync across all clients:

- **Cross-Browser Sync**: Open app in multiple browsers - see same job queue
- **Persistent State**: Jobs survive browser refresh and server restart
- **Real-Time Updates**: Status changes sync within 10 seconds

### API Job Discovery (NEW)
Jobs submitted directly via API automatically appear in the UI:

```bash
# Submit job via API
curl -X POST http://localhost:8000/api/v1/analysis/componentized/async \
  -H "Content-Type: application/json" \
  -d '{"master": "/path/to/master.mov", "components": [...]}'

# Job automatically appears in UI within 10 seconds!
```

### Key Endpoints
- `GET /api/v1/batch-queue` - Get/sync batch queue state
- `POST /api/v1/batch-queue` - Save batch queue state
- `GET /api/v1/job-registry` - List all jobs (UI + API submitted)
- `GET /api/v1/jobs/{job_id}` - Get job status and results

## 📖 Usage

### Command Line Interface

#### Basic Analysis
```bash
python -m sync_analyzer.cli.sync_cli master.mov dub.mov
```

#### Advanced Options
```bash
python -m sync_analyzer.cli.sync_cli \
  --methods mfcc correlation ai \
  --output-dir ./reports \
  --json-only \
  --quiet \
  master.mov dub.mov
```

#### Batch Processing
```bash
python -m sync_analyzer.cli.batch_processor \
  --input-dir ./media_files \
  --output-dir ./sync_reports \
  --methods mfcc
```

### Web Interface

1. **Start the server:**
   ```bash
   cd web_ui
   python server.py
   ```

2. **Open browser to:** http://localhost:3001

3. **Basic workflow:**
   - Navigate to your media files using the file browser
   - Select master and dub files by clicking them
   - Click "Analyze" to detect sync offset
   - Use "Auto Fix" for immediate repair or "Manual Repair" for fine-tuning
   - View results in the batch processing table

### API Integration

The web server exposes REST APIs for programmatic access:

```python
import requests

# Analyze files
response = requests.post('http://localhost:3001/api/analyze', json={
    'master_file': '/path/to/master.mov',
    'dub_file': '/path/to/dub.mov',
    'methods': ['mfcc']
})

# Repair with detected offset
response = requests.post('http://localhost:3001/api/repair', json={
    'file_path': '/path/to/dub.mov',
    'offset_seconds': -2.5,
    'output_dir': './repaired_files'
})
```

## 🔧 Recent Improvements (January 2026)

### AI-Powered GPU Analysis
- **Wav2Vec2 GPU Mode**: Neural network-based sync detection with full GPU acceleration
- **Smart Hybrid Verification**: Automatic MFCC verification when GPU results are inconsistent
- **Bars/Tone Detection**: Automatic detection and skipping of test patterns
- **Sub-frame Refinement**: Targeted MFCC refinement step for precise results

### Cross-Browser Sync
- **Server-Side Storage**: Batch queue stored in Redis for cross-browser sync
- **API Job Discovery**: Jobs submitted via API automatically appear in UI
- **Real-Time Updates**: Status syncs across all browser sessions
- **Persistent State**: Jobs survive browser refresh and server restart

### Enhanced UI Features
- **Componentized Analysis**: Per-component results for multichannel files
- **Offset Visualization**: Interactive timeline with offset markers
- **Analysis Findings**: Detailed messaging (tail length, bars/tone, head differences)
- **Export Options**: CSV, JSON, HTML Report, Table View, Waveform View
- **Job Management**: Restart completed jobs, refresh stale statuses

### Production Reliability
- **Supervisord Integration**: Automatic process restart on crash
- **Celery/Redis Queue**: Robust job queuing with retry logic
- **Health Monitoring**: Dashboard for GPU, CPU, memory, and job status

### Analysis Method Improvements
- **Audio Fingerprinting**: Chromaprint-based sync detection
- **Channel-Aware Mode**: Per-channel analysis for discrete multichannel
- **Confidence Scoring**: Improved confidence calculations
- **Method Findings**: Detailed analysis insights per component

### Key Files
- `sync_analyzer/core/simple_gpu_sync.py`: Wav2Vec2 GPU detector with bars/tone detection
- `sync_analyzer/core/fingerprint_sync.py`: Chromaprint fingerprint detector
- `fastapi_app/app/api/v1/endpoints/batch_queue.py`: Server-side batch queue API
- `fastapi_app/app/api/v1/endpoints/job_registry.py`: API job discovery
- `fastapi_app/app/services/componentized_service.py`: Smart hybrid analysis logic

## 🏗 Architecture

### Core Components

```
sync_analyzer/
├── core/                          # Core analysis algorithms
│   ├── audio_sync_detector.py     # Main detection engine (MFCC, Onset, Spectral)
│   ├── simple_gpu_sync.py         # Wav2Vec2 GPU detector (NEW)
│   ├── fingerprint_sync.py        # Chromaprint fingerprint detector (NEW)
│   ├── optimized_large_file_detector.py  # Chunked analysis for long files
│   └── feature_extractors.py      # Audio feature extraction
├── cli/                           # Command-line interfaces
│   ├── sync_cli.py                # Primary CLI tool
│   └── batch_processor.py         # Batch processing utility
├── reports/                       # Report generation
│   └── sync_reporter.py           # JSON/visual report generator
└── utils/                         # Shared utilities
    ├── audio_utils.py             # Audio processing helpers
    └── file_utils.py              # File system utilities

fastapi_app/                       # FastAPI Backend (NEW)
├── main.py                        # Application entry point
├── app/
│   ├── api/v1/endpoints/
│   │   ├── analysis.py            # Sync analysis endpoints
│   │   ├── componentized.py       # Componentized analysis
│   │   ├── batch_queue.py         # Server-side queue storage (NEW)
│   │   ├── job_registry.py        # API job discovery (NEW)
│   │   ├── dashboard.py           # Backend monitoring
│   │   └── repair.py              # Audio repair endpoints
│   ├── services/
│   │   └── componentized_service.py  # Smart hybrid analysis logic
│   └── tasks/
│       └── analysis_tasks.py      # Celery background tasks
└── requirements.txt

web_ui/
├── app.html             # Main web interface
├── app.js               # Frontend JavaScript (cross-browser sync)
├── style.css            # Modern dark-themed UI
├── dashboard.html       # Backend monitoring dashboard (NEW)
└── styles/              # Additional stylesheets
```

### Analysis Methods

1. **MFCC (Mel-Frequency Cepstral Coefficients)**
   - Fast, reliable method for most content
   - Excellent for speech and music
   - ~2-5 second analysis time

2. **Onset Detection**
   - Detects audio transients (attacks, beats)
   - Best for content with clear transients
   - Robust across different audio types

3. **Spectral Analysis**
   - Frequency-domain comparison
   - Good for tonal content
   - Complements other methods

4. **🚀 Wav2Vec2 GPU (AI-Powered)**
   - Neural network-based using Facebook's Wav2Vec2 model
   - Full GPU acceleration with PyTorch
   - 10-50x faster than CPU methods
   - Cross-correlation on GPU using FFT
   - Automatic bars/tone detection

5. **🧠 Smart Hybrid Mode**
   - Runs GPU analysis first for speed
   - Automatically verifies with MFCC+Onset if results inconsistent
   - Perfect for multichannel componentized files
   - Refinement step for sub-frame accuracy

6. **🔊 Audio Fingerprinting**
   - Chromaprint-based fingerprint matching
   - Best for identical content comparison
   - Not suitable for dubbed content (different languages)

## 📊 Output Formats

### JSON Reports
```json
{
  "analysis_id": "20250827_143052",
  "master_file": "master.mov",
  "dub_file": "dub.mov",
  "sync_results": {
    "consensus_offset_seconds": -2.456,
    "confidence_score": 0.94,
    "methods_used": ["mfcc"],
    "frame_offsets": [
      {"fps": 23.976, "frames": -58.9, "display": "-2.46s (-59f @23.976)"}
    ]
  },
  "analysis_metadata": {
    "duration_seconds": 4.2,
    "timestamp": "2025-08-27T14:30:52",
    "system_info": {...}
  }
}
```

### Web Interface Results
- Real-time analysis progress
- Visual offset indicators with color coding
- Batch processing status and statistics
- Detailed expandable results per file pair

## ⚙ Configuration

### Environment Variables
```bash
# General Settings
export SYNC_ANALYZER_TEMP_DIR="/tmp/sync_analyzer"
export SYNC_ANALYZER_LOG_LEVEL="INFO"
export MOUNT_PATH="/mnt/data"              # Base path for file access

# GPU/AI Settings
export USE_GPU=true                         # Enable GPU acceleration
export AI_WAV2VEC2_MODEL_PATH=""           # Custom Wav2Vec2 model path
export AI_MODEL_CACHE_DIR="./models"       # Model cache directory
export HF_LOCAL_ONLY=1                     # Use local models only (no HuggingFace downloads)
export YAMNET_MODEL_PATH=""                # Custom YAMNet model path

# Long File Settings
export LONG_FILE_THRESHOLD_SECONDS=180     # Threshold for chunked analysis
export LONG_FILE_GPU_BYPASS=true           # Bypass chunking for GPU
export LONG_FILE_GPU_BYPASS_MAX_SECONDS=900

# Redis/Celery Settings
export REDIS_URL="redis://localhost:6379/0"
export CELERY_BROKER_URL="redis://localhost:6379/0"

# Security
export ALLOWED_ORIGINS="http://localhost:8000,http://localhost:3002"
```

### Server Configuration
The FastAPI server runs on port 8000 by default:
```bash
# Start all services (FastAPI + Celery via Supervisord)
bash start_all.sh

# Or start manually
uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Analysis Defaults
Configure in `fastapi_app/app/core/config.py`:
- Default analysis methods
- Frame rate presets
- Confidence thresholds
- Output directories

## 🔍 Troubleshooting

### Common Issues

**"FFmpeg not found"**
```bash
# Install FFmpeg
sudo apt-get install ffmpeg  # Ubuntu/Debian
brew install ffmpeg          # macOS
```

**"Permission denied" on repair**
```bash
# Check file permissions
chmod 644 your_video_file.mov
```

**Web UI not loading**
```bash
# Check server is running
curl http://localhost:3001/
# Check for port conflicts
lsof -i :3001
```

### Performance Tuning

**For large files:**
- Use MFCC method for speed
- Increase analysis window size
- Consider file preprocessing

**For batch processing:**
- Use `--quiet` flag to reduce output
- Implement parallel processing for multiple cores
- Monitor disk space for output files

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

For detailed repository setup, style, testing, and PR conventions, see `CONTRIBUTING.md`.

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black sync_analyzer/ web_ui/
flake8 sync_analyzer/ web_ui/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏢 Professional Use

This system is designed for professional broadcast, post-production, and media workflows. It has been tested with:

- **Broadcast Television**: Multi-language dubbing sync correction
- **Film Post-Production**: ADR and dialogue replacement sync
- **Streaming Media**: Content localization workflows
- **Educational Media**: Lecture capture sync correction

For enterprise licensing and support, please contact: [your-email@company.com]

## 🙋 Support

- **Documentation**: See `docs/` directory for detailed guides
- **Issues**: GitHub Issues for bug reports and feature requests
- **Discussions**: GitHub Discussions for community support
- **Professional Support**: Contact for enterprise support options

---

**Built for professionals, by professionals.** 🎬🎵



