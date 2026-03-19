import asyncio
import json
import logging
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from os import getenv

from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from autogen_core import CancellationToken
from autogen_ext.tools.mcp import (
    SseServerParams,
    create_mcp_server_session,
    mcp_server_tools,
)
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from autogen_agent_base.agent import get_agent_chat

load_dotenv()


class ChatMessage(BaseModel):
    """OpenAI-style message (optional alternative to `message`)."""

    role: str = Field(..., description="user, assistant, or system")
    content: str = Field(..., description="Message text")


class ChatRequest(BaseModel):
    """Chat request: use `message` or `messages` (last user wins); set `stream` for SSE chunks."""

    message: str | None = Field(
        None, description="Single user message (simplest). Ignored if `messages` is set."
    )
    messages: list[ChatMessage] | None = Field(
        None,
        description="OpenAI-style list; last user message is used as the task.",
    )
    stream: bool = Field(
        False,
        description="If true, response is SSE: chat.completion.chunk events, then data: [DONE].",
    )

    @model_validator(mode="after")
    def _need_user_input(self):
        if self.messages:
            if not any(m.role == "user" for m in self.messages):
                raise ValueError("messages must include at least one role=user entry")
            return self
        if self.message is not None and self.message != "":
            return self
        raise ValueError("Provide non-empty `message` or `messages` with a user turn")

    def user_task(self) -> str:
        if self.messages:
            for m in reversed(self.messages):
                if m.role == "user":
                    return m.content
        return self.message or ""


class ChatResponse(BaseModel):
    """Non-streaming chat response (user + assistant messages)."""

    messages: list[dict] = Field(
        ...,
        description="Conversation turns; last entry is typically the assistant reply.",
    )
    finish_reason: str = Field(
        ...,
        description="Why generation stopped (e.g. stop).",
        examples=["stop"],
    )


class HealthResponse(BaseModel):
    """Service health status."""

    status: str = Field(
        ..., description="Current service status.", examples=["healthy"]
    )
    agent_initialized: bool = Field(
        ...,
        description="Whether the MCP-backed agent is ready to serve requests.",
    )


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
    description="FastAPI service for AutoGen AssistantAgent with MCP tools. "
    "POST /chat/completions with `message` or `messages`; set `stream: true` for OpenAI-style SSE chunks.",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Chat", "description": "Chat completion operations"},
        {"name": "Health", "description": "Service health monitoring"},
    ],
)


def _assistant_content_from_result(result) -> str:
    if not result.messages:
        return ""
    last = result.messages[-1]
    if isinstance(last, TextMessage):
        return last.content or ""
    return getattr(last, "content", None) or str(last)


@app.post(
    "/chat/completions",
    response_model=ChatResponse,
    summary="Create chat completion",
    description=(
        "Creates a model response for the given chat conversation. "
        "When `stream=false`, returns a complete JSON body with `messages` and `finish_reason`. "
        "When `stream=true`, returns Server-Sent Events with `chat.completion.chunk` deltas "
        "(OpenAI-style `data: {json}\\n\\n`), terminated by `data: [DONE]\\n\\n`."
    ),
    tags=["Chat"],
)
async def chat(request: ChatRequest):
    agent = getattr(app.state, "mcp_agent", None)
    if agent is None:
        err = (
            getattr(app.state, "mcp_agent_error", None)
            or "Agent not initialized (MCP connection failed or not ready)"
        )
        raise HTTPException(status_code=503, detail=err)

    user_text = request.user_task()
    model_id = getenv("MODEL_ID") or "model"

    if request.stream:

        async def event_generator():
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            created = int(time.time())
            cancel_token = CancellationToken()
            logger = logging.getLogger(__name__)
            try:
                async for ev in agent.run_stream(
                    task=user_text,
                    cancellation_token=cancel_token,
                ):
                    if isinstance(ev, ModelClientStreamingChunkEvent) and ev.content:
                        data = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_id,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": ev.content},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(data)}\n\n"

                final_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_id,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception:
                logger.exception("Error in stream event_generator")
                err = {
                    "error": {
                        "message": "Internal server error",
                        "type": "server_error",
                    }
                }
                yield f"data: {json.dumps(err)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        cancel_token = CancellationToken()
        result = await agent.run(
            task=user_text,
            cancellation_token=cancel_token,
        )
        response_messages = [{"role": "user", "content": user_text}]
        content = _assistant_content_from_result(result)
        response_messages.append({"role": "assistant", "content": content})
        return ChatResponse(messages=response_messages, finish_reason="stop")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["Health"],
)
async def health():
    agent_initialized = getattr(app.state, "mcp_agent", None) is not None
    body = {
        "status": "healthy" if agent_initialized else "not_ready",
        "agent_initialized": agent_initialized,
    }
    if not agent_initialized:
        return JSONResponse(status_code=503, content=body)
    return body


if __name__ == "__main__":
    import uvicorn

    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
