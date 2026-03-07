import json
import re
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import WorldSetting, Character, Entity


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
        # Try to find JSON block with ```json ... ```
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            # Fallback: find raw JSON object
            json_match = re.search(r'\{[\s\S]*"era"[\s\S]*"characters"[\s\S]*\}', text)
            raw = json_match.group(0) if json_match else None

        if raw:
            data = json.loads(raw)

            # Parse entities
            entities = [Entity(**e) for e in data.get("entities", [])]

            # Parse characters
            characters = [Character(**c) for c in data.get("characters", [])]

            return WorldSetting(
                era=data["era"],
                locations=data.get("locations", []),
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

        return str(crew.kickoff())

    def build_world(self, context: StoryContext) -> WorldSetting:
        """Build world setting from story seed."""
        task_desc = f"""
Based on this story seed, create a complete world setting:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

Output a complete world setting following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        world = self._extract_world(result)
        context.world = world
        return world
