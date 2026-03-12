from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task, after_kickoff

from crewai_web_search.tools import WebSearchTool


@CrewBase
class AssistanceAgents:
    """Assistants crew"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, llm: LLM, **kwargs):
        self.llm = llm
        self.step_callback = kwargs.pop("step_callback", None)
        self.enable_stream = kwargs.pop("stream", False)

    @after_kickoff  # Optional hook to be executed after the crew has finished
    def log_results(self, output):
        # Example of logging results, dynamically changing the output
        print(f"Results: {output}")
        return output

    @agent
    def ai_assistant(self) -> Agent:
        return Agent(
            config=self.agents_config["ai_assistant"],
            tools=[WebSearchTool()],
            verbose=True,
            llm=self.llm,
            max_iter=3,
            max_retry_limit=1,
        )

    @task
    def generate_response_task(self) -> Task:
        return Task(
            config=self.tasks_config["generate_response_task"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the AI Assistant crew"""

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            step_callback=self.step_callback,
            stream=self.enable_stream,
        )
