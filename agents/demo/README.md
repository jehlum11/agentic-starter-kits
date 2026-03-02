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

- **Ollama** installed on your machine ([ollama.com](https://ollama.com/) or `brew install ollama`)
- **NPS API Key** — free from [developer.nps.gov](https://developer.nps.gov) (sign up to get a 40-character key)
- **uv** package manager ([docs.astral.sh/uv](https://docs.astral.sh/uv/))

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
| `setup-cluster.sh` | `setup-cluster.sh` | Deploys Ollama on cluster |
| `cleanup-cluster.sh` | `cleanup-cluster.sh` | Removes all cluster resources |
| `k8s/ollama-deployment.yaml` | `k8s/ollama-deployment.yaml` | Ollama pod for the cluster |
| `k8s/ollama-service.yaml` | `k8s/ollama-service.yaml` | Ollama service |

Also add these lines to `requirements.txt`:
```
httpx>=0.27.0
mlflow>=2.19.0
```

And in `main.py`, change `recursion_limit` from `10` to `25`.

> **Model note:** `qwen2.5:7b` is recommended for reliable function calling. Smaller models like `llama3.2:3b` struggle with multi-tool orchestration, and `llama3.1:8b` does not produce structured tool calls through LlamaStack.

> **Import fix:** After copying `tools.py` and `agent.py`, replace all occurrences of `langgraph_outdoor_activity_agent` with `langgraph_react_agent_base` in the import lines.

---

## Run locally

### 1. Start Ollama

Ollama is a system-level application (not a Python package). It must be installed separately and runs outside the virtual environment.

```bash
ollama serve
```

Keep this running in its own terminal. Ollama needs to be running before the deploy script can pull models and start LlamaStack.

### 2. Run the deploy script

In a new terminal:

```bash
cd agents/base/langgraph_react_agent
chmod +x deploy-local.sh
./deploy-local.sh
```

This script will:
- Create a Python virtual environment and install dependencies
- Pull Ollama model (`qwen2.5:7b`)
- Start LlamaStack in the background
- Launch the interactive agent

Make sure `qwen2.5:7b` is registered in `run_llama_server.yaml` under `registered_resources.models`:

```yaml
- model_id: qwen2.5:7b
  provider_id: ollama
  model_type: llm
  metadata: { }
```

### Try it out

```
I want to go hiking near Denver this weekend. What day is best?
Is it safe to go running outdoors in San Francisco tomorrow morning?
I want to go biking in Yosemite next weekend, any recommendations?
```

---

## Deploy to OpenShift cluster

### 1. Update `.env` for cluster

Set the `CONTAINER_IMAGE` to your registry. The `BASE_URL` and `MODEL_ID` will be auto-detected by the deploy script once Ollama is running on the cluster.

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

This will:
- Deploy Ollama on the cluster and pull the `qwen2.5:7b` model
- Verify NPS API key and MLflow connectivity

### 4. Deploy the agent

```bash
chmod +x deploy-cluster.sh
./deploy-cluster.sh
```

This will:
- Auto-detect the in-cluster Ollama URL (`http://ollama.<namespace>.svc.cluster.local:11434/v1`)
- Build and push the Docker image
- Create K8s secrets
- Deploy the agent and print the route URL

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

This removes the agent, Ollama, and all associated secrets from the cluster.

---

## MLflow Tracing (Optional)

MLflow tracing is already wired into `agent.py` — it activates automatically when `MLFLOW_TRACKING_URI` is set. No code changes needed.

### Enable tracing

Uncomment the MLflow lines in `.env`:

```
MLFLOW_TRACKING_URI=https://your-mlflow-gateway-url/mlflow
MLFLOW_TRACKING_TOKEN=your-openshift-token
MLFLOW_WORKSPACE=your-workspace-name
MLFLOW_ENABLE_WORKSPACES=true
```

For RHOAI/OpenShift AI deployments, the tracking token is your OpenShift token (`oc whoami -t`) and the workspace matches your MLflow workspace name.

For cluster deployment, add to `k8s/deployment.yaml`:

```yaml
- name: MLFLOW_TRACKING_URI
  value: "https://your-mlflow-gateway-url/mlflow"
- name: MLFLOW_WORKSPACE
  value: "your-workspace-name"
- name: MLFLOW_ENABLE_WORKSPACES
  value: "true"
```

When set, every agent query automatically traces all tool calls, LLM requests, and responses to your MLflow instance.

When not set, tracing is disabled and the agent runs normally with no overhead.

See [MLflow LangGraph Tracing docs](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/) for details.

---

## What changed (summary)

| File | Change |
|------|--------|
| `src/.../tools.py` | Replaced 2 dummy tools with 6 real API tools (geocoding, weather, air quality, sunrise/sunset, NPS parks, NPS alerts) |
| `src/.../agent.py` | Updated tool imports, domain-specific system prompt, and MLflow tracing |
| `requirements.txt` | Added `httpx>=0.27.0` and `mlflow>=2.19.0` |
| `.env` | All secrets and config (LLM, NPS, MLflow) in one file |
| `main.py` | Increased recursion limit from 10 to 25 |
| `run_llama_server.yaml` | Added `qwen2.5:7b` to registered models |
| `deploy-local.sh` | One-command local setup and run |
| `deploy-cluster.sh` | One-command cluster deployment |
| `setup-cluster.sh` | Pre-flight check for cluster dependencies |

Everything else — `Dockerfile`, `k8s/`, `examples/` — stays the same.

---

## APIs Used

- [Open-Meteo](https://open-meteo.com/) — Weather, air quality, geocoding (free, no key required)
- [National Park Service API](https://developer.nps.gov) — Park search and alerts (free key required)
