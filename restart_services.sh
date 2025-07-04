#!/bin/bash

# Restart functional services only (excluding infrastructure containers)
# Infrastructure containers (mysql_db, ngrok, dozzle) will not be restarted

echo "🔄 Restarting functional services..."

# List of functional services to restart
SERVICES=(
    "web"
    "web_dev" 
    "accounts_service"
    "bot_message_service"
    "contacts_service"
)

# Restart each service
for service in "${SERVICES[@]}"; do
    echo "🔄 Restarting $service..."
    docker-compose restart "$service"
    if [ $? -eq 0 ]; then
        echo "✅ $service restarted successfully"
    else
        echo "❌ Failed to restart $service"
    fi
done

echo "🎉 All functional services restarted!"
echo "📋 Infrastructure services (mysql_db, ngrok, dozzle) were not restarted"
