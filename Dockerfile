# Dockerfile
FROM python:3.11-slim

# Install nginx and envsubst (via gettext-base)
RUN apt-get update && \
    apt-get install -y nginx gettext-base && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy your FastAPI app & static files
COPY main.py /app/main.py
COPY x402static /app/x402static
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Copy nginx template and entrypoint
COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Nginx listens on 4022 inside container
EXPOSE 4022

# Default envs (can override at runtime)
ENV ADDRESS=0x0000000000000000000000000000000000000000
ENV JWT_SECRET=change-me
ENV X402_PRICE=0.001
ENV X402_NETWORK=base-sepolia
ENV X402_APP_NAME="x402 Omniacs"
ENV X402_APP_LOGO=/x402static/omniacsdao_logo.png
ENV X402_CDP_CLIENT_KEY=""
ENV TOKEN_TTL_SECONDS=86400
ENV UPSTREAM_URL=http://127.0.0.1:4564

ENTRYPOINT ["/app/entrypoint.sh"]
