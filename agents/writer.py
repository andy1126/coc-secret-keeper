import json
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ChapterOutline


class WriterAgent:
    """Agent for writing chapter content."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/writer.md", "r", encoding="utf-8") as f:
            return f.read()

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

        return str(crew.kickoff())

    def write_chapter(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
    ) -> str:
        """Write a single chapter."""
        world_dict = context.world.model_dump() if context.world else {}
        outline_dict = chapter.model_dump()

        previous_chapters = "\n\n".join(
            f"Chapter {i+1}:\n{text}"
            for i, text in enumerate(context.chapters)
        ) if context.chapters else "无"

        task_desc = f"""
Write chapter {chapter.number}: "{chapter.title}"

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Chapter Outline:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

Previous Chapters Summary:
{previous_chapters}

Write the chapter content in Chinese. Target word count: {chapter.word_target}.
Maintain the mood: {chapter.mood}.
Include foreshadowing: {chapter.foreshadowing}
Include payoffs: {chapter.payoffs}
"""

        result = self._run_agent(task_desc)
        context.chapters.append(result)
        return result

    def revise_chapter(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
        chapter_text: str,
        issues: list[dict],
    ) -> str:
        """Revise a chapter based on review feedback."""
        issues_desc = "\n".join(
            f"- [{i['category']}] {i['description']} → 建议: {i['suggestion']}"
            for i in issues
        )

        task_desc = f"""
Revise chapter {chapter.number}: "{chapter.title}"

Original text:
{chapter_text}

Issues to fix:
{issues_desc}

Rewrite the chapter fixing all listed issues while maintaining the same story flow.
Output the complete revised chapter in Chinese.
"""

        result = self._run_agent(task_desc)
        # Replace the chapter in context
        idx = chapter.number - 1
        if idx < len(context.chapters):
            context.chapters[idx] = result
        return result
