#!/usr/bin/env bash
set -euo pipefail

mode="${1:-api}"
shift || true

# Ensure writable dirs exist
mkdir -p "${UPLOAD_DIR:-/opt/app/uploads}" "${AI_MODEL_CACHE_DIR:-/opt/app/ai_models}" /opt/app/logs

case "$mode" in
  api)
    exec uvicorn main:app --app-dir /opt/app/fastapi_app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
    ;;
  all)
    uvicorn main:app --app-dir /opt/app/fastapi_app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" &
    exec python web_ui/server.py
    ;;
  ui)
    exec python web_ui/server.py
    ;;
  *)
    exec "$mode" "$@"
    ;;
esac
