#!/bin/bash

# Professional Audio Sync Analyzer UI Startup Script
# Starts the web interface on port 8080

echo "🎵 Professional Audio Sync Analyzer UI"
echo "======================================="

# Check if we're in the right directory
if [ ! -f "server.py" ]; then
    echo "❌ Error: server.py not found. Please run from sync_ui directory."
    exit 1
fi

# Check if mount path exists
if [ ! -d "/mnt/data" ]; then
    echo "⚠️  Warning: /mnt/data mount point does not exist"
    echo "   The UI will still work but file browsing may be limited"
fi

# Check Python dependencies
echo "🔧 Checking dependencies..."
python3 -c "import flask, flask_cors" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required dependencies..."
    pip install flask flask-cors
fi

# Create required directories
mkdir -p ui_sync_reports

echo ""
echo "🚀 Starting UI Server..."
echo "   Access the UI at: http://localhost:3002"
echo "   Press Ctrl+C to stop"
echo ""

# Start the server
python3 server.py