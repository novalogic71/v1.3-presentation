#!/bin/bash
set -Eeuo pipefail

# Professional Audio Sync Analyzer - All-in-One Server Startup Script
# Now with SUPERVISORD for automatic process recovery!
#
# Features:
#   ✅ Automatic restart if FastAPI or Celery crash
#   ✅ Centralized log management
#   ✅ Process health monitoring
#   ✅ Graceful shutdown

# Resolve repo root based on this script's location
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

# Mode detection
MODE="${1:-production}"  # Default to production mode

echo "🎵 Professional Audio Sync Analyzer - Starting All Services"
echo "============================================================"
echo "   Mode: $MODE (use 'dev' for development mode)"
echo "   Redis + Celery Worker + FastAPI (Port 8000)"
echo ""

# ─────────────────────────────────────────────────────────────────
# Kill existing processes FIRST
# ─────────────────────────────────────────────────────────────────
echo "🔪 Killing any existing processes..."

# Kill any existing supervisord for this app
pkill -f "supervisord.*sync-analyzer" 2>/dev/null && echo "   Killed existing supervisord" || true

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
        echo "⚠️  Redis not running. Attempting to start..."
        # Try to start Redis
        if command -v redis-server &>/dev/null; then
            redis-server --daemonize yes 2>/dev/null && sleep 2
            if redis-cli ping 2>/dev/null | grep -q "PONG"; then
                echo "✅ Redis started successfully"
                REDIS_AVAILABLE=true
            fi
        fi
        if [ "$REDIS_AVAILABLE" = false ]; then
            echo "⚠️  Could not start Redis. Start manually: redis-server --daemonize yes"
        fi
    fi
else
    echo "⚠️  redis-cli not found. Install: sudo apt install redis-server"
fi

if [ "$REDIS_AVAILABLE" = false ]; then
    echo ""
    echo "⚠️  Redis not available - using in-memory fallback"
    echo "   (Jobs will NOT persist across server restarts)"
    if [ -t 0 ]; then  # Only prompt if interactive
        read -t 10 -p "Continue without Redis? [Y/n] " -n 1 -r || REPLY="Y"
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Exiting. Please start Redis first."
            exit 1
        fi
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Environment setup
# ─────────────────────────────────────────────────────────────────
export HF_HOME="${AI_MODEL_CACHE_DIR:-$API_DIR/ai_models}"
export REDIS_URL="$REDIS_URL"
export PYTHONPATH="$ROOT_DIR:$API_DIR:${PYTHONPATH:-}"

# Set DEBUG based on mode
if [ "$MODE" = "dev" ]; then
    export DEBUG=true
else
    export DEBUG=false
fi

# Create required directories
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR" 2>/dev/null || true
mkdir -p "$ROOT_DIR/web_ui/proxy_cache" 2>/dev/null || true
mkdir -p "$ROOT_DIR/web_ui/ui_sync_reports" 2>/dev/null || true
mkdir -p "$ROOT_DIR/sync_reports" 2>/dev/null || true
mkdir -p /tmp/sync_logs 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────
# Check for Supervisord
# ─────────────────────────────────────────────────────────────────
SUPERVISORD_AVAILABLE=false
SUPERVISORD_BIN=""

# Check for supervisord in multiple locations
# 1. Current venv
# 2. Related venvs (shared environments)
# 3. System PATH
for check_venv in "$VENV_DIR" "$ROOT_DIR/../Sync_dub_final/venv" "$ROOT_DIR/fastapi_app/fastapi_venv"; do
    if [ -x "$check_venv/bin/supervisord" ]; then
        SUPERVISORD_BIN="$check_venv/bin/supervisord"
        SUPERVISORCTL_BIN="$check_venv/bin/supervisorctl"
        SUPERVISORD_AVAILABLE=true
        echo "ℹ️  Found supervisord: $SUPERVISORD_BIN"
        break
    fi
done

# Fall back to system supervisord
if [ "$SUPERVISORD_AVAILABLE" = false ] && command -v supervisord &>/dev/null; then
    SUPERVISORD_BIN="supervisord"
    SUPERVISORCTL_BIN="supervisorctl"
    SUPERVISORD_AVAILABLE=true
    echo "ℹ️  Using system supervisord"
fi

# If still not found, offer to install it
if [ "$SUPERVISORD_AVAILABLE" = false ]; then
    echo ""
    echo "⚠️  Supervisord not found for automatic process recovery."
    if [ -t 0 ]; then  # Interactive terminal
        read -t 10 -p "Install supervisor now? [Y/n] " -n 1 -r || REPLY="Y"
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "📦 Installing supervisor..."
            "$PY" -m pip install supervisor
            if [ -x "$VENV_DIR/bin/supervisord" ]; then
                SUPERVISORD_BIN="$VENV_DIR/bin/supervisord"
                SUPERVISORCTL_BIN="$VENV_DIR/bin/supervisorctl"
                SUPERVISORD_AVAILABLE=true
                echo "✅ Supervisor installed successfully"
            fi
        fi
    fi
fi

# ─────────────────────────────────────────────────────────────────
# Generate runtime supervisord config
# ─────────────────────────────────────────────────────────────────
SUPERVISOR_CONF="$ROOT_DIR/supervisord.runtime.conf"

generate_supervisor_config() {
    cat > "$SUPERVISOR_CONF" << EOF
[supervisord]
nodaemon=true
logfile=$LOG_DIR/supervisord.log
logfile_maxbytes=10MB
logfile_backups=3
loglevel=info
pidfile=/tmp/sync-analyzer-supervisord.pid
identifier=sync-analyzer-supervisor

[unix_http_server]
file=/tmp/sync-analyzer-supervisor.sock
chmod=0700

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///tmp/sync-analyzer-supervisor.sock

[program:fastapi]
command=$PY $API_DIR/main.py
directory=$API_DIR
autostart=true
autorestart=true
startsecs=10
startretries=5
stopwaitsecs=30
stdout_logfile=$LOG_DIR/fastapi.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=$LOG_DIR/fastapi_error.log
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=PYTHONPATH="$ROOT_DIR:$API_DIR",PYTHONUNBUFFERED="1",DEBUG="$DEBUG",REDIS_URL="$REDIS_URL",HF_HOME="$HF_HOME"
EOF

    # Add Celery program only if Redis is available
    if [ "$REDIS_AVAILABLE" = true ]; then
        cat >> "$SUPERVISOR_CONF" << EOF

[program:celery]
command=$PY -m celery -A app.core.celery_app worker --loglevel=info --concurrency=4 --hostname=sync-worker@%%h
directory=$API_DIR
autostart=true
autorestart=true
startsecs=10
startretries=5
stopwaitsecs=30
stopasgroup=true
killasgroup=true
stdout_logfile=$LOG_DIR/celery.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=$LOG_DIR/celery_error.log
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=PYTHONPATH="$ROOT_DIR:$API_DIR",PYTHONUNBUFFERED="1",REDIS_URL="$REDIS_URL"
EOF
    fi
}

# ─────────────────────────────────────────────────────────────────
# Start with Supervisord (if available) or fallback to manual
# ─────────────────────────────────────────────────────────────────

if [ "$SUPERVISORD_AVAILABLE" = true ]; then
    echo ""
    echo "🛡️  Using SUPERVISORD for reliable process management"
    echo "   ✅ Auto-restart on crash"
    echo "   ✅ Centralized logging"
    echo "   ✅ Health monitoring"
    echo ""
    
    # Generate config
    generate_supervisor_config
    
    echo "🚀 Starting services via supervisord..."
    
    # Start supervisord
    "$SUPERVISORD_BIN" -c "$SUPERVISOR_CONF" &
    SUPERVISOR_PID=$!
    
    # Wait for services to start
    echo "⏳ Waiting for services..."
    for i in {1..30}; do
        sleep 2
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            echo "✅ FastAPI Server is healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Services failed to start"
            echo "   Check logs: $LOG_DIR/fastapi.log"
            tail -20 "$LOG_DIR/fastapi.log" 2>/dev/null || true
            exit 1
        fi
        echo "   Attempt $i/30..."
    done
    
    # Print summary
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "🎉 All services started with SUPERVISORD!"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "🌐 Web UI:      http://localhost:8000/app"
    echo "📚 API Docs:    http://localhost:8000/docs"
    echo "🩺 Health:      http://localhost:8000/health"
    echo ""
    echo "🛡️  Process Supervision: ENABLED"
    echo "   ✅ Processes auto-restart on crash"
    echo "   ✅ Logs: $LOG_DIR/"
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
    echo "📋 Management commands:"
    echo "   Status:   $SUPERVISORCTL_BIN -c $SUPERVISOR_CONF status"
    echo "   Restart:  $SUPERVISORCTL_BIN -c $SUPERVISOR_CONF restart all"
    echo "   Logs:     tail -f $LOG_DIR/fastapi.log"
    echo ""
    echo "🛑 Press Ctrl+C to stop all services"
    echo ""
    
    # Cleanup on exit
    cleanup() {
        echo ""
        echo "🛑 Stopping all services..."
        "$SUPERVISORCTL_BIN" -c "$SUPERVISOR_CONF" shutdown 2>/dev/null || true
        kill $SUPERVISOR_PID 2>/dev/null || true
        rm -f /tmp/sync-analyzer-supervisor.sock /tmp/sync-analyzer-supervisord.pid
        echo "✅ All services stopped"
        exit 0
    }
    
    trap cleanup SIGINT SIGTERM
    
    # Wait for supervisor
    wait $SUPERVISOR_PID
    
else
    # ─────────────────────────────────────────────────────────────────
    # Fallback: Manual process management (legacy mode)
    # ─────────────────────────────────────────────────────────────────
    echo ""
    echo "⚠️  Supervisord not found - using legacy process management"
    echo "   Install for auto-restart: pip install supervisor"
    echo ""
    
    # Start Celery Worker
    CELERY_PID=""
    if [ "$REDIS_AVAILABLE" = true ]; then
        echo "🚀 Starting Celery Worker..."
        cd "$API_DIR"
        "$PY" -m celery -A app.core.celery_app worker \
            --loglevel=info \
            --concurrency=4 \
            --hostname="sync-worker@%h" \
            > "$LOG_DIR/celery.log" 2>&1 &
        CELERY_PID=$!
        cd "$ROOT_DIR"
        
        sleep 4
        if kill -0 $CELERY_PID 2>/dev/null; then
            echo "✅ Celery Worker running (PID: $CELERY_PID)"
        else
            echo "⚠️  Celery Worker failed to start"
            echo "   Check: $LOG_DIR/celery.log"
            CELERY_PID=""
        fi
    fi
    
    # Start FastAPI
    echo ""
    echo "🚀 Starting FastAPI Server (Port 8000)..."
    cd "$API_DIR"
    "$PY" main.py > "$LOG_DIR/fastapi.log" 2>&1 &
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
            echo "   Check: $LOG_DIR/fastapi.log"
            tail -20 "$LOG_DIR/fastapi.log" 2>/dev/null || true
            [ -n "$CELERY_PID" ] && kill $CELERY_PID 2>/dev/null || true
            exit 1
        fi
        echo "   Attempt $i/20..."
    done
    
    # Print summary
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "🎉 All services started (legacy mode)"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "🌐 Web UI:      http://localhost:8000/app"
    echo "📚 API Docs:    http://localhost:8000/docs"
    echo "🩺 Health:      http://localhost:8000/health"
    echo ""
    echo "⚠️  Process Supervision: DISABLED"
    echo "   ❌ Processes will NOT auto-restart on crash"
    echo "   💡 Install supervisor: pip install supervisor"
    echo ""
    if [ "$REDIS_AVAILABLE" = true ]; then
        echo "🔄 Job Queue:   Celery + Redis (persistent)"
    else
        echo "🔄 Job Queue:   In-memory (non-persistent)"
    fi
    echo ""
    echo "📋 PIDs:"
    echo "   FastAPI: $FASTAPI_PID"
    [ -n "$CELERY_PID" ] && echo "   Celery:  $CELERY_PID"
    echo ""
    echo "📝 Logs: $LOG_DIR/"
    echo "🛑 Press Ctrl+C to stop all services"
    echo ""
    
    # Cleanup on exit
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
fi
