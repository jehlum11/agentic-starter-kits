<div style="text-align: center;">

![LlamaIndex Logo](/images/llamaindex_logo.svg)

# WebSearch Agent

</div>

---

## What this agent does

Agent built on LlamaIndex that uses a web search tool to query the internet and use the results in its answers.

---

### Preconditions:

- You need to change .env.template file to .env
- Decide what way you want to go `local` or `RH OpenShift Cluster` and fill needed values
- use `./init.sh` that will add those values from .env to environment variables

Go to agent dir

```bash
cd agents/llamaindex/websearch_agent
```

Copy .env file

```bash
mv template.env .env
```

#### Local

Edit the `.env` file with your local configuration:

```ini
BASE_URL=http://localhost:8321
MODEL_ID=ollama/llama3.2:3b
API_KEY=not-needed
CONTAINER_IMAGE=not-needed
```

##### Tracing

```ini
MLFLOW_TRACKING_URI="http://localhost:5000"
MLFLOW_EXPERIMENT_NAME="LlamaIndex Local Experiment"
MLFLOW_HTTP_REQUEST_TIMEOUT=2
MLFLOW_HTTP_REQUEST_MAX_RETRIES=0
```

#### OpenShift Cluster

Edit the `.env` file and fill in all required values:

```ini
API_KEY=your-api-key-here
BASE_URL=https://your-llama-stack-distribution.com/v1
MODEL_ID=llama-3.1-8b-instruct
CONTAINER_IMAGE=quay.io/your-username/llamaindex-websearch-agent:latest
```

**Notes:**

- `API_KEY` - contact your cluster administrator
- `BASE_URL` - should end with `/v1`
- `MODEL_ID` - contact your cluster administrator
- `CONTAINER_IMAGE` - full image path where the agent container will be pushed and pulled from.
  The image is built locally, pushed to this registry, and then deployed to OpenShift.

  Format: `<registry>/<namespace>/<image-name>:<tag>`

  Examples:
    - Quay.io: `quay.io/your-username/llamaindex-websearch-agent:latest`
    - Docker Hub: `docker.io/your-username/llamaindex-websearch-agent:latest`
    - GHCR: `ghcr.io/your-org/llamaindex-websearch-agent:latest`

##### Tracing

To enable tracing and logging with MLflow on your OpenShift cluster, add the following environment variables to your `.env` file:

```ini
MLFLOW_TRACKING_URI="https://<openshift-dashboard-url>/mlflow"
MLFLOW_TRACKING_TOKEN="<your-openshift-token>"
MLFLOW_EXPERIMENT_NAME="<your-experiment-name>"
MLFLOW_TRACKING_INSECURE_TLS="true"
MLFLOW_WORKSPACE="default"
```

**Notes:**
- `MLFLOW_TRACKING_URI` - Replace `<openshift-dashboard-url>` with your OpenShift cluster's data science gateway URL
- `MLFLOW_TRACKING_TOKEN` - Your openshift authentication token. It can be obtained from the openshift console.
- `MLFLOW_EXPERIMENT_NAME` - A descriptive name for your experiment (e.g., "LlamaIndex Cluster Demo")
- `MLFLOW_TRACKING_INSECURE_TLS` - Set to `"true"` if your OpenShift cluster does not use trusted certificates
- `MLFLOW_WORKSPACE` - Project name

- Tracing is optional; if you do not set `MLFLOW_TRACKING_URI`, the application will run without MLflow logging.

- If `MLFLOW_TRACKING_URI` is set, the application will attempt to connect to the MLflow server at startup. If the server is unreachable, the application will log a warning and continue running without tracing.

- You can control how long the application waits for the MLflow server by setting `MLFLOW_HEALTH_CHECK_TIMEOUT` (in seconds, default: `5`).

Create and activate a virtual environment (Python 3.12) in this directory using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12
source .venv/bin/activate
```

(On Windows: `.venv\Scripts\activate`)

Make scripts executable

```bash
chmod +x init.sh
```

Add to values from .env to environment variables

```bash
source ./init.sh
```

---

## Local usage (Ollama + LlamaStack Server)

Create package with agent and install it to venv

```bash
uv pip install -e .
```

```bash
uv pip install ollama
```

Install mlflow (>=3.10.0) - *Optional: Only required if tracing is enabled*
```bash
uv pip install "mlflow>=3.10.0"
```

Install app from Ollama site or via Brew

```bash
#brew install ollama
# or
curl -fsSL https://ollama.com/install.sh | sh
```

Pull Required Model

```bash
ollama pull llama3.2:3b
```

Start Ollama Service

```bash
ollama serve
```

> **Keep this terminal open!**\
> Ollama needs to keep running.

Start MLflow Server
```bash
mlflow server --port 5000
```
>**Keep this terminal open** - the server needs to keep running.

Start LlamaStack Server

```bash
llama stack run ../../../run_llama_server.yaml
```

> **Keep this terminal open** - the server needs to keep running.\
> You should see output indicating the server started on `http://localhost:8321`.

Run the example:

```bash
uv run examples/execute_ai_service_locally.py
```

# Deployment on RedHat OpenShift Cluster

Login to OC

```bash
oc login -u "login" -p "password" https://super-link-to-cluster:111
```

Login ex. Docker

```bash
docker login -u='login' -p='password' quay.io
```

Install MLflow for RHOAI 3.2 or 3.3 - *Optional: Only required if tracing is enabled*
```bash
uv pip install "git+https://github.com/red-hat-data-services/mlflow@rhoai-3.3"
```

Make deploy file executable

```bash
chmod +x deploy.sh
```

Build image and deploy Agent

```bash
./deploy.sh
```

This will:

- Create Kubernetes secret for API key
- Build and push the Docker image
- Deploy the agent to OpenShift
- Create Service and Route

COPY the route URL and PASTE into the CURL below

```bash
oc get route llamaindex-websearch-agent -o jsonpath='{.spec.host}'
```

Send a test request:

Non-streaming

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Which company is consider the best?"}], "stream": false}'
```

Streaming

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Which company is consider the best?"}], "stream": true}'
```

Pretty Printed Stream

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Which company is consider the best?"}], "stream": true}' |
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

## Agent-Specific Documentation

Each agent has detailed documentation for setup and deployment:

- https://ollama.com/
- https://formulae.brew.sh/formula/ollama#default
- https://docs.llamaindex.ai/
- https://docs.llamaindex.ai/en/stable/module_guides/workflow/
- https://llama-stack.readthedocs.io/