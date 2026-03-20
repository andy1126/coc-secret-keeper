from __future__ import annotations

import json
import logging
from collections.abc import Generator
from typing import Any

import litellm
from crewai import Agent, Task, Crew, LLM

from models.story_context import StoryContext
from models.schemas import ChapterOutline

logger = logging.getLogger("coc.llm")


class WriterAgent:
    """Agent for writing chapter content."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        from agents.prompt_loader import load_prompt_with_skills

        return load_prompt_with_skills("prompts/writer.md", "writer")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Writer",
            goal="Write compelling Cthulhu fiction",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="Chapter content in Chinese",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("WriterAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("WriterAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def _build_write_task_desc(self, context: StoryContext, chapter: ChapterOutline) -> str:
        """Build the task description for writing a chapter."""
        world_dict = context.world.model_dump() if context.world else {}
        outline_dict = chapter.model_dump()

        previous_chapters = (
            "\n\n".join(
                f"第{i+1}章摘要:\n{summary}" for i, summary in enumerate(context.chapter_summaries)
            )
            if context.chapter_summaries
            else "无"
        )

        beats_checklist = ""
        if chapter.key_beats:
            beats_list = "\n".join(f"  {i+1}. {beat}" for i, beat in enumerate(chapter.key_beats))
            beats_checklist = f"""
Key Beats Checklist (MUST cover ALL of these in order):
{beats_list}
"""

        next_chapter_info = "这是最后一章，请确保给出合适的结局。"
        if chapter.number < len(context.outline):
            next_ch = context.outline[chapter.number]
            next_chapter_info = (
                f"下一章：第{next_ch.number}章「{next_ch.title}」\n"
                f"情绪基调：{next_ch.mood}\n"
                f"摘要：{next_ch.summary}"
            )

        previous_ending = "无（这是第一章）"
        if context.chapter_endings:
            previous_ending = context.chapter_endings[-1]

        writing_style = context.seed.get("writing_style", {})
        style_block = ""
        if writing_style:
            lines = []
            if writing_style.get("style"):
                lines.append(f"- 文风: {writing_style['style']}")
            if writing_style.get("narration"):
                lines.append(f"- 叙事方式: {writing_style['narration']}")
            if writing_style.get("writing_style_notes"):
                lines.append(f"- 补充要求: {writing_style['writing_style_notes']}")
            if lines:
                style_block = (
                    "\nWriting Style Requirements:\n"
                    + "\n".join(lines)
                    + "\n\nYou MUST write in this style throughout the chapter.\n"
                )

        return f"""
Write chapter {chapter.number}: "{chapter.title}"

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}
{style_block}
Chapter Outline:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

Previous Chapters Summary:
{previous_chapters}

Previous Chapter Ending (last 500 chars):
{previous_ending}

The opening of this chapter must naturally continue from the above ending.
{beats_checklist}
Next Chapter Preview:
{next_chapter_info}

Ensure the chapter ending naturally sets up the transition to the next chapter.

Write the chapter content in Chinese. Target word count: {chapter.word_target}.
Maintain the mood: {chapter.mood}.
Include foreshadowing: {chapter.foreshadowing}
Include payoffs: {chapter.payoffs}

IMPORTANT: You MUST cover every key beat listed above. Do not conclude the chapter
until all beats have been addressed. Check this list before writing your ending.
"""

    def _build_revise_task_desc(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
        chapter_text: str,
        issues: list[dict[str, Any]],
    ) -> str:
        """Build the task description for revising a chapter."""
        issues_desc = "\n".join(
            f"- [{i['category']}] {i['description']} → 建议: {i['suggestion']}" for i in issues
        )

        writing_style = context.seed.get("writing_style", {})
        style_reminder = ""
        if writing_style:
            parts = []
            if writing_style.get("style"):
                parts.append(writing_style["style"])
            if writing_style.get("narration"):
                parts.append(writing_style["narration"])
            if writing_style.get("writing_style_notes"):
                parts.append(writing_style["writing_style_notes"])
            if parts:
                style_reminder = f"\nRemember to maintain the writing style: {', '.join(parts)}\n"

        return f"""
Revise chapter {chapter.number}: "{chapter.title}"

Original text:
{chapter_text}

Issues to fix:
{issues_desc}

Rewrite the chapter fixing all listed issues while maintaining the same story flow.
{style_reminder}Output the complete revised chapter in Chinese.
"""

    def write_chapter(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
    ) -> str:
        """Write a single chapter."""
        task_desc = self._build_write_task_desc(context, chapter)

        result = self._run_agent(task_desc)
        idx = chapter.number - 1
        if idx < len(context.chapters):
            # Chapter slot already exists (e.g. retry / re-generation) — replace
            context.chapters[idx] = result
        else:
            context.chapters.append(result)
        if idx < len(context.chapter_endings):
            context.chapter_endings[idx] = result[-500:] if len(result) > 500 else result
        else:
            context.chapter_endings.append(result[-500:] if len(result) > 500 else result)
        return result

    def summarize_chapter(self, chapter: ChapterOutline, chapter_text: str) -> str:
        """Generate a 200-300 word Chinese summary for a completed chapter."""
        task_desc = f"""
为第{chapter.number}章「{chapter.title}」撰写一段200-300字的中文摘要。

章节正文：
{chapter_text}

摘要需涵盖：
1. 主要情节推进（发生了什么关键事件）
2. 角色状态变化（心理、关系、处境）
3. 伏笔与回收（本章埋设或回收了哪些线索）
4. 结尾状态（章末人物/局面停留在什么状态）

只输出摘要文本，不要加标题或额外格式。
"""
        return self._run_agent(task_desc)

    def revise_chapter(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
        chapter_text: str,
        issues: list[dict[str, Any]],
    ) -> str:
        """Revise a chapter based on review feedback."""
        task_desc = self._build_revise_task_desc(context, chapter, chapter_text, issues)

        result = self._run_agent(task_desc)
        # Replace the chapter in context
        idx = chapter.number - 1
        if idx < len(context.chapters):
            context.chapters[idx] = result
        # Update chapter ending to match revised content
        if idx < len(context.chapter_endings):
            ending = result[-500:] if len(result) > 500 else result
            context.chapter_endings[idx] = ending
        return result

    # -- Streaming variants (bypass CrewAI, use litellm directly) --

    def write_chapter_stream(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
        litellm_params: dict[str, Any],
    ) -> Generator[str, None, None]:
        """Stream chapter writing token-by-token via litellm.

        Yields content chunks. Caller must pass the accumulated full response
        to finalize_write_chapter() after iteration completes.
        """
        task_desc = self._build_write_task_desc(context, chapter)
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": task_desc},
        ]

        logger.info("WriterAgent.write_chapter_stream: calling litellm (ch %d)", chapter.number)
        response = litellm.completion(messages=messages, **litellm_params)
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    def finalize_write_chapter(
        self, full_response: str, context: StoryContext, chapter: ChapterOutline
    ) -> None:
        """Update context after streaming write completes."""
        logger.info(
            "WriterAgent.finalize_write_chapter: ch %d (%d chars)",
            chapter.number,
            len(full_response),
        )
        idx = chapter.number - 1
        if idx < len(context.chapters):
            context.chapters[idx] = full_response
        else:
            context.chapters.append(full_response)
        ending = full_response[-500:] if len(full_response) > 500 else full_response
        if idx < len(context.chapter_endings):
            context.chapter_endings[idx] = ending
        else:
            context.chapter_endings.append(ending)

    def revise_chapter_stream(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
        chapter_text: str,
        issues: list[dict[str, Any]],
        litellm_params: dict[str, Any],
    ) -> Generator[str, None, None]:
        """Stream chapter revision token-by-token via litellm.

        Yields content chunks. Caller must pass the accumulated full response
        to finalize_revise_chapter() after iteration completes.
        """
        task_desc = self._build_revise_task_desc(context, chapter, chapter_text, issues)
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": task_desc},
        ]

        logger.info("WriterAgent.revise_chapter_stream: calling litellm (ch %d)", chapter.number)
        response = litellm.completion(messages=messages, **litellm_params)
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    def finalize_revise_chapter(
        self, full_response: str, context: StoryContext, chapter: ChapterOutline
    ) -> None:
        """Update context after streaming revision completes."""
        logger.info(
            "WriterAgent.finalize_revise_chapter: ch %d (%d chars)",
            chapter.number,
            len(full_response),
        )
        idx = chapter.number - 1
        if idx < len(context.chapters):
            context.chapters[idx] = full_response
        if idx < len(context.chapter_endings):
            ending = full_response[-500:] if len(full_response) > 500 else full_response
            context.chapter_endings[idx] = ending
