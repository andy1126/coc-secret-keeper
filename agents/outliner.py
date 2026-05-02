from __future__ import annotations

import json
import logging

from crewai import Agent, Task, Crew, LLM

from models.story_context import StoryContext
from models.schemas import ChapterOutline, ConflictDesign

logger = logging.getLogger("coc.llm")


class OutlinerAgent:
    """Agent for creating story outlines — one chapter per LLM call."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        from agents.prompt_loader import load_prompt_with_skills

        return load_prompt_with_skills("prompts/outliner.md", "outliner")

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

    @staticmethod
    def _get_zone_for_chapter(chapter_num: int, total_chapters: int) -> str:
        """Determine which narrative zone a chapter belongs to based on position."""
        ratio = chapter_num / total_chapters
        if ratio <= 0.25:
            return "setup"
        elif ratio <= 0.85:
            return "crucible"
        else:
            return "aftermath"

    @staticmethod
    def _get_position_guidance(zone: str) -> str:
        """Return Chinese-language guidance for a chapter based on its narrative zone."""
        guidance = {
            "setup": (
                "铺垫区指导：本章处于故事开篇阶段。建立世界观氛围和时代基调，"
                "引入主要角色及其初始状态，埋设关键伏笔和核心悬念。"
                "展示角色日常生活以建立读者情感连接，暗示暗流涌动但尚未爆发。"
            ),
            "crucible": (
                "熔炉区指导：本章处于故事中段冲突升级阶段。逐步升级紧张感和危机，"
                "分层揭示信息但保留核心秘密，推进多条冲突线索的交织。"
                "设置转折点或反转（如适用），角色面临关键选择展示性格弧线。"
            ),
            "aftermath": (
                "余波区指导：本章处于故事尾声收束阶段。推向高潮和解决，"
                "回收主要伏笔，完成角色弧线转变，揭示核心真相。"
                "留下适当的余韵和不确定性，呼应开篇形成结构闭环。"
            ),
        }
        return guidance.get(zone, "")

    def _extract_single_chapter(self, text: str) -> ChapterOutline:
        """Extract a single ChapterOutline from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)
        if not data:
            raise ValueError("Could not extract JSON from response")

        # Prefer old-style {"chapters": [{...}]} as fallback
        if "chapters" in data and isinstance(data["chapters"], list) and data["chapters"]:
            return ChapterOutline(**data["chapters"][0])

        return ChapterOutline(**data)

    def _build_chapter_task_desc(
        self,
        *,
        seed: dict[str, object],
        world_dict: dict[str, object],
        conflict_section: str,
        chapter_num: int,
        target_chapters: int,
        zone: str,
        previous_chapters_json: str,
        feedback_section: str,
        original_chapter: ChapterOutline | None,
    ) -> str:
        """Build the task description for a single chapter generation call."""
        position_guidance = self._get_position_guidance(zone)

        zone_names = {"setup": "铺垫区", "crucible": "熔炉区", "aftermath": "余波区"}
        zone_name = zone_names.get(zone, zone)

        previous_display = previous_chapters_json if previous_chapters_json else "无（这是第一章）"

        original_section = ""
        if original_chapter is not None:
            original_json = json.dumps(original_chapter.model_dump(), ensure_ascii=False, indent=2)
            original_section = f"""
本章原始大纲（对比参考，根据反馈选择性修改）:
{original_json}
"""

        return f"""生成第 {chapter_num} 章的大纲（共 {target_chapters} 章）
叙事区域: {zone_name}

{position_guidance}

故事种子:
{json.dumps(seed, ensure_ascii=False, indent=2)}

世界观设定:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}
{conflict_section}

已生成的前文章节:
{previous_display}
{original_section}
{feedback_section}

请输出第 {chapter_num} 章的单个 ChapterOutline JSON 对象（不要包在数组中），严格遵循你 system prompt 中的输出格式。number 字段必须为 {chapter_num}。
"""

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
        """Create chapter outline — one chapter per LLM call."""
        world_dict = context.world.model_dump() if context.world else {}

        conflict_section = ""
        if context.conflict_design:
            conflict_section = f"""
冲突设计（按三区结构安排章节，注意冲突线索交织），根据内容取章节标题:
{self._format_conflict_for_prompt(context.conflict_design)}
"""

        feedback_section = (
            f"\n\n用户反馈（请考虑以下反馈修改本章）:\n{feedback}" if feedback else ""
        )

        outline: list[ChapterOutline] = []

        for chapter_num in range(1, target_chapters + 1):
            zone = self._get_zone_for_chapter(chapter_num, target_chapters)

            previous_json = json.dumps(
                [c.model_dump() for c in outline], ensure_ascii=False, indent=2
            )

            original_chapter = None
            if feedback and context.outline and chapter_num <= len(context.outline):
                original_chapter = context.outline[chapter_num - 1]

            task_desc = self._build_chapter_task_desc(
                seed=context.seed,
                world_dict=world_dict,
                conflict_section=conflict_section,
                chapter_num=chapter_num,
                target_chapters=target_chapters,
                zone=zone,
                previous_chapters_json=previous_json,
                feedback_section=feedback_section,
                original_chapter=original_chapter,
            )

            from agents.json_utils import run_with_retry

            chapter = run_with_retry(
                lambda: self._run_agent(task_desc),
                self._extract_single_chapter,
                label=f"OutlinerAgent-ch{chapter_num}",
            )

            # Enforce correct chapter number (LLM might output wrong one)
            chapter.number = chapter_num
            outline.append(chapter)
            logger.info(
                "OutlinerAgent: chapter %d/%d done — %s",
                chapter_num,
                target_chapters,
                chapter.title,
            )

        context.outline = outline
        return outline
