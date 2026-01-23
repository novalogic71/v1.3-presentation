#!/bin/bash
set -e

echo "🎵 Professional Audio Sync Analyzer - Starting Services"
echo "==================================================="

# Default to running Celery in dev unless explicitly disabled
RUN_CELERY=${RUN_CELERY:-true}

# Start FastAPI backend
echo "🚀 Starting FastAPI Backend (Port ${PORT_API:-8000})..."
cd /app/fastapi_app
python main.py &
API_PID=$!

# Wait for API to be ready
echo "⏳ Waiting for FastAPI to start..."
for i in {1..30}; do
    if curl -f http://localhost:${PORT_API:-8000}/health >/dev/null 2>&1; then
        echo "✅ FastAPI Backend running (PID: $API_PID)"
        break
    fi
    sleep 1
done

# Start Celery worker (dev only)
if [ "$RUN_CELERY" = "true" ]; then
    echo "🚀 Starting Celery Worker..."
    cd /app/fastapi_app
    celery -A app.core.celery_app worker --loglevel=info --concurrency=4 --hostname=sync-worker@%h &
    CELERY_PID=$!
    echo "✅ Celery Worker running (PID: $CELERY_PID)"
else
    echo "⏭️  Skipping Celery Worker (RUN_CELERY=$RUN_CELERY)"
    CELERY_PID=""
fi

# Start Flask web UI
echo "🚀 Starting Web UI Frontend (Port ${PORT_UI:-3002})..."
cd /app/web_ui
python server.py &
UI_PID=$!

# Wait for UI to be ready
echo "⏳ Waiting for Web UI to start..."
for i in {1..30}; do
    if curl -f http://localhost:${PORT_UI:-3002} >/dev/null 2>&1; then
        echo "✅ Web UI Frontend running (PID: $UI_PID)"
        break
    fi
    sleep 1
done

echo ""
echo "🎉 All services started successfully!"
echo "=================================="
echo "📡 FastAPI Backend: http://localhost:${PORT_API:-8000}"
echo "   📚 API Docs: http://localhost:${PORT_API:-8000}/docs"
if [ "$RUN_CELERY" = "true" ]; then
  echo "🧵 Celery Worker: running"
fi
echo "🌐 Web UI Frontend: http://localhost:${PORT_UI:-3002}"
echo ""
echo "🛑 Press Ctrl+C to stop all services"

# Keep container running and handle signals
trap "kill $API_PID $UI_PID $CELERY_PID 2>/dev/null; exit" SIGTERM SIGINT
wait
