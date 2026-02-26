<div style="text-align: center;">

![LangGraph Logo](/images/langgraph_logo.svg)
# Outdoor Activity Agent

</div>

---
## What this agent does
Outdoor activity planning agent that recommends the best day and time window for activities like hiking, biking, or running. It reasons across weather forecasts, air quality, daylight data, and National Park Service information to produce concrete, actionable recommendations. Built with LangGraph and LangChain.

### Tools
| Tool | API | Description |
|------|-----|-------------|
| `geocode_location` | Open-Meteo Geocoding | Converts a place name to coordinates and timezone |
| `get_weather_forecast` | Open-Meteo Forecast | 14-day daily forecast (temp, precipitation, wind, UV) |
| `get_air_quality` | Open-Meteo Air Quality | Daily AQI and pollutant levels |
| `get_sunrise_sunset` | Open-Meteo Forecast | Sunrise, sunset, and daylight duration for a date |
| `search_national_parks` | NPS API | Search parks by state and activity |
| `get_park_alerts` | NPS API | Active alerts, closures, and cautions for a park |

---
### Preconditions:
- You need to copy/paste .env file and change its values to yours
- Get a free NPS API key from https://developer.nps.gov
- Decide what way you want to go `local` or `RH OpenShift Cluster` and fill needed values
- use `./init.sh` that will add those values from .env to environment variables



Copy .env file
```bash
cp template.env agents/community/langgraph_outdoor_activity_agent/.env
```

#### Local
Edit the `.env` file with your local configuration:

```
BASE_URL=http://localhost:8321
MODEL_ID=ollama/llama3.2:3b
API_KEY=not-needed
CONTAINER_IMAGE=not-needed
NPS_API_KEY=your-nps-api-key-here
```

#### OpenShift Cluster
Edit the `.env` file and fill in all required values:

```
API_KEY=your-api-key-here
BASE_URL=https://your-llama-stack-distribution.com/v1
MODEL_ID=llama-3.1-8b-instruct
CONTAINER_IMAGE=quay.io/your-username/langgraph-outdoor-activity-agent:latest
NPS_API_KEY=your-nps-api-key-here
```

**Notes:**
- `API_KEY` - contact your cluster administrator
- `BASE_URL` - should end with `/v1`
- `MODEL_ID` - contact your cluster administrator
- `NPS_API_KEY` - free key from https://developer.nps.gov (sign up required)
- `CONTAINER_IMAGE` - full image path where the agent container will be pushed and pulled from.
  The image is built locally, pushed to this registry, and then deployed to OpenShift.

  Format: `<registry>/<namespace>/<image-name>:<tag>`

  Examples:
  - Quay.io: `quay.io/your-username/langgraph-outdoor-activity-agent:latest`
  - Docker Hub: `docker.io/your-username/langgraph-outdoor-activity-agent:latest`
  - GHCR: `ghcr.io/your-org/langgraph-outdoor-activity-agent:latest`

Go to agent dir
```bash
cd agents/community/langgraph_outdoor_activity_agent
```

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
./init.sh
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
>**Keep this terminal open!**\
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

### Example queries
```
I want to go hiking in Colorado next weekend, any recommendations?
What's the best day for a bike ride in San Francisco this week?
Is it safe to go running outdoors in Denver tomorrow morning?
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

Make deploy file executable
```bash
chmod +x deploy.sh
```

Build image and deploy Agent
```bash
./deploy.sh
```

This will:
- Create Kubernetes secret for API key and NPS API key
- Build and push the Docker image
- Deploy the agent to OpenShift
- Create Service and Route

COPY the route URL and PASTE into the CURL below
```bash
oc get route langgraph-outdoor-activity-agent -o jsonpath='{.spec.host}'
```

Send a test request:
```bash
curl -X POST https://<YOUR_ROUTE_URL>/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to go hiking in Colorado next weekend, any recommendations?"}'
```

## APIs Used
- [Open-Meteo](https://open-meteo.com/) — Free weather, air quality, and geocoding APIs (no key required)
- [National Park Service API](https://developer.nps.gov) — Park search and alerts (free API key required)
