#!/bin/bash

echo "🚀 Starting ngrok tunnel for backend..."

# Check if NGROK_AUTHTOKEN is provided
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "❌ NGROK_AUTHTOKEN environment variable is required!"
    echo "📝 Please:"
    echo "   1. Sign up at https://dashboard.ngrok.com/signup"
    echo "   2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   3. Add NGROK_AUTHTOKEN=your_token_here to your .env file"
    echo "   4. Restart the containers"
    echo ""
    echo "🔄 Waiting for authtoken... (container will keep running)"
    while [ -z "$NGROK_AUTHTOKEN" ]; do
        sleep 30
        echo "   Still waiting for NGROK_AUTHTOKEN..."
    done
fi

# Configure ngrok with authtoken
echo "🔑 Configuring ngrok with authtoken..."
ngrok config add-authtoken $NGROK_AUTHTOKEN

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
while ! curl -s http://backend:8000/health > /dev/null; do
    echo "   Waiting for backend..."
    sleep 2
done

echo "✅ backend is ready!"

# Start ngrok tunnel
echo "🌐 Starting ngrok tunnel..."
ngrok http backend:8000 --log=stdout --log-level=info &

# Wait for ngrok to start
sleep 5

# Get and display the public URL
echo "🔍 Getting ngrok public URL..."
for i in {1..10}; do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4 | head -1)

    if [ ! -z "$NGROK_URL" ]; then
        echo ""
        echo "🎉 =================================="
        echo "🌐 Ngrok tunnel established!"
        echo "📝 Public URL: $NGROK_URL"
        echo "🔗 Webhook URL: $NGROK_URL/api/v1/leancloud/webhook/{token}"
        echo "📊 Ngrok dashboard: http://localhost:4040"
        echo "=================================="
        echo ""
        break
    else
        echo "   Attempt $i: Waiting for ngrok to be ready..."
        sleep 2
    fi
done

if [ -z "$NGROK_URL" ]; then
    echo "❌ Failed to get ngrok URL after 10 attempts"
    echo "📊 Check ngrok dashboard at http://localhost:4040"
fi

# Keep the container running
echo "🔄 Keeping ngrok running..."
wait
