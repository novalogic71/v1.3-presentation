#!/bin/bash
set -Eeuo pipefail

# Ensure we are running under bash even if invoked via `sh start_all.sh`
if [ -z "${BASH_VERSION:-}" ]; then
  echo "❌ This script requires bash. Run: bash Sync_dub_final/start_all.sh"
  exit 1
fi

# Professional Audio Sync Analyzer - All Services Startup Script
# Starts FastAPI backend and Web UI frontend

# Resolve repo root based on this script's location so it works
# no matter where it's invoked from.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

echo "🎵 Professional Audio Sync Analyzer - Starting All Services"
echo "==========================================================="

has_cmd() { command -v "$1" >/dev/null 2>&1; }

# Function to check if port is in use (tries lsof, ss, then Python socket)
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

# Function to kill process on port (tries lsof, then fuser)
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
    else
        echo "⚠️  Unable to auto-kill processes on port ${port} (no lsof/fuser). Please free the port manually." >&2
    fi
}

# Check for required files using absolute paths
if [ ! -f "$ROOT_DIR/fastapi_app/main.py" ] || [ ! -f "$ROOT_DIR/web_ui/server.py" ]; then
    echo "❌ Error: Required files not found under $ROOT_DIR"
    exit 1
fi

# Stop any existing services
echo "🔍 Checking for existing services..."
check_port 8000 && kill_port 8000
check_port 3002 && kill_port 3002

# Start FastAPI backend
echo ""
echo "🚀 Starting FastAPI Backend (Port 8000)..."
API_DIR="$ROOT_DIR/fastapi_app"
VENV_DIR="$API_DIR/fastapi_venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# Fallback to project-level venvs if fastapi_venv is missing
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
    echo "❌ Python not found in virtual environment. Looked in:"
    echo "   - $API_DIR/fastapi_venv/bin/python"
    echo "   - $ROOT_DIR/venv/bin/python"
    echo "   - $ROOT_DIR/.venv/bin/python"
    echo "   Create a venv and install deps:"
    echo "     python -m venv venv && source venv/bin/activate && pip install -r fastapi_app/requirements.txt"
    exit 1
fi

# Print environment info and ensure FastAPI dependencies are installed (including transformers/torch)
echo "🐍 Python binary: $PY"
echo "📦 Pip binary:    $PIP"
"$PY" -V || true
"$PY" - <<'PY'
import sys
print('sys.executable =', sys.executable)
try:
    import fastapi, uvicorn, transformers, torch  # noqa: F401
    print('FASTAPI_DEPS_OK')
except Exception as e:
    print('FASTAPI_DEPS_MISSING:', e)
    raise SystemExit(1)
PY
if [ $? -ne 0 ]; then
    echo "📦 Installing FastAPI dependencies (fastapi_app/requirements.txt)..."
    "$PIP" install -r "$API_DIR/requirements.txt" || {
        echo "❌ Failed to install FastAPI dependencies";
        exit 1;
    }
fi

# Configure AI model cache directory for both HuggingFace and custom code
export AI_MODEL_CACHE_DIR="${AI_MODEL_CACHE_DIR:-$API_DIR/ai_models}"
export HF_HOME="$AI_MODEL_CACHE_DIR"
echo "🧠 AI_MODEL_CACHE_DIR set to: $AI_MODEL_CACHE_DIR"
echo "🧠 HF_HOME set to: $HF_HOME"

# Start API using the venv's Python explicitly (avoid relying on shell activation)
"$PY" "$API_DIR/main.py" &
FASTAPI_PID=$!

# Wait for FastAPI to start and check multiple times
echo "⏳ Waiting for FastAPI to start..."
for i in {1..10}; do
    sleep 2
    if check_port 8000; then
        echo "✅ FastAPI Backend running (PID: $FASTAPI_PID)"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ FastAPI failed to start on port 8000 after 20 seconds"
        kill $FASTAPI_PID 2>/dev/null || true
        exit 1
    fi
    echo "   Attempt $i/10 - still waiting..."
done

# Start Web UI frontend
echo ""
echo "🚀 Starting Web UI Frontend (Port 3002)..."
UI_DIR="$ROOT_DIR/web_ui"

# Check Python dependencies for UI (install into the same venv)
"$PY" - <<'PY' 2>/dev/null || UI_DEPS_MISSING=1
try:
    import flask, flask_cors  # noqa: F401
    print('UI_DEPS_OK')
except Exception:
    raise SystemExit(1)
PY
if [ "${UI_DEPS_MISSING:-0}" = "1" ]; then
    echo "📦 Installing Web UI dependencies into venv..."
    "$PIP" install flask flask-cors || {
        echo "❌ Failed to install Web UI dependencies";
        exit 1;
    }
fi

# Create required directories
mkdir -p "$UI_DIR/ui_sync_reports"

# Start UI server in background (use same venv Python)
"$PY" "$UI_DIR/server.py" &
UI_PID=$!

# Wait for Web UI to start and check multiple times
echo "⏳ Waiting for Web UI to start..."
for i in {1..10}; do
    sleep 2
    if check_port 3002; then
        echo "✅ Web UI Frontend running (PID: $UI_PID)"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Web UI failed to start on port 3002 after 20 seconds"
        kill $FASTAPI_PID $UI_PID 2>/dev/null || true
        exit 1
    fi
    echo "   Attempt $i/10 - still waiting..."
done

echo ""
echo "🎉 All services started successfully!"
echo "=================================="
echo "📡 FastAPI Backend: http://localhost:8000"
echo "   📚 API Docs: http://localhost:8000/docs"
echo "   🩺 Health: http://localhost:8000/health"
echo ""
echo "🌐 Web UI Frontend: http://localhost:3002"
echo "   🎛️ Main Interface: http://localhost:3002"
echo ""
echo "📋 Service PIDs:"
echo "   FastAPI: $FASTAPI_PID"
echo "   Web UI: $UI_PID"
echo ""
echo "🛑 Press Ctrl+C to stop all services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    kill $FASTAPI_PID $UI_PID 2>/dev/null || true
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on script termination
trap cleanup SIGINT SIGTERM

# Wait for background processes
wait
