FROM nginx:alpine

# Configure Alpine mirrors for China
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# Install tools for health checks, env substitution and certificate bootstrap.
RUN apk add --no-cache curl gettext openssl

# Copy custom nginx configuration templates
COPY conf.d/ /etc/nginx/templates/
COPY entrypoint.sh /entrypoint.sh

# Create directories for SSL certificates
RUN mkdir -p /etc/nginx/ssl
RUN chmod +x /entrypoint.sh

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Use nginx with environment variable substitution and first-run cert bootstrap.
CMD ["/entrypoint.sh"]
