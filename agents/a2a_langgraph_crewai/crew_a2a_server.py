"""
CrewAI agent exposed as an A2A server (JSON-RPC over HTTP via a2a-sdk).

Run: uv run python crew_a2a_server.py
OpenShift: PORT=8080 (set by platform); local default CREW_A2A_PORT=9100.
"""

from __future__ import annotations

import asyncio
import logging
from os import getenv

import uvicorn
from crewai import Agent, Crew, LLM, Task
from dotenv import load_dotenv

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_llm: LLM | None = None


def _listen_port() -> int:
    """OpenShift sets PORT=8080; locally use CREW_A2A_PORT (default 9100)."""
    if p := getenv("PORT"):
        return int(p)
    return int(getenv("CREW_A2A_PORT", "9100"))


def _ensure_llm() -> LLM:
    global _llm
    if _llm is not None:
        return _llm
    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")
    api_key = getenv("API_KEY", "no-key")
    if not base_url or not model_id:
        raise RuntimeError("BASE_URL and MODEL_ID must be set (see template.env).")
    if not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"
    _llm = LLM(
        model=f"openai/{model_id}",
        base_url=base_url,
        api_key=api_key,
        temperature=0.2,
    )
    return _llm


def _run_crew(user_prompt: str) -> str:
    llm = _ensure_llm()
    specialist = Agent(
        role="Specialist",
        goal="Answer the user's question clearly and accurately.",
        backstory="You are a concise expert. Respond in plain text without role-playing headers.",
        llm=llm,
        verbose=False,
    )
    task = Task(
        description=user_prompt,
        expected_output="A direct, helpful answer.",
        agent=specialist,
    )
    crew = Crew(agents=[specialist], tasks=[task], verbose=False)
    return str(crew.kickoff())


class CrewA2AExecutor(AgentExecutor):
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        text = context.get_user_input()
        if not text.strip():
            await event_queue.enqueue_event(
                new_agent_text_message("Error: empty user message.")
            )
            return
        try:
            result = await asyncio.to_thread(_run_crew, text)
            await event_queue.enqueue_event(new_agent_text_message(result))
        except Exception as e:  # noqa: BLE001
            logger.exception("Crew kickoff failed")
            await event_queue.enqueue_event(
                new_agent_text_message(f"CrewAI error: {e!s}")
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported in this demo")


def main() -> None:
    public_base = getenv("CREW_A2A_PUBLIC_URL", "http://127.0.0.1:9100").rstrip("/")
    port = _listen_port()

    skill = AgentSkill(
        id="crew_specialist",
        name="CrewAI specialist",
        description="Single-agent CrewAI crew backed by an OpenAI-compatible LLM.",
        tags=["crewai", "text"],
        examples=["Explain what A2A is in one paragraph."],
    )

    agent_card = AgentCard(
        name="CrewAI A2A Specialist",
        description="Minimal CrewAI agent speaking the A2A protocol.",
        url=f"{public_base}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
        supports_authenticated_extended_card=False,
    )

    handler = DefaultRequestHandler(
        agent_executor=CrewA2AExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    )
    logger.info("Crew A2A listening on 0.0.0.0:%s (card url=%s)", port, agent_card.url)
    uvicorn.run(app.build(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
