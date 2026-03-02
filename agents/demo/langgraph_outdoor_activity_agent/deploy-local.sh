#!/bin/bash
#
# Local deployment script for the Outdoor Activity Agent
#
# Prerequisites:
#   - Ollama installed (brew install ollama)
#   - uv installed (https://docs.astral.sh/uv/)
#   - .env file configured
#
# Usage:
#   ./deploy-local.sh
#

set -e

echo "=== Outdoor Activity Agent - Local Deployment ==="
echo ""

# Check prerequisites
if ! command -v ollama &> /dev/null; then
    echo "ERROR: Ollama is not installed. Install it with: brew install ollama"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Install it from: https://docs.astral.sh/uv/"
    exit 1
fi

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy it from the demo directory."
    exit 1
fi

source .env

# Step 1: Set up Python environment
echo "--- Setting up Python environment ---"
if [ ! -d .venv ]; then
    uv venv --python 3.12
fi
source .venv/bin/activate

# Step 2: Copy utils.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if [ -f "$ROOT_DIR/utils.py" ]; then
    # Detect the package directory (works for both demo and base template)
    PKG_DIR=$(find src -maxdepth 1 -type d ! -name src | head -1)
    if [ -n "$PKG_DIR" ]; then
        cp "$ROOT_DIR/utils.py" "$PKG_DIR/" && echo "Utils.py copied to $PKG_DIR/"
    fi
fi

# Step 3: Install dependencies
echo "--- Installing dependencies ---"
uv pip install -e . --quiet

# Step 4: Pull Ollama models
echo "--- Checking Ollama models ---"
if ! pgrep -x "ollama" > /dev/null 2>&1 && ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama in background..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
fi

echo "Pulling qwen2.5:7b (if not already pulled)..."
ollama pull qwen2.5:7b 2>&1 | tail -1

# Step 5: Create milvus data directory
mkdir -p milvus_data

# Step 6: Start LlamaStack in background
echo "--- Starting LlamaStack ---"
LLAMA_CONFIG="$ROOT_DIR/run_llama_server.yaml"
if [ ! -f "$LLAMA_CONFIG" ]; then
    echo "ERROR: run_llama_server.yaml not found at $LLAMA_CONFIG"
    exit 1
fi

# Kill any existing LlamaStack
pkill -f "llama stack run" 2>/dev/null || true
sleep 2

uv run llama stack run "$LLAMA_CONFIG" > /tmp/llamastack.log 2>&1 &
LLAMA_PID=$!

echo "Waiting for LlamaStack to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8321/v1/models > /dev/null 2>&1; then
        echo "LlamaStack is running on http://localhost:8321"
        break
    fi
    if ! kill -0 $LLAMA_PID 2>/dev/null; then
        echo "ERROR: LlamaStack failed to start. Check /tmp/llamastack.log"
        exit 1
    fi
    sleep 2
done

# Step 7: Run the agent
echo ""
echo "=== Starting Outdoor Activity Agent ==="
echo "LlamaStack PID: $LLAMA_PID (kill with: kill $LLAMA_PID)"
echo ""
uv run examples/execute_ai_service_locally.py
