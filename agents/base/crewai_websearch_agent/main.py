import asyncio
import json
import re
from contextlib import asynccontextmanager
from os import getenv

from crewai import LLM
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from crewai_web_search.crew import AssistanceAgents


class ChatRequest(BaseModel):
    """Incoming chat request body for the /chat and /stream endpoints."""

    message: str


# Global LLM instance
llm = None

# Patterns that indicate CrewAI internal scaffolding in the output
_REACT_NOISE = re.compile(
    r"(^|\n)\s*(Thought:\s*|Action:\s*|Action Input:\s*|Observation:\s*|Final Answer:\s*).*",
    re.DOTALL,
)
_CREWAI_PROMPT_MARKER = "\n\n\nYou ONLY have access to"


def _clean_content(text: str) -> str:
    """Strip CrewAI internal ReAct scaffolding and prompt noise from output."""
    # Strip appended retry instructions
    idx = text.find(_CREWAI_PROMPT_MARKER)
    if idx != -1:
        text = text[:idx]

    # Strip ReAct format artifacts (Thought:/Action:/Final Answer: prefixes)
    text = _REACT_NOISE.sub("", text)

    return text.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the CrewAI LLM on startup."""
    global llm

    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")
    api_key = getenv("API_KEY", "no-key")

    if base_url and not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    llm = LLM(
        model=f"openai/{model_id}",
        base_url=base_url,
        api_key=api_key,
        temperature=0.7,
    )

    yield

    llm = None


app = FastAPI(
    title="CrewAI Web Search Agent API",
    description="FastAPI service for CrewAI Web Search Agent",
    lifespan=lifespan,
)


@app.post("/chat")
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint. Returns the final answer."""
    global llm

    if llm is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        inputs = {
            "user_prompt": request.message,
            "custom_instruction": "",
        }

        crew = AssistanceAgents(llm=llm).crew()
        result = await asyncio.to_thread(crew.kickoff, inputs=inputs)

        response_messages = [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": _clean_content(str(result))},
        ]

        return {"messages": response_messages, "finish_reason": "stop"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


@app.post("/stream")
async def stream(request: ChatRequest):
    """Streaming chat endpoint using CrewAI's native token-level streaming.

    Uses Crew(stream=True) with kickoff_async() which returns a
    CrewStreamingOutput that yields StreamChunk objects with real
    token-by-token content from the LLM.
    """
    global llm

    if llm is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def _event_generator():
        inputs = {
            "user_prompt": request.message,
            "custom_instruction": "",
        }

        crew = AssistanceAgents(llm=llm, stream=True).crew()

        # kickoff_async with stream=True returns CrewStreamingOutput
        streaming_output = await crew.kickoff_async(inputs=inputs)

        # Buffer tokens until we see "Final Answer:" — everything before
        # that is internal ReAct reasoning (Thought/Action/Observation).
        buffer = ""
        emitting = False

        async for chunk in streaming_output:
            if chunk.chunk_type.value != "text" or not chunk.content:
                continue

            if emitting:
                # Already past "Final Answer:", emit tokens directly
                sse_chunk = {
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": chunk.content},
                        "finish_reason": None,
                    }]
                }
                yield f"data: {json.dumps(sse_chunk)}\n\n"
            else:
                buffer += chunk.content
                # Check if we've reached the final answer
                marker = "Final Answer:"
                idx = buffer.find(marker)
                if idx != -1:
                    emitting = True
                    # Emit any text after the marker that arrived in this chunk
                    remainder = buffer[idx + len(marker):]
                    if remainder.strip():
                        sse_chunk = {
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": remainder.lstrip()},
                                "finish_reason": None,
                            }]
                        }
                        yield f"data: {json.dumps(sse_chunk)}\n\n"

        # If no "Final Answer:" was found, send the cleaned full buffer
        if not emitting and buffer.strip():
            cleaned = _clean_content(buffer)
            if cleaned:
                sse_chunk = {
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": cleaned},
                        "finish_reason": None,
                    }]
                }
                yield f"data: {json.dumps(sse_chunk)}\n\n"

        # Send final stop event
        final_chunk = {
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health():
    """Return service health status."""
    return {"status": "healthy", "agent_initialized": llm is not None}


if __name__ == "__main__":
    import uvicorn

    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
