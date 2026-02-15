#!/bin/bash
# =============================================================================
# FILESERVER01 Entrypoint — starts Samba (smbd + nmbd)
# =============================================================================
set -e

echo "[fileserver] Starting nmbd..."
nmbd -D

echo "[fileserver] Starting smbd in foreground..."
exec smbd -F --no-process-group
