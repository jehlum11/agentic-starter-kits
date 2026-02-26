<div style="text-align: center;">

# Demo: Outdoor Activity Agent

</div>

---

## Overview

This demo shows how to customize the base **LangGraph ReAct Agent** template (`agents/base/langgraph_react_agent/`) to build a real agent with live API tools. You only need to replace **two files** — `tools.py` and `agent.py` — and add one dependency.

The resulting agent recommends the best day and time window for outdoor activities by reasoning across weather, air quality, daylight, and National Park Service data.

**Example query:** *"I want to go hiking in Colorado next weekend, any recommendations?"*

---

## Prerequisites

- **Ollama** installed on your machine ([ollama.com](https://ollama.com/) or `brew install ollama`)
- **NPS API Key** — free from [developer.nps.gov](https://developer.nps.gov) (sign up to get a 40-character key)
- **uv** package manager ([docs.astral.sh/uv](https://docs.astral.sh/uv/))

---

## Step-by-Step

All commands are run from the repository root.

### 1. Go to the base template

```bash
cd agents/base/langgraph_react_agent
```

### 2. Set up your `.env` file

```bash
cp ../../../template.env .env
```

Edit `.env` and set:

```
API_KEY=not-needed
BASE_URL=http://localhost:8321
MODEL_ID=ollama/llama3.2:3b
CONTAINER_IMAGE=not-needed
NPS_API_KEY=your-nps-api-key-here
```

### 3. Copy `tools.py` from the demo

```bash
cp ../../demo/langgraph_outdoor_activity_agent/src/langgraph_outdoor_activity_agent/tools.py \
   src/langgraph_react_agent_base/tools.py
```

Then fix the import at the top of `src/langgraph_react_agent_base/tools.py` — change:

```python
from langgraph_outdoor_activity_agent.utils import get_env_var
```

to:

```python
from langgraph_react_agent_base.utils import get_env_var
```

### 4. Copy `agent.py` from the demo

```bash
cp ../../demo/langgraph_outdoor_activity_agent/src/langgraph_outdoor_activity_agent/agent.py \
   src/langgraph_react_agent_base/agent.py
```

Then fix the imports at the top of `src/langgraph_react_agent_base/agent.py` — change:

```python
from langgraph_outdoor_activity_agent.tools import (
    geocode_location,
    get_weather_forecast,
    get_air_quality,
    get_sunrise_sunset,
    search_national_parks,
    get_park_alerts,
)
from langgraph_outdoor_activity_agent.utils import get_env_var
```

to:

```python
from langgraph_react_agent_base.tools import (
    geocode_location,
    get_weather_forecast,
    get_air_quality,
    get_sunrise_sunset,
    search_national_parks,
    get_park_alerts,
)
from langgraph_react_agent_base.utils import get_env_var
```

### 5. Add `httpx` to dependencies

Open `requirements.txt` and add this line:

```
httpx>=0.27.0
```

### 6. (Optional) Increase recursion limit

The agent uses 6 tools, so it may need more reasoning steps. In `main.py`, find:

```python
config={"recursion_limit": 10}
```

and change it to:

```python
config={"recursion_limit": 15}
```

### 7. Initialize and install

```bash
chmod +x init.sh
./init.sh
```

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

### 8. Start Ollama (Terminal 1)

Ollama is a system-level application (not a Python package). It must be installed separately and runs outside the virtual environment.

```bash
ollama serve
```

Keep this terminal open. Then pull the required models in a **new terminal**:

```bash
ollama pull llama3.2:3b
ollama pull embeddinggemma:latest
```

> **Note:** `embeddinggemma:latest` is required by the LlamaStack server config, even though this agent doesn't use embeddings directly.

### 9. Start LlamaStack (Terminal 2)

LlamaStack is an API gateway that wraps Ollama with an OpenAI-compatible interface. It runs inside the virtual environment.

```bash
cd agents/base/langgraph_react_agent
source .venv/bin/activate
mkdir -p milvus_data
uv run llama stack run ../../../run_llama_server.yaml
```

Wait until you see: `Uvicorn running on http://['::', '0.0.0.0']:8321`

> **Note:** The `milvus_data` directory is needed by the LlamaStack vector store provider. Create it before starting the server.

### 10. Run the agent (Terminal 3)

```bash
cd agents/base/langgraph_react_agent
source .venv/bin/activate
uv run examples/execute_ai_service_locally.py
```

### 11. Try it out

```
I want to go hiking in Colorado next weekend, any recommendations?
What's the best day for a bike ride in San Francisco this week?
Is it safe to go running outdoors in Denver tomorrow morning?
```

---

## What changed (summary)

| File                 | Change                                                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `src/.../tools.py` | Replaced 2 dummy tools with 6 real API tools (geocoding, weather, air quality, sunrise/sunset, NPS parks, NPS alerts) |
| `src/.../agent.py` | Updated tool imports and added a domain-specific system prompt                                                        |
| `requirements.txt` | Added `httpx>=0.27.0` for HTTP API calls                                                                            |
| `.env`             | Added `NPS_API_KEY`                                                                                                 |
| `main.py`          | (Optional) Increased recursion limit from 10 to 15                                                                    |

Everything else — `main.py`, `Dockerfile`, `k8s/`, `examples/`, `deploy.sh` — stays the same.

---

## APIs Used

- [Open-Meteo](https://open-meteo.com/) — Weather, air quality, geocoding (free, no key required)
- [National Park Service API](https://developer.nps.gov) — Park search and alerts (free key required)
