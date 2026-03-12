import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ChapterOutline, ConflictDesign

logger = logging.getLogger("coc.llm")


class OutlinerAgent:
    """Agent for creating story outlines."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/outliner.md", "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _format_conflict_for_prompt(conflict: ConflictDesign) -> str:
        """Format conflict design as human-readable text for LLM consumption."""
        lines = [f"叙事策略: {conflict.narrative_strategy}"]
        lines.append(f"主题贯穿线: {conflict.thematic_throughline}")
        lines.append(f"张力曲线: {conflict.tension_shape}")
        lines.append("")
        lines.append("冲突线索:")
        for t in conflict.threads:
            lines.append(f"  - {t.name} ({t.thread_type}): {t.description} [风险: {t.stakes}]")
        lines.append("")
        zone_labels = {"setup": "铺垫区", "crucible": "熔炉区", "aftermath": "余波区"}
        for zone_key in ("setup", "crucible", "aftermath"):
            lines.append(f"【{zone_labels[zone_key]}】")
            for beat in conflict.beats:
                if beat.zone == zone_key:
                    thread_tags = ", ".join(beat.threads)
                    lines.append(f"  · {beat.name}: {beat.description} → [{thread_tags}]")
        return "\n".join(lines)

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

        feedback_section = (
            f"""

用户反馈（请根据以下反馈修改大纲）:
{feedback}
"""
            if feedback
            else ""
        )

        existing_outline = (
            [c.model_dump() for c in context.outline] if context.outline and feedback else None
        )

        conflict_section = ""
        if context.conflict_design:
            conflict_section = f"""
冲突设计（按三区结构安排章节，注意冲突线索交织），根据内容取章节标题:
{self._format_conflict_for_prompt(context.conflict_design)}
"""

        if existing_outline:
            task_desc = f"""
Based on the following existing outline and user feedback, revise the outline.
Keep everything the user didn't mention unchanged, only modify what the feedback requests.

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}
{conflict_section}

Current Outline:
{json.dumps(existing_outline, ensure_ascii=False, indent=2)}

{feedback_section}

Target number of chapters: {target_chapters}

Output the revised complete outline following the format in your instructions.
"""
        else:
            task_desc = f"""
Create a story outline based on:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}
{conflict_section}

Target number of chapters: {target_chapters}

Output a complete outline following the format in your instructions.
"""

        from agents.json_utils import run_with_retry

        outline = run_with_retry(
            lambda: self._run_agent(task_desc),
            self._extract_outline,
            label="OutlinerAgent",
        )
        context.outline = outline
        return outline
