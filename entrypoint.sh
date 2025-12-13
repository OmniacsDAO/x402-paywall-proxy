#!/usr/bin/env bash
set -e

# Ensure required env vars
if [ -z "$UPSTREAM_URL" ]; then
  echo "ERROR: UPSTREAM_URL environment variable is not set"
  exit 1
fi

if [ -z "$JWT_SECRET" ]; then
  echo "ERROR: JWT_SECRET environment variable is not set"
  exit 1
fi

# If COOKIE_NAME not explicitly given, derive it from JWT_SECRET
if [ -z "$COOKIE_NAME" ]; then
  HASH=$(printf '%s' "$JWT_SECRET" | sha256sum | cut -c1-8)
  export COOKIE_NAME="x402_${HASH}_token"
fi

echo "Using cookie name: $COOKIE_NAME"

# Substitute env vars into nginx template
envsubst '$UPSTREAM_URL $COOKIE_NAME' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Start FastAPI app (x402 backend)
/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 4021 &

# Start NGINX in foreground
nginx -g 'daemon off;'
