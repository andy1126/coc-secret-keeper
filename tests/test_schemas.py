from typing import Any

import pytest
from pydantic import ValidationError
from models.schemas import (
    Character,
    Entity,
    Location,
    WorldSetting,
    ChapterOutline,
    Secret,
    Tension,
    TimelineEvent,
    ResearchQuestion,
    ResearchNote,
    ConflictDesign,
    ConflictThread,
    DramaticBeat,
    NarrativeIssue,
)
from models.story_context import StoryContext


def test_character_creation() -> None:
    char = Character(
        name="张三",
        background="考古学家",
        personality="好奇、固执",
        motivation="寻找失落的真相",
        arc="从怀疑到疯狂",
        relationships=["李四：同事", "王五：导师"],
    )
    assert char.name == "张三"
    assert len(char.relationships) == 2


def test_entity_creation() -> None:
    entity = Entity(
        name="古老者",
        description="来自星际的古老生物",
        influence="通过梦境影响人类心智",
    )
    assert entity.name == "古老者"


def test_world_setting_creation() -> None:
    world = WorldSetting(
        era="1920年代",
        locations=[
            Location(name="阿卡姆镇", description="新英格兰的小镇"),
            Location(name="密斯卡托尼克大学", description="藏有禁书的学府"),
        ],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="人类并非万物之主",
        rules=["不可直视古神", "知识带来疯狂"],
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
    assert len(world.locations) == 2
    assert world.locations[0].name == "阿卡姆镇"
    assert len(world.characters) == 1


def test_chapter_outline_creation() -> None:
    chapter = ChapterOutline(
        number=1,
        title="开端",
        summary="主角发现神秘手稿",
        mood="悬疑、不安",
        word_target=3000,
        foreshadowing=["手稿上的符号", "奇怪的梦境"],
        payoffs=[],
    )
    assert chapter.number == 1
    assert chapter.word_target == 3000


# --- Task 1: New schema models ---


def test_secret_creation() -> None:
    secret = Secret(content="镇长是邪教领袖", known_by=["镇长", "牧师"], layer=2)
    assert secret.layer == 2
    assert len(secret.known_by) == 2


def test_tension_creation() -> None:
    tension = Tension(parties=["镇长", "调查员"], nature="秘密", status="潜伏")
    assert tension.nature == "秘密"


def test_timeline_event_creation() -> None:
    event = TimelineEvent(when="1920年春", event="矿坑坍塌", consequences="镇民恐慌")
    assert "矿坑" in event.event


def test_research_question_creation() -> None:
    q = ResearchQuestion(topic="genre", question="调查类克苏鲁的经典模式？")
    assert q.topic == "genre"


def test_research_note_creation() -> None:
    note = ResearchNote(
        topic="psychology",
        findings="面对不可名状恐惧时，人类会经历否认→恐惧→解离三阶段",
        sources=["《恐惧心理学》", "洛夫克拉夫特书信集"],
    )
    assert len(note.sources) == 2


def _make_conflict_design(**overrides: Any) -> ConflictDesign:
    """Helper to build a valid ConflictDesign with sensible defaults."""
    defaults: dict[str, Any] = dict(
        narrative_strategy="通过日记碎片拼接揭示真相",
        threads=[
            ConflictThread(
                name="求知之祸",
                thread_type="epistemic",
                description="渴望真相 vs 恐惧疯狂",
                stakes="理智崩溃",
            ),
            ConflictThread(
                name="邪教阴谋",
                thread_type="societal",
                description="邪教组织阻止调查",
                stakes="生命威胁",
            ),
        ],
        beats=[
            DramaticBeat(
                zone="setup",
                name="发现笔记",
                description="发现失踪教授的笔记",
                threads=["求知之祸"],
            ),
            DramaticBeat(
                zone="crucible",
                name="盟友背叛",
                description="可信赖的盟友其实是邪教成员",
                threads=["求知之祸", "邪教阴谋"],
            ),
            DramaticBeat(
                zone="crucible",
                name="直面仪式",
                description="直面古神仪式现场",
                threads=["求知之祸", "邪教阴谋"],
            ),
            DramaticBeat(
                zone="aftermath",
                name="真相掩埋",
                description="真相被掩埋，主角带着创伤离开",
                threads=["求知之祸"],
            ),
        ],
        tension_shape="慢炖型：长时间不安积累后猛然爆发",
        thematic_throughline="知识即诅咒",
    )
    defaults.update(overrides)
    return ConflictDesign(**defaults)


def test_conflict_design_creation() -> None:
    cd = _make_conflict_design()
    assert "日记" in cd.narrative_strategy
    assert len(cd.threads) == 2
    assert len(cd.beats) == 4
    zones_present = {b.zone for b in cd.beats}
    assert zones_present == {"setup", "crucible", "aftermath"}


def test_narrative_issue_creation() -> None:
    issue = NarrativeIssue(
        dimension="tension_sufficiency",
        severity="major",
        description="第3-5章缺乏冲突",
        suggestion="加入对抗",
        target="outline",
    )
    assert issue.target == "outline"


def test_narrative_issue_conflict_target() -> None:
    issue = NarrativeIssue(
        dimension="character_agency",
        severity="major",
        description="冲突设计被动",
        suggestion="重设内在冲突",
        target="conflict",
    )
    assert issue.target == "conflict"


# --- Task 2: WorldSetting new fields ---


def test_world_setting_with_new_fields() -> None:
    world = WorldSetting(
        era="1920年代",
        locations=[Location(name="阿卡姆镇", description="小镇")],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="真相",
        rules=["规则1"],
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
        secrets=[Secret(content="镇长是邪教领袖", known_by=["镇长"], layer=2)],
        tensions=[Tension(parties=["镇长", "调查员"], nature="秘密", status="潜伏")],
        timeline=[TimelineEvent(when="1920年春", event="矿坑坍塌", consequences="恐慌")],
    )
    assert len(world.secrets) == 1
    assert len(world.tensions) == 1
    assert len(world.timeline) == 1


def test_world_setting_new_fields_default_empty() -> None:
    world = WorldSetting(
        era="1920年代",
        locations=[],
        entities=[],
        forbidden_knowledge="",
        rules=[],
        characters=[],
    )
    assert world.secrets == []
    assert world.tensions == []
    assert world.timeline == []


# --- Task 3: ChapterOutline new fields ---


def test_chapter_outline_with_new_fields() -> None:
    chapter = ChapterOutline(
        number=1,
        title="开端",
        summary="主角发现手稿",
        mood="悬疑",
        word_target=3000,
        foreshadowing=["符号"],
        payoffs=[],
        pov="主角",
        information_reveal=["失踪案"],
        twist="手稿伪造",
        subplot="牧师秘密",
    )
    assert chapter.pov == "主角"
    assert chapter.twist == "手稿伪造"


def test_chapter_outline_new_fields_defaults() -> None:
    chapter = ChapterOutline(number=1, title="开端", summary="摘要", mood="悬疑", word_target=3000)
    assert chapter.pov == ""
    assert chapter.information_reveal == []
    assert chapter.twist is None
    assert chapter.subplot is None


# --- Task 4: StoryContext new fields ---


def test_story_context_new_fields() -> None:
    ctx = StoryContext()
    assert ctx.research_questions == []
    assert ctx.research_notes == []
    assert ctx.conflict_design is None


# --- key_beats ---


def test_chapter_outline_key_beats_default() -> None:
    """key_beats defaults to empty list for backward compatibility."""
    chapter = ChapterOutline(number=1, title="开端", summary="摘要", mood="悬疑", word_target=3000)
    assert chapter.key_beats == []


def test_chapter_outline_with_key_beats() -> None:
    chapter = ChapterOutline(
        number=1,
        title="开端",
        summary="摘要",
        mood="悬疑",
        word_target=3000,
        key_beats=["发现古籍", "与馆长对话", "听到低语"],
    )
    assert len(chapter.key_beats) == 3


# --- chapter_endings ---


def test_story_context_chapter_endings_default() -> None:
    ctx = StoryContext()
    assert ctx.chapter_endings == []


# --- ConflictDesign flat beats structure ---


def test_conflict_thread_types() -> None:
    """thread_type Literal rejects invalid values."""
    # Valid
    t = ConflictThread(name="t", thread_type="epistemic", description="d", stakes="s")
    assert t.thread_type == "epistemic"

    # Invalid
    with pytest.raises(ValidationError):
        ConflictThread(name="t", thread_type="invalid_type", description="d", stakes="s")  # type: ignore[arg-type]


def test_conflict_beats_zone_coverage() -> None:
    """ConflictDesign rejects missing zones in beats."""
    base = _make_conflict_design()

    # Missing aftermath zone
    with pytest.raises(ValidationError):
        ConflictDesign(
            narrative_strategy="x",
            threads=base.threads,
            beats=[
                DramaticBeat(zone="setup", name="a", description="a", threads=["求知之祸"]),
                DramaticBeat(zone="crucible", name="b", description="b", threads=["求知之祸"]),
            ],
            tension_shape="x",
            thematic_throughline="x",
        )


def test_conflict_design_thread_count() -> None:
    """ConflictDesign requires 1-6 threads."""
    base = _make_conflict_design()
    beats = base.beats

    # 1 thread — valid now
    cd = ConflictDesign(
        narrative_strategy="x",
        threads=[ConflictThread(name="t", thread_type="moral", description="d", stakes="s")],
        beats=beats,
        tension_shape="x",
        thematic_throughline="x",
    )
    assert len(cd.threads) == 1

    # 7 threads — too many
    with pytest.raises(ValidationError):
        ConflictDesign(
            narrative_strategy="x",
            threads=[
                ConflictThread(name=f"t{i}", thread_type="moral", description="d", stakes="s")
                for i in range(7)
            ],
            beats=beats,
            tension_shape="x",
            thematic_throughline="x",
        )


def test_story_context_roundtrip_with_new_conflict() -> None:
    """StoryContext with new ConflictDesign survives to_dict/from_dict roundtrip."""
    ctx = StoryContext()
    ctx.conflict_design = _make_conflict_design()

    data = ctx.to_dict()
    restored = StoryContext.from_dict(data)

    assert restored.conflict_design is not None
    assert len(restored.conflict_design.threads) == 2
    zones_present = {b.zone for b in restored.conflict_design.beats}
    assert zones_present == {"setup", "crucible", "aftermath"}
    assert restored.conflict_design.narrative_strategy == ctx.conflict_design.narrative_strategy
