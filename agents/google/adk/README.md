<div style="text-align: center;">

# Google ADK 2.0 Agent

</div>

---

## What this agent does

General-purpose agent using Google Agent Development Kit (ADK) 2.0 with a web search tool. It uses the LiteLLM model
connector to route inference through a LlamaStack server's OpenAI-compatible API endpoint.

---

### Preconditions:

- You need to change .env.template file to .env
- Decide what way you want to go `local` or `RH OpenShift Cluster` and fill needed values
- use `./init.sh` that will add those values from .env to environment variables

Go to agent dir

```bash
cd agents/google/adk
```

Change the name of .env file

```bash
mv template.env .env
```

#### Local

Edit the `.env` file with your local configuration:

```
BASE_URL=http://localhost:8321
MODEL_ID=ollama/llama3.2:3b
API_KEY=not-needed
CONTAINER_IMAGE=not-needed
```

#### OpenShift Cluster

Edit the `.env` file and fill in all required values:

```
API_KEY=your-api-key-here
BASE_URL=https://your-llama-stack-distribution.com/v1
MODEL_ID=llama-3.1-8b-instruct
CONTAINER_IMAGE=quay.io/your-username/google-adk-agent:latest
```

**Notes:**

- `API_KEY` - contact your cluster administrator
- `BASE_URL` - should end with `/v1`
- `MODEL_ID` - contact your cluster administrator
- `CONTAINER_IMAGE` - full image path where the agent container will be pushed and pulled from.
  The image is built locally, pushed to this registry, and then deployed to OpenShift.

  Format: `<registry>/<namespace>/<image-name>:<tag>`

  Examples:
    - Quay.io: `quay.io/your-username/google-adk-agent:latest`
    - Docker Hub: `docker.io/your-username/google-adk-agent:latest`
    - GHCR: `ghcr.io/your-org/google-adk-agent:latest`

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

Install app from Ollama site or via Brew

```bash
#brew install ollama
# or
curl -fsSL https://ollama.com/install.sh | sh
```

Pull Required Model

```bash
ollama pull llama3.1:8b
```

Start Ollama Service

```bash
ollama serve
```

> **Keep this terminal open!**\
> Ollama needs to keep running.

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

---

## LlamaStack Connectivity via LiteLLM

This agent uses **Google ADK 2.0** with the **LiteLLM model connector** to connect to LlamaStack or any
OpenAI-compatible endpoint:

- **LiteLLM** translates between ADK's model interface and OpenAI-compatible APIs
- **`OPENAI_API_BASE`**: Set automatically from `BASE_URL` to point to LlamaStack (e.g., `http://localhost:8321/v1`)
- **`OPENAI_API_KEY`**: Set automatically from `API_KEY`; can be `not-needed` for local LlamaStack
- **Model format**: Uses `openai/<model_id>` prefix for LiteLLM's OpenAI provider routing

The OpenAI-compatible API allows **switching between providers** without code changes:
just update `BASE_URL`, `MODEL_ID`, and `API_KEY` in your `.env` file.

### Supported Providers:

- **Local**: Ollama via LlamaStack (`http://localhost:8321/v1`)
- **OpenAI**: OpenAI API (`https://api.openai.com/v1`)
- **Azure OpenAI**: Azure endpoints
- **vLLM**: Self-hosted vLLM servers
- **Any OpenAI-compatible API**

---

## Deployment on RedHat OpenShift Cluster

Login to OC

```bash
oc login -u "login" -p "password" https://super-link-to-cluster:111
```

Login ex. Docker

```bash
docker login -u='login' -p='password' quay.io
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
oc get route google-adk-agent -o jsonpath='{.spec.host}'
```

Send a test request:

Non-streaming

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Best server service?"}], "stream": false}'
```

Streaming

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Search for RedHat OpenShift"}],
    "stream": true
  }'
```

---

## Playground UI

A browser-based chat interface served directly by the agent at the root URL — no separate process needed.

### Running the Playground

Start the agent and the playground in two terminals:

Agent:

```bash
cd agents/google/adk
source .venv/bin/activate
source ./init.sh
lsof -ti:8000 | xargs kill -9 2>/dev/null
uvicorn main:app --port 8000
```

UI App:

```bash
cd agents/google/adk
source .venv/bin/activate
source ./init.sh
lsof -ti:5001 | xargs kill -9 2>/dev/null
flask --app playground/app run --port 5001
```

Open [http://localhost:5001](http://localhost:5001) in your browser.

A green dot in the header means the agent is connected and ready. Type a message and press **Enter** to send.

When deployed to OpenShift, the playground is available at the route URL.

| Variable    | Default                 | Description                  |
|-------------|-------------------------|------------------------------|
| `AGENT_URL` | `http://localhost:8000` | URL of the running agent API |

If the agent runs on a different host or port:

```bash
AGENT_URL=https://your-agent-url flask --app playground/app run --port 5001
```

---

## Agent-Specific Documentation

### Architecture

This agent combines three key components:

1. **Google ADK 2.0 LlmAgent**: Manages the agent loop (reason, call tools, observe, answer)
2. **LiteLLM Model Connector**: Routes LLM calls to any OpenAI-compatible API (LlamaStack)
3. **InMemoryRunner**: Handles session management and agent execution

```
User Input -> ADK LlmAgent -> LiteLLM -> LlamaStack (OpenAI API)
                 |                           |
                 v                           v
            Tool Calls              LLM Inference
                 |                           |
                 v                           v
          Tool Results              Model Response
                 |                           |
                 +------ Agent Loop ---------+
                              |
                              v
                       Final Response
```

### Configuration

**Environment Variables:**

| Variable          | Description        | Example                                |
|-------------------|--------------------|----------------------------------------|
| `BASE_URL`        | LLM API endpoint   | `http://localhost:8321/v1`             |
| `MODEL_ID`        | Model identifier   | `ollama/llama3.2:3b`                   |
| `API_KEY`         | API authentication | `not-needed` (local) or API key        |
| `CONTAINER_IMAGE` | Container registry | `quay.io/user/google-adk-agent:latest` |

**Customization:**

Edit `src/adk_agent/tools.py` to add new tools:

```python
def my_custom_tool(query: str) -> dict:
    """Description of what this tool does.

    Args:
        query: The input for the tool.

    Returns:
        A dict with status and result.
    """
    return {"status": "success", "result": "Tool output here"}
```

Then register it in `src/adk_agent/__init__.py`:

```python
from .tools import dummy_web_search, my_custom_tool

TOOLS = [dummy_web_search, my_custom_tool]
```

### Troubleshooting

**Error: "OPENAI_API_BASE not set"**

- Solution: Ensure `BASE_URL` is set in your `.env` file and run `source ./init.sh`

**Tool calls returned as plain text instead of function calls**

- This can happen with smaller models (e.g., `llama3.2:3b`). Try a larger model or ensure
  the model supports function calling through LlamaStack.

**LiteLLM debug mode**

- To see the actual API requests being made, add to your code:
  ```python
  import litellm
  litellm._turn_on_debug()
  ```

### Additional Resources

- **Google ADK 2.0 Documentation**: https://google.github.io/adk-docs/2.0/
- **LiteLLM Documentation**: https://docs.litellm.ai/
- **Llama Stack Documentation**: https://llama-stack.readthedocs.io/
- **Ollama Documentation**: https://ollama.com/docs

---

## License

MIT License
