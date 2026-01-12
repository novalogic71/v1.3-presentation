#!/bin/bash
# Stop the server

echo "🛑 Stopping server..."
pkill -9 -f "python.*main.py" 2>/dev/null
pkill -9 -f "uvicorn" 2>/dev/null
fuser -k 8000/tcp 2>/dev/null
echo "✅ Server stopped"

