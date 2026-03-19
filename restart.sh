#!/bin/bash
# LearningTool — Restart all services

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f docker-compose.yml ]; then
    echo "Error: docker-compose.yml not found."
    echo "Run setup first: python3 setup.py"
    exit 1
fi

echo "Restarting LearningTool..."
docker compose down
docker compose up -d

echo ""
echo -n "Waiting for services"
for i in $(seq 1 60); do
    if curl -s http://localhost:8100 > /dev/null 2>&1; then
        echo ""
        echo ""
        echo "Ready! Open http://localhost:8100 in your browser."
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo ""
echo "Services are still starting. Check status with: docker compose ps"
