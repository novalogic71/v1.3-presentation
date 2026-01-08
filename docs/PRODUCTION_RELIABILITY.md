# Production Reliability Guide

This guide covers everything needed to run the Professional Audio Sync Analyzer reliably for **unattended operation**.

## Quick Start

**The main startup script now includes automatic process supervision!**

```bash
cd /mnt/data/amcmurray/Sync_dub/v1.3-presentation
./start_all.sh              # Production mode (default) - auto-restart on crash
./start_all.sh dev          # Development mode - hot-reload enabled
```

### Alternative Deployment Methods

**Docker:**
```bash
bash deploy/start-production.sh
```

**Systemd (Native Linux):**
```bash
sudo bash deploy/install-systemd.sh
sudo systemctl start sync-analyzer
```

---

## What Was Added for Reliability

### 1. Process Supervision (supervisord) - NOW DEFAULT
**Problem:** If FastAPI or Celery crashes, nothing restarts them.

**Solution:** The main `start_all.sh` now automatically uses supervisord:
- Automatically restarts crashed processes (up to 5 retries)
- Logs process events to `logs/`
- Centralized process management
- Falls back to legacy mode if supervisord not available

### 2. Redis Connection Resilience
**Problem:** If Redis becomes temporarily unavailable, the app crashes.

**Solution:** Updated `celery_app.py` with:
- Automatic reconnection on connection loss
- Configurable retry limits
- Graceful degradation when Redis unavailable

### 3. Health Monitoring
**Problem:** No way to know if services are healthy without manual checks.

**Solution:** Added `scripts/healthcheck.sh` that checks:
- FastAPI health endpoint
- Redis connectivity
- Disk space usage
- Log file sizes

### 4. Production Docker Compose
**Problem:** Original Docker setup lacks proper health checks and restarts.

**Solution:** Created `docker-compose.production.yml` with:
- Redis container with persistence
- Proper health check dependencies
- Automatic restart policies
- Log rotation
- Memory limits

### 5. Systemd Services
**Problem:** Native deployments have no automatic restart.

**Solution:** Created systemd service files in `deploy/`:
- `sync-analyzer.service` - FastAPI backend
- `sync-analyzer-celery.service` - Celery worker
- Both have automatic restart on failure

---

## Deployment Options

### Docker Deployment (Recommended)

**Prerequisites:**
- Docker & Docker Compose installed
- NVIDIA Docker runtime (if using GPU)

**Start:**
```bash
bash deploy/start-production.sh
```

**Monitor:**
```bash
# View logs
docker logs -f sync-analyzer-app

# Check health
bash scripts/healthcheck.sh

# Supervisor status (inside container)
docker exec sync-analyzer-app supervisorctl status
```

**Stop:**
```bash
docker compose -f docker-compose.production.yml down
```

### Systemd Deployment (Native)

**Prerequisites:**
- Python 3.10+
- Redis server installed
- FFmpeg installed

**Install:**
```bash
# As root
sudo bash deploy/install-systemd.sh
```

**Manage:**
```bash
# Start
sudo systemctl start sync-analyzer
sudo systemctl start sync-analyzer-celery

# Status
sudo systemctl status sync-analyzer

# Logs
journalctl -u sync-analyzer -f

# Stop
sudo systemctl stop sync-analyzer
sudo systemctl stop sync-analyzer-celery
```

---

## Configuration for Production

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required
DEBUG=false
MOUNT_PATH=/mnt/data
REDIS_URL=redis://localhost:6379/0

# Recommended
LOG_LEVEL=INFO
LOG_FILE=/opt/sync-analyzer/logs/app.log
USE_GPU=true

# Optional tuning
LONG_FILE_THRESHOLD_SECONDS=180
AI_MODEL_CACHE_DIR=/opt/sync-analyzer/ai_models
```

### Key Settings for Reliability

| Setting | Value | Description |
|---------|-------|-------------|
| `DEBUG` | `false` | Disables hot-reload and verbose logging |
| `LOG_LEVEL` | `INFO` | Reduces log noise |
| `REDIS_URL` | Required | Job queue persistence |
| `LOG_FILE` | Set path | File logging with rotation |

---

## Monitoring & Alerts

### Health Check Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Professional Audio Sync Analyzer API",
  "version": "2.0.0"
}
```

### Automated Health Monitoring

Add to crontab for regular checks:

```bash
# Check every 5 minutes
*/5 * * * * /opt/sync-analyzer/scripts/healthcheck.sh >> /var/log/sync-analyzer-health.log 2>&1
```

### Process Status File

The event listener creates `/app/logs/process_status.json` when processes fail:

```json
{
  "timestamp": "2025-01-08T12:00:00",
  "event": "PROCESS_STATE_EXITED",
  "process": "fastapi",
  "status": "UNHEALTHY"
}
```

Monitor this file for external alerting.

---

## Log Management

### Log Locations

| Log | Location | Description |
|-----|----------|-------------|
| FastAPI | `/app/logs/fastapi.log` | API requests and errors |
| Celery | `/app/logs/celery.log` | Background job processing |
| Supervisor | `/app/logs/supervisord.log` | Process management |
| Events | `/app/logs/process_events.log` | Process state changes |

### Log Rotation

Logs are automatically rotated:
- **Max size:** 10MB per file
- **Backups:** 5 files kept
- **Docker:** Uses json-file driver with 50MB max

### Cleanup Old Logs

```bash
# Manual cleanup
find /app/logs -name "*.log.*" -mtime +7 -delete
```

---

## Troubleshooting

### FastAPI Won't Start

```bash
# Check logs
docker logs sync-analyzer-app
# or
tail -f /opt/sync-analyzer/logs/fastapi_error.log

# Common issues:
# - Port 8000 already in use
# - MOUNT_PATH doesn't exist
# - Missing dependencies
```

### Redis Connection Failures

```bash
# Check Redis is running
redis-cli ping

# Check connection from app
docker exec sync-analyzer-app redis-cli -h redis ping

# Restart Redis
docker restart sync-analyzer-redis
```

### Jobs Not Processing

```bash
# Check Celery worker status
docker exec sync-analyzer-app supervisorctl status celery

# Check Celery logs
docker exec sync-analyzer-app tail -f /app/logs/celery.log

# Restart Celery
docker exec sync-analyzer-app supervisorctl restart celery
```

### High Memory Usage

```bash
# Check container stats
docker stats sync-analyzer-app

# Restart with memory limit
# Edit docker-compose.production.yml:
#   deploy.resources.limits.memory: 4G
```

---

## Backup & Recovery

### What to Backup

1. **Database:** `sync_reports/sync_reports.db`
2. **Reports:** `reports/`, `sync_reports/`
3. **Configuration:** `.env`, `supervisord.conf`
4. **AI Models:** `ai_models/` (or re-download)

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backup/sync-analyzer-$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

cp -r sync_reports "$BACKUP_DIR/"
cp -r reports "$BACKUP_DIR/"
cp .env "$BACKUP_DIR/"
```

### Recovery

1. Stop services
2. Restore backup files
3. Restart services
4. Verify health check passes

---

## Checklist for Unattended Operation

- [ ] Use `docker-compose.production.yml` or systemd services
- [ ] Set `DEBUG=false`
- [ ] Redis is running and persistent (`appendonly yes`)
- [ ] Log rotation configured
- [ ] Health check scheduled in cron
- [ ] Disk space monitoring in place
- [ ] Backup script scheduled
- [ ] External alerting configured (optional)

---

## Files Added/Modified for Reliability

```
├── start_all.sh                        # UPDATED: Now uses supervisord by default!
├── supervisord.conf                    # Docker process management config
├── supervisord.runtime.conf            # Auto-generated at runtime (gitignored)
├── Dockerfile.production               # Production Docker image
├── docker-compose.production.yml       # Production compose with Redis
├── deploy/
│   ├── sync-analyzer.service           # Systemd service for FastAPI
│   ├── sync-analyzer-celery.service    # Systemd service for Celery
│   ├── install-systemd.sh              # Installation script
│   └── start-production.sh             # Docker production startup
├── scripts/
│   ├── healthcheck.sh                  # Health check script
│   └── supervisor_eventlistener.py     # Process event monitoring
└── docs/
    └── PRODUCTION_RELIABILITY.md       # This guide
```

