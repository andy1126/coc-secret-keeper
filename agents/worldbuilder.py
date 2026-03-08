import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import WorldSetting, Character, Entity, Location

logger = logging.getLogger("coc.llm")


class WorldbuilderAgent:
    """Agent for building Cthulhu mythos world settings."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/worldbuilder.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_world(self, text: str) -> WorldSetting:
        """Extract world setting from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)

        if data:
            # Parse locations (handle both string and dict formats)
            locations = []
            for loc in data.get("locations", []):
                if isinstance(loc, str):
                    locations.append(Location(name=loc, description=""))
                elif isinstance(loc, dict):
                    locations.append(Location(**loc))

            # Parse entities
            entities = [Entity(**e) for e in data.get("entities", [])]

            # Parse characters
            characters = [Character(**c) for c in data.get("characters", [])]

            return WorldSetting(
                era=data["era"],
                locations=locations,
                entities=entities,
                forbidden_knowledge=data.get("forbidden_knowledge", ""),
                rules=data.get("rules", []),
                characters=characters,
            )

        raise ValueError("Could not extract world setting from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Worldbuilder",
            goal="Build Cthulhu mythos world settings",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted world setting",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("WorldbuilderAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("WorldbuilderAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def build_world(
        self, context: StoryContext, feedback: str | None = None
    ) -> WorldSetting:
        """Build world setting from story seed."""
        feedback_section = f"""

用户反馈（请根据以下反馈修改世界观）:
{feedback}
""" if feedback else ""

        task_desc = f"""
Based on this story seed, create a complete world setting:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}
{feedback_section}

Output a complete world setting following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        world = self._extract_world(result)
        context.world = world
        return world
