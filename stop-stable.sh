#!/bin/bash
echo "Stopping stable chat service environment..."
docker-compose -f docker-compose.stable.yml down
echo ""
echo "Stable environment has been stopped."
echo "Database data is preserved in the 'stable_mysql_data' volume and will be available when you restart."
echo ""
echo "To start the stable environment again, run: ./start-stable.sh" 