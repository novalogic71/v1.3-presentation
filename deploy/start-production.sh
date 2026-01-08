#!/bin/bash
# Production Startup Script
# Ensures services are started in the correct order with proper health checks

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "═══════════════════════════════════════════════════════════════"
echo "  Professional Audio Sync Analyzer - Production Startup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

cd "$ROOT_DIR"

# Check if Docker is available
if ! command -v docker &>/dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

# Use docker compose v2 if available, otherwise docker-compose
COMPOSE_CMD="docker compose"
if ! docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
fi

echo "🔧 Using: $COMPOSE_CMD"
echo ""

# Stop any existing containers
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.production.yml down --remove-orphans 2>/dev/null || true

# Build and start
echo ""
echo "🏗️  Building containers..."
$COMPOSE_CMD -f docker-compose.production.yml build

echo ""
echo "🚀 Starting services..."
$COMPOSE_CMD -f docker-compose.production.yml up -d

# Wait for health checks
echo ""
echo "⏳ Waiting for services to become healthy..."

MAX_WAIT=120
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check Redis health
    REDIS_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' sync-analyzer-redis 2>/dev/null || echo "unknown")
    
    # Check App health
    APP_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' sync-analyzer-app 2>/dev/null || echo "unknown")
    
    echo "  Redis: $REDIS_HEALTH | App: $APP_HEALTH (${ELAPSED}s)"
    
    if [ "$REDIS_HEALTH" = "healthy" ] && [ "$APP_HEALTH" = "healthy" ]; then
        break
    fi
    
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

echo ""
if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "⚠️  Warning: Services may not be fully healthy yet"
    echo "   Check logs with: docker logs sync-analyzer-app"
else
    echo "✅ All services are healthy!"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Services Started Successfully"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "🌐 Web UI:     http://localhost:8000/app"
echo "📚 API Docs:   http://localhost:8000/docs"
echo "🩺 Health:     http://localhost:8000/health"
echo ""
echo "📋 Useful commands:"
echo "   View logs:     docker logs -f sync-analyzer-app"
echo "   Stop:          $COMPOSE_CMD -f docker-compose.production.yml down"
echo "   Restart:       $COMPOSE_CMD -f docker-compose.production.yml restart"
echo "   Health check:  bash scripts/healthcheck.sh"
echo ""

