#!/bin/bash

# Navigate to the script's directory to ensure docker-compose command works from any path
cd "$(dirname "$0")"

echo "Starting all services in detached mode..."

# Use --build to rebuild images if necessary
# Use -d to run in the background (detached mode)
docker-compose up --build -d

echo "All services started." 