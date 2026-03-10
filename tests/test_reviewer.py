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


def test_review_includes_key_beats_check():
    """Reviewer task_desc should include key_beats check items."""
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
            key_beats=["发现古籍", "与馆长对话"],
        )
    ]

    mock_result = (
        '```json\n{"passed": true, "issues": [], "strengths": [], "overall_assessment": "ok"}\n```'
    )

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        agent.review_chapter(context, chapter_number=1, chapter_text="测试文本")

    task_desc = mock_run.call_args[0][0]
    assert "发现古籍" in task_desc
    assert "与馆长对话" in task_desc
    assert "key beat" in task_desc


def test_review_includes_previous_ending():
    """Non-first chapter review should include previous chapter ending."""
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.chapter_endings = ["上一章末尾文本"]
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=1000),
        ChapterOutline(number=2, title="深入", summary="深入", mood="紧张", word_target=1000),
    ]

    mock_result = (
        '```json\n{"passed": true, "issues": [], "strengths": [], "overall_assessment": "ok"}\n```'
    )

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        agent.review_chapter(context, chapter_number=2, chapter_text="测试文本")

    task_desc = mock_run.call_args[0][0]
    assert "上一章末尾文本" in task_desc
    assert "Previous Chapter Ending" in task_desc


def test_review_includes_transition_check():
    """Non-first chapter review should include transition check."""
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=1000),
        ChapterOutline(number=2, title="深入", summary="深入", mood="紧张", word_target=1000),
    ]

    mock_result = (
        '```json\n{"passed": true, "issues": [], "strengths": [], "overall_assessment": "ok"}\n```'
    )

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        agent.review_chapter(context, chapter_number=2, chapter_text="测试文本")

    task_desc = mock_run.call_args[0][0]
    assert "naturally connect" in task_desc
    assert "scene continuity" in task_desc
