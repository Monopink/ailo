#!/bin/bash

echo "Starting to update the stable environment code..."
echo "This script will rebuild services and apply the latest code changes while preserving database data."

# Stop services
echo "Stopping current services..."
docker-compose -f docker-compose.stable.yml down

# Rebuild services
echo "Rebuilding services..."
docker-compose -f docker-compose.stable.yml build stable_chat web_dev_stable

# Start services
echo "Starting updated services..."
docker-compose -f docker-compose.stable.yml up -d

echo ""
echo "Stable environment has been successfully updated!"
echo ""
echo "Services available at:"
echo " - Stable Chat Service: http://localhost:8100"
echo " - Stable Frontend: http://localhost:8101"
echo " - Stable MySQL Database: localhost:3307 (for direct DB connections)"
echo ""
echo "To stop the stable environment, run: ./stop-stable.sh" 