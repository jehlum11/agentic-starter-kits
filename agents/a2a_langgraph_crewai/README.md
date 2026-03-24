<div style="text-align: center;">

# A2A: LangGraph ↔ CrewAI

</div>

---

## What this agent does

An **A2A (Agent-to-Agent)** example: a **CrewAI** pod exposes an A2A JSON-RPC server, and a **LangGraph** pod acts as an orchestrator that calls the Crew specialist over HTTP/A2A inside the cluster (or locally). Both images are built from one `Dockerfile` with `A2A_ROLE=crew` or `langgraph`.

---

### Preconditions

- Copy/rename the env template and set values for your environment
- Choose **local** or **RH OpenShift Cluster** and fill the needed values
- Run **`source ./init.sh`** so variables from `.env` are loaded into your shell (required before `./deploy.sh` on OpenShift)

Go to agent dir:

```bash
cd agents/a2a_langgraph_crewai
```

Rename the env file:

```bash
mv template.env .env
```

#### Local (no cluster)

Edit `.env` for local dev. You can use placeholders for images if you only run Python locally:

```
API_KEY=your-key-or-not-needed
BASE_URL=http://localhost:8321/v1
MODEL_ID=ollama/llama3.1:8b
CONTAINER_IMAGE_CREW=not-needed
CONTAINER_IMAGE_LANGGRAPH=not-needed
CREW_A2A_PUBLIC_URL=http://127.0.0.1:9100
LANGGRAPH_A2A_PUBLIC_URL=http://127.0.0.1:9200
CREW_A2A_URL=http://127.0.0.1:9100
CREW_A2A_PORT=9100
LANGGRAPH_A2A_PORT=9200
```

#### OpenShift Cluster

Edit `.env` and fill in all required values:

```
API_KEY=your-api-key-here
BASE_URL=https://your-llama-stack.example.com/v1
MODEL_ID=your-model-id
CONTAINER_IMAGE_CREW=quay.io/your-org/a2a-langgraph-crewai:crew
CONTAINER_IMAGE_LANGGRAPH=quay.io/your-org/a2a-langgraph-crewai:langgraph
```

For deploy, `CREW_A2A_PUBLIC_URL` / `LANGGRAPH_A2A_PUBLIC_URL` are set automatically from OpenShift Routes; local defaults in `template.env` are for running servers on your machine.

**Notes:**

- `API_KEY` — contact your cluster administrator or your LLM provider
- `BASE_URL` — must include `/v1` for OpenAI-compatible chat
- `MODEL_ID` — model id accepted by that endpoint
- `CONTAINER_IMAGE_CREW` / `CONTAINER_IMAGE_LANGGRAPH` — full image references (different tags, e.g. `:crew` and `:langgraph`). Images are built locally, pushed to the registry, then deployed.

Create and activate a virtual environment (Python 3.12+) in this directory using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.12
source .venv/bin/activate
```

(On Windows: `.venv\Scripts\activate`)

Make scripts executable:

```bash
chmod +x init.sh deploy.sh
```

Load values from `.env` into environment variables:

```bash
source ./init.sh
```

---

## Local run (no cluster)

```bash
uv sync
```

Use **three terminals** (after `source ./init.sh` in each, or export the same vars):

```bash
# Terminal 1
uv run python crew_a2a_server.py

# Terminal 2
uv run python langgraph_a2a_server.py

# Terminal 3
uv run python demo_client.py "Your question here"
```

Default ports: **9100** (Crew), **9200** (LangGraph). Do not set `PORT` unless you mirror the container (`8080`).

---

## Deploying to OpenShift

Log in to the cluster:

```bash
oc login -u "login" -p "password" https://your-cluster:6443
oc project <namespace>
```

Log in to your container registry (e.g. Quay):

```bash
docker login -u='login' -p='password' quay.io
```

Install **gettext** (`envsubst`) if needed (e.g. `brew install gettext` on macOS).

In the agent directory, load `.env` **in the same shell** you use for deploy:

```bash
cd agents/a2a_langgraph_crewai
source ./init.sh
./deploy.sh
```

`./deploy.sh` will:

1. Build and push **two** images (`--build-arg A2A_ROLE=crew|langgraph`)
2. Create `Secret` `a2a-langgraph-crewai-secrets` with `API_KEY`
3. Remove prior Deployment/Service/Route for this stack (label `app.kubernetes.io/part-of=a2a-langgraph-crewai`)
4. Apply `Service` and `Route` for both agents
5. Read public hostnames from `oc get route` and set `CREW_A2A_PUBLIC_URL` / `LANGGRAPH_A2A_PUBLIC_URL` to `https://…`
6. Apply `Deployment` manifests with those URLs (Agent Card for external clients). The LangGraph pod uses in-cluster `CREW_A2A_URL=http://a2a-crew-agent:8080`

### Test from your laptop (demo client)

```bash
export LANGGRAPH_A2A_PUBLIC_URL="https://$(oc get route a2a-langgraph-agent -o jsonpath='{.spec.host}')"
uv run python demo_client.py "Test question"
```

### Operational notes

- **TLS**: Routes use `edge` termination (same pattern as other agents in this repo).
- **Secrets**: do not commit `.env`; `API_KEY` is stored in the Kubernetes `Secret`.
- **Resources**: tune limits in YAML if your LLM stack needs it.
- **Scaling**: MVP assumes **one replica** per Deployment; scaling out would need shared state for A2A tasks.
- **BASE_URL** must be reachable **from the pods** (cluster egress or in-cluster LLM service).

---

## Architecture (OpenShift)

| Resource | Role |
|----------|------|
| `Deployment` **a2a-crew-agent** | CrewAI + A2A server, port **8080** |
| `Deployment` **a2a-langgraph-agent** | LangGraph + tool → `CREW_A2A_URL` |
| `Service` + `Route` ×2 | HTTPS; hosts feed Agent Card URLs |
| Inside the cluster | `CREW_A2A_URL=http://a2a-crew-agent:8080` |

---

## Files

| File / directory | Description |
|------------------|-------------|
| `init.sh` | Load and validate `.env` (use `source ./init.sh`) |
| `crew_a2a_server.py` | CrewAI A2A server |
| `langgraph_a2a_server.py` | LangGraph A2A server (calls Crew) |
| `a2a_reply.py` | A2A client helper |
| `demo_client.py` | JSON-RPC example against the orchestrator |
| `Dockerfile` + `entrypoint.sh` | Image with `A2A_ROLE` |
| `k8s/*.yaml` | Deployment / Service / Route |
| `deploy.sh` | Build, push, apply (run after `source ./init.sh`) |

---

## References

- [A2A Python SDK](https://pypi.org/project/a2a-sdk/)
- Related patterns: `agents/crewai/websearch_agent/`, `agents/langgraph/react_agent/`
