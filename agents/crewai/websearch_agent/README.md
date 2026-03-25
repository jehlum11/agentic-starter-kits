<div style="text-align: center;">

![CrewAI logo](/images/crewai_logo.svg)

# Web Search Agent

</div>

---

## What this agent does

A web search agent built with the CrewAI framework. It uses a ReAct-style agent with a web search tool to answer
user questions. Use with any OpenAI-compatible API.

---

### Preconditions

- Copy/paste the `.env` file and set values for your environment
- Choose **local** or **RH OpenShift Cluster** and fill the needed values
- Run `./init.sh` to load values from `.env` into the environment

Go to agent dir:

```bash
cd agents/crewai/websearch_agent
```

Change the name of .env file

```bash
mv template.env .env
```

#### Local but with a use of OpenAI API

Edit the `.env` file with your local configuration:

**OpenAI API** directly:

```ini
BASE_URL=http://localhost:8321
MODEL_ID=ollama/llama3.1:8b
API_KEY=not-needed
CONTAINER_IMAGE=not-needed
```

##### Tracing

```ini
MLFLOW_TRACKING_URI="http://localhost:5000"
MLFLOW_EXPERIMENT_NAME="CrewAI Local Experiment"
MLFLOW_HTTP_REQUEST_TIMEOUT=2
MLFLOW_HTTP_REQUEST_MAX_RETRIES=0
```

#### OpenShift Cluster

Edit the `.env` file and fill in all required values:

```ini
API_KEY=your-api-key-here
BASE_URL=https://your-llama-stack-distribution.com/v1
MODEL_ID=llama-3.1-8b-instruct
CONTAINER_IMAGE=quay.io/your-username/crewai-websearch-agent:latest
```

**Notes:**

- `API_KEY` – contact your cluster administrator
- `BASE_URL` – should end with `/v1`
- `MODEL_ID` – contact your cluster administrator
- `CONTAINER_IMAGE` – full image path where the agent container will be pushed and pulled from. The image is built
  locally, pushed to this registry, and then deployed to OpenShift.

  Format: `<registry>/<namespace>/<image-name>:<tag>`

  Examples:

    - Quay.io: `quay.io/your-username/crewai-websearch-agent:latest`
    - Docker Hub: `docker.io/your-username/crewai-websearch-agent:latest`
    - GHCR: `ghcr.io/your-org/crewai-websearch-agent:latest`

##### Tracing

To enable tracing and logging with MLflow on your OpenShift cluster, add the following environment variables to your `.env` file:

```ini
MLFLOW_TRACKING_URI="https://<openshift-dashboard-url>/mlflow"
MLFLOW_TRACKING_TOKEN="<your-openshift-token>"
MLFLOW_EXPERIMENT_NAME="<your-experiment-name>"
MLFLOW_TRACKING_INSECURE_TLS="true" # If the OpenShift cluster does not use trusted certificates
MLFLOW_WORKSPACE="<your project name>"
```

**Notes:**
- `MLFLOW_TRACKING_URI` – Replace `<openshift-dashboard-url>` with your OpenShift cluster's data science gateway URL
- `MLFLOW_TRACKING_TOKEN` – Your OpenShift authentication token. It can be obtained from the OpenShift console.
- `MLFLOW_EXPERIMENT_NAME` – A descriptive name for your experiment (e.g., "CrewAI Cluster Experiment")
- `MLFLOW_TRACKING_INSECURE_TLS` – Set to `"true"` if your OpenShift cluster does not use trusted certificates
- `MLFLOW_WORKSPACE` – Project name

- Tracing is optional; if you do not set `MLFLOW_TRACKING_URI`, the application will run without MLflow logging.

- If `MLFLOW_TRACKING_URI` is set, the application will attempt to connect to the MLflow server at startup. If the server is unreachable, the application will log a warning and continue running without tracing.

- You can control how long the application waits for the MLflow server by setting `MLFLOW_HEALTH_CHECK_TIMEOUT` (in seconds, default: `5`).

Create and activate a virtual environment (Python 3.12) in this directory using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12
source .venv/bin/activate
```

(On Windows: `.venv\Scripts\activate`)

Make scripts executable:

```bash
chmod +x init.sh
```

Load values from `.env` into environment variables:

```bash
source ./init.sh
```

---

## Local usage (Ollama + LlamaStack Server)

Create package with agent and install it in venv:

```bash
uv pip install -e .
```

Install mlflow (>=3.10.0) - *Optional: Only required if tracing is enabled*
```bash
uv pip install "mlflow>=3.10.0"
```

Install Ollama from the [Ollama site](https://ollama.com/) or via Brew:

```bash
# brew install ollama
# or
curl -fsSL https://ollama.com/install.sh | sh
```

Pull required models:
CrewAI agent need a bigger model then others.

```bash
ollama pull llama3.1:8b
```

Start Ollama service:

```bash
ollama serve
```

> **Keep this terminal open!**
> Ollama needs to keep running.

Start MLflow server:

```bash
mlflow server --port 5000
```

> **Keep this terminal open** – the server needs to keep running.

Start LlamaStack server:

```bash
llama stack run ../../../run_llama_server.yaml
```

> **Keep this terminal open** – the server needs to keep running.
> You should see output indicating the server started on `http://localhost:8321`.

Run the example:

```bash
uv run examples/execute_ai_service_locally.py
```

---

## Deployment on Red Hat OpenShift Cluster

Install MLflow for RHOAI 3.2 or 3.3 - *Optional: Only required if tracing is enabled*
```bash
uv pip install "git+https://github.com/red-hat-data-services/mlflow@rhoai-3.3"
```

Make deploy script executable:

```bash
chmod +x deploy.sh
```

Build image and deploy agent:

```bash
./deploy.sh
```

This will:

- Create Kubernetes secret for API key
- Build and push the Docker image
- Deploy the agent to OpenShift
- Create Service and Route

Get the route URL:

```bash
oc get route crewai-websearch-agent -o jsonpath='{.spec.host}'
```

Send a test request:

Non-streaming

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the best cluster hosting service?"}], "stream": false}'
```

Streaming

```bash
curl -sN -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the best cluster hosting service?"}], "stream": true}'
```

Pretty Printed Stream

```bash
curl -sN -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the best cluster hosting service?"}], "stream": true}' |
   jq -R -r -j --stream 'scan("^data:(.*)")[] | fromjson.choices[0].delta.content // empty'
```

---

## Playground UI

A browser-based chat interface is served directly by the agent at the root URL — no separate process needed.

### Running the Playground

Start the agent and open the root URL in your browser:

```bash
uvicorn main:app --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

A green dot in the header means the agent is connected and ready. Type a message and press **Enter** to send.

When deployed to OpenShift, the playground is available at the route URL.

### Standalone Flask Playground (alternative)

You can also run the playground as a separate Flask app if needed:

```bash
uv pip install flask
```

```bash
# Terminal 1: Start the agent
uvicorn main:app --port 8000

# Terminal 2: Start the playground
flask --app playground/app run --port 5001
```

| Variable    | Default                  | Description                     |
|-------------|--------------------------|---------------------------------|
| `AGENT_URL` | `http://localhost:8000`  | URL of the running agent API    |

If the agent runs on a different host or port:

```bash
AGENT_URL=https://your-agent-url flask --app playground/app run --port 5001
```

---

## MLflow Tracing

This agent supports [MLflow tracing](https://mlflow.org/docs/latest/genai/tracing/) for observability. When `MLFLOW_TRACKING_URI` is set in `.env`, tracing is automatically enabled on startup.

### How it works

CrewAI uses a [hybrid provider model](https://docs.crewai.com/en/concepts/llms) for LLM calls:

- **Native SDK providers** (OpenAI, Anthropic, Google, Azure, Bedrock) — CrewAI routes calls directly through the provider's SDK
- **LiteLLM fallback** (all other providers) — CrewAI routes calls through [LiteLLM](https://docs.litellm.ai/), which requires `crewai[litellm]`

`mlflow.crewai.autolog()` traces CrewAI orchestration (Crew, Task, Agent, Tool, Memory spans), but **LLM call-level tracing requires an additional autolog** depending on which path CrewAI uses:

| LLM Provider Path | Autologs Needed |
|---|---|
| LiteLLM (non-native providers, OpenAI-compatible endpoints) | `mlflow.crewai.autolog()` + `mlflow.litellm.autolog()` |
| OpenAI (native SDK) | `mlflow.crewai.autolog()` + `mlflow.openai.autolog()` |
| Anthropic (native SDK) | `mlflow.crewai.autolog()` + `mlflow.anthropic.autolog()` |
| Google Gemini (native SDK) | `mlflow.crewai.autolog()` + `mlflow.gemini.autolog()` |
| Azure (native SDK) | `mlflow.crewai.autolog()` + `mlflow.openai.autolog()` |
| AWS Bedrock (native SDK) | `mlflow.crewai.autolog()` + `mlflow.bedrock.autolog()` |

### Configuring the LLM provider for tracing

Set the `LLM_PROVIDER` environment variable in your `.env` to match the LLM provider you're using. This controls which `mlflow.<provider>.autolog()` is called alongside `mlflow.crewai.autolog()`:

| `LLM_PROVIDER` value | MLflow autolog enabled | When to use |
|---|---|---|
| `litellm` (default) | `mlflow.litellm.autolog()` | OpenAI-compatible endpoints (OpenShift, vLLM, Ollama, etc.) |
| `openai` | `mlflow.openai.autolog()` | Direct OpenAI API with recognized model names |
| `anthropic` | `mlflow.anthropic.autolog()` | Anthropic API |
| `gemini` | `mlflow.gemini.autolog()` | Google Gemini API |
| `azure` | `mlflow.openai.autolog()` | Azure OpenAI (uses OpenAI-compatible SDK) |
| `bedrock` | `mlflow.bedrock.autolog()` | AWS Bedrock |

This template defaults to `litellm` since it targets **OpenAI-compatible endpoints** (OpenShift, vLLM, Ollama via LlamaStack, etc.) using the `openai/` model prefix with a custom `BASE_URL`.

---

## Agent-Specific Documentation

- [CrewAI Documentation](https://docs.crewai.com/)
- [CrewAI Tools](https://docs.crewai.com/concepts/tools)
- [CrewAI LLM Connections](https://docs.crewai.com/en/concepts/llms)
- [MLflow CrewAI Tracing](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/crewai/)
- [Ollama](https://ollama.com/)
- [Ollama (Homebrew)](https://formulae.brew.sh/formula/ollama#default)
