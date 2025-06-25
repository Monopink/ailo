#!/bin/bash

echo "Starting stable chat service environment..."
echo "This will run an independent instance of the chat service and its database for long-term use."

docker-compose -f docker-compose.stable.yml up -d

echo ""
echo "Stable environment started successfully!"
echo ""
echo "Services available at:"
echo " - Stable Chat Service: http://localhost:8100"
echo " - Stable Frontend (stable_web_dev): http://localhost:8101"
echo " - Stable MySQL Database: localhost:3307 (for direct DB connections)"
echo ""
echo "To stop the stable environment, run: ./stop-stable.sh" 