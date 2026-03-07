import json
import logging
from crewai import LLM

from models.story_context import StoryContext

logger = logging.getLogger("coc.llm")


class BrainstormAgent:
    """Brainstorm agent for collecting story seeds through conversation.

    NOTE: This agent uses direct LLM calls instead of CrewAI Agent/Task/Crew
    because brainstorming requires multi-turn conversation with history.
    CrewAI Crews are designed for one-shot task execution and would lose
    conversation context between turns.
    """

    def __init__(self, llm: LLM):
        self.llm = llm
        self.prompt = self._load_prompt()
        self.conversation_history: list[dict[str, str]] = []

    def _load_prompt(self) -> str:
        with open("prompts/brainstorm.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_seed(self, text: str) -> dict:
        """Extract JSON seed from agent response."""
        from agents.json_utils import extract_json_object

        return extract_json_object(text) or {}

    def chat(self, user_input: str, context: StoryContext) -> str:
        """Process user input and return agent response.

        Uses direct LLM.call() to maintain multi-turn conversation history.
        """
        self.conversation_history.append({"role": "user", "content": user_input})

        messages = [
            {"role": "system", "content": self.prompt},
            *self.conversation_history,
            {
                "role": "user",
                "content": f"\n\n当前已收集的故事种子: {json.dumps(context.seed, ensure_ascii=False)}",
            },
        ]

        logger.info("BrainstormAgent.chat: calling LLM with %d messages", len(messages))
        result_text = self.llm.call(messages=messages)
        logger.info("BrainstormAgent.chat: received response (%d chars)", len(result_text))

        self.conversation_history.append({"role": "assistant", "content": result_text})

        # Try to extract seed if JSON is present
        seed = self._extract_seed(result_text)
        if seed:
            context.seed.update(seed)

        return result_text

    def is_complete(self, context: StoryContext) -> bool:
        """Check if enough information has been gathered."""
        required = ["theme", "era", "atmosphere", "protagonist"]
        return all(k in context.seed for k in required)
