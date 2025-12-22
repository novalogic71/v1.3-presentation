# Professional Audio Sync Analyzer - Multi-Service Dockerfile
# Runs both FastAPI backend and Flask web UI

FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV MOUNT_PATH=/mnt/data
ENV PORT_API=8000
ENV PORT_UI=3002

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    ffprobe \
    libsndfile1 \
    libasound2-dev \
    portaudio19-dev \
    python3-dev \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt .
COPY fastapi_app/requirements.txt ./fastapi_app/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r fastapi_app/requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p \
    uploads \
    ai_models \
    logs \
    reports \
    web_ui/ui_sync_reports \
    web_ui/proxy_cache \
    repaired_sync_files

# Copy startup script
COPY docker-start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose ports
EXPOSE 8000 3002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health && curl -f http://localhost:3002 || exit 1

# Run startup script
CMD ["/bin/bash", "/app/start.sh"]

