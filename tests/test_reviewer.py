import pytest
from unittest.mock import Mock, patch
from agents.reviewer import ReviewerAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline


def test_reviewer_creation():
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)
    assert agent is not None


def test_review_chapter():
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=1000, foreshadowing=[], payoffs=[])
    ]

    mock_result = """
```json
{
  "passed": false,
  "issues": [
    {"category": "atmosphere", "severity": "minor", "description": "氛围不够", "suggestion": "加强感官描写"}
  ],
  "strengths": ["情节推进好"],
  "overall_assessment": "基本合格，需要小修"
}
```
"""

    with patch.object(agent, '_run_agent', return_value=mock_result):
        result = agent.review_chapter(context, chapter_number=1, chapter_text="测试文本")

    assert not result.passed
    assert len(result.issues) == 1
    assert result.issues[0]["severity"] == "minor"
    assert len(result.get_minor_issues()) == 1
    assert len(result.get_major_issues()) == 0
