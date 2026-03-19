#!/bin/bash
# LearningTool — Stop all services

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f docker-compose.yml ]; then
    echo "No docker-compose.yml found — nothing to stop."
    exit 0
fi

echo "Stopping LearningTool..."
docker compose down

echo ""
echo "All services stopped."
