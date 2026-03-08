import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ChapterOutline

logger = logging.getLogger("coc.llm")


class OutlinerAgent:
    """Agent for creating story outlines."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/outliner.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_outline(self, text: str) -> list[ChapterOutline]:
        """Extract chapter outline from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)

        if data:
            chapters = [ChapterOutline(**c) for c in data.get("chapters", [])]
            return chapters

        raise ValueError("Could not extract outline from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Outliner",
            goal="Create compelling story outlines",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted outline with chapters",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("OutlinerAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("OutlinerAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def create_outline(
        self,
        context: StoryContext,
        target_chapters: int = 10,
        feedback: str | None = None,
    ) -> list[ChapterOutline]:
        """Create chapter outline from world setting."""
        world_dict = context.world.model_dump() if context.world else {}

        feedback_section = f"""

用户反馈（请根据以下反馈修改大纲）:
{feedback}
""" if feedback else ""

        task_desc = f"""
Create a story outline based on:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}
{feedback_section}

Target number of chapters: {target_chapters}

Output a complete outline following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        outline = self._extract_outline(result)
        context.outline = outline
        return outline
