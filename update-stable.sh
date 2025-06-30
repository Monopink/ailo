#!/bin/bash

echo "Starting to update the stable environment code..."
echo "This script will rebuild services and apply the latest code changes while preserving database data."

# Stop services, rebuild if necessary, and start them again.
# The --build flag tells Compose to rebuild images before starting containers.
echo "Rebuilding and starting services..."
docker-compose -f docker-compose.stable.yml up -d --build

echo ""
echo "Stable environment has been successfully updated!"
echo ""
echo "Services available at:"
echo " - Stable Chat Service: http://localhost:8100"
echo " - Stable Frontend: http://localhost:8101"
echo " - Stable MySQL Database: localhost:3307 (for direct DB connections)"
echo ""
echo "To stop the stable environment, run: ./stop-stable.sh" 