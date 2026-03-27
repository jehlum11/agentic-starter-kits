<div style="text-align: center;">

![LangGraph Logo](/images/langgraph_logo.svg)

# Human-in-the-Loop Agent

</div>

---

## What this agent does

Agent with **Human-in-the-Loop (HITL) approval** that pauses execution before running sensitive tools (e.g.
`create_file`) and waits for human review. Simple questions are answered directly without triggering the approval loop.
Built with LangGraph and LangChain.

**How it works:**

```
User Input → LLM decides tool → Is it sensitive?
                                    ├── No  → Execute tool automatically → Return result
                                    └── Yes → PAUSE (interrupt) → Human approves/rejects
                                                                    ├── Approved → Execute tool → Return result
                                                                    └── Rejected → Return rejection message
```

---

### Preconditions:

- You need to change template.env file to .env
- Decide what way you want to go `local` or `RH OpenShift Cluster` and fill needed values
- use `./init.sh` that will add those values from .env to environment variables

Go to agent dir

```bash
cd agents/langgraph/human_in_the_loop
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
CONTAINER_IMAGE=quay.io/your-username/langgraph-hitl-agent:latest
```

**Notes:**

- `API_KEY` - contact your cluster administrator
- `BASE_URL` - should end with `/v1`
- `MODEL_ID` - contact your cluster administrator
- `CONTAINER_IMAGE` - full image path where the agent container will be pushed and pulled from.
  The image is built locally, pushed to this registry, and then deployed to OpenShift.

  Format: `<registry>/<namespace>/<image-name>:<tag>`

  Examples:
    - Quay.io: `quay.io/your-username/langgraph-hitl-agent:latest`
    - Docker Hub: `docker.io/your-username/langgraph-hitl-agent:latest`
    - GHCR: `ghcr.io/your-org/langgraph-hitl-agent:latest`

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
ollama pull llama3.2:3b
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

## Human-in-the-Loop Features

### How Approval Works

This agent classifies tools into two categories:

| Category      | Tools         | Behavior                                  |
|---------------|---------------|-------------------------------------------|
| **Safe**      | general chat  | Responded to directly, no approval needed |
| **Sensitive** | `create_file` | Paused for human review before execution  |

When the LLM decides to call a sensitive tool, the agent:

1. **Pauses** execution using LangGraph's `interrupt()` mechanism
2. **Returns** the pending tool call details with `finish_reason: "pending_approval"`
3. **Includes** a `thread_id` to identify the paused conversation
4. **Waits** for a follow-up request with the human's decision

### API Approval Flow

**Step 1: Send a message that triggers a sensitive tool**

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Create a file named report.md with info about LangChain"}],
    "stream": false,
    "thread_id": "conversation-1"
  }'
```

**Response** (agent paused, waiting for approval):

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "{\"question\": \"Do you approve the following tool call(s)?\", \"tool_calls\": [\"Tool: create_file, Args: {...}\"], \"options\": [\"yes\", \"no\"]}"
      },
      "finish_reason": "pending_approval"
    }
  ],
  "thread_id": "conversation-1"
}
```

**Step 2: Approve or reject the tool call**

```bash
# Approve
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": ""}],
    "thread_id": "conversation-1",
    "approval": "yes"
  }'

# Or reject
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": ""}],
    "thread_id": "conversation-1",
    "approval": "no"
  }'
```

### Thread-Based Conversations

Each conversation requires a `thread_id` for HITL to work:

- The `thread_id` identifies the paused graph state
- You **must** use the same `thread_id` when sending the approval
- State is stored in-memory using LangGraph's `MemorySaver` checkpointer
- State does not persist across server restarts (use a database checkpointer for production)

---

## OpenAI SDK for Llama-stack Connectivity

This agent uses the **OpenAI SDK** (via LangChain's `ChatOpenAI`) to connect to Llama-stack or any OpenAI-compatible
endpoint:

- **`base_url`**: Points to Llama-stack server endpoint (e.g., `http://localhost:8321/v1`)
- **`model`**: Uses Llama-stack's model identifier (e.g., `ollama/llama3.2:3b`)
- **`api_key`**: Can be "not-needed" for local Llama-stack, required for remote OpenAI

The OpenAI-compatible API allows **switching between providers** without code changes:
just update `BASE_URL`, `MODEL_ID`, and `API_KEY` in your `.env` file.

### Supported Providers:

- **Local**: Ollama via Llama-stack (`http://localhost:8321/v1`)
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
oc get route langgraph-hitl-agent -o jsonpath='{.spec.host}'
```

Send test requests (3-step HITL flow):

**Step 1: Ask a general question (no approval needed)**

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is RedHat OpenShift Cluster"}],
    "stream": false,
    "thread_id": "demo-1"
  }'
```

**Step 2: Ask to write that info into a file (triggers approval)**

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write that information into a file called demo.md"}],
    "stream": false,
    "thread_id": "demo-1"
  }'
```

The agent will pause and return `finish_reason: "pending_approval"` with the `create_file` tool call details.

**Step 3: Approve the file creation**

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": ""}],
    "thread_id": "demo-1",
    "approval": "yes"
  }'
```

The agent resumes, executes `create_file`, and returns the final result.

Streaming (3-step HITL flow with `stream: true`):

**Step 1: Ask a general question (no approval needed)**

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is RedHat OpenShift Cluster"}],
    "stream": true,
    "thread_id": "demo-2"
  }'
```

**Step 2: Ask to write that info into a file (triggers approval)**

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write that information into a file called demo.md"}],
    "stream": true,
    "thread_id": "demo-2"
  }'
```

**Step 3: Approve the file creation**

```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": ""}],
    "stream": true,
    "thread_id": "demo-2",
    "approval": "yes"
  }'
```

---

## Playground UI

A browser-based chat interface with built-in Human-in-the-Loop approval support. When the agent pauses for approval, an
**Approve / Reject** banner appears directly in the chat.

### Running the Playground

Start the agent and the playground in two terminals:

Agent:

```bash
cd agents/langgraph/human_in_the_loop
source .venv/bin/activate
source ./init.sh
lsof -ti:8000 | xargs kill -9 2>/dev/null
uvicorn main:app --port 8000
```

UI App:

```bash
cd agents/langgraph/human_in_the_loop
source .venv/bin/activate
source ./init.sh
lsof -ti:5001 | xargs kill -9 2>/dev/null
flask --app playground/app run --port 5001
```

Open [http://localhost:5001](http://localhost:5001) in your browser.

A green dot in the header means the agent is connected and ready. Type a message and press **Enter** to send.

When the agent wants to call a sensitive tool (e.g. `create_file`), an approval banner will appear with **Approve** and
**Reject** buttons. Click one to resume the agent.

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

1. **LangGraph StateGraph**: Custom workflow with conditional routing for safe vs sensitive tools
2. **LangGraph Interrupts**: `interrupt()` pauses execution; `Command(resume=...)` resumes it
3. **ChatOpenAI**: OpenAI-compatible LLM client (connects to Llama-stack or OpenAI)

```
User Input → Agent Node (LLM) → Route Decision
                                   ├── No tools → END
                                   ├── Safe tool → Tool Node → Agent Node (loop)
                                   └── Sensitive tool → Human Approval Node
                                                          ├── interrupt() → PAUSE
                                                          ├── resume("yes") → Tool Node → Agent Node → END
                                                          └── resume("no") → Rejection Message → END
```

### Key Differences from Base ReAct Agent

This agent extends the base LangGraph ReAct agent with:

1. **Human-in-the-Loop**: Sensitive tool calls require explicit human approval
2. **Interrupt Mechanism**: Uses LangGraph's `interrupt()` / `Command(resume=...)` pattern
3. **Tool Classification**: Tools are categorized as safe or sensitive
4. **Thread-Based State**: Checkpointer preserves graph state across approval requests
5. **Custom Routing**: Conditional edges route to approval node only for sensitive tools

### Configuration

**Environment Variables:**

| Variable          | Description        | Example                                    |
|-------------------|--------------------|--------------------------------------------|
| `BASE_URL`        | LLM API endpoint   | `http://localhost:8321/v1`                 |
| `MODEL_ID`        | Model identifier   | `ollama/llama3.2:3b`                       |
| `API_KEY`         | API authentication | `not-needed` (local) or API key            |
| `CONTAINER_IMAGE` | Container registry | `quay.io/user/langgraph-hitl-agent:latest` |

**Customization:**

Edit `src/human_in_the_loop/agent.py` to add more sensitive tools to the interrupt list:

```python
hitl_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "create_file": True,
        "delete_record": True,
    },
)
```

Edit `src/human_in_the_loop/tools.py` to add new tools:

```python
@tool("delete_record", parse_docstring=True)
def delete_record(record_id: str) -> str:
    """Delete a record from the database. Requires human approval."""
    # Implementation here
```

### Troubleshooting

**Error: "No user message found in messages list"**

- Solution: Ensure your request includes at least one message with `"role": "user"`

**Approval request returns error**

- Solution: Use the same `thread_id` from the pending approval response
- The graph state must exist in the checkpointer for resume to work

**State lost after server restart**

- The default `MemorySaver` is in-memory only
- For production, use `PostgresSaver` (see `react_with_database_memory` agent for reference)

### Additional Resources

- **LangGraph Interrupts**: https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **LangChain Documentation**: https://python.langchain.com/
- **Llama Stack Documentation**: https://llama-stack.readthedocs.io/
- **Ollama Documentation**: https://ollama.com/docs

---

## License

MIT License
