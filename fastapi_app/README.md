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
- **Real-time Progress**: Live progress tracking with detailed stage information
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

### 📊 Progress Tracking & Monitoring
- **Real-time Updates**: Live progress reporting for all analysis stages
- **AI Model Progress**: Window-by-window Wav2Vec2 processing updates
- **Multi-stage Breakdown**: Detailed progress for embedding extraction, similarity computation, and alignment
- **GPU Utilization**: Monitor CUDA memory usage and processing status
- **Status Messages**: Descriptive progress messages like "Processing window 23/45"
- **Consensus Tracking**: Progress updates for traditional methods (MFCC, onset, spectral)
- **API Progress Monitoring**: REST endpoints for real-time progress queries

#### Progress Flow Example
```
AI Analysis: Starting master audio processing... (5%)
AI Analysis: Master embeddings - Processing window 10/45 (25%)
AI Analysis: Processing dub audio... (40%)  
AI Analysis: Dub embeddings - Processing window 30/45 (67%)
AI Analysis: Computing similarity matrix... (75%)
AI Analysis: Finding optimal alignment... (90%)
AI Analysis: Complete! (100%)
```

## 🔧 Recent Critical Fixes (September 2025)

### ✅ Fixed Offset Calculation Accuracy
- **Issue**: Cross-correlation formulas had 1.487x scaling errors causing 7+ second offset inaccuracies
- **Fix**: Corrected reference points in all analysis methods (MFCC, Onset, Spectral, Chunked)
- **Accuracy**: Improved from 7+ second errors to ~0.3 second precision
- **Sample Rate**: Fixed mismatch between 48kHz original files and 22kHz resampled analysis

### ⚡ Multi-GPU Support & Batch Processing
- **Issue**: Batch processing hung at 90% during AI analysis due to GPU memory exhaustion
- **Fix**: Implemented automatic workload distribution across all available GPUs
- **Performance**: Round-robin GPU assignment prevents memory buildup
- **Result**: Batch processing now completes successfully with better resource utilization

### 📂 Files Modified
- `app/services/sync_analyzer_service.py`: Multi-GPU integration
- `sync_analyzer/core/optimized_large_file_detector.py`: Offset formula and sample rate fixes
- `sync_analyzer/core/audio_sync_detector.py`: Correlation reference point corrections
- `sync_analyzer/ai/embedding_sync_detector.py`: Multi-GPU support and memory cleanup

## 🏗 Architecture

```
fastapi_app/
├── app/
│   ├── api/v1/           # API endpoints and routers
│   ├── core/             # Core configuration and utilities
│   ├── models/           # Pydantic data models
│   ├── services/         # Business logic services
│   └── middleware/       # Custom middleware
├── static/               # Static files (if any)
├── main.py              # FastAPI application entry point
├── requirements.txt     # Python dependencies
├── .env.example        # Environment variables template
└── README.md           # This file
```

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

#### Windows
```bash
# Download FFmpeg from https://ffmpeg.org/download.html
# Add to PATH environment variable
```

#### GPU Setup (Optional but Recommended)
```bash
# Ubuntu/Debian - Install NVIDIA drivers and CUDA
sudo apt update
sudo apt install nvidia-driver-545 nvidia-cuda-toolkit

# Verify GPU and CUDA installation
nvidia-smi
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Check GPU memory
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

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
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:3002", "http://localhost:8000"]
# The API also auto-allows same-host UI origins on ports 3000/3002.

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

# Caching
ENABLE_CACHING=true
CACHE_TTL=3600
```

## 🚀 Running the Application

### Development Mode
```bash
# Activate virtual environment
source venv/bin/activate

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode
```bash
# Run with production settings
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker (Optional)
```bash
# Build image
docker build -t sync-analyzer-api .

# Run container
docker run -p 8000:8000 -v /mnt/data:/mnt/data sync-analyzer-api
```

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

### API Help
- **API Help**: http://localhost:8000/api/help

## 🔌 API Endpoints

### Analysis Endpoints

#### 1. Start Sync Analysis
```http
POST /api/v1/analysis/sync
Content-Type: application/json

{
  "master_file": "/mnt/data/audio/master.wav",
  "dub_file": "/mnt/data/audio/dub.wav",
  "methods": ["mfcc", "onset"],
  "enable_ai": true,
  "ai_model": "wav2vec2",
  "sample_rate": 22050,
  "window_size": 30.0,
  "confidence_threshold": 0.8
}
```

**Curl Example:**
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

#### 2. Get Analysis Status (with Real-time Progress)
```http
GET /api/v1/analysis/{analysis_id}
```

**Response Example with Progress:**
```json
{
  "analysis_id": "analysis_20250827_143052_abc12345",
  "status": "processing",
  "progress": 67.5,
  "status_message": "AI Analysis: Dub embeddings - Processing window 23/45",
  "created_at": "2025-08-31T18:00:00Z",
  "updated_at": "2025-08-31T18:02:34Z",
  "estimated_completion": "2025-08-31T18:03:45Z"
}
```

**Curl Example:**
```bash
# Get current status and progress
curl -X GET "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"

# Monitor progress in real-time (watch every 2 seconds)
watch -n 2 'curl -s "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345" | jq ".progress, .status_message"'
```

#### 3. Cancel Analysis
```http
DELETE /api/v1/analysis/{analysis_id}
```

**Curl Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/analysis/analysis_20250827_143052_abc12345"
```

#### 4. Batch Analysis
```http
POST /api/v1/analysis/batch
Content-Type: application/json

{
  "file_pairs": [
    {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"},
    {"master": "/mnt/data/audio/master2.wav", "dub": "/mnt/data/audio/dub2.wav"}
  ],
  "analysis_config": {
    "methods": ["mfcc"],
    "sample_rate": 22050
  },
  "parallel_processing": true,
  "max_workers": 4
}
```

**Curl Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/analysis/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "file_pairs": [
      {"master": "/mnt/data/audio/master1.wav", "dub": "/mnt/data/audio/dub1.wav"}
    ],
    "analysis_config": {
      "methods": ["mfcc"],
      "sample_rate": 22050
    }
  }'
```

#### 5. List Analyses
```http
GET /api/v1/analysis/?page=1&page_size=20&status=completed
```

**Curl Examples:**
```bash
# Get first page
curl -X GET "http://localhost:8000/api/v1/analysis/?page=1&page_size=20"

# Filter by status
curl -X GET "http://localhost:8000/api/v1/analysis/?status=completed"

# Get specific page
curl -X GET "http://localhost:8000/api/v1/analysis/?page=2&page_size=10"
```

### File Management Endpoints

#### 1. List Files
```http
GET /api/v1/files?path=/mnt/data/audio
```

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/files?path=/mnt/data/audio"
```

#### 2. Upload File
```http
POST /api/v1/files/upload
Content-Type: multipart/form-data

file: @/path/to/audio.wav
file_type: audio
description: Master audio track
tags: ["master", "audio", "sync"]
```

**Curl Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/files/upload" \
  -F "file=@/path/to/audio.wav" \
  -F "file_type=audio" \
  -F "description=Master audio track" \
  -F "tags=master,audio,sync"
```

### AI Endpoints

#### 1. List AI Models
```http
GET /api/v1/ai/models
```

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/ai/models"
```

#### 2. AI Analysis
```http
POST /api/v1/ai/sync
Content-Type: application/json

{
  "audio_file": "/mnt/data/audio/sample.wav",
  "model": "wav2vec2",
  "extract_embeddings": true,
  "analyze_sync": false
}
```

**Curl Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/ai/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_file": "/mnt/data/audio/sample.wav",
    "model": "wav2vec2",
    "extract_embeddings": true
  }'
```

### Waveform Endpoints

Pre-generated waveforms enable instant QC visualization in the browser.

#### 1. Get Waveforms by Analysis ID
```http
GET /api/v1/waveforms/analysis/{analysis_id}
```

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/waveforms/analysis/analysis_20250109_120000_abc123"
```

#### 2. Generate Waveforms
```http
POST /api/v1/waveforms/generate
Content-Type: application/json

{
  "master_path": "/mnt/data/project/master.mp4",
  "dub_path": "/mnt/data/project/dub.mxf",
  "analysis_id": "analysis_20250109_120000_abc123"
}
```

**Curl Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/waveforms/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "master_path": "/mnt/data/project/master.mp4",
    "dub_path": "/mnt/data/project/dub.mxf",
    "analysis_id": "analysis_20250109_120000_abc123"
  }'
```

#### 3. List Cached Waveforms
```http
GET /api/v1/waveforms/list?limit=50
```

#### 4. Clear Waveform Cache
```http
DELETE /api/v1/waveforms/clear?older_than_days=30
```

### Health and Monitoring

#### 1. Health Check
```http
GET /health
```

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/health"
```

#### 2. API Help
```http
GET /api/help
```

**Curl Example:**
```bash
curl -X GET "http://localhost:8000/api/help"
```

## 📊 Response Examples

### Successful Analysis Response
```json
{
  "success": true,
  "analysis_id": "analysis_20250827_143052_abc12345",
  "status": "completed",
  "result": {
    "analysis_id": "analysis_20250827_143052_abc12345",
    "master_file": "/mnt/data/audio/master.wav",
    "dub_file": "/mnt/data/audio/dub.wav",
    "status": "completed",
    "consensus_offset": {
      "offset_seconds": -2.456,
      "offset_samples": -54032,
      "offset_frames": {
        "23.976": -58.9,
        "24.0": -58.9,
        "25.0": -61.4,
        "29.97": -73.6,
        "30.0": -73.7
      },
      "confidence": 0.94
    },
    "method_results": [
      {
        "method": "mfcc",
        "offset": {
          "offset_seconds": -2.456,
          "offset_samples": -54032,
          "confidence": 0.94
        },
        "processing_time": 3.2,
        "quality_score": 0.92,
        "metadata": {
          "mfcc_coefficients": 13,
          "window_size": 30.0
        }
      },
      {
        "method": "ai",
        "offset": {
          "offset_seconds": -2.445,
          "offset_samples": -53892,
          "confidence": 0.96
        },
        "processing_time": 8.7,
        "quality_score": 0.96,
        "metadata": {
          "model": "wav2vec2",
          "embedding_similarity": 0.94,
          "temporal_consistency": 0.97,
          "ai_analysis": true,
          "gpu_used": true,
          "total_windows_processed": 45
        }
      }
    ],
    "ai_result": {
      "model": "wav2vec2",
      "embedding_similarity": 0.94,
      "temporal_consistency": 0.97,
      "model_confidence": 0.96,
      "processing_time": 8.7,
      "model_metadata": {
        "offset_samples": -53892,
        "offset_seconds": -2.445,
        "gpu_memory_used": "1184 MiB",
        "cuda_device": "RTX 2080 Ti"
      }
    },
    "overall_confidence": 0.95,
    "method_agreement": 0.98,
    "sync_status": "❌ SYNC CORRECTION NEEDED (> 100ms)",
    "recommendations": [
      "Dub audio is 2.45 seconds behind master (AI: 96% confidence, MFCC: 94% confidence)",
      "Excellent method agreement (98%) - high reliability",
      "AI analysis confirms traditional detection with superior precision",
      "Recommend audio correction using FFmpeg or professional editing software"
    ]
  },
  "timestamp": "2025-08-27T14:30:52Z"
}
```

### Error Response
```json
{
  "success": false,
  "error": "File not found: /mnt/data/audio/nonexistent.wav",
  "error_code": "FILE_NOT_FOUND",
  "details": {
    "file_path": "/mnt/data/audio/nonexistent.wav"
  },
  "timestamp": "2025-08-27T14:30:52Z"
}
```

## 🔧 Development

### Code Quality
```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/

# Run tests
pytest tests/
```

### Adding New Endpoints
1. Create endpoint function in appropriate router file
2. Add Pydantic models for request/response validation
3. Update API documentation with examples
4. Add tests
5. Update this README with curl examples

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_analysis.py

# Run with verbose output
pytest -v
```

## 🚀 Deployment

### Production Considerations
- Use a production ASGI server (Gunicorn + Uvicorn)
- Set up proper logging and monitoring
- Configure rate limiting and security headers
- Use environment variables for configuration
- Set up health checks and monitoring
- Consider using a reverse proxy (Nginx)

### Docker Deployment
```bash
# Build production image
docker build -t sync-analyzer-api:latest .

# Run with production settings
docker run -d \
  --name sync-analyzer-api \
  -p 8000:8000 \
  -v /mnt/data:/mnt/data \
  -e DEBUG=false \
  -e LOG_LEVEL=INFO \
  sync-analyzer-api:latest
```

### Systemd Service
```ini
[Unit]
Description=Professional Audio Sync Analyzer API
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/sync-analyzer-api
Environment=PATH=/opt/sync-analyzer-api/venv/bin
ExecStart=/opt/sync-analyzer-api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 🐛 Troubleshooting

### Common Issues

#### FFmpeg Not Found
```bash
# Check if FFmpeg is installed
ffmpeg -version

# Install FFmpeg if missing
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS
```

#### Port Already in Use
```bash
# Check what's using the port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn main:app --port 8001
```

#### Memory Issues with AI Models
- Reduce `AI_BATCH_SIZE` in configuration
- Use CPU-only mode by setting `USE_GPU=false`
- Increase system memory or use swap

#### GPU Issues & Multi-GPU Support

**Multi-GPU Configuration (NEW):**
- The system automatically distributes workload across all available GPUs
- Uses round-robin assignment based on process ID for load balancing
- Resolves batch processing hang issues and memory exhaustion

**GPU Troubleshooting:**
```bash
# Check GPU availability and count
nvidia-smi
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Devices: {torch.cuda.device_count()}')"

# Monitor GPU memory distribution during batch processing
watch -n 1 nvidia-smi

# Check GPU memory usage per device
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Force CPU mode if GPU issues
export USE_GPU=false

# Monitor which GPU each process uses (NEW)
# Look for log messages like "Using GPU 1 of 3 available GPUs"
tail -f logs/app.log | grep "GPU"
```

**Multi-GPU Benefits:**
- Prevents 90% hang in AI analysis during batch processing
- Better memory utilization across multiple GPUs
- Faster processing for batch workloads
- Automatic cleanup prevents memory leaks

#### File Permission Issues
```bash
# Check file permissions
ls -la /mnt/data/

# Fix permissions if needed
chmod 755 /mnt/data/
chown www-data:www-data /mnt/data/
```

### Logs and Debugging
```bash
# Check application logs
tail -f logs/app.log

# Enable debug mode
export DEBUG=true
export LOG_LEVEL=DEBUG

# Check system resources
htop
df -h
free -h
```

## 📈 Performance

### Optimization Tips
- Use appropriate analysis methods for your content
- Enable parallel processing for batch operations
- **Use GPU acceleration for AI models when available** (3-5x speedup typical)
- Configure appropriate cache TTL values
- Monitor and adjust rate limiting as needed
- For AI analysis: GPU processing significantly faster than CPU
  - **CPU**: ~45-60 seconds for 2-minute audio file
  - **GPU**: ~8-15 seconds for 2-minute audio file (RTX 2080 Ti)
  - **Memory**: GPU uses ~1GB VRAM vs ~2GB system RAM for CPU

### Progress Monitoring Examples
```bash
# Monitor AI analysis progress in real-time
watch -n 1 'curl -s "http://localhost:8000/api/v1/analysis/ANALYSIS_ID" | jq ".progress, .status_message"'

# Monitor GPU utilization during analysis
nvidia-smi -l 1

# Check progress with detailed output
curl -s "http://localhost:8000/api/v1/analysis/ANALYSIS_ID" | jq '
{
  progress: .progress,
  status: .status,
  message: .status_message,
  eta: .estimated_completion
}'
```

### Benchmarking
```bash
# Test API performance
ab -n 1000 -c 10 http://localhost:8000/health

# Test analysis endpoint with timing
curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{"master_file": "...", "dub_file": "...", "methods": ["ai"], "enable_ai": true}' \
  -w "Total time: %{time_total}s\n"

# Compare GPU vs CPU performance
# GPU mode
time curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{"master_file": "...", "dub_file": "...", "methods": ["ai"], "enable_ai": true}'

# CPU mode (set USE_GPU=false in .env)
time curl -X POST "http://localhost:8000/api/v1/analysis/sync" \
  -H "Content-Type: application/json" \
  -d '{"master_file": "...", "dub_file": "...", "methods": ["ai"], "enable_ai": true}'
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Use type hints throughout the code
- Write comprehensive tests
- Update documentation for new features
- Add curl examples for new endpoints

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: This README and API docs
- **Issues**: GitHub Issues for bug reports
- **Discussions**: GitHub Discussions for questions
- **Email**: support@sync-analyzer.com

## 🙏 Acknowledgments

- **FastAPI team** for the excellent web framework
- **Pydantic team** for data validation
- **FFmpeg team** for audio/video processing
- **PyTorch team** for AI framework and CUDA integration
- **Hugging Face** for Transformers library and pre-trained models
- **Facebook Research** for Wav2Vec2 model architecture
- **NVIDIA** for CUDA toolkit and GPU acceleration support
- All contributors to the sync analyzer project

## ✨ What's New

### v2.1.0 - Progress Tracking & GPU Acceleration
- 🚀 **Real-time progress tracking** with window-level granularity
- 🎯 **Native progress bars** for AI model processing 
- 🔥 **Full GPU acceleration** with automatic CUDA detection
- 📊 **Detailed progress monitoring** via REST API
- ⚡ **3-5x speedup** with GPU processing vs CPU
- 🎬 **Professional-grade performance** for broadcast workflows

---

**Built for professionals, by professionals.** 🎬🎵 **Now with GPU power!** ⚡

For enterprise licensing and support, please contact: [support@sync-analyzer.com]
