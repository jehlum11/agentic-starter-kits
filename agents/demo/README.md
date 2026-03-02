<div style="text-align: center;">

# Demo: Outdoor Activity Agent

</div>

---

## Overview

This demo shows how to customize the base **LangGraph ReAct Agent** template (`agents/base/langgraph_react_agent/`) to build a real agent with live API tools.

The resulting agent recommends the best day and time window for outdoor activities by reasoning across weather, air quality, daylight, and National Park Service data.

**Example query:** *"I want to go hiking near Denver this weekend. What day is best?"*

---

## Prerequisites

- **uv** package manager ([docs.astral.sh/uv](https://docs.astral.sh/uv/))
- **NPS API Key** — free from [developer.nps.gov](https://developer.nps.gov) (sign up to get a 40-character key)
- **Ollama** — only if using a local model ([ollama.com](https://ollama.com/) or `brew install ollama`)

---

## How `.env` drives everything

The `.env` file is the single source of configuration. All scripts read from it to decide what to do:

```
# LLM Configuration
API_KEY=not-needed
BASE_URL=http://localhost:8321
MODEL_ID=ollama/qwen2.5:7b
CONTAINER_IMAGE=not-needed

# National Park Service API Key
NPS_API_KEY=your-nps-api-key

# MLflow Tracing (optional)
# MLFLOW_TRACKING_URI=https://your-mlflow-gateway/mlflow
# MLFLOW_TRACKING_TOKEN=your-token
# MLFLOW_WORKSPACE=your-workspace
# MLFLOW_ENABLE_WORKSPACES=true
```

**The key field is `BASE_URL`:**

| `BASE_URL` value | What happens |
|---|---|
| `http://localhost:8321` | Scripts deploy Ollama + LlamaStack locally, or Ollama on the cluster |
| `https://api.openai.com/v1` (or any remote URL) | Scripts skip Ollama/LlamaStack entirely — agent connects directly to the hosted model |

> **Model note:** `qwen2.5:7b` is recommended for reliable function calling with Ollama. Smaller models like `llama3.2:3b` struggle with multi-tool orchestration.

---

## Files to copy to the base template

From the demo directory, copy these files into `agents/base/langgraph_react_agent/`:

| Source file | Destination | Notes |
|-------------|-------------|-------|
| `src/.../tools.py` | `src/langgraph_react_agent_base/tools.py` | Fix import: change `langgraph_outdoor_activity_agent` to `langgraph_react_agent_base` |
| `src/.../agent.py` | `src/langgraph_react_agent_base/agent.py` | Fix imports: change `langgraph_outdoor_activity_agent` to `langgraph_react_agent_base` |
| `.env` | `.env` | All secrets and config — share securely with your team |
| `deploy-local.sh` | `deploy-local.sh` | One-command local setup and run |
| `deploy-cluster.sh` | `deploy-cluster.sh` | One-command cluster deployment |
| `setup-cluster.sh` | `setup-cluster.sh` | Deploys Ollama on cluster (or configures hosted model) |
| `cleanup-cluster.sh` | `cleanup-cluster.sh` | Removes all cluster resources |
| `cleanup-local.sh` | `cleanup-local.sh` | Stops LlamaStack, cleans up local |
| `k8s/ollama-deployment.yaml` | `k8s/ollama-deployment.yaml` | Ollama pod for the cluster |
| `k8s/ollama-service.yaml` | `k8s/ollama-service.yaml` | Ollama service |

Also add these lines to `requirements.txt`:
```
httpx>=0.27.0
mlflow>=2.19.0
```

And in `main.py`, change `recursion_limit` from `10` to `25`.

> **Import fix:** After copying `tools.py` and `agent.py`, replace all occurrences of `langgraph_outdoor_activity_agent` with `langgraph_react_agent_base` in the import lines.

---

## Run locally

### With local Ollama (default `.env`)

Start Ollama in one terminal:
```bash
ollama serve
```

Run the agent in another terminal:
```bash
cd agents/base/langgraph_react_agent
chmod +x deploy-local.sh
./deploy-local.sh
```

The script detects `localhost` in `BASE_URL` and automatically:
- Pulls the model from `MODEL_ID`
- Starts LlamaStack
- Launches the interactive agent

### With a hosted model (e.g. OpenAI)

Update `.env`:
```
API_KEY=sk-your-openai-key
BASE_URL=https://api.openai.com/v1
MODEL_ID=gpt-4o-mini
```

Then run:
```bash
./deploy-local.sh
```

The script detects a remote `BASE_URL` and skips Ollama and LlamaStack — it just installs dependencies and runs the agent directly.

### To change the Ollama model

Update these three places:
- `MODEL_ID` in `.env` (e.g. `ollama/qwen2.5:7b`)
- The model entry in `run_llama_server.yaml` under `registered_resources.models`

### Try it out

```
I want to go hiking near Denver this weekend. What day is best?
Is it safe to go running outdoors in San Francisco tomorrow morning?
I want to go biking in Yosemite next weekend, any recommendations?
```

### Clean up

```bash
chmod +x cleanup-local.sh
./cleanup-local.sh
```

---

## Deploy to OpenShift cluster

### 1. Update `.env` for cluster

Set `CONTAINER_IMAGE` to the registry path where the deploy script will build and push the agent image:

```
CONTAINER_IMAGE=quay.io/your-username/langgraph-outdoor-activity-agent:latest
```

### 2. Login

```bash
oc login -u "login" -p "password" https://your-cluster:port
docker login -u='login' -p='password' quay.io
```

### 3. Set up cluster dependencies (run once)

```bash
chmod +x setup-cluster.sh
./setup-cluster.sh
```

The script prompts you to choose:
- **Local Ollama** — deploys Ollama on the cluster, pulls the model, verifies NPS/MLflow
- **Hosted model** — asks for `BASE_URL`, `MODEL_ID`, `API_KEY`, saves them to `.env`, skips Ollama

### 4. Deploy the agent

```bash
chmod +x deploy-cluster.sh
./deploy-cluster.sh
```

The script reads `.env` and:
- If `BASE_URL` is `localhost` → replaces it with the in-cluster Ollama URL, checks Ollama is running
- If `BASE_URL` is a remote URL → uses it directly, skips Ollama check
- Builds and pushes the Docker image
- Creates K8s secrets
- Deploys the agent and prints the route URL

### 5. Test

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to go hiking near Denver this weekend. What day is best?"}'
```

### 6. Tear down cluster resources

```bash
chmod +x cleanup-cluster.sh
./cleanup-cluster.sh
```

---

## MLflow Tracing (Optional)

MLflow tracing is already wired into `agent.py`. It activates when `MLFLOW_TRACKING_URI` is set in `.env`. No code changes needed.

Uncomment the MLflow lines in `.env`:

```
MLFLOW_TRACKING_URI=https://your-mlflow-gateway-url/mlflow
MLFLOW_TRACKING_TOKEN=your-openshift-token
MLFLOW_WORKSPACE=your-workspace-name
MLFLOW_ENABLE_WORKSPACES=true
```

- The tracking token is auto-refreshed from `oc whoami -t` by the deploy scripts
- On the cluster, MLflow env vars are injected into the agent pod automatically by `deploy-cluster.sh`
- When not set, tracing is disabled with no overhead

See [MLflow LangGraph Tracing docs](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/) for details.

---

## What changed (summary)

| File | Change |
|------|--------|
| `src/.../tools.py` | Replaced 2 dummy tools with 6 real API tools (geocoding, weather, air quality, sunrise/sunset, NPS parks, NPS alerts) |
| `src/.../agent.py` | Updated tool imports, domain-specific system prompt, and MLflow tracing |
| `requirements.txt` | Added `httpx>=0.27.0` and `mlflow>=2.19.0` |
| `.env` | Single config file that drives all scripts (LLM, NPS, MLflow) |
| `main.py` | Increased recursion limit from 10 to 25 |
| `run_llama_server.yaml` | Added `qwen2.5:7b` to registered models |
| `deploy-local.sh` | One-command local run (auto-detects Ollama vs hosted) |
| `deploy-cluster.sh` | One-command cluster deploy (auto-detects Ollama vs hosted) |
| `setup-cluster.sh` | Cluster setup (prompts for Ollama or hosted model) |
| `cleanup-cluster.sh` | Removes all cluster resources |
| `cleanup-local.sh` | Stops LlamaStack, cleans up local |

Everything else — `Dockerfile`, `k8s/`, `examples/` — stays the same.

---

## APIs Used

- [Open-Meteo](https://open-meteo.com/) — Weather, air quality, geocoding (free, no key required)
- [National Park Service API](https://developer.nps.gov) — Park search and alerts (free key required)
