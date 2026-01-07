#!/bin/bash
# scripts/generate_manifest.sh
# Generate Kali tool manifest by scanning container

set -euo pipefail

CONTAINER_IMAGE="${KALI_IMAGE:-red-kali-worker:latest}"
OUTPUT_FILE="${OUTPUT_FILE:-tools/manifest.yaml}"

echo "Generating tool manifest from $CONTAINER_IMAGE..."

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Run Kali container and scan for tools
# Note: Using -L to follow symlinks (e.g., sqlmap -> ../share/sqlmap/sqlmap.py)
docker run --rm "$CONTAINER_IMAGE" /bin/bash -c '
  # Get all executables from Kali-specific paths (follow symlinks with -L)
  find -L /usr/bin /usr/sbin /usr/share/metasploit-framework/tools \
       /usr/share/wordlists -maxdepth 2 -executable 2>/dev/null | \
  while read tool; do
    basename "$tool"
  done | sort -u
' | python3 scripts/categorize_tools.py > "$OUTPUT_FILE"

echo "Manifest written to $OUTPUT_FILE"
