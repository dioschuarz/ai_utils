#!/bin/bash
# Startup script to start all MCP servers in the background
# This script can be run at system startup or manually

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Starting MCP Servers"
echo "============================================================"

# Check if unified compose file exists
if [ -f "docker-compose.yml" ]; then
    echo "Using unified docker-compose.yml..."
    docker compose -f docker-compose.yml up -d
    echo "✓ All servers started in background"
else
    echo "Using individual docker-compose files..."
    python3 manage_mcp_servers.py start
fi

echo ""
echo "Servers are running in the background."
echo "Check status with: python3 manage_mcp_servers.py status"
echo "View logs with: python3 manage_mcp_servers.py logs <server> --follow"
