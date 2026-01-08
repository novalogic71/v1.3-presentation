#!/bin/bash
set -Eeuo pipefail

# Professional Audio Sync Analyzer - All-in-One Server Startup Script
# Starts Redis, Celery Worker, and FastAPI backend with integrated Web UI

# Resolve repo root based on this script's location
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

echo "🎵 Professional Audio Sync Analyzer - Starting All Services"
echo "============================================================"
echo "   Redis + Celery Worker + FastAPI (Port 8000)"
echo ""

# ─────────────────────────────────────────────────────────────────
# Kill existing processes FIRST
# ─────────────────────────────────────────────────────────────────
echo "🔪 Killing any existing processes..."

# Kill by port - more reliable than pkill
for PORT in 8000 3002; do
    if command -v fuser &>/dev/null; then
        fuser -k ${PORT}/tcp 2>/dev/null && echo "   Killed process on port $PORT" || true
    elif command -v lsof &>/dev/null; then
        lsof -ti:$PORT | xargs -r kill -9 2>/dev/null && echo "   Killed process on port $PORT" || true
    fi
done

# Kill Celery workers
pkill -9 -f "celery.*sync_analyzer" 2>/dev/null && echo "   Killed Celery workers" || true
pkill -9 -f "celery.*worker" 2>/dev/null || true

# Kill any lingering Python processes from our app
pkill -9 -f "python.*fastapi_app/main.py" 2>/dev/null && echo "   Killed FastAPI processes" || true
pkill -9 -f "uvicorn.*main:app.*8000" 2>/dev/null || true

# Give processes time to die
sleep 3

# Verify ports are free
for PORT in 8000; do
    if command -v lsof &>/dev/null && lsof -ti:$PORT &>/dev/null; then
        echo "⚠️  Warning: Port $PORT still in use after cleanup"
        lsof -ti:$PORT | xargs ps -p 2>/dev/null || true
    fi
done

echo "✅ Cleanup complete"
echo ""

# ─────────────────────────────────────────────────────────────────
# Check prerequisites
# ─────────────────────────────────────────────────────────────────
if [ ! -f "$ROOT_DIR/fastapi_app/main.py" ]; then
    echo "❌ Error: Required files not found under $ROOT_DIR"
    exit 1
fi

# Setup Python environment
API_DIR="$ROOT_DIR/fastapi_app"
VENV_DIR="$API_DIR/fastapi_venv"
PY="$VENV_DIR/bin/python"

# Fallback to project-level venvs
if [ ! -d "$VENV_DIR" ]; then
    for alt in "$ROOT_DIR/venv" "$ROOT_DIR/.venv"; do
        if [ -d "$alt" ]; then
            echo "ℹ️  Using alternate virtualenv: $alt"
            VENV_DIR="$alt"
            PY="$VENV_DIR/bin/python"
            break
        fi
    done
fi

if [ ! -x "$PY" ]; then
    echo "❌ Python not found in virtual environment."
    echo "   Create a venv and install deps:"
    echo "     python -m venv venv && source venv/bin/activate && pip install -r fastapi_app/requirements.txt"
    exit 1
fi

echo "🐍 Python: $PY"

# ─────────────────────────────────────────────────────────────────
# Check Redis
# ─────────────────────────────────────────────────────────────────
REDIS_AVAILABLE=false
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo ""
echo "🔍 Checking Redis..."
if command -v redis-cli &>/dev/null; then
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo "✅ Redis is running"
        REDIS_AVAILABLE=true
    else
        echo "⚠️  Redis not running. Start with: redis-server --daemonize yes"
    fi
else
    echo "⚠️  redis-cli not found. Install: sudo apt install redis-server"
fi

if [ "$REDIS_AVAILABLE" = false ]; then
    echo ""
    echo "⚠️  Redis not available - using in-memory fallback"
    echo "   (Jobs will NOT persist across server restarts)"
    read -t 10 -p "Continue without Redis? [Y/n] " -n 1 -r || REPLY="Y"
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Exiting. Please start Redis first."
        exit 1
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Environment setup
# ─────────────────────────────────────────────────────────────────
export HF_HOME="${AI_MODEL_CACHE_DIR:-$API_DIR/ai_models}"
export DEBUG=true
export REDIS_URL="$REDIS_URL"
export PYTHONPATH="$ROOT_DIR:$API_DIR:${PYTHONPATH:-}"

# Create required directories
mkdir -p "$ROOT_DIR/web_ui/proxy_cache" 2>/dev/null || true
mkdir -p "$ROOT_DIR/web_ui/ui_sync_reports" 2>/dev/null || true
mkdir -p "$ROOT_DIR/sync_reports" 2>/dev/null || true
mkdir -p /tmp/sync_logs 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────
# Start Celery Worker
# ─────────────────────────────────────────────────────────────────
CELERY_PID=""
if [ "$REDIS_AVAILABLE" = true ]; then
    echo ""
    echo "🚀 Starting Celery Worker..."
    cd "$API_DIR"
    "$PY" -m celery -A app.core.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        --hostname="sync-worker@%h" \
        > /tmp/sync_logs/celery_worker.log 2>&1 &
    CELERY_PID=$!
    cd "$ROOT_DIR"
    
    sleep 4
    if kill -0 $CELERY_PID 2>/dev/null; then
        echo "✅ Celery Worker running (PID: $CELERY_PID)"
    else
        echo "⚠️  Celery Worker failed to start"
        echo "   Check: /tmp/sync_logs/celery_worker.log"
        CELERY_PID=""
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Start FastAPI
# ─────────────────────────────────────────────────────────────────
echo ""
echo "🚀 Starting FastAPI Server (Port 8000)..."
cd "$API_DIR"
"$PY" main.py > /tmp/sync_logs/fastapi.log 2>&1 &
FASTAPI_PID=$!
cd "$ROOT_DIR"

# Wait for FastAPI to start
echo "⏳ Waiting for FastAPI..."
for i in {1..20}; do
    sleep 2
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ FastAPI Server running (PID: $FASTAPI_PID)"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "❌ FastAPI failed to start"
        echo "   Check: /tmp/sync_logs/fastapi.log"
        tail -20 /tmp/sync_logs/fastapi.log 2>/dev/null || true
        [ -n "$CELERY_PID" ] && kill $CELERY_PID 2>/dev/null || true
        exit 1
    fi
    echo "   Attempt $i/20..."
done

# ─────────────────────────────────────────────────────────────────
# Print summary
# ─────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "🎉 All services started successfully!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "🌐 Web UI:      http://localhost:8000/app"
echo "📚 API Docs:    http://localhost:8000/docs"
echo "🩺 Health:      http://localhost:8000/health"
echo ""
if [ "$REDIS_AVAILABLE" = true ]; then
    echo "🔄 Job Queue:   Celery + Redis (persistent)"
    echo "   ✅ Jobs survive browser refresh"
    echo "   ✅ Jobs survive server restart"
else
    echo "🔄 Job Queue:   In-memory (non-persistent)"
    echo "   ✅ Jobs survive browser refresh"
    echo "   ❌ Jobs lost on server restart"
fi
echo ""
echo "📋 PIDs:"
echo "   FastAPI: $FASTAPI_PID"
[ -n "$CELERY_PID" ] && echo "   Celery:  $CELERY_PID"
echo ""
echo "📝 Logs:"
echo "   tail -f /tmp/sync_logs/fastapi.log"
[ -n "$CELERY_PID" ] && echo "   tail -f /tmp/sync_logs/celery_worker.log"
echo ""
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# ─────────────────────────────────────────────────────────────────
# Cleanup on exit
# ─────────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    kill $FASTAPI_PID 2>/dev/null || true
    [ -n "$CELERY_PID" ] && kill $CELERY_PID 2>/dev/null || true
    pkill -f "celery.*sync_analyzer" 2>/dev/null || true
    echo "✅ All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for background processes
wait
