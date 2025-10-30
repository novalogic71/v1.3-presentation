# Professional Audio Sync Analyzer

A comprehensive professional-grade audio synchronization analysis and repair system designed for broadcast television, film post-production, and media workflows. This system provides both command-line tools and a modern web interface for detecting and correcting audio-video sync issues.

## ✨ Features

### 🎯 Core Analysis Engine
- **Multi-Method Detection**: MFCC, cross-correlation, and AI-enhanced algorithms
- **High Precision**: Sub-frame accuracy with millisecond-level offset detection
- **Multi-GPU Support**: Automatic workload distribution across available GPUs (NEW)
- **Professional Grade**: Optimized for broadcast television and film workflows
- **Fixed Offset Calculations**: Corrected cross-correlation formulas for accurate sync detection (NEW)
- **Comprehensive Reporting**: Detailed JSON and visual reports with confidence metrics

### 🌐 Modern Web Interface
- **Intuitive UI**: Professional dark-themed interface with real-time feedback
- **Batch Processing**: Queue multiple file pairs for automated analysis
- **Visual Results**: Clear presentation of sync offset data and statistics
- **Integrated Repair**: One-click audio sync correction with FFmpeg integration
- **File Management**: Browser-based file selection with directory navigation

### 🔧 Automated Repair
- **FFmpeg Integration**: Professional-quality audio offset correction
- **Quality Preservation**: Lossless video copying with precise audio adjustment
- **Backup Creation**: Automatic backup of original files before modification
- **Batch Repair**: Process multiple files efficiently with queue management

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

## ⚡ GPU & Multi-GPU Support

- **Multi-GPU Acceleration** (NEW):
  - Automatic load balancing across all available GPUs
  - Round-robin distribution based on process ID prevents memory exhaustion
  - Resolves batch processing hang issues at 90% progress
  - Core MFCCs, AI models, and cross-correlation run on distributed GPUs
- **GPU Configuration**:
  - Enable in CLI with `--gpu`; in API set `USE_GPU=true`
  - Falls back to CPU (librosa) if CUDA/torchaudio aren't available
  - GPU memory cleanup prevents batch processing failures
- Long Files (API):
  - The API may bypass chunked analysis when a CUDA GPU is available for faster full‑length analysis.
  - Env controls:
    - `LONG_FILE_THRESHOLD_SECONDS` (default 180)
    - `LONG_FILE_GPU_BYPASS` (default true)
    - `LONG_FILE_GPU_BYPASS_MAX_SECONDS` (default 900)
- Offline AI Models:
  - Wav2Vec2 (Transformers):
    - `AI_WAV2VEC2_MODEL_PATH=/path/to/local/wav2vec2`
    - `HF_LOCAL_ONLY=1` and optional `AI_MODEL_CACHE_DIR=/path/to/cache`
  - YAMNet (TensorFlow SavedModel):
    - `YAMNET_MODEL_PATH=/path/to/yamnet_saved_model` (directory with `saved_model.pb`)
    - Optional: `AI_MODEL_CACHE_DIR` if you keep models under a shared cache root
    - To avoid network, leave `AI_ALLOW_ONLINE_MODELS` unset (default) or set `=0`
- UI Behavior:
  - Single Analyze uses the API (server decides GPU/chunked). Progress messages indicate the chosen path.
  - Batch uses the CLI and respects the UI “GPU Accel” toggle (adds `--gpu`).

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

## 🔧 Recent Improvements (September 2025)

### Fixed Offset Calculation Issues
- **Corrected Cross-Correlation Formula**: Fixed the fundamental math error in offset calculation that was causing 1.487x scaling errors
- **Sample Rate Consistency**: Resolved mismatch between original file sample rates (48kHz) and resampled rates (22kHz)
- **Method Consistency**: All analysis methods (MFCC, Onset, Spectral, Chunked) now use consistent correlation reference points
- **Improved Accuracy**: Offset detection now accurate within ~0.3 seconds instead of 7+ second errors

### Multi-GPU Support
- **Automatic Load Balancing**: Distributes workload across all available GPUs using process ID-based round-robin
- **Memory Management**: Added GPU memory cleanup to prevent batch processing failures
- **Batch Processing Fix**: Resolved 90% hang issue in AI analysis during batch processing
- **Performance Boost**: Significant speedup for multi-file analysis workflows

### Location of Changes
- `sync_analyzer/core/optimized_large_file_detector.py`: Fixed chunked analyzer offset calculation and sample rate
- `sync_analyzer/core/audio_sync_detector.py`: Corrected MFCC, Onset, and Spectral method formulas  
- `sync_analyzer/ai/embedding_sync_detector.py`: Added multi-GPU support and memory cleanup
- All components: Implemented round-robin GPU selection for load balancing

## 🏗 Architecture

### Core Components

```
sync_analyzer/
├── core/                 # Core analysis algorithms
│   ├── audio_sync_detector.py    # Main detection engine
│   ├── feature_extractors.py     # Audio feature extraction
│   └── correlation_analyzer.py   # Cross-correlation analysis
├── cli/                  # Command-line interfaces
│   ├── sync_cli.py              # Primary CLI tool
│   └── batch_processor.py       # Batch processing utility
├── reports/              # Report generation
│   └── sync_reporter.py         # JSON/visual report generator
└── utils/               # Shared utilities
    ├── audio_utils.py           # Audio processing helpers
    └── file_utils.py            # File system utilities

web_ui/
├── server.py            # Flask web server
├── index.html           # Main web interface
├── app.js               # Frontend JavaScript logic
├── style.css            # Modern UI styling
└── static/              # Static assets
```

### Analysis Methods

1. **MFCC (Mel-Frequency Cepstral Coefficients)**
   - Fast, reliable method for most content
   - Excellent for speech and music
   - ~2-5 second analysis time

2. **Cross-Correlation**
   - Raw audio waveform analysis
   - Best for pure audio content
   - Higher computational cost

3. **AI-Enhanced** (Future)
   - Machine learning-based detection
   - Handles complex audio scenarios
   - Adaptive to content type

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
export SYNC_ANALYZER_TEMP_DIR="/tmp/sync_analyzer"
export SYNC_ANALYZER_LOG_LEVEL="INFO"
export SYNC_ANALYZER_DEFAULT_METHOD="mfcc"
```

### Server Configuration
Edit `web_ui/server.py` for:
- Port configuration (default: 3001)
- File serving directories
- Analysis method defaults
- Output directory settings

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



