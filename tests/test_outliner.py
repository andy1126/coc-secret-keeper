"""Tests for OutlinerAgent with incremental per-chapter generation."""

import pytest
from unittest.mock import Mock, patch

from agents.outliner import OutlinerAgent
from models.story_context import StoryContext
from models.schemas import (
    ChapterOutline,
    ConflictDesign,
    ConflictThread,
    DramaticBeat,
    WorldSetting,
    Location,
    Entity,
    Character,
)


def _make_single_chapter_json(number: int) -> str:
    """Build a valid single-chapter JSON response."""
    return f"""
```json
{{
  "number": {number},
  "title": "第{number}章标题",
  "summary": "章节摘要",
  "mood": "悬疑",
  "word_target": 3000,
  "foreshadowing": ["伏笔{number}"],
  "payoffs": [],
  "pov": "主角",
  "information_reveal": ["信息{number}"],
  "twist": null,
  "subplot": null,
  "key_beats": ["事件{number}a", "事件{number}b", "事件{number}c"]
}}
```
"""


# ── Zone determination ────────────────────────────────────────────────


def test_get_zone_for_chapter_setup() -> None:
    assert OutlinerAgent._get_zone_for_chapter(1, 10) == "setup"
    assert OutlinerAgent._get_zone_for_chapter(2, 10) == "setup"  # 2/10 = 0.2 ≤ 0.25


def test_get_zone_for_chapter_crucible() -> None:
    assert OutlinerAgent._get_zone_for_chapter(3, 10) == "crucible"  # 0.3
    assert OutlinerAgent._get_zone_for_chapter(8, 10) == "crucible"  # 0.8


def test_get_zone_for_chapter_aftermath() -> None:
    assert OutlinerAgent._get_zone_for_chapter(9, 10) == "aftermath"  # 0.9
    assert OutlinerAgent._get_zone_for_chapter(10, 10) == "aftermath"  # 1.0


def test_get_zone_for_chapter_single_chapter() -> None:
    """Chapter 1 of 1 falls into aftermath (ratio=1.0 > 0.85)."""
    assert OutlinerAgent._get_zone_for_chapter(1, 1) == "aftermath"


# ── Position guidance ──────────────────────────────────────────────────


def test_get_position_guidance_setup() -> None:
    guidance = OutlinerAgent._get_position_guidance("setup")
    assert "铺垫区" in guidance
    assert "开篇" in guidance


def test_get_position_guidance_crucible() -> None:
    guidance = OutlinerAgent._get_position_guidance("crucible")
    assert "熔炉区" in guidance


def test_get_position_guidance_aftermath() -> None:
    guidance = OutlinerAgent._get_position_guidance("aftermath")
    assert "余波区" in guidance


def test_get_position_guidance_unknown() -> None:
    assert OutlinerAgent._get_position_guidance("nonexistent") == ""


# ── Extraction ─────────────────────────────────────────────────────────


def test_extract_single_chapter_valid() -> None:
    agent = OutlinerAgent(llm=Mock())
    json_str = """```json
{"number": 1, "title": "测试", "summary": "摘要", "mood": "悬疑", "word_target": 3000}
```"""
    chapter = agent._extract_single_chapter(json_str)
    assert isinstance(chapter, ChapterOutline)
    assert chapter.number == 1
    assert chapter.title == "测试"


def test_extract_single_chapter_fallback_from_array() -> None:
    """Old-style {"chapters": [{...}]} should still work."""
    agent = OutlinerAgent(llm=Mock())
    json_str = """```json
{"chapters": [{"number": 1, "title": "测试", "summary": "摘要", "mood": "悬疑", "word_target": 3000}]}
```"""
    chapter = agent._extract_single_chapter(json_str)
    assert isinstance(chapter, ChapterOutline)
    assert chapter.number == 1


def test_extract_single_chapter_invalid() -> None:
    agent = OutlinerAgent(llm=Mock())
    with pytest.raises(ValueError, match="Could not extract JSON"):
        agent._extract_single_chapter("no json here at all")


def test_extract_single_chapter_invalid_json_structure() -> None:
    """Valid JSON but not matching ChapterOutline schema."""
    agent = OutlinerAgent(llm=Mock())
    with pytest.raises(ValueError):
        agent._extract_single_chapter('{"not_a_chapter": true}')


# ── Creation (fresh) ───────────────────────────────────────────────────


def test_outliner_creation() -> None:
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    assert agent is not None


def test_create_outline_single_chapter() -> None:
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    context = StoryContext()
    context.seed = {"theme": "调查", "atmosphere": "悬疑"}

    mock_result = _make_single_chapter_json(1)

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        outline = agent.create_outline(context, target_chapters=1)

    assert len(outline) == 1
    assert isinstance(outline[0], ChapterOutline)
    assert outline[0].number == 1
    mock_run.assert_called_once()


def test_create_outline_multiple_chapters() -> None:
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    context = StoryContext()
    context.seed = {"theme": "调查", "atmosphere": "悬疑"}

    mock_results = [_make_single_chapter_json(i) for i in range(1, 4)]

    with patch.object(agent, "_run_agent", side_effect=mock_results) as mock_run:
        outline = agent.create_outline(context, target_chapters=3)

    assert len(outline) == 3
    assert mock_run.call_count == 3
    for i, ch in enumerate(outline, 1):
        assert ch.number == i


def test_create_outline_chapter_number_enforcement() -> None:
    """LLM outputs wrong chapter number — it must be corrected to the loop index."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    context = StoryContext()
    context.seed = {"theme": "调查"}

    # LLM outputs number=99 regardless
    def wrong_number_json():
        return '```json\n{"number": 99, "title": "第X章", "summary": "摘要", "mood": "悬疑", "word_target": 3000}\n```'

    with patch.object(agent, "_run_agent", side_effect=[wrong_number_json() for _ in range(3)]):
        outline = agent.create_outline(context, target_chapters=3)

    assert [ch.number for ch in outline] == [1, 2, 3]


def test_create_outline_previous_chapters_in_context() -> None:
    """Later chapters receive previous chapters' data in the task description."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    context = StoryContext()
    context.seed = {"theme": "调查", "atmosphere": "悬疑"}

    mock_results = [
        _make_single_chapter_json(1),
        _make_single_chapter_json(2),
        _make_single_chapter_json(3),
    ]

    with patch.object(agent, "_run_agent", side_effect=mock_results) as mock_run:
        agent.create_outline(context, target_chapters=3)

    # Chapter 2's task should mention chapter 1's title
    ch2_task = mock_run.call_args_list[1][0][0]
    assert "第1章标题" in ch2_task

    # Chapter 3's task should mention chapters 1 and 2
    ch3_task = mock_run.call_args_list[2][0][0]
    assert "第1章标题" in ch3_task
    assert "第2章标题" in ch3_task


def test_create_outline_with_conflict_design() -> None:
    """Conflict design text should appear in per-chapter task descriptions."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext(seed={"theme": "调查", "target_chapters": 10})
    context.world = WorldSetting(
        era="1924",
        locations=[Location(name="图书馆", description="禁书")],
        entities=[Entity(name="奈亚", description="外神", influence="化身")],
        forbidden_knowledge="真相",
        rules=["规则"],
        characters=[
            Character(
                name="李教授",
                background="考古",
                personality="严谨",
                motivation="求知",
                arc="堕落",
                relationships=[],
            )
        ],
    )
    context.conflict_design = ConflictDesign(
        narrative_strategy="逐步揭示",
        threads=[
            ConflictThread(
                name="求知之祸", thread_type="epistemic", description="渴望vs恐惧", stakes="理智"
            ),
            ConflictThread(
                name="邪教操控", thread_type="societal", description="馆长阻止", stakes="生命"
            ),
        ],
        beats=[
            DramaticBeat(
                zone="setup", name="发现笔记", description="发现笔记", threads=["求知之祸"]
            ),
            DramaticBeat(
                zone="crucible",
                name="盟友背叛",
                description="盟友是邪教",
                threads=["求知之祸", "邪教操控"],
            ),
            DramaticBeat(
                zone="crucible",
                name="直面仪式",
                description="直面仪式",
                threads=["求知之祸", "邪教操控"],
            ),
            DramaticBeat(
                zone="aftermath", name="真相掩埋", description="真相掩埋", threads=["求知之祸"]
            ),
        ],
        tension_shape="慢炖型",
        thematic_throughline="知识即诅咒",
    )

    mock_result = _make_single_chapter_json(1)

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        agent.create_outline(context, 1)

    task_desc = mock_run.call_args[0][0]
    assert "冲突" in task_desc or "conflict" in task_desc.lower()


# ── Revision mode ──────────────────────────────────────────────────────


def test_create_outline_revision_mode() -> None:
    """Revision mode: each chapter should receive original outline + feedback."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    # Pre-populate 2 chapters in context.outline
    existing_ch1 = ChapterOutline(
        number=1,
        title="旧标题1",
        summary="旧摘要1",
        mood="悬疑",
        word_target=2000,
        foreshadowing=[],
        payoffs=[],
        key_beats=["旧节拍"],
    )
    existing_ch2 = ChapterOutline(
        number=2,
        title="旧标题2",
        summary="旧摘要2",
        mood="紧张",
        word_target=2500,
        foreshadowing=[],
        payoffs=[],
        key_beats=["旧节拍2"],
    )

    context = StoryContext(seed={"theme": "调查"})
    context.outline = [existing_ch1, existing_ch2]

    mock_results = [
        _make_single_chapter_json(1),
        _make_single_chapter_json(2),
    ]

    with patch.object(agent, "_run_agent", side_effect=mock_results) as mock_run:
        agent.create_outline(context, target_chapters=2, feedback="请修改第1章标题")

    # Both calls should include feedback
    for call_args in mock_run.call_args_list:
        task_desc = call_args[0][0]
        assert "请修改第1章标题" in task_desc

    # Chapter 1 call should include original chapter 1
    ch1_task = mock_run.call_args_list[0][0][0]
    assert "旧标题1" in ch1_task

    # Chapter 2 call should include original chapter 2
    ch2_task = mock_run.call_args_list[1][0][0]
    assert "旧标题2" in ch2_task


def test_create_outline_revision_mode_extra_chapters() -> None:
    """When target_chapters > len(context.outline), extra chapters have no original."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext(seed={"theme": "调查"})
    context.outline = [
        ChapterOutline(
            number=1,
            title="旧标题",
            summary="旧摘要",
            mood="悬疑",
            word_target=2000,
            foreshadowing=[],
            payoffs=[],
            key_beats=["旧"],
        )
    ]

    mock_results = [
        _make_single_chapter_json(1),
        _make_single_chapter_json(2),
        _make_single_chapter_json(3),
    ]

    with patch.object(agent, "_run_agent", side_effect=mock_results):
        outline = agent.create_outline(context, target_chapters=3, feedback="请精简")

    assert len(outline) == 3
    # Should not crash on chapters 2 and 3 (no original chapter)


def test_create_outline_no_feedback_no_original() -> None:
    """Fresh creation with context.outline present but no feedback: no revision mode."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext(seed={"theme": "调查"})
    context.outline = [
        ChapterOutline(
            number=1,
            title="旧标题",
            summary="旧摘要",
            mood="悬疑",
            word_target=2000,
            foreshadowing=[],
            payoffs=[],
            key_beats=["旧"],
        )
    ]

    mock_results = [_make_single_chapter_json(1), _make_single_chapter_json(2)]

    with patch.object(agent, "_run_agent", side_effect=mock_results) as mock_run:
        agent.create_outline(context, target_chapters=2)

    # Without feedback, no original chapter should be included
    ch1_task = mock_run.call_args_list[0][0][0]
    assert "本章原始大纲" not in ch1_task


# ── Retry on failure ───────────────────────────────────────────────────


def test_per_chapter_retry_on_extraction_failure() -> None:
    """A single chapter's extraction failure triggers retry for that chapter only."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}

    # Chapter 1: succeeds immediately, Chapter 2: fails twice then succeeds
    call_count = {"ch2": 0}

    def run_side_effect(task_desc):
        if "第 1 章" in task_desc:
            return _make_single_chapter_json(1)
        else:
            call_count["ch2"] += 1
            if call_count["ch2"] < 3:
                return "invalid json {{{{{"
            return _make_single_chapter_json(2)

    with patch.object(agent, "_run_agent", side_effect=run_side_effect) as mock_run:
        outline = agent.create_outline(context, target_chapters=2)

    assert len(outline) == 2
    # 1st chapter: 1 call. 2nd chapter: 3 calls (2 fails + 1 success)
    assert mock_run.call_count == 4
