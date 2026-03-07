import json
import re
from crewai import Agent, Task, Crew

from models.story_context import StoryContext


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
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*"passed"[\s\S]*\}', text)
            raw = json_match.group(0) if json_match else None

        if raw:
            data = json.loads(raw)
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

        return str(crew.kickoff())

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

        previous_text = "\n\n".join(context.chapters) if context.chapters else "无"

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
        """Perform full-text final review after all chapters are complete.

        Checks: foreshadowing payoffs, character arcs, atmosphere
        consistency, ending echoes opening.
        """
        world_dict = context.world.model_dump() if context.world else {}
        outline_dict = [ch.model_dump() for ch in context.outline]

        full_text = "\n\n".join(
            f"第{i+1}章: {context.outline[i].title}\n{text}"
            for i, text in enumerate(context.chapters)
        )

        task_description = f"""
Perform a FINAL full-text review of the complete story.

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Outline:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

Full Text:
{full_text}

Check the following specifically:
1. 所有伏笔是否都已回收
2. 所有角色弧线是否完整
3. 整体氛围是否连贯一致
4. 结局是否呼应开篇

Provide a complete review following the format in your instructions.
"""

        result = self._run_agent(task_description)
        review = self._extract_review(result)

        context.review_notes.append(
            f"FINAL REVIEW: {'PASS' if review.passed else 'NEEDS_REVISION'}"
        )

        return review
