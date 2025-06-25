#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "Stopping and removing all services..."

# The 'down' command stops and removes containers, networks defined in docker-compose
docker-compose down

echo "All services stopped and removed." 