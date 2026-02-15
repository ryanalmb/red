#!/bin/bash
# =============================================================================
# Exchange Simulator Entrypoint
# =============================================================================
set -e

# Generate self-signed cert for OWA
if [ ! -f /app/cert.pem ]; then
    echo "[exchange] Generating self-signed TLS certificate..."
    python3 -c "
from subprocess import run
run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-keyout', '/app/key.pem',
     '-out', '/app/cert.pem', '-days', '365', '-nodes',
     '-subj', '/CN=exchange.psyche.local/O=PSYCHE/C=US'], check=True)
"
fi

echo "[exchange] Starting Exchange OWA simulator on port 443..."
exec gunicorn -w 2 -b 0.0.0.0:443 \
    --certfile=/app/cert.pem --keyfile=/app/key.pem \
    app:app
