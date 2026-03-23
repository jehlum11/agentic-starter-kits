"""
LangGraph ReAct-style orchestrator exposed as A2A; delegates to the CrewAI A2A agent via tool.

Run (after crew_a2a_server): uv run python langgraph_a2a_server.py
OpenShift: PORT=8080; set CREW_A2A_URL to the in-cluster Service URL (e.g. http://a2a-crew-agent:8080).
"""

from __future__ import annotations

import logging
from os import getenv

import uvicorn
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from a2a_reply import send_a2a_text_message

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_graph = None


def _listen_port() -> int:
    if p := getenv("PORT"):
        return int(p)
    return int(getenv("LANGGRAPH_A2A_PORT", "9200"))


def _crew_base_url() -> str:
    return getenv("CREW_A2A_URL", "http://127.0.0.1:9100").rstrip("/")


def _normalize_openai_base_url(base_url: str) -> str:
    """Match crew_a2a_server + react_agent: OpenAI-compatible chat is under .../v1/chat/completions."""
    u = base_url.strip()
    if not u.endswith("/v1"):
        u = u.rstrip("/") + "/v1"
    return u


@tool
async def ask_crew_specialist(question: str) -> str:
    """Ask the remote CrewAI A2A specialist for a detailed answer. Use for harder or domain-specific questions."""
    return await send_a2a_text_message(_crew_base_url(), question)


def _build_graph():
    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")
    api_key = getenv("API_KEY") or "no-key"
    if not base_url or not model_id:
        raise RuntimeError("BASE_URL and MODEL_ID must be set (see template.env).")

    base_url = _normalize_openai_base_url(base_url)
    logger.info("ChatOpenAI base_url (normalized)=%s", base_url)

    is_local = any(h in base_url for h in ("localhost", "127.0.0.1"))
    if not is_local and not api_key:
        raise ValueError("API_KEY is required for non-local BASE_URL.")

    chat = ChatOpenAI(
        model=model_id,
        temperature=0.01,
        api_key=api_key,
        base_url=base_url,
    )
    system_prompt = (
        "You are the orchestrator. Answer simple questions yourself. "
        "For deeper or specialized questions, call ask_crew_specialist once, "
        "then summarize the final answer for the user."
    )
    return create_agent(
        model=chat,
        tools=[ask_crew_specialist],
        system_prompt=system_prompt,
    )


def _ensure_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def _last_ai_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                parts = []
                for block in c:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return "\n".join(parts) if parts else str(c)
            return str(c)
    return ""


class LangGraphA2AExecutor(AgentExecutor):
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user = context.get_user_input()
        if not user.strip():
            await event_queue.enqueue_event(
                new_agent_text_message("Error: empty user message.")
            )
            return
        try:
            graph = _ensure_graph()
            out = await graph.ainvoke({"messages": [HumanMessage(content=user)]})
            messages = out.get("messages", [])
            reply = _last_ai_text(messages) or str(out)
            await event_queue.enqueue_event(new_agent_text_message(reply))
        except Exception as e:  # noqa: BLE001
            logger.exception("LangGraph invoke failed")
            await event_queue.enqueue_event(
                new_agent_text_message(f"LangGraph error: {e!s}")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported in this demo")


def main() -> None:
    public_base = getenv("LANGGRAPH_A2A_PUBLIC_URL", "http://127.0.0.1:9200").rstrip(
        "/"
    )
    port = _listen_port()

    skill = AgentSkill(
        id="langgraph_orchestrator",
        name="LangGraph orchestrator",
        description="ReAct-style agent that can delegate to a CrewAI peer over A2A.",
        tags=["langgraph", "text", "a2a"],
        examples=[
            "What is 2+2?",
            "Ask the specialist to explain agent-to-agent protocols.",
        ],
    )

    agent_card = AgentCard(
        name="LangGraph A2A Orchestrator",
        description="LangGraph agent using A2A JSON-RPC to call a CrewAI specialist.",
        url=f"{public_base}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
        supports_authenticated_extended_card=False,
    )

    handler = DefaultRequestHandler(
        agent_executor=LangGraphA2AExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    )
    logger.info(
        "LangGraph A2A listening on 0.0.0.0:%s (crew peer=%s)",
        port,
        _crew_base_url(),
    )
    uvicorn.run(app.build(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
