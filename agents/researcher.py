import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ResearchNote

logger = logging.getLogger("coc.llm")


class ResearcherAgent:
    """Agent for systematic LLM-based research across multiple dimensions."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        from agents.prompt_loader import load_prompt_with_skills

        return load_prompt_with_skills("prompts/researcher.md", "researcher")

    def _extract_notes(self, text: str) -> list[ResearchNote]:
        """Extract research notes from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)
        if data:
            return [ResearchNote(**n) for n in data.get("notes", [])]
        raise ValueError("Could not extract research notes from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Researcher",
            goal="Systematically research creative material for story design",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted research notes",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("ResearcherAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("ResearcherAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def research(self, context: StoryContext) -> list[ResearchNote]:
        """Answer research questions with structured findings."""
        questions_text = "\n".join(
            f"- [{q.topic}] {q.question}" for q in context.research_questions
        )

        task_desc = f"""
基于以下故事种子和研究问题，进行系统性研究。

故事种子:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

研究问题:
{questions_text}

请针对每个问题提供结构化的研究发现，包括具体的文学作品、心理学理论、历史事实或戏剧技巧作为参考。

输出JSON格式:
```json
{{
  "notes": [
    {{
      "topic": "对应的研究主题",
      "findings": "详细的研究发现",
      "sources": ["参考来源1", "参考来源2"]
    }}
  ]
}}
```
"""
        from agents.json_utils import run_with_retry

        notes = run_with_retry(
            lambda: self._run_agent(task_desc),
            self._extract_notes,
            label="ResearcherAgent",
        )
        context.research_notes = notes
        return notes
