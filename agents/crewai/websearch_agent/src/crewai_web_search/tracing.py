from os import getenv
import time
import requests
from dotenv import load_dotenv
from typing import Callable, Optional

import logging

logger = logging.getLogger("tracing")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s"
)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def check_mlflow_health(mlflow_tracking_uri: str, max_wait_time: int = 60, retry_interval: int = 1) -> None:
    """
    Check MLflow health by trying the /health endpoint. If it fails, retry for a certain duration before giving up.
    args:
        mlflow_tracking_uri: base URI of the MLflow server
        max_wait_time: total time to keep retrying before giving up (in seconds)
        retry_interval: time to wait between retries (in seconds)
    """
    mlflow_health_endpoint = "/health"
    mlflow_url = f"{mlflow_tracking_uri.rstrip('/')}{mlflow_health_endpoint}"
    start_time = time.time()

    while True:
        try:
            response = requests.get(mlflow_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"MLflow health check passed at {mlflow_url} with status code {response.status_code}.")
                return  # Success, exit the function without error
            else:
                logger.warning(
                    f"MLflow returned status code {response.status_code} at {mlflow_url}\n"
                    f"  Status Code: {response.status_code}\n"
                    f"  Reason: {response.reason}\n"
                    f"  Response Body: {response.text[:500]}"
                )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to connect to MLflow at {mlflow_url}: {e}")

        elapsed_time = time.time() - start_time
        if elapsed_time >= max_wait_time:
            logger.error(f"MLflow server is unavailable after {max_wait_time} seconds of checking.")
            raise RuntimeError("MLflow server is unavailable. Please start the server or check the URI.")

        logger.warning(f"Retrying in {retry_interval} seconds...")
        time.sleep(retry_interval)

def wrap_func_with_mlflow_trace(func: Callable, type: str, name: str = None) -> Callable:
    """
    Wrap a function with MLflow.trace(span_type=SpanType.<type>) if MLflow is enabled.

    Returns the original function if MLflow is not installed or tracing is disabled.
    """
    tracking_uri: Optional[str] = getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        return func

    import mlflow
    from mlflow.entities import SpanType

    if type == "tool":
        return mlflow.trace(span_type=SpanType.TOOL, name=name)(func)
    elif type == "agent":
        return mlflow.trace(span_type=SpanType.AGENT, name=name)(func)
    else:
        raise ValueError(f"Unsupported trace type: {type}")


def enable_tracing() -> None:
    """
    Enable MLflow tracing if MLFLOW_TRACKING_URI is set.

    Behavior:
    1. If MLFLOW_TRACKING_URI is not set: tracing is skipped.
    2. If MLFLOW_TRACKING_URI is set:
       - Try to connect to the server.
       - If the server is reachable: tracing is enabled.
       - If the server is unreachable: raise RuntimeError and crash the application.
    """
    load_dotenv()
    tracking_uri: Optional[str] = getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        logger.info("[Tracing] MLFLOW_TRACKING_URI not set. Tracing is disabled.")
        return

    import importlib
    import mlflow
    import mlflow.crewai

    # Check if server is reachable
    try:
        check_mlflow_health(mlflow_tracking_uri=tracking_uri)
        logger.info(f"[Tracing] MLflow server is reachable at {tracking_uri}")
    except RuntimeError as e:
        logger.warning(f"[Tracing] MLflow server is unreachable at {tracking_uri}")
        raise RuntimeError(
                    f"MLFLOW_TRACKING_URI is set but server is unreachable: {tracking_uri}. "
                    f"Start the server or check the URI. Error: {e}"
                )

    # Server is reachable → enable tracing
    mlflow.set_tracking_uri(tracking_uri)
    experiment_name: str = getenv("MLFLOW_EXPERIMENT_NAME", "default-agent-experiment")
    mlflow.set_experiment(experiment_name)
    mlflow.config.enable_async_logging()

    # CrewAI orchestration tracing (Crew, Task, Agent, Tool spans) — always enabled
    mlflow.crewai.autolog()

    # LLM call-level tracing — depends on which provider path CrewAI uses.
    # CrewAI native providers (openai, anthropic, gemini, azure, bedrock) bypass
    # the crewai.LLM.call patch, so we need a provider-specific autolog.
    # Non-native providers go through LiteLLM, so we use mlflow.litellm.autolog().
    provider_autolog_map = {
        "openai": "mlflow.openai",
        "anthropic": "mlflow.anthropic",
        "gemini": "mlflow.gemini",
        "azure": "mlflow.openai",
        "bedrock": "mlflow.bedrock",
        "litellm": "mlflow.litellm",
    }

    llm_provider: str = getenv("LLM_PROVIDER", "litellm").lower().strip()

    if llm_provider not in provider_autolog_map:
        logger.warning(
            f"[Tracing] Unknown LLM_PROVIDER '{llm_provider}'. "
            f"Supported: {', '.join(provider_autolog_map.keys())}. Falling back to 'litellm'."
        )
        llm_provider = "litellm"

    module_name = provider_autolog_map[llm_provider]
    module = importlib.import_module(module_name)
    module.autolog()

    logger.info(
        f"[Tracing Enabled] MLflow -> {tracking_uri}, Experiment: {experiment_name}, "
        f"LLM Provider: {llm_provider} ({module_name}.autolog())"
    )
