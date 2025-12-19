# Professional Audio Sync Analyzer - FastAPI Application

A production-ready FastAPI application that provides RESTful API access to the Professional Audio Sync Analyzer system. This application offers comprehensive audio synchronization analysis with both traditional signal processing methods and AI-enhanced detection.

## 🚀 Features

### Core Analysis Engine
- **Multi-Method Detection**: MFCC, cross-correlation, onset detection, and AI-enhanced algorithms
- **High Precision**: Sub-frame accuracy with millisecond-level offset detection
- **Professional Grade**: Optimized for broadcast television and film workflows
- **Comprehensive Reporting**: Detailed JSON and visual reports with confidence metrics

### API Features ⚡
- **RESTful Design**: Clean, intuitive REST API endpoints
- **Async Processing**: Non-blocking analysis operations with background processing
- **Real-time Progress**: Live progress tracking with Server-Sent Events (SSE)
- **Batch Processing**: Analyze multiple file pairs simultaneously
- **Comprehensive Validation**: Request/response validation with Pydantic models
- **Native Progress Bars**: Window-level progress tracking for AI models
- **GPU Utilization Monitoring**: Real-time GPU memory and processing status

### AI Integration 🤖
- **Deep Learning Models**: Wav2Vec2, YAMNet, and custom spectral embeddings
- **GPU Acceleration**: Full CUDA support with automatic GPU detection (3x RTX 2080 Ti tested)
- **Model Management**: Automatic model loading and caching
- **Progress Tracking**: Real-time AI processing updates with window-level progress
- **Embedding Extraction**: High-quality audio embeddings with detailed progress reporting

### Workflow Features 🔧
- **Analyze-and-Repair Workflow**: Complete end-to-end sync correction in one API call
- **Per-Channel Repair**: Apply individual offsets to multichannel/multi-mono audio
- **Intelligent Repair**: Automatic repair application based on configurable thresholds
- **Package Generation**: Create ZIP packages with repaired files, reports, and visualizations

### File Management 📁
- **Proxy Audio Streaming**: Transcode any audio (including Dolby Atmos) to browser-friendly formats
- **FFprobe Integration**: Detailed codec/container analysis for debugging
- **Raw File Serving**: Direct file access for downloads
- **UI State Persistence**: Save batch queue state across browser sessions

---

## 🏗 Architecture

```
fastapi_app/
├── app/
│   ├── api/v1/              # API endpoints and routers
│   │   └── endpoints/
│   │       ├── analysis.py      # Sync analysis endpoints
│   │       ├── batch.py         # Batch processing (CSV upload)
│   │       ├── files.py         # File management
│   │       ├── ai.py            # AI model endpoints
│   │       ├── health.py        # Health monitoring
│   │       ├── reports.py       # Report generation
│   │       ├── repair.py        # Per-channel repair
│   │       ├── analyze_and_repair.py  # Complete workflow
│   │       └── ui_state.py      # UI state persistence
│   ├── core/                # Core configuration and utilities
│   ├── models/              # Pydantic data models
│   ├── services/            # Business logic services
│   └── middleware/          # Custom middleware
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── API_WORKFLOW.md          # Comprehensive API workflow guide
├── CURL_EXAMPLES.md         # Ready-to-use curl commands
└── README.md                # This file
```

---

## 📋 Prerequisites

- **Python**: 3.9+ (3.10 recommended)
- **FFmpeg**: Installed and accessible in PATH
- **Memory**: Minimum 4GB RAM (8GB+ recommended for AI models)
- **Storage**: At least 2GB free space for AI model caching
- **GPU (Optional)**: NVIDIA GPU with CUDA support for accelerated AI processing
  - Tested: 3x RTX 2080 Ti (11GB VRAM each)
  - Minimum: GTX 1060 (6GB VRAM) or equivalent
  - CUDA 11.0+ and cuDNN required for GPU acceleration

### System Requirements

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg python3-pip python3-venv
```

#### macOS
```bash
brew install ffmpeg python3
```

#### GPU Setup (Optional but Recommended)
```bash
# Ubuntu/Debian - Install NVIDIA drivers and CUDA
sudo apt update
sudo apt install nvidia-driver-545 nvidia-cuda-toolkit

# Verify GPU and CUDA installation
nvidia-smi
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

---

## 🛠 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd fastapi_app
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Verify Installation
```bash
python -c "import fastapi, uvicorn; print('FastAPI installed successfully')"
ffmpeg -version
```

---

## ⚙ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Application settings
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ALLOWED_HOSTS=["*"]
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"]

# File system
MOUNT_PATH=/mnt/data
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=1073741824  # 1GB in bytes

# Analysis settings
ENABLED_METHODS=["mfcc", "onset", "spectral", "correlation", "ai"]
ENABLED_AI_MODELS=["wav2vec2", "yamnet", "spectral"]
DEFAULT_SAMPLE_RATE=22050
DEFAULT_WINDOW_SIZE=30.0
DEFAULT_CONFIDENCE_THRESHOLD=0.7

# AI settings
AI_MODEL_CACHE_DIR=./ai_models
USE_GPU=true  # Enables multi-GPU support with automatic load balancing
AI_BATCH_SIZE=4

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# Rate limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60
```

---

## 🚀 Running the Application

### Development Mode
```bash
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker
```bash
docker build -t sync-analyzer-api .
docker run -p 8000:8000 -v /mnt/data:/mnt/data sync-analyzer-api
```

---

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

### API Help
- **API Help**: http://localhost:8000/api/help

---

## 🔌 API Endpoints Overview

### Health & Monitoring (`/api/v1/health/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Comprehensive system health |
| `/ffmpeg` | GET | FFmpeg availability |
| `/ai-models` | GET | AI models status |
| `/filesystem` | GET | File system health |
| `/system` | GET | System resources |

### Analysis (`/api/v1/analysis/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sync` | POST | Start sync analysis |
| `/{analysis_id}` | GET | Get analysis status/results |
| `/{analysis_id}/progress/stream` | GET | SSE progress stream |
| `/{analysis_id}` | DELETE | Cancel analysis |
| `/` | GET | List all analyses |
| `/batch` | POST | Start batch analysis |
| `/sync/{analysis_id}/timeline` | GET | Get timeline data |

### Batch Processing (`/api/v1/analysis/batch/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload-csv` | POST | Upload batch CSV |
| `/{batch_id}/start` | POST | Start batch processing |
| `/{batch_id}/status` | GET | Get batch status |
| `/{batch_id}/results` | GET | Get batch results |
| `/{batch_id}` | DELETE | Cancel batch |

### Workflows (`/api/v1/workflows/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze-and-repair` | POST | Start complete workflow |
| `/analyze-and-repair/{workflow_id}/status` | GET | Get workflow status |
| `/analyze-and-repair/{workflow_id}/download/{file_type}` | GET | Download files |
| `/analyze-and-repair/workflows` | GET | List all workflows |
| `/analyze-and-repair/{workflow_id}` | DELETE | Cleanup workflow |

### Repair (`/api/v1/repair/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repair/per-channel` | POST | Apply per-channel offsets |

### Files (`/api/v1/files/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | List files in directory |
| `/upload` | POST | Upload file |
| `/probe` | GET | FFprobe file analysis |
| `/proxy-audio` | GET | Stream transcoded audio |
| `/raw` | GET | Get raw file |
| `/{file_id}` | GET | Get file info |
| `/{file_id}` | DELETE | Delete file |

### AI (`/api/v1/ai/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/models` | GET | List AI models |
| `/models/{model_name}` | GET | Get model info |

### Reports (`/api/v1/reports/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{analysis_id}` | GET | Get analysis report |
| `/{analysis_id}/formatted` | GET | Get formatted report |
| `/search` | GET | Search by file pair |
| `/` | GET | List reports |

### UI State (`/api/v1/ui/state/`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/batch-queue` | GET | Get batch queue state |
| `/batch-queue` | POST | Save batch queue state |
| `/batch-queue` | DELETE | Clear batch queue |

---

## 📊 Quick Start Examples

### Start Sync Analysis
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "methods": ["mfcc", "onset"],
    "enable_ai": true,
    "ai_model": "wav2vec2"
  }'
```

### Monitor Progress (SSE)
```bash
curl -N "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345/progress/stream"
```

### Start Analyze-and-Repair Workflow
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

### Proxy Audio for Browser Playback
```bash
curl -X GET "http://localhost:8000/api/v1/files/proxy-audio?path=/mnt/data/audio/atmos.ec3&format=wav"
```

---

## 📈 Performance

### GPU vs CPU Performance
| Audio Length | CPU | GPU (RTX 2080 Ti) | Speedup |
|--------------|-----|-------------------|---------|
| 2 minutes | ~45-60s | ~8-15s | 3-5x |
| 10 minutes | ~4-5min | ~1-2min | 3-4x |
| 60 minutes | ~25-30min | ~8-10min | 3x |

### Multi-GPU Benefits
- Automatic workload distribution across GPUs
- Prevents memory exhaustion during batch processing
- Round-robin GPU assignment for load balancing
- Faster processing for batch workloads

---

## 🐛 Troubleshooting

### Common Issues

#### FFmpeg Not Found
```bash
ffmpeg -version
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS
```

#### Port Already in Use
```bash
lsof -i :8000
kill -9 <PID>
uvicorn main:app --port 8001
```

#### GPU Issues
```bash
# Check GPU availability
nvidia-smi
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# Force CPU mode
export USE_GPU=false
```

### Logs and Debugging
```bash
tail -f logs/app.log
export DEBUG=true
export LOG_LEVEL=DEBUG
```

---

## 🔧 Development

### Code Quality
```bash
black app/ tests/
flake8 app/ tests/
mypy app/
pytest tests/
```

### Adding New Endpoints
1. Create endpoint function in appropriate router file
2. Add Pydantic models for request/response validation
3. Update API documentation with examples
4. Add tests
5. Update CURL_EXAMPLES.md

---

## 📄 Related Documentation

- [API Workflow Guide](./API_WORKFLOW.md) - Complete API workflow documentation
- [CURL Examples](./CURL_EXAMPLES.md) - Ready-to-use curl commands
- [Batch Processing Examples](./BATCH_PROCESSING_EXAMPLES.md) - Batch workflow examples

---

## ✨ What's New in v1.3.0

### New Features
- 🔧 **Analyze-and-Repair Workflow**: Complete end-to-end sync correction API
- 🔊 **Per-Channel Repair**: Individual channel offset correction
- 📡 **SSE Progress Streaming**: Real-time progress via Server-Sent Events
- 🎵 **Proxy Audio Streaming**: Transcode Atmos/E-AC-3 for browser playback
- 📊 **Timeline API**: Operator-friendly timeline data for visualization
- 💾 **UI State Persistence**: Save batch queue across browser sessions
- 🔍 **FFprobe Integration**: Detailed codec analysis endpoint
- 🔎 **Report Search**: Search reports by file pair

### Improvements
- Multi-GPU support with automatic load balancing
- Enhanced progress tracking with window-level granularity
- Better error handling and validation
- Comprehensive API documentation

---

**Built for professionals, by professionals.** 🎬🎵

For enterprise licensing and support, please contact: [support@sync-analyzer.com]
