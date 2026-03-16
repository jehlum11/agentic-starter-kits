<div style="text-align: center;">

# Langflow Simple Tool Calling Agent

</div>

---

## What this agent does

Outdoor activity planning agent built with Langflow. It recommends the best day and time for outdoor activities by reasoning across weather forecasts, air quality, and National Park Service data.

**Example query:** *"I want to go hiking near Denver this weekend. What day is best?"*

### Tools
| Tool | API | Description |
|------|-----|-------------|
| Open-Meteo Forecast | Open-Meteo | Daily weather forecast (temp, wind, precipitation, UV) |
| NPS Search Parks | NPS API | Search national parks by state |
| NPS Park Alerts | NPS API | Active alerts and closures for a park |

---

## Run locally

### Prerequisites

- **Podman** + **podman-compose** installed

  **macOS:**
  ```bash
  brew install podman             # install podman runtime
  brew install podman-compose     # install compose plugin
  podman machine init             # create a Linux VM (podman runs containers in a VM on macOS)
  podman machine start            # start the VM
  ```

  **Linux:**
  ```bash
  sudo dnf install -y podman      # install podman runtime
  pip install podman-compose      # install compose plugin
  sudo systemctl start podman     # start the podman service
  ```

### Start the local stack

```bash
cd agents/base/langflow_simple_tool_calling_agent
chmod +x deploy-local.sh cleanup-local.sh
./deploy-local.sh
```

This starts:
- **Langflow** on http://localhost:7860 — the agent UI
- **PostgreSQL** — shared database for Langflow and Langfuse
- **Ollama** on http://localhost:11434 — local LLM (qwen2.5:7b), runs natively on host for GPU acceleration
- **Langfuse v2** on http://localhost:3000 — tracing (admin@langflow.local / admin123)

### Import and configure the flow

1. Open http://localhost:7860
2. On first launch, Langflow asks you to create a flow — create a **Blank Flow** (this is just to get past the initial screen)
3. Click the **Langflow icon** (top left) to go to the projects page
4. Click **Upload Flow** and select `flows/outdoor-activity-agent.json`
5. Configure the flow components:

   | Component | Field | Value |
   |-----------|-------|-------|
   | KServe vLLM | api_base | http://host.containers.internal:11434/v1 |
   | KServe vLLM | model_name | qwen2.5:7b |
   | KServe vLLM | api_key | dummy |
   | NPS Search Parks | api_key | Get one free at https://developer.nps.gov |
   | NPS Park Alerts | api_key | Same NPS key as above |
6. Run the agent from the Langflow UI

> **Note:** Ollama runs natively on your machine (not in a container) to leverage GPU acceleration. On Apple Silicon Macs, this uses Metal for faster inference. Response times vary by hardware — expect 30 seconds to a few minutes per tool call. For faster responses, point the agent to a GPU-backed cluster endpoint (see [Remote model](#remote-model-instead-of-ollama)).

### Query the agent via API

Once the flow is running, you can query it via the Langflow API:

```bash
curl -X POST http://localhost:7860/api/v1/run/<flow-id> \
  -H "Content-Type: application/json" \
  -d '{"input_value": "What is the best day to hike near Denver?", "output_type": "chat", "input_type": "chat"}'
```

Replace `<flow-id>` with the flow ID from the Langflow UI. You can find it in the browser URL bar when you open the flow — e.g., `http://localhost:7860/flow/27e7203d-b2b1-4700-962a-144a66155f14` → the flow ID is `27e7203d-b2b1-4700-962a-144a66155f14`.

On the cluster, replace `localhost:7860` with your cluster's Langflow route URL.

### Stop the local stack

```bash
./cleanup-local.sh          # stop services, keep data
./cleanup-local.sh --force  # stop services, remove all data
```

**What gets preserved vs wiped:**

| Data | `cleanup-local.sh` | `cleanup-local.sh --force` |
|------|---------------------|----------------------------|
| Downloaded Ollama models (e.g., qwen2.5:7b) | Kept | Kept (stored on host, not in containers) |
| Imported Langflow flows | Kept | **Deleted** (re-import needed) |
| Langfuse traces | Kept | **Deleted** |
| PostgreSQL data | Kept | **Deleted** |
| `.env` and `.ollama-enabled` config | Kept | **Deleted** |

---

## Deploy to cluster

This agent assumes Langflow, Langfuse, and an LLM (LlamaStack/KServe) are already running on the cluster.

### Steps

1. Open the Langflow UI on your cluster
2. Import `flows/outdoor-activity-agent.json`
3. Configure the flow components:
   - **KServe vLLM**: set `api_base` to your cluster's LLM endpoint and `model_name` to your model ID. You can connect directly to the model or go through LlamaStack:

     | Option | api_base | model_name |
     |--------|----------|------------|
     | Via LlamaStack | http://llamastack-service.\<namespace\>.svc.cluster.local:8321/v1 | vllm//mnt/models |
     | Direct to KServe | http://\<model\>-predictor.\<namespace\>.svc.cluster.local:8080/v1 | /mnt/models |
   - **NPS Search Parks**: set `api_key` (get one free at https://developer.nps.gov)
   - **NPS Park Alerts**: set `api_key` (same NPS key)
4. Run the agent

No Docker build, no Helm chart, no k8s manifests needed.

---

## Pointing agent to different models

### Local model (Ollama)

By default, the local stack runs **qwen2.5:7b** on Ollama. After importing the flow, set these values in the **KServe vLLM** component:

| Field | Value |
|-------|-------|
| api_base | http://host.containers.internal:11434/v1 |
| model_name | qwen2.5:7b |
| api_key | dummy |

> Ollama runs natively on your host machine (not in a container) for GPU acceleration. Use `host.containers.internal` so containerized Langflow can reach it. Ollama doesn't require authentication, so api_key can be any non-empty string (e.g., dummy).

If you want to use a different model:

1. Pull the model on Ollama:
   ```bash
   ollama pull <model-name>
   ```
   Or edit `local/.env` to change the default model and restart:
   ```
   OLLAMA_MODEL=llama3.1:8b
   ```
   Then: `./cleanup-local.sh && ./deploy-local.sh`

2. Update the **KServe vLLM** component in the Langflow UI:

   | Field | Value |
   |-------|-------|
   | api_base | http://host.containers.internal:11434/v1 |
   | model_name | your-model-name |

> **Note:** Make sure you have enough CPU/GPU resources locally to run the model. Also, not all models handle tool calling well — for example, smaller models like Llama 3.2 1B may fail at tool calling, causing connection errors when the agent tries to invoke tools. Models like `qwen2.5:7b` and `llama3.1:8b` are known to work well with tool calling.

### Remote model (instead of Ollama)

If you primarily work with a remote model endpoint, or don't have enough local CPU/GPU resources to host a model, you can skip installing Ollama entirely by answering **n** when prompted by `deploy-local.sh`.

Then update the **KServe vLLM** component in the Langflow UI to point to your remote endpoint:

| Field | Value |
|-------|-------|
| api_base | your-model-endpoint/v1 |
| model_name | your-model-id |
| api_key | your-api-key |

---

## Viewing traces in Langfuse

After running the agent, traces are automatically sent to Langfuse.

**Locally:**
1. Open http://localhost:3000 (login: admin@langflow.local / admin123)
2. Select the **Langflow Agent** project
3. Click **Traces** in the left sidebar
4. Click on any trace to see the full agent execution — LLM calls, tool invocations, inputs, and outputs

**On cluster:**
1. Open the Langfuse route on your cluster
2. Select the **Langflow Agent** project
3. Click **Traces** in the left sidebar

---

## Exporting flows

When you export a flow from Langflow (e.g., to share with your team or commit to the repo), **API keys and secrets are embedded in the exported JSON file**. Before sharing or committing:

1. Open the exported JSON file
2. Search for `"api_key"` fields and clear their `"value"` entries
3. Or use this command to strip all API keys:
   ```bash
   python3 -c "
   import json, sys
   with open(sys.argv[1]) as f: d = json.load(f)
   for n in d.get('data',{}).get('nodes',[]):
       t = n.get('data',{}).get('node',{}).get('template',{})
       if 'api_key' in t and t['api_key'].get('value'):
           t['api_key']['value'] = ''
   with open(sys.argv[1],'w') as f: json.dump(d, f, indent=2)
   " flows/outdoor-activity-agent.json
   ```

---

## APIs Used

- [Open-Meteo](https://open-meteo.com/) — Weather and air quality (free, no key required)
- [National Park Service API](https://developer.nps.gov) — Park search and alerts (free key required)
