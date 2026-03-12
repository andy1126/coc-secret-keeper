from unittest.mock import Mock, patch
from agents.narrative_reviewer import NarrativeReviewerAgent, NarrativeReviewResult
from models.story_context import StoryContext
from models.schemas import (
    WorldSetting,
    Location,
    Entity,
    Character,
    Secret,
    Tension,
    TimelineEvent,
    ChapterOutline,
    ConflictDesign,
    ConflictThread,
    DramaticBeat,
)


def _make_full_context():
    ctx = StoryContext(seed={"theme": "调查", "era": "1920年代", "target_chapters": 10})
    ctx.world = WorldSetting(
        era="1924年",
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
        secrets=[Secret(content="祭坛", known_by=["馆长"], layer=2)],
        tensions=[Tension(parties=["李教授", "馆长"], nature="秘密", status="潜伏")],
        timeline=[TimelineEvent(when="1920", event="失踪", consequences="封锁")],
    )
    ctx.conflict_design = ConflictDesign(
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
    ctx.outline = [
        ChapterOutline(
            number=1,
            title="抵达",
            summary="来到小镇",
            mood="不安",
            word_target=3000,
            foreshadowing=["钟声"],
            payoffs=[],
            pov="主角",
            information_reveal=["失踪案"],
            twist=None,
            subplot=None,
        )
    ]
    return ctx


def test_review_narrative_passed():
    agent = NarrativeReviewerAgent(llm=Mock())
    context = _make_full_context()

    mock_result = '```json\n{"passed": true, "issues": [], "strengths": ["张力充分"]}\n```'
    with patch.object(agent, "_run_agent", return_value=mock_result):
        result = agent.review_narrative(context)

    assert result.passed is True


def test_review_narrative_with_conflict_target():
    agent = NarrativeReviewerAgent(llm=Mock())
    context = _make_full_context()

    mock_result = """
```json
{
  "passed": false,
  "issues": [{"dimension": "character_agency", "severity": "major",
              "description": "冲突被动", "suggestion": "重设", "target": "conflict"}],
  "strengths": []
}
```
"""
    with patch.object(agent, "_run_agent", return_value=mock_result):
        result = agent.review_narrative(context)

    assert result.passed is False
    assert result.get_major_issues()[0].target == "conflict"


def test_review_result_helpers():
    data = {
        "passed": False,
        "issues": [
            {
                "dimension": "tension_sufficiency",
                "severity": "major",
                "description": "空章节",
                "suggestion": "加冲突",
                "target": "outline",
            },
            {
                "dimension": "asset_utilization",
                "severity": "minor",
                "description": "未用实体",
                "suggestion": "加入",
                "target": "world",
            },
            {
                "dimension": "character_agency",
                "severity": "major",
                "description": "被动",
                "suggestion": "重设",
                "target": "conflict",
            },
        ],
        "strengths": [],
    }
    result = NarrativeReviewResult(data)
    assert len(result.get_major_issues()) == 2
    assert len(result.get_minor_issues()) == 1
    assert len(result.get_world_issues()) == 1
    assert len(result.get_outline_issues()) == 1
    assert len(result.get_conflict_issues()) == 1
