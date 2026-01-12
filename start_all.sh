#!/bin/bash
# Professional Audio Sync Analyzer - Simple Startup Script

cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"

echo "🎵 Professional Audio Sync Analyzer"
echo "===================================="
echo ""

# ─────────────────────────────────────────────────────────────────
# Kill existing processes
# ─────────────────────────────────────────────────────────────────
echo "🛑 Stopping existing processes..."
pkill -9 -f "python.*main.py" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null
pkill -9 -f "celery" 2>/dev/null
pkill -9 -f "supervisord" 2>/dev/null
fuser -k 8000/tcp 2>/dev/null
sleep 2
echo "✅ Cleanup complete"
echo ""

# ─────────────────────────────────────────────────────────────────
# Find Python
# ─────────────────────────────────────────────────────────────────
if [ -x "$ROOT_DIR/venv/bin/python" ]; then
    PY="$ROOT_DIR/venv/bin/python"
elif [ -x "$ROOT_DIR/fastapi_app/fastapi_venv/bin/python" ]; then
    PY="$ROOT_DIR/fastapi_app/fastapi_venv/bin/python"
else
    echo "❌ Python venv not found!"
    echo "   Run: python -m venv venv && source venv/bin/activate && pip install -r fastapi_app/requirements.txt"
    exit 1
fi
echo "🐍 Python: $PY"

# ─────────────────────────────────────────────────────────────────
# Environment setup
# ─────────────────────────────────────────────────────────────────
export HUGGINGFACE_HUB_CACHE="$ROOT_DIR/ai_models"
export TRANSFORMERS_CACHE="$ROOT_DIR/ai_models"
export AI_MODEL_CACHE_DIR="$ROOT_DIR/ai_models"
export HF_HOME="$ROOT_DIR/ai_models"
export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/fastapi_app"
mkdir -p "$ROOT_DIR/logs" 2>/dev/null

echo "🤖 AI Model Cache: $AI_MODEL_CACHE_DIR"

# ─────────────────────────────────────────────────────────────────
# Start Celery Worker (for background job processing)
# ─────────────────────────────────────────────────────────────────
echo ""
echo "🔧 Starting Celery worker..."
cd "$ROOT_DIR/fastapi_app"
HUGGINGFACE_HUB_CACHE="$HUGGINGFACE_HUB_CACHE" TRANSFORMERS_CACHE="$TRANSFORMERS_CACHE" HF_HOME="$HF_HOME" AI_MODEL_CACHE_DIR="$AI_MODEL_CACHE_DIR" PYTHONPATH="$PYTHONPATH" $PY -m celery -A app.core.celery_app worker --loglevel=info --concurrency=2 > "$ROOT_DIR/logs/celery.log" 2>&1 &
CELERY_PID=$!
cd "$ROOT_DIR"
echo "   Celery PID: $CELERY_PID"

# ─────────────────────────────────────────────────────────────────
# Start the server
# ─────────────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting server..."
echo "⏳ Loading AI model (takes ~15 seconds)..."

cd "$ROOT_DIR/fastapi_app"
HUGGINGFACE_HUB_CACHE="$HUGGINGFACE_HUB_CACHE" TRANSFORMERS_CACHE="$TRANSFORMERS_CACHE" HF_HOME="$HF_HOME" AI_MODEL_CACHE_DIR="$AI_MODEL_CACHE_DIR" $PY main.py > "$ROOT_DIR/logs/server.log" 2>&1 &
SERVER_PID=$!
cd "$ROOT_DIR"

# Wait for server to be ready
for i in {1..30}; do
    sleep 2
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo "════════════════════════════════════════"
        echo "✅ SERVER READY!"
        echo "════════════════════════════════════════"
        echo ""
        echo "🌐 Web UI:  http://localhost:8000/app"
        echo "📚 API:     http://localhost:8000/docs"
        echo ""
        echo "📝 Logs:    tail -f logs/server.log"
        echo "🛑 Stop:    ./stop.sh"
        echo ""
        exit 0
    fi
    printf "."
done

# Failed to start
echo ""
echo "❌ Server failed to start!"
echo ""
echo "Last 20 lines of log:"
tail -20 "$ROOT_DIR/logs/server.log"
exit 1
