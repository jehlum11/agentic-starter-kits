import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from openai_responses_agent_base.agent import get_agent_closure, AIAgent
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# OpenAI-compatible request/response models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = False


# Global variable for agent factory (get_agent callable)
get_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the agent closure on startup and clear it on shutdown.

    Reads BASE_URL and MODEL_ID from the environment and sets the global get_agent
    for the /chat/completions endpoint. Uses OpenAI client and Responses API (no agentic framework).
    """
    global get_agent

    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")

    if base_url and not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    get_agent = get_agent_closure(base_url=base_url, model_id=model_id)

    yield

    get_agent = None


app = FastAPI(
    title="OpenAI Responses Agent API",
    description="FastAPI service for agent (OpenAI client + pure Python, Responses API, no agentic framework)",
    lifespan=lifespan,
)


def _build_user_message(messages: list[ChatMessage]) -> str:
    """Extract the last user message from the OpenAI-format messages list."""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    raise ValueError("No user message found in messages list")


def _make_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.

    When stream=false, returns a full chat.completion response.
    When stream=true, returns SSE chat.completion.chunk events.
    """
    global get_agent

    if get_agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    user_message = _build_user_message(request.messages)
    model_id = request.model or getenv("MODEL_ID", "model")

    if request.stream:
        return await _handle_stream(user_message, model_id)
    else:
        return await _handle_chat(user_message, model_id)


async def _handle_chat(user_message: str, model_id: str):
    """Handle non-streaming chat completion."""
    global get_agent

    try:
        agent = get_agent()
        messages = [{"role": "user", "content": user_message}]

        result = await agent.run(input=messages)

        # Extract the final assistant content and context messages
        assistant_content = ""
        context_messages = result.get("messages", [])

        # Find the last assistant message with content
        for msg in reversed(context_messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
                assistant_content = msg["content"]
                break

        return {
            "id": _make_completion_id(),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": assistant_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "context": context_messages,
            "usage": None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


async def _handle_stream(user_message: str, model_id: str):
    """Handle streaming chat completion with OpenAI-compatible SSE chunks."""
    global get_agent

    completion_id = _make_completion_id()
    created = int(time.time())

    async def event_generator():
        try:
            queue: asyncio.Queue = asyncio.Queue()

            def on_event(event_type: str, data: dict):
                queue.put_nowait((event_type, data))

            def run_agent():
                adapter = get_agent()
                agent = AIAgent(
                    model=adapter._model_id,
                    base_url=adapter._base_url,
                    api_key=adapter._api_key,
                )
                for name, func in adapter._tools:
                    agent.register_tool(name, func)
                return agent.query(user_message, on_event=on_event)

            task = asyncio.get_event_loop().run_in_executor(None, run_agent)

            while not task.done():
                try:
                    event_type, event_data = await asyncio.wait_for(queue.get(), timeout=0.1)
                    chunk_data = _map_event_to_chunk(event_type, event_data, completion_id, created, model_id)
                    if chunk_data:
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                except asyncio.TimeoutError:
                    continue

            # Drain remaining events
            while not queue.empty():
                event_type, event_data = queue.get_nowait()
                chunk_data = _map_event_to_chunk(event_type, event_data, completion_id, created, model_id)
                if chunk_data:
                    yield f"data: {json.dumps(chunk_data)}\n\n"

            answer = task.result()
            if answer:
                data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_id,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": answer},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(data)}\n\n"

            # Send final chunk with finish_reason
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
            error_data = {
                "error": {
                    "message": "Internal server error",
                    "type": "server_error",
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _map_event_to_chunk(event_type: str, event_data: dict, completion_id: str, created: int, model_id: str) -> dict | None:
    """Map an internal agent event to an OpenAI-compatible SSE chunk."""
    if event_type == "tool_call":
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": event_data.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": event_data.get("name", ""),
                                    "arguments": json.dumps(event_data.get("args", {})),
                                },
                            }
                        ],
                    },
                    "finish_reason": None,
                }
            ],
        }
    elif event_type == "tool_result":
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "tool",
                        "content": str(event_data.get("output", "")),
                        "name": event_data.get("name", ""),
                    },
                    "finish_reason": None,
                }
            ],
        }
    return None


@app.get("/health")
async def health():
    """Return service health and whether the agent has been initialized."""
    return {"status": "healthy", "agent_initialized": get_agent is not None}


if __name__ == "__main__":
    import uvicorn

    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
