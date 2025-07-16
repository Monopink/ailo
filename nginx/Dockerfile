FROM nginx:alpine

# Configure Alpine mirrors for China
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# Install curl and envsubst for health checks and environment variable substitution
RUN apk add --no-cache curl gettext

# Copy custom nginx configuration templates
COPY conf.d/ /etc/nginx/templates/

# Create directories for SSL certificates
RUN mkdir -p /etc/nginx/ssl

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Use nginx with environment variable substitution
CMD ["sh", "-c", "envsubst '$$DOMAIN' < /etc/nginx/templates/default.conf > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
