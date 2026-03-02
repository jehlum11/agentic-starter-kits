#!/bin/bash
#
# Local deployment script for the Outdoor Activity Agent
#
# Supports both local Ollama and hosted model (OpenAI, etc.)
#
# Prerequisites:
#   - uv installed (https://docs.astral.sh/uv/)
#   - Ollama installed if using local model (brew install ollama)
#   - .env file configured
#
# Usage:
#   ./deploy-local.sh
#

set -e

echo "=== Outdoor Activity Agent - Local Deployment ==="
echo ""

if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Install it from: https://docs.astral.sh/uv/"
    exit 1
fi

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy it from the demo directory."
    exit 1
fi

source .env

# Refresh MLflow tracking token from oc if available
if [ -n "$MLFLOW_TRACKING_URI" ] && command -v oc &> /dev/null && oc whoami > /dev/null 2>&1; then
    export MLFLOW_TRACKING_TOKEN=$(oc whoami -t)
    echo "MLflow tracking token refreshed from oc"
fi

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
    PKG_DIR=$(find src -maxdepth 1 -type d ! -name src | head -1)
    if [ -n "$PKG_DIR" ]; then
        cp "$ROOT_DIR/utils.py" "$PKG_DIR/" && echo "Utils.py copied to $PKG_DIR/"
    fi
fi

# Step 3: Install dependencies
echo "--- Installing dependencies ---"
uv pip install -e . --quiet

# Detect if using local Ollama or hosted model
if echo "$BASE_URL" | grep -q "localhost"; then
    ## ============================================
    # Local Ollama flow
    ## ============================================
    if ! command -v ollama &> /dev/null; then
        echo "ERROR: Ollama is not installed. Install it with: brew install ollama"
        exit 1
    fi

    echo "--- Checking Ollama ---"
    if ! pgrep -x "ollama" > /dev/null 2>&1 && ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Starting Ollama in background..."
        ollama serve > /dev/null 2>&1 &
        sleep 3
    fi

    # Pull model from MODEL_ID, strip ollama/ prefix
    PULL_MODEL="${MODEL_ID#ollama/}"
    echo "Pulling ${PULL_MODEL} (if not already pulled)..."
    ollama pull "${PULL_MODEL}" 2>&1 | tail -1

    # Start LlamaStack
    mkdir -p milvus_data

    echo "--- Starting LlamaStack ---"
    LLAMA_CONFIG="$ROOT_DIR/run_llama_server.yaml"
    if [ ! -f "$LLAMA_CONFIG" ]; then
        echo "ERROR: run_llama_server.yaml not found at $LLAMA_CONFIG"
        exit 1
    fi

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

    echo ""
    echo "=== Starting Outdoor Activity Agent (Local Ollama) ==="
    echo "LlamaStack PID: $LLAMA_PID (kill with: kill $LLAMA_PID)"
    echo ""
    uv run examples/execute_ai_service_locally.py
else
    ## ============================================
    # Hosted model flow — no Ollama, no LlamaStack
    ## ============================================
    echo ""
    echo "Using hosted model at: ${BASE_URL}"
    echo "Model: ${MODEL_ID}"
    echo ""
    echo "=== Starting Outdoor Activity Agent (Hosted Model) ==="
    echo ""
    uv run examples/execute_ai_service_locally.py
fi
