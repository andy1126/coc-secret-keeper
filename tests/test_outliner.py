from unittest.mock import Mock, patch
from agents.outliner import OutlinerAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline


def test_outliner_creation():
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    assert agent is not None


def test_create_outline():
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查", "atmosphere": "悬疑"}
    context.world = None  # Would have world data

    mock_result = """
```json
{
  "chapters": [
    {"number": 1, "title": "神秘来信", "summary": "主角收到奇怪的信", "mood": "悬疑", "word_target": 3000, "foreshadowing": ["信上的符号"], "payoffs": []}
  ],
  "total_word_estimate": 25000,
  "narrative_arc": "渐进式恐怖"
}
```
"""

    with patch.object(agent, "_run_agent", return_value=mock_result):
        outline = agent.create_outline(context, target_chapters=6)

    assert len(outline) == 1
    assert isinstance(outline[0], ChapterOutline)
