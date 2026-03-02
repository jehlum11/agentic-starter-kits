from typing import Any

import os

import mlflow
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

# Load .env into os.environ so MLflow picks up MLFLOW_TRACKING_TOKEN,
# MLFLOW_WORKSPACE, MLFLOW_ENABLE_WORKSPACES automatically
load_dotenv()

from langgraph_outdoor_activity_agent.tools import (
    geocode_location,
    get_weather_forecast,
    get_air_quality,
    get_sunrise_sunset,
    search_national_parks,
    get_park_alerts,
)
from langgraph_outdoor_activity_agent.utils import get_env_var

# Enable MLflow tracing if MLFLOW_TRACKING_URI is set
_tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
if _tracking_uri:
    from mlflow.store.workspace_rest_store_mixin import WorkspaceRestStoreMixin
    WorkspaceRestStoreMixin._probe_workspace_support = lambda self: True

    mlflow.set_tracking_uri(_tracking_uri)
    mlflow.set_experiment("outdoor-activity-agent")
    mlflow.langchain.autolog(log_traces=True)


def get_graph_closure(
    model_id: str = None,
    base_url: str = None,
    api_key: str = None,
) -> Any:
    """Build and return a LangGraph ReAct agent for outdoor activity planning.

    Creates a ChatOpenAI client, wires six tools (geocoding, weather, air
    quality, sunrise/sunset, NPS park search, and park alerts), and uses
    create_agent to produce a graph that runs the ReAct loop.

    Args:
        model_id: LLM model identifier. Uses MODEL_ID env if omitted.
        base_url: Base URL for the LLM API. Uses BASE_URL env if omitted.
        api_key: API key for the LLM. Uses API_KEY env if omitted.

    Returns:
        A LangGraph agent (CompiledGraph) that accepts {"messages": [...]} and returns updated state.
    """

    if not api_key:
        api_key = get_env_var("API_KEY")
    if not base_url:
        base_url = get_env_var("BASE_URL")
    if not model_id:
        model_id = get_env_var("MODEL_ID")

    is_local = any(host in base_url for host in ["localhost", "127.0.0.1"])

    if not is_local and not api_key:
        raise ValueError("API_KEY is required for non-local environments.")

    tools = [
        geocode_location,
        get_weather_forecast,
        get_air_quality,
        get_sunrise_sunset,
        search_national_parks,
        get_park_alerts,
    ]

    chat = ChatOpenAI(
        model=model_id,
        temperature=0.01,
        api_key=api_key,
        base_url=base_url,
    )

    system_prompt = """\
You are an outdoor activity planning expert. You recommend the best day and time \
for outdoor activities using weather, air quality, daylight, and park data.

CRITICAL: Call tools ONE AT A TIME. Wait for each result before calling the next tool. \
Do NOT call multiple tools at once. Follow this exact order:

STEP 1: Call geocode_location with the location name (e.g. "Denver"). \
Wait for the result. Extract latitude, longitude, timezone, and state from the response.

STEP 2: Call search_national_parks with the state_code (e.g. "CO"). \
Wait for the result. Note the parkCode of the most relevant park for hiking/outdoor activities.

STEP 3: Call get_weather_forecast with the latitude and longitude from Step 1. \
Wait for the result. Identify the best day(s) with low precipitation and moderate wind.

STEP 4: Call get_air_quality with the same latitude and longitude. \
Wait for the result. Check that AQI is below 100 for the recommended day.

STEP 5: Call get_sunrise_sunset with the latitude, longitude, and the best date \
in YYYY-MM-DD format (e.g. "2026-03-07"). Wait for the result.

STEP 6: Call get_park_alerts with the parkCode from Step 2 (e.g. "romo"). \
Wait for the result.

STEP 7: Provide your final recommendation including:
- Best day and start time based on sunrise
- Weather conditions (temp, wind, precipitation, UV)
- Air quality status
- Recommended park and any active alerts
- Gear suggestions

RULES:
- NEVER call a tool with null or empty values. Every parameter must have a real value.
- Use YYYY-MM-DD format for dates (e.g. "2026-03-07"), never "tomorrow" or "next weekend".
- Always geocode first. Do not guess coordinates.
- If a tool returns an error, acknowledge it and continue with other tools."""

    agent = create_agent(model=chat, tools=tools, system_prompt=system_prompt)

    return agent
