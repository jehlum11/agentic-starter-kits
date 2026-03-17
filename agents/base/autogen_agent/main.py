import asyncio
import logging
import os
from os import getenv
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from autogen_core import CancellationToken
from autogen_agentchat.messages import TextMessage
from autogen_ext.tools.mcp import (
    SseServerParams,
    create_mcp_server_session,
    mcp_server_tools,
)

from autogen_agent_base.agent import get_agent_chat
from dotenv import load_dotenv

load_dotenv()


# Request/Response models (same API shape as before)
class ChatRequest(BaseModel):
    """Incoming chat request body for the /chat endpoint."""

    message: str


class ChatResponse(BaseModel):
    """Structured chat response with message history."""

    messages: list[dict]
    finish_reason: str


MCP_SYSTEM_PROMPT = (
    "You are a helpful assistant. Your goal is to answer the user's question directly in every interaction. "
    "ONLY call a tool if you cannot answer with your own knowledge or if external/up-to-date information is required. "
    "If you call a tool and receive a response, extract the relevant answer and present it as your FINAL answer to the user. "
    "Never call tools more than once for the same user question. Be polite, concise, and accurate in every reply."
)


async def _mcp_agent_holder(
    app: FastAPI, shutdown_event: asyncio.Event, ready_event: asyncio.Event
):
    """Hold MCP session and AutoGen agent; signal when ready, wait until shutdown."""
    mcp_url = getenv("MCP_SERVER_URL")
    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")
    api_key = os.environ.get("API_KEY", "")
    if base_url and not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    logger = logging.getLogger(__name__)
    server_params = SseServerParams(url=mcp_url, timeout=60, sse_read_timeout=300)
    try:
        async with create_mcp_server_session(server_params) as session:
            await session.initialize()
            tools = await mcp_server_tools(server_params=server_params, session=session)
            get_agent = get_agent_chat(
                model_id=model_id,
                base_url=base_url,
                api_key=api_key,
                tools=tools,
            )
            agent = get_agent(system_prompt=MCP_SYSTEM_PROMPT)
            app.state.mcp_agent = agent
            ready_event.set()
            await shutdown_event.wait()
    except Exception as e:
        app.state.mcp_agent = None
        logger.exception("MCP agent init failed: %s", e)
        traceback.print_exception(type(e), e, e.__traceback__)
        app.state.mcp_agent_error = str(e)
        ready_event.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to MCP server, build AutoGen agent with MCP tools, keep connection until shutdown."""
    app.state.mcp_agent = None
    app.state.mcp_agent_error = None
    shutdown_event = asyncio.Event()
    ready_event = asyncio.Event()
    task = asyncio.create_task(_mcp_agent_holder(app, shutdown_event, ready_event))
    try:
        await asyncio.wait_for(ready_event.wait(), timeout=60.0)
    except asyncio.TimeoutError:
        app.state.mcp_agent_error = "MCP connection timeout"
    yield
    shutdown_event.set()
    await asyncio.wait_for(task, timeout=10.0)


app = FastAPI(
    title="AutoGen Agent API (MCP)",
    description="FastAPI service for AutoGen AssistantAgent with MCP tools (same behavior as interact_with_mcp.py)",
    lifespan=lifespan,
)


@app.post("/chat/completions", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint: accepts a message, runs the MCP-backed AutoGen agent, returns the response.
    """
    agent = getattr(app.state, "mcp_agent", None)
    if agent is None:
        err = (
            getattr(app.state, "mcp_agent_error", None)
            or "Agent not initialized (MCP connection failed or not ready)"
        )
        raise HTTPException(status_code=503, detail=err)

    try:
        cancel_token = CancellationToken()
        result = await agent.run(
            task=request.message,
            cancellation_token=cancel_token,
        )
        response_messages = [{"role": "user", "content": request.message}]
        content = ""
        if result.messages:
            last = result.messages[-1]
            content = getattr(last, "content", None) or str(last)
            if isinstance(last, TextMessage):
                content = last.content or ""
        response_messages.append({"role": "assistant", "content": content})
        return ChatResponse(messages=response_messages, finish_reason="stop")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


@app.get("/health")
async def health():
    """Return service health and whether the MCP agent is ready."""
    return {
        "status": "healthy",
        "agent_initialized": getattr(app.state, "mcp_agent", None) is not None,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
