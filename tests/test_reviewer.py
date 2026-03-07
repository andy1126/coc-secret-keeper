from unittest.mock import Mock, patch
from agents.reviewer import ReviewerAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline

import pytest


def test_reviewer_creation():
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)
    assert agent is not None


def test_review_chapter():
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.chapter_summaries = ["前一章的摘要内容"]
    context.outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="开始",
            mood="悬疑",
            word_target=1000,
            foreshadowing=[],
            payoffs=[],
        )
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

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        result = agent.review_chapter(context, chapter_number=1, chapter_text="测试文本")

    assert not result.passed
    assert len(result.issues) == 1
    assert result.issues[0]["severity"] == "minor"
    assert len(result.get_minor_issues()) == 1
    assert len(result.get_major_issues()) == 0

    # Verify task description uses summaries
    task_desc = mock_run.call_args[0][0]
    assert "前一章的摘要内容" in task_desc
    assert "摘要:" in task_desc


def test_review_completeness_issue():
    """Reviewer should detect completeness issues as major."""
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="开始",
            mood="悬疑",
            word_target=1000,
            foreshadowing=["古老符号"],
            payoffs=[],
        )
    ]

    mock_result = """
```json
{
  "passed": false,
  "issues": [
    {
      "category": "completeness",
      "severity": "major",
      "description": "章节在句中截断，未完成",
      "suggestion": "补全章节结尾"
    }
  ],
  "strengths": [],
  "overall_assessment": "章节不完整"
}
```
"""

    with patch.object(agent, "_run_agent", return_value=mock_result):
        result = agent.review_chapter(context, chapter_number=1, chapter_text="截断的文本...")

    assert not result.passed
    assert len(result.get_major_issues()) == 1
    assert result.get_major_issues()[0]["category"] == "completeness"


def test_final_review_uses_summaries():
    """Final review should use chapter_summaries, not full text."""
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = None
    context.outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="开始",
            mood="悬疑",
            word_target=1000,
            foreshadowing=[],
            payoffs=[],
        )
    ]
    context.chapters = ["很长的全文内容"]
    context.chapter_summaries = ["简短摘要"]

    mock_result = """
```json
{
  "passed": true,
  "issues": [],
  "strengths": ["故事完整"],
  "overall_assessment": "通过"
}
```
"""

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        result = agent.final_review(context)

    assert result.passed
    task_desc = mock_run.call_args[0][0]
    assert "简短摘要" in task_desc
    assert "很长的全文内容" not in task_desc
    assert "宏观" in task_desc


def test_final_review_guard_mismatch():
    """Final review should raise ValueError when summaries/chapters mismatch."""
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.chapters = ["chapter 1", "chapter 2"]
    context.chapter_summaries = ["summary 1"]  # mismatch
    context.outline = []

    with pytest.raises(ValueError, match="chapter_summaries"):
        agent.final_review(context)
