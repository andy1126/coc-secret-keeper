from unittest.mock import Mock, patch
from agents.researcher import ResearcherAgent
from models.story_context import StoryContext
from models.schemas import ResearchQuestion, ResearchNote


def test_researcher_creation():
    agent = ResearcherAgent(llm=Mock())
    assert agent is not None


def test_research():
    agent = ResearcherAgent(llm=Mock())
    context = StoryContext(
        seed={"theme": "调查", "era": "1920年代"},
        research_questions=[
            ResearchQuestion(topic="genre", question="调查类克苏鲁的经典模式？"),
            ResearchQuestion(topic="psychology", question="面对恐惧的心理反应？"),
        ],
    )

    mock_result = """
```json
{
  "notes": [
    {
      "topic": "genre",
      "findings": "经典模式包括：渐进揭示、不可靠叙述者、知识即诅咒",
      "sources": ["《克苏鲁的呼唤》", "《敦威治恐怖事件》"]
    },
    {
      "topic": "psychology",
      "findings": "恐惧反应三阶段：否认、恐慌、解离",
      "sources": ["恐惧心理学研究"]
    }
  ]
}
```
"""
    with patch.object(agent, "_run_agent", return_value=mock_result):
        notes = agent.research(context)

    assert len(notes) == 2
    assert isinstance(notes[0], ResearchNote)
    assert notes[0].topic == "genre"
    assert len(context.research_notes) == 2
