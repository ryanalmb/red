#!/bin/bash
# =============================================================================
# Mail Server Entrypoint — starts Postfix + Dovecot
# =============================================================================
set -e

echo "[mail-entrypoint] Starting Postfix..."
postfix start

echo "[mail-entrypoint] Starting Dovecot in foreground..."
exec dovecot -F
