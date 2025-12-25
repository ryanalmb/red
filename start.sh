#!/bin/bash

# Cyber-Red Startup Script

# 1. Resolve Project Root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 2. Check for Virtual Environment
VENV_PATH="$SCRIPT_DIR/venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

PYTHON_EXEC="$VENV_PATH/bin/python3"

# 3. Check for Docker Permissions
echo "🔍 Checking Docker connectivity..."
if docker ps &> /dev/null; then
    echo "✅ Docker is accessible."
    CMD="$PYTHON_EXEC -m src.main"
else
    echo "⚠️  Current user cannot access Docker socket."
    echo "🔒 Attempting to run with sudo..."
    
    # Check if we can sudo without password or prompt user
    CMD="sudo $PYTHON_EXEC -m src.main"
fi

# 4. Launch App
echo "🚀 Launching Cyber-Red..."
echo "Command: $CMD"
$CMD
