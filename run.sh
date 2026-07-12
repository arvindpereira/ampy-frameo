#!/bin/bash
# Frameo Linker Runner Script
# Activates virtual environment and launches the Flask server.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Initializing Python virtual environment..."
    python3 -m venv .venv || { echo "ERROR: python3 -m venv failed." >&2; exit 1; }
    .venv/bin/pip install -r requirements.txt || { echo "ERROR: failed to install requirements." >&2; exit 1; }
fi

echo "Starting Frameo Linker server..."
echo "Your browser should open automatically. If not, visit http://127.0.0.1:5001"
exec .venv/bin/python3 app.py
