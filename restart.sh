#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "Restarting all services..."

# First, run the stop script to ensure a clean shutdown
# The './' is important to specify that the script is in the current directory
./stop.sh

echo "" # Add a blank line for better readability

# Then, run the start script to bring everything back up
./start.sh

echo "All services have been restarted."
