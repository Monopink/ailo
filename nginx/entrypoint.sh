#!/bin/sh
set -eu

if [ -z "${DOMAIN:-}" ]; then
  echo "[ERROR] DOMAIN is required"
  exit 1
fi

TEMPLATE_NAME="${NGINX_TEMPLATE:-app.conf}"
TEMPLATE_FILE="/etc/nginx/templates/${TEMPLATE_NAME}"
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-backend:8000}"
ADMIN_AUTH_REALM="${ADMIN_AUTH_REALM:-Production Admin}"

if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "[ERROR] template not found: $TEMPLATE_FILE"
  exit 1
fi

envsubst '$DOMAIN $BACKEND_UPSTREAM $ADMIN_AUTH_REALM' < "$TEMPLATE_FILE" > /etc/nginx/conf.d/default.conf

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
CERT_FILE="${CERT_DIR}/fullchain.pem"
KEY_FILE="${CERT_DIR}/privkey.pem"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
  echo "[WARN] Certificate files not found, generating temporary self-signed certificate for ${DOMAIN}"
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=${DOMAIN}" >/dev/null 2>&1
fi

exec nginx -g 'daemon off;'
