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

```
BASE_URL=http://localhost:8321
MODEL_ID=ollama/llama3.1:8b
API_KEY=not-needed
CONTAINER_IMAGE=not-needed
```

#### OpenShift Cluster

Edit the `.env` file and fill in all required values:

```
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

## Agent-Specific Documentation

- [CrewAI Documentation](https://docs.crewai.com/)
- [CrewAI Tools](https://docs.crewai.com/concepts/tools)
- [Ollama](https://ollama.com/)
- [Ollama (Homebrew)](https://formulae.brew.sh/formula/ollama#default)
