from unittest.mock import Mock
from agents.design_team import DesignResult, run_design_team, format_issues
from agents.narrative_reviewer import NarrativeReviewResult
from models.story_context import StoryContext
from models.schemas import (
    WorldSetting,
    Location,
    Entity,
    Character,
    ChapterOutline,
    ConflictDesign,
    ConflictThread,
    DramaticBeat,
    StoryZone,
    ResearchQuestion,
    ResearchNote,
    NarrativeIssue,
)


def _make_context():
    return StoryContext(seed={"theme": "调查", "era": "1920年代", "target_chapters": 10})


def _make_world():
    return WorldSetting(
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


def _make_conflict():
    return ConflictDesign(
        narrative_strategy="逐步揭示",
        threads=[
            ConflictThread(
                name="求知之祸", thread_type="epistemic", description="渴望vs恐惧", stakes="理智"
            ),
            ConflictThread(
                name="邪教操控", thread_type="societal", description="馆长阻止", stakes="生命"
            ),
        ],
        zones=[
            StoryZone(
                zone="setup",
                beats=[DramaticBeat(name="发现笔记", description="发现笔记", threads=["求知之祸"])],
            ),
            StoryZone(
                zone="crucible",
                beats=[
                    DramaticBeat(
                        name="盟友背叛", description="盟友是邪教", threads=["求知之祸", "邪教操控"]
                    ),
                    DramaticBeat(
                        name="直面仪式", description="直面仪式", threads=["求知之祸", "邪教操控"]
                    ),
                ],
            ),
            StoryZone(
                zone="aftermath",
                beats=[DramaticBeat(name="真相掩埋", description="真相掩埋", threads=["求知之祸"])],
            ),
        ],
        tension_shape="慢炖型",
        thematic_throughline="知识即诅咒",
    )


def _make_outline():
    return [
        ChapterOutline(
            number=1,
            title="抵达",
            summary="来到小镇",
            mood="不安",
            word_target=3000,
        )
    ]


def _make_passing_review():
    return NarrativeReviewResult({"passed": True, "issues": [], "strengths": ["张力充分"]})


def _make_failing_review(target="outline"):
    return NarrativeReviewResult(
        {
            "passed": False,
            "issues": [
                {
                    "dimension": "tension_sufficiency",
                    "severity": "major",
                    "description": "空章节",
                    "suggestion": "加冲突",
                    "target": target,
                }
            ],
            "strengths": [],
        }
    )


def _make_mock_agents():
    worldbuilder = Mock()
    worldbuilder.generate_questions.side_effect = lambda ctx: setattr(
        ctx,
        "research_questions",
        [ResearchQuestion(topic="genre", question="经典模式？")],
    )
    worldbuilder.build_world.side_effect = lambda ctx, **kw: setattr(ctx, "world", _make_world())

    researcher = Mock()
    researcher.research.side_effect = lambda ctx: setattr(
        ctx,
        "research_notes",
        [ResearchNote(topic="genre", findings="渐进揭示", sources=["引用"])],
    )

    conflict_architect = Mock()
    conflict_architect.design_conflicts.side_effect = lambda ctx, **kw: setattr(
        ctx, "conflict_design", _make_conflict()
    )

    outliner = Mock()
    outliner.create_outline.side_effect = lambda ctx, *a, **kw: setattr(
        ctx, "outline", _make_outline()
    )

    reviewer = Mock()
    reviewer.review_narrative.return_value = _make_passing_review()

    return worldbuilder, researcher, conflict_architect, outliner, reviewer


def test_design_team_full_pipeline_passes():
    """Happy path: all 4 phases run, reviewer passes."""
    ctx = _make_context()
    wb, res, ca, out, rev = _make_mock_agents()

    result = run_design_team(ctx, wb, res, ca, out, rev)

    assert isinstance(result, DesignResult)
    assert result.review.passed is True
    assert result.iterations == 0
    wb.generate_questions.assert_called_once()
    res.research.assert_called_once()
    wb.build_world.assert_called_once()
    ca.design_conflicts.assert_called_once()
    out.create_outline.assert_called_once()
    rev.review_narrative.assert_called_once()


def test_design_team_iterates_on_outline_issue():
    """Outline-only issue: only outliner reruns."""
    ctx = _make_context()
    wb, res, ca, out, rev = _make_mock_agents()
    rev.review_narrative.side_effect = [
        _make_failing_review("outline"),
        _make_passing_review(),
    ]

    result = run_design_team(ctx, wb, res, ca, out, rev)

    assert result.review.passed is True
    assert result.iterations == 1
    wb.build_world.assert_called_once()  # not rebuilt
    ca.design_conflicts.assert_called_once()  # not rebuilt
    assert out.create_outline.call_count == 2


def test_design_team_iterates_on_conflict_issue():
    """Conflict issue: conflict architect + outliner rerun."""
    ctx = _make_context()
    wb, res, ca, out, rev = _make_mock_agents()
    rev.review_narrative.side_effect = [
        _make_failing_review("conflict"),
        _make_passing_review(),
    ]

    result = run_design_team(ctx, wb, res, ca, out, rev)

    assert result.review.passed is True
    wb.build_world.assert_called_once()  # not rebuilt
    assert ca.design_conflicts.call_count == 2
    assert out.create_outline.call_count == 2


def test_design_team_iterates_on_world_issue():
    """World issue: world + conflict + outline all rebuild."""
    ctx = _make_context()
    wb, res, ca, out, rev = _make_mock_agents()
    rev.review_narrative.side_effect = [
        _make_failing_review("world"),
        _make_passing_review(),
    ]

    result = run_design_team(ctx, wb, res, ca, out, rev)

    assert result.review.passed is True
    assert wb.build_world.call_count == 2
    assert ca.design_conflicts.call_count == 2
    assert out.create_outline.call_count == 2


def test_design_team_max_iterations():
    """After 2 failed rounds, stops and returns."""
    ctx = _make_context()
    wb, res, ca, out, rev = _make_mock_agents()
    rev.review_narrative.return_value = _make_failing_review("outline")

    result = run_design_team(ctx, wb, res, ca, out, rev, max_rounds=2)

    assert result.review.passed is False
    # initial + 2 rounds = 3 reviews
    assert rev.review_narrative.call_count == 3


def test_design_team_progress_callback():
    """Progress callback is called for each phase."""
    ctx = _make_context()
    wb, res, ca, out, rev = _make_mock_agents()
    progress_calls = []

    def on_progress(phase, status):
        progress_calls.append((phase, status))

    run_design_team(ctx, wb, res, ca, out, rev, on_progress=on_progress)

    phase_names = [p for p, s in progress_calls]
    assert "research_questions" in phase_names
    assert "research" in phase_names
    assert "world_building" in phase_names
    assert "conflict_design" in phase_names
    assert "outline" in phase_names
    assert "review" in phase_names


def test_format_issues():
    issues = [
        NarrativeIssue(
            dimension="tension_sufficiency",
            severity="major",
            description="空章节",
            suggestion="加冲突",
            target="outline",
        )
    ]
    result = format_issues(issues)
    assert "tension_sufficiency" in result
    assert "空章节" in result
