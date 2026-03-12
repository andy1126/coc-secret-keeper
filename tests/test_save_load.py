import json

import pytest

from app import SAVE_VERSION, VALID_STAGES, build_save_data, parse_save_data
from models.schemas import (
    Character,
    ChapterOutline,
    Entity,
    Location,
    ResearchNote,
    ResearchQuestion,
    WorldSetting,
)
from models.story_context import StoryContext


def _make_full_context() -> StoryContext:
    """Create a StoryContext with data at every field for round-trip testing."""
    world = WorldSetting(
        era="1920年代",
        locations=[Location(name="阿卡姆", description="诡异小镇")],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="真相",
        rules=["不可直视"],
        characters=[
            Character(
                name="张三",
                background="学者",
                personality="好奇",
                motivation="求知",
                arc="堕落",
                relationships=["李四"],
            )
        ],
    )
    outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="发现手稿",
            mood="不安",
            word_target=3000,
            foreshadowing=["符号"],
            payoffs=[],
        ),
        ChapterOutline(
            number=2,
            title="深入",
            summary="追查线索",
            mood="恐惧",
            word_target=3500,
            foreshadowing=[],
            payoffs=["符号"],
        ),
    ]
    return StoryContext(
        seed={"theme": "宇宙恐怖", "era": "1920", "atmosphere": "阴暗"},
        research_questions=[ResearchQuestion(topic="genre", question="经典叙事模式？")],
        research_notes=[
            ResearchNote(topic="genre", findings="渐进揭示是克苏鲁核心", sources=["引用"])
        ],
        world=world,
        outline=outline,
        chapters=["第一章正文...", "第二章正文..."],
        chapter_summaries=["摘要一", "摘要二"],
        review_notes=["审核备注"],
    )


# --- Tests ---


def test_save_progress_schema():
    ctx = StoryContext(seed={"theme": "测试"})
    data = build_save_data(ctx, "brainstorm", [])

    assert data["version"] == SAVE_VERSION
    assert "saved_at" in data
    assert data["stage"] == "brainstorm"
    assert data["context"] == ctx.to_dict()
    assert data["chat_history"] == []


def test_save_load_roundtrip():
    ctx = _make_full_context()
    chat = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "开始"}]

    save_data = build_save_data(ctx, "writing", chat)
    raw = json.dumps(save_data, ensure_ascii=False).encode()

    loaded_ctx, loaded_stage, loaded_chat = parse_save_data(raw)

    assert loaded_stage == "writing"
    assert loaded_chat == chat
    assert loaded_ctx.to_dict() == ctx.to_dict()


def test_load_invalid_json():
    with pytest.raises(ValueError, match="无效的 JSON"):
        parse_save_data(b"not json at all")


def test_load_missing_keys():
    incomplete = json.dumps({"version": 1, "stage": "brainstorm"}).encode()
    with pytest.raises(ValueError, match="缺少必要字段"):
        parse_save_data(incomplete)


def test_load_invalid_stage():
    data = {
        "version": 1,
        "stage": "nonexistent",
        "context": StoryContext().to_dict(),
        "chat_history": [],
    }
    with pytest.raises(ValueError, match="无效的阶段"):
        parse_save_data(json.dumps(data).encode())


def test_load_invalid_context():
    data = {
        "version": 1,
        "stage": "brainstorm",
        "context": {"outline": "not a list"},
        "chat_history": [],
    }
    with pytest.raises(ValueError, match="无法解析存档数据"):
        parse_save_data(json.dumps(data).encode())


def test_save_at_each_stage():
    for stage in VALID_STAGES:
        ctx = StoryContext()
        data = build_save_data(ctx, stage, [])
        raw = json.dumps(data).encode()
        loaded_ctx, loaded_stage, _ = parse_save_data(raw)
        assert loaded_stage == stage


def test_save_load_partial_design_research_only():
    """Partial design: research_questions populated, world is None."""
    ctx = StoryContext(
        seed={"theme": "恐怖", "target_chapters": 8},
        research_questions=[ResearchQuestion(topic="genre", question="经典模式？")],
        research_notes=[ResearchNote(topic="genre", findings="渐进揭示", sources=["引用"])],
    )
    save_data = build_save_data(ctx, "design", [])
    raw = json.dumps(save_data, ensure_ascii=False).encode()

    loaded_ctx, loaded_stage, _ = parse_save_data(raw)

    assert loaded_stage == "design"
    assert len(loaded_ctx.research_questions) == 1
    assert len(loaded_ctx.research_notes) == 1
    assert loaded_ctx.world is None
    assert loaded_ctx.conflict_design is None
    assert loaded_ctx.outline == []


def test_save_load_partial_design_through_world():
    """Partial design: world populated, conflict_design is None."""
    world = WorldSetting(
        era="1920年代",
        locations=[Location(name="阿卡姆", description="诡异小镇")],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="真相",
        rules=["不可直视"],
        characters=[
            Character(
                name="张三",
                background="学者",
                personality="好奇",
                motivation="求知",
                arc="堕落",
                relationships=[],
            )
        ],
    )
    ctx = StoryContext(
        seed={"theme": "恐怖", "target_chapters": 8},
        research_questions=[ResearchQuestion(topic="genre", question="经典模式？")],
        research_notes=[ResearchNote(topic="genre", findings="渐进揭示", sources=["引用"])],
        world=world,
    )
    save_data = build_save_data(ctx, "design", [])
    raw = json.dumps(save_data, ensure_ascii=False).encode()

    loaded_ctx, loaded_stage, _ = parse_save_data(raw)

    assert loaded_stage == "design"
    assert loaded_ctx.world is not None
    assert loaded_ctx.world.era == "1920年代"
    assert loaded_ctx.conflict_design is None
    assert loaded_ctx.outline == []
