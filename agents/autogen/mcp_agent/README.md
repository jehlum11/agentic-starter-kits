# AutoGen Agent (MCP)

An AutoGen-based agent with MCP tools: it connects to the MCP server over SSE, loads tools (e.g. churn / deployment), and answers user questions. Exposes a FastAPI API with a `/chat` endpoint.

---

## What this agent does

The agent uses AutoGen (AssistantAgent) and `autogen_ext.tools.mcp`: it connects to the MCP server over SSE, loads MCP tools (e.g. `invoke_churn`, which calls the model via `DEPLOYMENT_URL`), and uses an LLM (Llama Stack / OpenAI) for reasoning and tool selection. Responses are returned via the `/chat/completions` endpoint.

---

### Preconditions

- A `.env` file in the agent directory (copy from `template.env` if present, or create one manually).
- Choose **local** or **Red Hat OpenShift cluster** and fill in the appropriate variables in `.env`.

Go to the agent directory:

```bash
cd agents/autogen/mcp_agent
```

#### The .env file

If `template.env` exists, copy it to `.env`:

```bash
cp template.env .env
```

Edit `.env`.

#### Local configuration

For local runs (e.g. Ollama), set at least:

```
BASE_URL=http://localhost:11434
MODEL_ID=llama3.2:3b
API_KEY=not-needed
MCP_SERVER_URL=http://127.0.0.1:8000/sse
CONTAINER_IMAGE=not-needed
CONTAINER_IMAGE_MCP=not-needed
```

Use port **8000** for MCP so the agent can run on **8080**. The app loads `.env` automatically. You will start the MCP server first (see "Local usage" below).

#### OpenShift cluster

For deployment on OpenShift, fill in all required values:

```
API_KEY=your-api-key-here
BASE_URL=https://your-llama-stack-distribution.com/v1
MODEL_ID=llama-3.1-8b-instruct
CONTAINER_IMAGE=quay.io/your-username/autogen-agent:latest
CONTAINER_IMAGE_MCP=quay.io/your-username/mcp-automl:latest
DEPLOYMENT_URL=https://...
DEPLOYMENT_TOKEN=...
```

**Notes:**

- `API_KEY` — LLM (Llama Stack) API key; contact your cluster administrator.
- `BASE_URL` — LLM API base URL; should end with `/v1`.
- `MODEL_ID` — Model identifier; contact your cluster administrator.
- `CONTAINER_IMAGE` — Full image path for the agent (registry/namespace/name:tag).
- `CONTAINER_IMAGE_MCP` — Full image path for the MCP server.
- `DEPLOYMENT_URL` / `DEPLOYMENT_TOKEN` — Used by MCP tools (e.g. calling the churn model).

Create and activate a virtual environment with [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12
source .venv/bin/activate
```

(On Windows: `.venv\Scripts\activate`.)

Install the project in editable mode:

```bash
uv pip install -e .
```

---

## Local usage

**Quick start (two terminals):**

1. **Terminal 1 — MCP server** (must be running before the agent):

   ```bash
   cd agents/autogen/mcp_agent/mcp_automl_template
   uv pip install -e .
   PORT=8000 uv run python mcp_server.py
   ```

2. **Terminal 2 — Agent:**

   ```bash
   cd agents/autogen/mcp_agent
   uv run uvicorn main:app --host 0.0.0.0 --port 8080
   ```

3. Test: `curl -X POST http://localhost:8080/chat/completions -H "Content-Type: application/json" -d '{"message": "What is 2+7? Use a tool!"}'`

---

**Details:**

- **MCP server** must be reachable at `MCP_SERVER_URL` (e.g. `http://127.0.0.1:8000/sse`). Start it first.
- **LLM** — local (Ollama) or remote; `BASE_URL` and `MODEL_ID` in `.env` must be correct (Ollama: `BASE_URL=http://localhost:11434`, `MODEL_ID=llama3.2:3b`).

Test the `/chat` endpoint:

```bash
curl -X POST http://localhost:8080/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2+7? Use a tool!"}'
```

**Streaming** (OpenAI-style SSE: `chat.completion.chunk` lines, then `data: [DONE]`):

```bash
curl -sN -X POST http://localhost:8080/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is 2+2? Use a tool if needed."}], "stream": true}'
```

You can use either `"message": "..."` or `"messages": [...]`; set `"stream": true` for token-by-token chunks.

Optional: interactive chat with MCP tools (LangGraph) — from the `mcp_automl_template` directory:

```bash
cd mcp_automl_template
# Set MCP_SERVER_URL in .env (or in agents/autogen/mcp_agent/.env)
uv run python interact_with_mcp.py
```

---

## Deployment on Red Hat OpenShift

Log in to the cluster:

```bash
oc login -u "login" -p "password" https://your-cluster:6443
```

Log in to the container registry (e.g. Quay):

```bash
docker login -u='login' -p='password' quay.io
```

Make the deploy script executable:

```bash
chmod +x init.sh deploy.sh
```

Build images and deploy (MCP first, then the agent):

```bash
./init.sh
./deploy.sh
```

The script will:

- Build and deploy the MCP server (from `mcp_automl_template`),
- Build and push the agent image,
- Create a Secret for the API key,
- Deploy the agent Deployment, Service, and Route.

Get the agent Route URL:

```bash
oc get route autogen-agent -o jsonpath='{.spec.host}'
```

Test the `/chat` endpoint:

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 17 + 25? Use your tools to compute it."}'
```

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"message": "Predict churn for this customer: Male, 12 months tenure, fiber optic, month-to-month contract, electronic check, monthly 70.35, total 800.40."}'
```

**Streaming** (`stream: true`): response is Server-Sent Events (`chat.completion.chunk` per line, then `data: [DONE]`). Use `curl -N` or `-sN` so chunks print live:

```bash
curl -sN -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is 17 + 25? Use your tools."}], "stream": true}'
```

---

## Troubleshooting

**Agent gets 503 when connecting to MCP, but `curl https://<mcp-route>/sse` returns 200 from your machine.**  
Requests from **inside** the cluster (agent pod) to the Route can be handled differently and return 503. `./deploy.sh` sets the agent’s `MCP_SERVER_URL` from the MCP **Route** when it exists (so the pod does not use the in-cluster Service URL). If you need the internal URL instead, adjust or comment out that block in `deploy.sh` after MCP deploy. **Local** use does not go through `deploy.sh`—set `MCP_SERVER_URL` in `.env` (e.g. `http://127.0.0.1:8000/sse`) for `main.py` / dev only.

**Agent fails with "All connection attempts failed" when using `http://mcp-automl:8080/sse`.**  
The agent pod cannot reach the MCP service. Check: **(1)** Same namespace — `oc get deployment mcp-automl autogen-agent` (no `-A`); if they are in different namespaces, use the full service DNS: `MCP_SERVER_URL=http://mcp-automl.<mcp-namespace>.svc.cluster.local:8080/sse`. **(2)** MCP has endpoints — `oc get endpoints mcp-automl` (ENDPOINTS should be non-empty). **(3)** Test from a pod — `oc run curl --rm -it --restart=Never --image=curlimages/curl -- curl -v -m 10 http://mcp-automl:8080/sse` (replace namespace in the URL if using FQDN).

---

## Documentation and references

- [AutoGen](https://microsoft.github.io/autogen/)
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/)
- MCP server in this repo: `mcp_automl_template/` (README, tool configuration, deploy).
