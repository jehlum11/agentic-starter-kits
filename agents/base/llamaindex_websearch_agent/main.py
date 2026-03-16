import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from llama_index_workflow_agent_base.agent import get_workflow_closure
from llama_index_workflow_agent_base.workflow import ToolCallEvent, InputEvent
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


# Global variable for workflow closure (get_agent callable)
get_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the LlamaIndex workflow closure on startup and clear it on shutdown."""
    global get_agent

    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")

    if base_url and not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    get_agent = get_workflow_closure(model_id=model_id, base_url=base_url)

    yield

    get_agent = None


# Create FastAPI app
app = FastAPI(
    title="LlamaIndex Websearch Agent API",
    description="FastAPI service for LlamaIndex Websearch Agent",
    lifespan=lifespan,
)


def _get_message_content(msg) -> str:
    """Extract text content from a LlamaIndex ChatMessage."""
    if hasattr(msg, "blocks") and msg.blocks:
        # Find the first block with text content (skip ToolCallBlock)
        for block in msg.blocks:
            if hasattr(block, "text"):
                return block.text or ""
        return ""
    if hasattr(msg, "content"):
        if isinstance(msg.content, str):
            return msg.content
        if isinstance(msg.content, list) and msg.content:
            first = msg.content[0]
            if isinstance(first, dict) and "text" in first:
                return first["text"] or ""
    return ""


def _message_to_response_dict(msg):
    """Map a LlamaIndex ChatMessage to OpenAI-compatible format."""
    role = getattr(msg, "role", "user")
    content = _get_message_content(msg)

    if role == "user":
        return {"role": "user", "content": content}

    if role == "assistant":
        msg_data = {"role": "assistant", "content": content or ""}
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls and getattr(msg, "additional_kwargs", None):
            tool_calls = msg.additional_kwargs.get("tool_calls")
        if tool_calls:
            if hasattr(tool_calls[0], "tool_id"):  # ToolSelection-like
                msg_data["tool_calls"] = [
                    {
                        "id": tc.tool_id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.tool_kwargs),
                        },
                    }
                    for tc in tool_calls
                ]
            elif hasattr(tool_calls[0], "id") and hasattr(tool_calls[0], "function"):
                # ChatCompletionMessageFunctionToolCall object
                msg_data["tool_calls"] = []
                for tc in tool_calls:
                    fn = tc.function
                    args = fn.arguments if hasattr(fn, "arguments") else ""
                    if isinstance(args, dict):
                        args = json.dumps(args)
                    msg_data["tool_calls"].append(
                        {
                            "id": tc.id,
                            "type": getattr(tc, "type", "function"),
                            "function": {
                                "name": fn.name if hasattr(fn, "name") else "",
                                "arguments": args,
                            },
                        }
                    )
            else:  # dict format (e.g. from additional_kwargs)
                msg_data["tool_calls"] = []
                for tc in tool_calls:
                    fn = tc.get("function", {}) or {}
                    args = fn.get("arguments", "")
                    if isinstance(args, dict):
                        args = json.dumps(args)
                    msg_data["tool_calls"].append(
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": fn.get("name", ""), "arguments": args},
                        }
                    )
        return msg_data

    if role == "tool":
        additional = getattr(msg, "additional_kwargs", {}) or {}
        return {
            "role": "tool",
            "tool_call_id": additional.get("tool_call_id", ""),
            "name": additional.get("name", ""),
            "content": content,
        }

    return None  # skip system or unknown


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

        # Extract the final assistant message content
        assistant_content = ""
        context_messages = []

        if result and "messages" in result and len(result["messages"]) > 0:
            for message in result["messages"]:
                if getattr(message, "role", None) == "system":
                    continue
                item = _message_to_response_dict(message)
                if item is not None:
                    context_messages.append(item)

            # Final assistant content is the last assistant message with content
            for item in reversed(context_messages):
                if item["role"] == "assistant" and item.get("content"):
                    assistant_content = item["content"]
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
            agent = get_agent()
            messages = [{"role": "user", "content": user_message}]

            handler = agent.run(input=messages)

            async for event in handler.stream_events():
                if isinstance(event, ToolCallEvent):
                    for tc in event.tool_calls:
                        tool_calls_delta = [
                            {
                                "index": 0,
                                "id": getattr(tc, "tool_id", ""),
                                "type": "function",
                                "function": {
                                    "name": tc.tool_name,
                                    "arguments": json.dumps(tc.tool_kwargs),
                                },
                            }
                        ]
                        data = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_id,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "role": "assistant",
                                        "tool_calls": tool_calls_delta,
                                    },
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(data)}\n\n"

                elif isinstance(event, InputEvent):
                    if event.input:
                        last_msg = event.input[-1]
                        if getattr(last_msg, "role", None) == "tool":
                            additional = getattr(last_msg, "additional_kwargs", {}) or {}
                            data = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model_id,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "tool",
                                            "content": _get_message_content(last_msg),
                                            "name": additional.get("name", ""),
                                        },
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield f"data: {json.dumps(data)}\n\n"

            result = await handler
            # Extract final answer from the result
            if result and "response" in result:
                content = _get_message_content(result["response"].message)
                if content:
                    data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": content},
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


@app.get("/health")
async def health():
    """Return service health and whether the workflow closure has been initialized."""
    return {"status": "healthy", "agent_initialized": get_agent is not None}


if __name__ == "__main__":
    import uvicorn

    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)