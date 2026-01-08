#!/bin/bash
# Health Check Script for Production Monitoring
# Can be called by external monitoring systems or cron

set -e

API_HOST="${API_HOST:-localhost}"
API_PORT="${API_PORT:-8000}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Check FastAPI health
check_api() {
    local response
    response=$(curl -sf --max-time 10 "http://${API_HOST}:${API_PORT}/health" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "✅ FastAPI: HEALTHY"
        return 0
    else
        echo "❌ FastAPI: UNHEALTHY"
        return 1
    fi
}

# Check Redis connectivity
check_redis() {
    if command -v redis-cli &>/dev/null; then
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q "PONG"; then
            echo "✅ Redis: HEALTHY"
            return 0
        else
            echo "❌ Redis: UNHEALTHY"
            return 1
        fi
    else
        echo "⚠️  Redis: Cannot check (redis-cli not installed)"
        return 0  # Don't fail if we can't check
    fi
}

# Check disk space
check_disk() {
    local usage
    usage=$(df -h /app 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
    if [ -n "$usage" ] && [ "$usage" -lt 90 ]; then
        echo "✅ Disk: ${usage}% used"
        return 0
    else
        echo "❌ Disk: ${usage}% used (>90% threshold)"
        return 1
    fi
}

# Check log file growth (detect runaway logging)
check_logs() {
    local log_size
    log_size=$(du -sm /app/logs 2>/dev/null | cut -f1)
    if [ -n "$log_size" ] && [ "$log_size" -lt 1000 ]; then
        echo "✅ Logs: ${log_size}MB"
        return 0
    else
        echo "⚠️  Logs: ${log_size}MB (consider cleanup)"
        return 0  # Warning only
    fi
}

# Main health check
main() {
    echo "═══════════════════════════════════════════════════"
    echo "  Health Check - $(date -Iseconds)"
    echo "═══════════════════════════════════════════════════"
    
    local exit_code=0
    
    check_api || exit_code=1
    check_redis || exit_code=1
    check_disk || exit_code=1
    check_logs
    
    echo "═══════════════════════════════════════════════════"
    
    if [ $exit_code -eq 0 ]; then
        echo "  Overall Status: ✅ HEALTHY"
    else
        echo "  Overall Status: ❌ UNHEALTHY"
    fi
    
    echo "═══════════════════════════════════════════════════"
    
    exit $exit_code
}

main "$@"

