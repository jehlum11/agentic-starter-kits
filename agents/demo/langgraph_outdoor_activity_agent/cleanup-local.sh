#!/bin/bash
#
# Clean up local deployment of the Outdoor Activity Agent
#
# Stops LlamaStack, and optionally removes the virtual environment.
#
# Usage:
#   ./cleanup-local.sh
#

echo "=== Outdoor Activity Agent - Local Cleanup ==="
echo ""

# Stop LlamaStack
echo "--- Stopping LlamaStack ---"
pkill -f "llama stack run" 2>/dev/null && echo "LlamaStack stopped" || echo "LlamaStack was not running"

# Remove milvus data
if [ -d milvus_data ]; then
    rm -rf milvus_data && echo "Removed milvus_data/"
fi

# Remove virtual environment
if [ -d .venv ]; then
    read -p "Remove .venv? (y/N) " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        rm -rf .venv && echo "Removed .venv/"
    else
        echo "Kept .venv/"
    fi
fi

echo ""
echo "=== Local Cleanup Complete ==="
echo ""
echo "Note: Ollama is still running. Stop it with: pkill ollama"
