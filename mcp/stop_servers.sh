#!/bin/bash
# Shutdown script to stop all MCP servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Stopping MCP Servers"
echo "============================================================"

# Check if unified compose file exists
if [ -f "docker-compose.yml" ]; then
    echo "Using unified docker-compose.yml..."
    docker compose -f docker-compose.yml down
    echo "✓ All servers stopped"
else
    echo "Using individual docker-compose files..."
    python3 manage_mcp_servers.py stop
fi
