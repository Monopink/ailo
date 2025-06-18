#!/bin/bash

echo "Stopping running containers..."
docker-compose down

echo "Rebuilding python service..."
docker-compose build python

echo "Starting all services..."
docker-compose up -d

echo "Showing logs..."
docker-compose logs -f 