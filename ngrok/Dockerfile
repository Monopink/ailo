# Ngrok service for exposing local services to the internet
FROM alpine:latest

# Install curl and bash
RUN apk add --no-cache curl bash

# Install ngrok
RUN curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar xz -C /usr/local/bin

# Create working directory
WORKDIR /app

# Copy startup script
COPY start-ngrok.sh /app/start-ngrok.sh
RUN chmod +x /app/start-ngrok.sh

# Expose ngrok web interface port
EXPOSE 4040

# Start ngrok
CMD ["/app/start-ngrok.sh"]
