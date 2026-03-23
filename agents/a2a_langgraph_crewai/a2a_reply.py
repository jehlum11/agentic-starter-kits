"""Helpers: call another A2A agent and turn SendMessageResponse into plain text."""

from __future__ import annotations

import warnings
from typing import Any
from uuid import uuid4

import httpx

# Legacy client is still the simplest JSON-RPC surface used in a2a-samples.
warnings.filterwarnings(
    "ignore",
    message=".*A2AClient is deprecated.*",
    category=DeprecationWarning,
)

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    JSONRPCErrorResponse,
    Message,
    MessageSendParams,
    SendMessageRequest,
    Task,
)
from a2a.utils import get_artifact_text, get_message_text


def _unwrap_send_result(response: Any) -> Any:
    root = response.root
    if isinstance(root, JSONRPCErrorResponse):
        raise RuntimeError(f"A2A JSON-RPC error: {root.error}")
    return root.result


def a2a_result_to_text(result: Message | Task | Any) -> str:
    if isinstance(result, Message):
        return get_message_text(result)
    if isinstance(result, Task):
        chunks: list[str] = []
        if result.artifacts:
            for art in result.artifacts:
                chunks.append(get_artifact_text(art))
        if chunks:
            return "\n".join(chunks)
        if result.status and result.status.message:
            return get_message_text(result.status.message)
        return str(result)
    return str(result)


async def send_a2a_text_message(
    base_url: str, text: str, timeout: float = 120.0
) -> str:
    """Fetch agent card, send one user text message, return assistant text."""
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resolver = A2ACardResolver(httpx_client=client, base_url=base)
        card = await resolver.get_agent_card()
        a2a = A2AClient(httpx_client=client, agent_card=card)
        payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": uuid4().hex,
            },
        }
        req = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**payload),
        )
        resp = await a2a.send_message(req)
        result = _unwrap_send_result(resp)
        return a2a_result_to_text(result)
