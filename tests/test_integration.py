from unittest.mock import Mock, patch

from models.story_context import StoryContext
from models.schemas import Character, Entity, Location, WorldSetting, ChapterOutline


def test_full_pipeline():
    """Test the full pipeline with mocked LLM."""
    context = StoryContext()

    # Step 1: Brainstorm
    context.seed = {
        "theme": "调查",
        "era": "1920年代",
        "atmosphere": "心理恐怖",
        "mythos_elements": ["古老者"],
        "protagonist": {"concept": "考古学家", "motivation": "寻找真相"},
    }

    # Step 2: World building
    context.world = WorldSetting(
        era="1924年，阿卡姆镇",
        locations=[Location(name="密斯卡托尼克大学", description="藏有禁书的学府")],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="人类渺小",
        rules=["不可直视古神"],
        characters=[
            Character(
                name="李教授",
                background="考古学",
                personality="严谨",
                motivation="求知",
                arc="堕落",
                relationships=[],
            )
        ],
    )

    # Step 3: Outline
    context.outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="主角发现神秘手稿",
            mood="悬疑",
            word_target=1000,
            foreshadowing=["手稿符号"],
            payoffs=[],
        ),
        ChapterOutline(
            number=2,
            title="调查",
            summary="主角开始调查",
            mood="紧张",
            word_target=1000,
            foreshadowing=[],
            payoffs=["手稿符号"],
        ),
    ]

    # Step 4: Writing
    context.chapters = ["第一章内容...", "第二章内容..."]

    # Verify
    assert len(context.chapters) == len(context.outline)
    assert context.world is not None
    assert len(context.world.characters) > 0


def test_review_classification():
    """Test review issue classification."""
    from agents.reviewer import ReviewResult

    review_data = {
        "passed": False,
        "issues": [
            {
                "category": "atmosphere",
                "severity": "minor",
                "description": "氛围不足",
                "suggestion": "加强",
            },
            {
                "category": "plot",
                "severity": "major",
                "description": "逻辑矛盾",
                "suggestion": "修改",
            },
        ],
        "strengths": [],
        "overall_assessment": "需要修订",
    }

    result = ReviewResult(review_data)

    assert len(result.get_minor_issues()) == 1
    assert len(result.get_major_issues()) == 1


def test_revision_loop_minor_issues():
    """Test that minor issues trigger writer revision."""
    from agents.writer import WriterAgent

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="诡异小镇")],
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

    mock_writer_llm = Mock()
    writer = WriterAgent(mock_writer_llm)

    # Simulate: write -> review (minor) -> revise -> review (pass)
    with patch.object(writer, "_run_agent", side_effect=["原始章节内容...", "修订后章节内容..."]):
        original = writer.write_chapter(context, context.outline[0])
        assert original == "原始章节内容..."

        revised = writer.revise_chapter(
            context,
            context.outline[0],
            original,
            [{"category": "atmosphere", "description": "氛围不足", "suggestion": "加强"}],
        )
        assert revised == "修订后章节内容..."
        assert context.chapters[0] == "修订后章节内容..."


def test_final_review():
    """Test final full-text review."""
    from agents.reviewer import ReviewerAgent

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="诡异小镇")],
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
    context.outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="开始",
            mood="悬疑",
            word_target=1000,
            foreshadowing=["线索A"],
            payoffs=[],
        ),
        ChapterOutline(
            number=2,
            title="结局",
            summary="结束",
            mood="恐惧",
            word_target=1000,
            foreshadowing=[],
            payoffs=["线索A"],
        ),
    ]
    context.chapters = ["第一章内容...", "第二章内容..."]
    context.chapter_summaries = ["第一章摘要", "第二章摘要"]

    mock_llm = Mock()
    reviewer = ReviewerAgent(mock_llm)

    mock_result = """```json
{
  "passed": true,
  "issues": [],
  "strengths": ["伏笔回收完整", "氛围连贯"],
  "overall_assessment": "整体质量良好"
}
```"""

    with patch.object(reviewer, "_run_agent", return_value=mock_result):
        review = reviewer.final_review(context)

    assert review.passed
    assert "FINAL REVIEW" in context.review_notes[-1]
