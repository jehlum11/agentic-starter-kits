#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$SCRIPT_DIR/local"

echo "=== Langflow Simple Tool Calling Agent - Local Deployment ==="
echo ""

# Check podman
if ! command -v podman &>/dev/null; then
  echo "ERROR: Podman is not installed."
  echo "  macOS: brew install podman podman-compose && podman machine init && podman machine start"
  echo "  Linux: sudo dnf install -y podman && pip install podman-compose"
  exit 1
fi

if ! command -v podman-compose &>/dev/null; then
  echo "ERROR: podman-compose is not installed. Install with: pip install podman-compose"
  exit 1
fi

# Copy .env if it doesn't exist
if [ ! -f "$LOCAL_DIR/.env" ]; then
  cp "$LOCAL_DIR/.env.example" "$LOCAL_DIR/.env"
  echo "Created .env from .env.example"
fi

# Generate Langfuse secrets if not already set
if ! grep -q '^LANGFUSE_ADMIN_PASSWORD=.\+' "$LOCAL_DIR/.env" 2>/dev/null; then
  GENERATED_PWD=$(openssl rand -base64 12)
  sed -i.bak "s/^LANGFUSE_ADMIN_PASSWORD=.*/LANGFUSE_ADMIN_PASSWORD=$GENERATED_PWD/" "$LOCAL_DIR/.env"
  rm -f "$LOCAL_DIR/.env.bak"
  echo "Generated Langfuse admin password."
fi

if ! grep -q '^LANGFUSE_ENCRYPTION_KEY=.\+' "$LOCAL_DIR/.env" 2>/dev/null; then
  GENERATED_KEY=$(openssl rand -hex 32)
  sed -i.bak "s/^LANGFUSE_ENCRYPTION_KEY=.*/LANGFUSE_ENCRYPTION_KEY=$GENERATED_KEY/" "$LOCAL_DIR/.env"
  rm -f "$LOCAL_DIR/.env.bak"
  echo "Generated Langfuse encryption key."
fi

# Ask about Ollama on first run
OLLAMA_FLAG="$LOCAL_DIR/.ollama-enabled"
if [ ! -f "$OLLAMA_FLAG" ]; then
  echo ""
  read -p "Do you want to use Ollama as a local LLM? (Y/n) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "yes" > "$OLLAMA_FLAG"
  else
    echo "no" > "$OLLAMA_FLAG"
    echo "Ollama disabled. You can point Langflow to an external model endpoint instead."
  fi
fi

USE_OLLAMA=$(cat "$OLLAMA_FLAG")

# Start Ollama natively (not in a container) for GPU acceleration
if [ "$USE_OLLAMA" = "yes" ]; then
  if ! command -v ollama &>/dev/null; then
    echo "Ollama is not installed. Installing..."
    if [[ "$(uname)" == "Darwin" ]]; then
      brew install ollama
    else
      curl -fsSL https://ollama.com/install.sh | sh
    fi
  fi

  # Start ollama if not already running
  if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
  else
    echo "Ollama is already running."
  fi

  # Pull model if needed
  if [ -f "$LOCAL_DIR/.env" ]; then
    OLLAMA_MODEL=$(grep -E '^OLLAMA_MODEL=' "$LOCAL_DIR/.env" | cut -d= -f2- || true)
  fi
  OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"

  if ollama list | grep -q "$OLLAMA_MODEL"; then
    echo "Ollama model '$OLLAMA_MODEL' already available."
  else
    echo "Pulling Ollama model: $OLLAMA_MODEL (first time only)..."
    ollama pull "$OLLAMA_MODEL" || \
      echo "Warning: Could not pull model. Run manually: ollama pull $OLLAMA_MODEL"
  fi
fi

cd "$LOCAL_DIR" || { echo "ERROR: Directory $LOCAL_DIR not found."; exit 1; }

# Start containerized services (Langflow, PostgreSQL, Langfuse)
echo ""
echo "Starting local stack (Langflow + PostgreSQL + Langfuse v3 + ClickHouse + MinIO + Redis)..."
podman-compose up -d

echo ""
echo "Waiting for Langflow to start (this may take a few minutes)..."
LANGFLOW_READY=false
for i in $(seq 1 60); do
  if curl -s http://localhost:7860/health >/dev/null 2>&1; then
    LANGFLOW_READY=true
    echo "Langflow is ready!"
    break
  fi
  sleep 5
done

if [ "$LANGFLOW_READY" = false ]; then
  echo "ERROR: Langflow did not start within 5 minutes."
  echo "Check logs: podman logs local_langflow_1"
  exit 1
fi

echo ""
echo "Waiting for Langfuse to start (this may take several minutes)..."
LANGFUSE_READY=false
for i in $(seq 1 60); do
  if curl -s http://localhost:3000/api/public/health >/dev/null 2>&1; then
    LANGFUSE_READY=true
    echo "Langfuse is ready!"
    break
  fi
  sleep 10
done

if [ "$LANGFUSE_READY" = false ]; then
  echo "WARNING: Langfuse did not start within 10 minutes. Tracing and logging will not work until it is up."
  echo "Check logs: podman logs local_langfuse-web_1"
fi

echo ""
echo "=== Local environment is ready ==="
echo ""
echo "  Langflow UI:  http://localhost:7860"
echo "  Langfuse:     http://localhost:3000  (login: admin@langflow.local / password auto-generated in local/.env)"
if [ "$USE_OLLAMA" = "yes" ]; then
  echo "  Ollama API:   http://localhost:11434  (running natively on host)"
fi
echo ""
echo "  Next steps:"
echo "    1. Open http://localhost:7860"
echo "    2. Import the flow: flows/outdoor-activity-agent.json"
echo "    3. Configure the flow components:"
echo "       - KServe vLLM: set api_base=http://host.containers.internal:11434/v1 and model_name=qwen2.5:7b"
echo "       - NPS Search Parks: set api_key (get one at https://developer.nps.gov)"
echo "       - NPS Park Alerts: set api_key (same NPS key)"
echo "    4. Run the agent from the Langflow UI"
echo ""
echo "  To stop:              ./cleanup-local.sh"
echo "  To stop and wipe data: ./cleanup-local.sh --force"
