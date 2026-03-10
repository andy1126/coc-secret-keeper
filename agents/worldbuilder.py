import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import (
    WorldSetting,
    Character,
    Entity,
    Location,
    Secret,
    Tension,
    TimelineEvent,
    ResearchQuestion,
)

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

            secrets = [Secret(**s) for s in data.get("secrets", [])]
            tensions = [Tension(**t) for t in data.get("tensions", [])]
            timeline = [TimelineEvent(**te) for te in data.get("timeline", [])]

            return WorldSetting(
                era=data["era"],
                locations=locations,
                entities=entities,
                forbidden_knowledge=data.get("forbidden_knowledge", ""),
                rules=data.get("rules", []),
                characters=characters,
                secrets=secrets,
                tensions=tensions,
                timeline=timeline,
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

    def _extract_questions(self, text: str) -> list[ResearchQuestion]:
        """Extract research questions from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)
        if data:
            return [ResearchQuestion(**q) for q in data.get("questions", [])]
        raise ValueError("Could not extract research questions from response")

    def generate_questions(self, context: StoryContext) -> list[ResearchQuestion]:
        """Analyze seed and generate research questions across 4 dimensions."""
        task_desc = f"""
分析以下故事种子，生成4-6个研究问题，覆盖以下维度：
- genre（类型）：该类型故事的经典叙事模式和手法
- psychology（心理）：角色面临的心理状态和反应
- history（历史）：故事设定时代的社会文化背景
- dramaturgy（戏剧理论）：如何设计递增的冲突与张力

故事种子:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

请输出JSON格式:
```json
{{
  "questions": [
    {{"topic": "genre", "question": "..."}},
    {{"topic": "psychology", "question": "..."}},
    {{"topic": "history", "question": "..."}},
    {{"topic": "dramaturgy", "question": "..."}}
  ]
}}
```
"""
        from agents.json_utils import run_with_retry

        questions = run_with_retry(
            lambda: self._run_agent(task_desc),
            self._extract_questions,
            label="WorldbuilderAgent.generate_questions",
        )
        context.research_questions = questions
        return questions

    def build_world(self, context: StoryContext, feedback: str | None = None) -> WorldSetting:
        """Build world setting from story seed."""
        feedback_section = (
            f"""

用户反馈（请根据以下反馈修改世界观）:
{feedback}
"""
            if feedback
            else ""
        )

        existing_world = context.world.model_dump() if context.world and feedback else None

        research_section = ""
        if context.research_notes:
            notes_dump = json.dumps(
                [n.model_dump() for n in context.research_notes],
                ensure_ascii=False,
                indent=2,
            )
            research_section = f"""
研究笔记（请充分利用以下研究成果丰富世界观）:
{notes_dump}
"""

        if existing_world:
            task_desc = f"""
Based on the following existing world setting and user feedback, revise the world setting.
Keep everything the user didn't mention unchanged, only modify what the feedback requests.

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

Current World Setting:
{json.dumps(existing_world, ensure_ascii=False, indent=2)}
{research_section}
{feedback_section}

Output the revised complete world setting following the format in your instructions.
"""
        else:
            task_desc = f"""
Based on this story seed, create a complete world setting:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}
{research_section}

Output a complete world setting following the format in your instructions.
"""

        from agents.json_utils import run_with_retry

        world = run_with_retry(
            lambda: self._run_agent(task_desc),
            self._extract_world,
            label="WorldbuilderAgent.build_world",
        )
        context.world = world
        return world
