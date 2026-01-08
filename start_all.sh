#!/bin/bash
set -Eeuo pipefail

# Ensure we are running under bash even if invoked via `sh start_all.sh`
if [ -z "${BASH_VERSION:-}" ]; then
  echo "❌ This script requires bash. Run: bash start_all.sh"
  exit 1
fi

# Professional Audio Sync Analyzer - All-in-One Server Startup Script
# Starts Redis, Celery Worker, and FastAPI backend with integrated Web UI

# Resolve repo root based on this script's location
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

echo "🎵 Professional Audio Sync Analyzer - Starting All Services"
echo "============================================================"
echo "   Redis + Celery Worker + FastAPI (Port 8000)"
echo ""

has_cmd() { command -v "$1" >/dev/null 2>&1; }

# Function to check if port is in use
check_port() {
    local port="$1"
    if has_cmd lsof; then
        lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1 && return 0 || return 1
    elif has_cmd ss; then
        ss -ltn 2>/dev/null | awk '{print $4}' | grep -E ":${port}$" >/dev/null 2>&1 && return 0 || return 1
    elif has_cmd python3; then
        python3 - <<PY >/dev/null 2>&1 && exit 0 || exit 1
import socket
s=socket.socket(); s.settimeout(0.25)
try:
    s.connect(('127.0.0.1', ${port}))
    print('in_use')
except Exception:
    pass
finally:
    s.close()
PY
        [ $? -eq 0 ] && return 0 || return 1
    else
        echo "⚠️  Cannot check port ${port}: no lsof/ss/python3" >&2
        return 1
    fi
}

# Function to kill process on port
kill_port() {
    local port="$1"
    if has_cmd lsof; then
        local pids
        pids=$(lsof -ti:"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "🔄 Stopping existing service on port $port (PID(s): $pids)"
            kill -9 $pids 2>/dev/null || true
            sleep 2
        fi
    elif has_cmd fuser; then
        echo "🔄 Attempting to stop processes on port $port via fuser"
        fuser -k "${port}/tcp" 2>/dev/null || true
        sleep 2
    fi
}

# Check for required files
if [ ! -f "$ROOT_DIR/fastapi_app/main.py" ]; then
    echo "❌ Error: Required files not found under $ROOT_DIR"
    exit 1
fi

# Setup Python environment
API_DIR="$ROOT_DIR/fastapi_app"
VENV_DIR="$API_DIR/fastapi_venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# Fallback to project-level venvs
if [ ! -d "$VENV_DIR" ]; then
    for alt in "$ROOT_DIR/venv" "$ROOT_DIR/.venv"; do
        if [ -d "$alt" ]; then
            echo "ℹ️  Using alternate virtualenv: $alt"
            VENV_DIR="$alt"
            PY="$VENV_DIR/bin/python"
            PIP="$VENV_DIR/bin/pip"
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

echo "🐍 Python binary: $PY"

# Check if Redis is available
REDIS_AVAILABLE=false
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo ""
echo "🔍 Checking Redis availability..."
if has_cmd redis-cli; then
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo "✅ Redis is running and responding"
        REDIS_AVAILABLE=true
    else
        echo "⚠️  Redis is installed but not running"
        echo "   Start Redis with: redis-server --daemonize yes"
        echo "   Or: sudo systemctl start redis"
    fi
else
    echo "⚠️  redis-cli not found"
    echo "   Install Redis: sudo apt install redis-server"
fi

if [ "$REDIS_AVAILABLE" = false ]; then
    echo ""
    echo "⚠️  Redis not available - jobs will use in-memory fallback"
    echo "   (Jobs will NOT persist across server restarts)"
    echo ""
    read -p "Continue without Redis? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please start Redis first."
        exit 1
    fi
fi

# Stop any existing services
echo ""
echo "🔍 Checking for existing services..."
check_port 8000 && kill_port 8000
check_port 3002 && kill_port 3002

# Kill existing Celery workers
pkill -f "celery.*sync_analyzer" 2>/dev/null || true
sleep 1

# Environment setup
export HF_HOME="${AI_MODEL_CACHE_DIR:-$API_DIR/ai_models}"
export DEBUG=true
export REDIS_URL="$REDIS_URL"
export PYTHONPATH="$ROOT_DIR:$API_DIR:${PYTHONPATH:-}"

# Create required directories
mkdir -p "$ROOT_DIR/web_ui/proxy_cache"
mkdir -p "$ROOT_DIR/web_ui/ui_sync_reports"
mkdir -p "$ROOT_DIR/sync_reports"
mkdir -p "$ROOT_DIR/logs"

# Start Celery worker if Redis is available
CELERY_PID=""
if [ "$REDIS_AVAILABLE" = true ]; then
    echo ""
    echo "🚀 Starting Celery Worker..."
    cd "$API_DIR"
    "$PY" -m celery -A app.core.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        --hostname="sync-worker@%h" \
        > "$ROOT_DIR/logs/celery_worker.log" 2>&1 &
    CELERY_PID=$!
    cd "$ROOT_DIR"
    
    # Wait for Celery to start
    sleep 3
    if kill -0 $CELERY_PID 2>/dev/null; then
        echo "✅ Celery Worker running (PID: $CELERY_PID)"
    else
        echo "⚠️  Celery Worker failed to start (check logs/celery_worker.log)"
        echo "   Continuing with in-memory fallback..."
        CELERY_PID=""
    fi
fi

# Start FastAPI
echo ""
echo "🚀 Starting FastAPI Server (Port 8000)..."
"$PY" "$API_DIR/main.py" > "$ROOT_DIR/logs/fastapi.log" 2>&1 &
FASTAPI_PID=$!

# Wait for FastAPI to start
echo "⏳ Waiting for FastAPI to start..."
for i in {1..15}; do
    sleep 2
    if check_port 8000; then
        echo "✅ FastAPI Server running (PID: $FASTAPI_PID)"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "❌ FastAPI failed to start (check logs/fastapi.log)"
        [ -n "$CELERY_PID" ] && kill $CELERY_PID 2>/dev/null || true
        exit 1
    fi
    echo "   Attempt $i/15 - still waiting..."
done

# Print summary
echo ""
echo "🎉 All services started successfully!"
echo "======================================="
echo ""
echo "🌐 Web UI & API: http://localhost:8000"
echo "   🎛️  Main App: http://localhost:8000/app"
echo "   🏠  Splash:   http://localhost:8000/"
echo ""
echo "📚 API Documentation:"
echo "   📖  Swagger:  http://localhost:8000/docs"
echo "   📘  ReDoc:    http://localhost:8000/redoc"
echo "   🩺  Health:   http://localhost:8000/health"
echo ""
if [ "$REDIS_AVAILABLE" = true ]; then
    echo "🔄 Background Jobs: Celery + Redis (persistent)"
    echo "   Jobs survive browser refresh AND server restart"
else
    echo "🔄 Background Jobs: In-memory fallback"
    echo "   ⚠️  Jobs survive browser refresh but NOT server restart"
fi
echo ""
echo "📋 Service PIDs:"
echo "   FastAPI: $FASTAPI_PID"
[ -n "$CELERY_PID" ] && echo "   Celery:  $CELERY_PID"
echo ""
echo "📝 Logs:"
echo "   FastAPI: $ROOT_DIR/logs/fastapi.log"
[ -n "$CELERY_PID" ] && echo "   Celery:  $ROOT_DIR/logs/celery_worker.log"
echo ""
echo "🛑 Press Ctrl+C to stop all services"

# Cleanup function
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
