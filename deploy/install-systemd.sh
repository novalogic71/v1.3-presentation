#!/bin/bash
# Install systemd services for Production Deployment
# Run as root or with sudo

set -e

INSTALL_DIR="/opt/sync-analyzer"
SERVICE_USER="sync-analyzer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "═══════════════════════════════════════════════════════════════"
echo "  Professional Audio Sync Analyzer - Systemd Installation"
echo "═══════════════════════════════════════════════════════════════"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Create service user if not exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" "$SERVICE_USER"
fi

# Create installation directory
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/uploads"
mkdir -p "$INSTALL_DIR/reports"
mkdir -p "$INSTALL_DIR/sync_reports"

# Copy application files (assumes script is run from repo root)
echo "Copying application files..."
cp -r "$(dirname "$SCRIPT_DIR")"/* "$INSTALL_DIR/"

# Set ownership
echo "Setting ownership..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create virtual environment if not exists
if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/fastapi_app/requirements.txt"
fi

# Install systemd service files
echo "Installing systemd services..."
cp "$SCRIPT_DIR/sync-analyzer.service" /etc/systemd/system/
cp "$SCRIPT_DIR/sync-analyzer-celery.service" /etc/systemd/system/

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable services
echo "Enabling services..."
systemctl enable sync-analyzer.service
systemctl enable sync-analyzer-celery.service

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Installation Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "To start the services:"
echo "  sudo systemctl start sync-analyzer"
echo "  sudo systemctl start sync-analyzer-celery"
echo ""
echo "To check status:"
echo "  sudo systemctl status sync-analyzer"
echo "  sudo systemctl status sync-analyzer-celery"
echo ""
echo "To view logs:"
echo "  journalctl -u sync-analyzer -f"
echo "  tail -f $INSTALL_DIR/logs/fastapi.log"
echo ""
echo "⚠️  Make sure Redis is installed and running:"
echo "  sudo apt install redis-server"
echo "  sudo systemctl enable redis-server"
echo "  sudo systemctl start redis-server"
echo ""

