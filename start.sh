#!/bin/bash
# LearningTool — Start all services

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Install it: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not available."
    echo "Install it: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if setup has been run
if [ ! -f docker-compose.yml ]; then
    echo "Error: docker-compose.yml not found."
    echo "Run setup first: python3 setup.py"
    exit 1
fi

# Check if containers need building
if ! docker images learningtool-app:latest --format "{{.ID}}" | grep -q .; then
    echo "First run — building containers (this may take 5-10 minutes)..."
    docker compose up --build -d
else
    docker compose up -d
fi

echo ""
echo "LearningTool is starting..."
echo ""

# Wait for health checks
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
echo "View logs with: docker compose logs -f"
