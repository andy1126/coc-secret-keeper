import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext

logger = logging.getLogger("coc.llm")


class ReviewResult:
    """Review result with issues classification."""

    def __init__(self, data: dict):
        self.passed = data.get("passed", False)
        self.issues = data.get("issues", [])
        self.strengths = data.get("strengths", [])
        self.overall_assessment = data.get("overall_assessment", "")

    def get_minor_issues(self) -> list[dict]:
        return [i for i in self.issues if i.get("severity") == "minor"]

    def get_major_issues(self) -> list[dict]:
        return [i for i in self.issues if i.get("severity") == "major"]


class ReviewerAgent:
    """Agent for reviewing chapter quality."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/reviewer.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_review(self, text: str) -> ReviewResult:
        """Extract review result from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)

        if data:
            return ReviewResult(data)

        raise ValueError("Could not extract review from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Reviewer",
            goal="Review story quality and identify issues",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted review",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("ReviewerAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("ReviewerAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def review_chapter(
        self,
        context: StoryContext,
        chapter_number: int,
        chapter_text: str,
    ) -> ReviewResult:
        """Review a chapter and classify issues."""
        world_dict = context.world.model_dump() if context.world else {}

        # Get outline for this chapter
        chapter_outline = None
        if context.outline and chapter_number <= len(context.outline):
            chapter_outline = context.outline[chapter_number - 1].model_dump()

        previous_text = (
            "\n\n".join(
                f"第{i+1}章摘要:\n{summary}" for i, summary in enumerate(context.chapter_summaries)
            )
            if context.chapter_summaries
            else "无"
        )

        task_desc = f"""
Review chapter {chapter_number}.

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Chapter Outline:
{json.dumps(chapter_outline, ensure_ascii=False, indent=2) if chapter_outline else "N/A"}

Previous Chapters:
{previous_text}

Chapter to Review:
{chapter_text}

IMPORTANT: Check for completeness issues:
1. Does the chapter cover ALL plot points in the outline summary?
2. Are all foreshadowing/payoff items from the outline addressed?
3. Is the text complete -- does it end with a proper sentence, or truncated mid-sentence?
If truncated or missing outline content, report as category "completeness" with severity "major".

Provide a complete review following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        review = self._extract_review(result)

        # Record review
        context.review_notes.append(
            f"Chapter {chapter_number}: {'PASS' if review.passed else 'NEEDS_REVISION'}"
        )

        return review

    def final_review(self, context: StoryContext) -> ReviewResult:
        """Perform summary-based macro review after all chapters are complete.

        Checks: foreshadowing payoffs, character arcs, atmosphere
        consistency, ending echoes opening. Uses chapter summaries
        instead of full text since per-chapter reviews already handled details.
        """
        if len(context.chapter_summaries) != len(context.chapters):
            raise ValueError(
                f"chapter_summaries ({len(context.chapter_summaries)}) "
                f"!= chapters ({len(context.chapters)}): "
                "all chapters must be summarized before final review"
            )

        world_dict = context.world.model_dump() if context.world else {}
        outline_dict = [ch.model_dump() for ch in context.outline]

        summaries_text = "\n\n".join(
            f"第{i+1}章「{context.outline[i].title}」摘要:\n{summary}"
            for i, summary in enumerate(context.chapter_summaries)
        )

        task_description = f"""
对完整故事进行终审（宏观审查）。

世界观设定:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

大纲:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

各章摘要:
{summaries_text}

请只检查以下宏观问题：
1. 所有伏笔是否都已回收——对照大纲中的 foreshadowing/payoffs 列表逐一核实
2. 所有角色弧线是否完整——每个角色是否走完了大纲规划的弧线
3. 整体氛围是否连贯一致——各章情绪基调是否符合大纲 mood 并形成递进
4. 结局是否呼应开篇——首尾是否形成呼应

请不要检查措辞、语法或单段落的氛围细节——这些已在逐章审核中处理。

Provide a complete review following the format in your instructions.
"""

        result = self._run_agent(task_description)
        review = self._extract_review(result)

        context.review_notes.append(
            f"FINAL REVIEW: {'PASS' if review.passed else 'NEEDS_REVISION'}"
        )

        return review
