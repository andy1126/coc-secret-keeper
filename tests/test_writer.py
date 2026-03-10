from unittest.mock import Mock, patch
from agents.writer import WriterAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline, WorldSetting, Character, Location


def test_writer_creation():
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)
    assert agent is not None


def test_write_chapter():
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
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
    context.chapter_summaries = ["第1章摘要：张三发现了古老的手稿。"]

    chapter_outline = ChapterOutline(
        number=2,
        title="深入",
        summary="主角深入调查",
        mood="悬疑",
        word_target=500,
        foreshadowing=["奇怪的符号"],
        payoffs=[],
    )

    mock_result = "张三拿起那本古老的书...（省略）"

    with patch.object(agent, "_run_agent", return_value=mock_result) as mock_run:
        chapter = agent.write_chapter(context, chapter_outline)

    assert chapter == mock_result
    assert len(context.chapters) == 1

    # Verify task description uses summaries, not full text
    task_desc = mock_run.call_args[0][0]
    assert "第1章摘要" in task_desc
    assert "章摘要:" in task_desc


def test_write_chapter_first_chapter():
    """First chapter should show '无' for previous summaries."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )

    chapter_outline = ChapterOutline(
        number=1,
        title="开端",
        summary="主角开始调查",
        mood="悬疑",
        word_target=500,
        foreshadowing=[],
        payoffs=[],
    )

    with patch.object(agent, "_run_agent", return_value="章节内容") as mock_run:
        agent.write_chapter(context, chapter_outline)

    task_desc = mock_run.call_args[0][0]
    assert "无" in task_desc


def test_summarize_chapter():
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    chapter_outline = ChapterOutline(
        number=1,
        title="开端",
        summary="主角发现手稿",
        mood="悬疑",
        word_target=500,
        foreshadowing=["奇怪的符号"],
        payoffs=[],
    )

    mock_summary = "张三在密斯卡托尼克大学的图书馆中发现了一本古老的手稿..."

    with patch.object(agent, "_run_agent", return_value=mock_summary) as mock_run:
        result = agent.summarize_chapter(chapter_outline, "很长的章节正文...")

    assert result == mock_summary
    task_desc = mock_run.call_args[0][0]
    assert "200-300" in task_desc
    assert "摘要" in task_desc
    assert "第1章" in task_desc


def test_write_chapter_includes_key_beats():
    """key_beats should appear as a checklist in task_desc."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )

    chapter_outline = ChapterOutline(
        number=1,
        title="开端",
        summary="主角开始调查",
        mood="悬疑",
        word_target=500,
        key_beats=["发现古籍", "与馆长对话", "听到低语"],
    )

    with patch.object(agent, "_run_agent", return_value="章节内容") as mock_run:
        agent.write_chapter(context, chapter_outline)

    task_desc = mock_run.call_args[0][0]
    assert "Key Beats Checklist" in task_desc
    assert "发现古籍" in task_desc
    assert "与馆长对话" in task_desc
    assert "听到低语" in task_desc
    assert "MUST cover every key beat" in task_desc


def test_write_chapter_includes_next_chapter_preview():
    """Non-last chapter should include next chapter preview."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500),
        ChapterOutline(number=2, title="深入", summary="深入调查", mood="紧张", word_target=500),
    ]

    with patch.object(agent, "_run_agent", return_value="章节内容") as mock_run:
        agent.write_chapter(context, context.outline[0])

    task_desc = mock_run.call_args[0][0]
    assert "深入" in task_desc
    assert "Next Chapter Preview" in task_desc


def test_write_chapter_last_chapter_no_next_preview():
    """Last chapter should show ending instruction."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )
    context.outline = [
        ChapterOutline(number=1, title="结局", summary="结局", mood="余韵", word_target=500),
    ]

    with patch.object(agent, "_run_agent", return_value="章节内容") as mock_run:
        agent.write_chapter(context, context.outline[0])

    task_desc = mock_run.call_args[0][0]
    assert "最后一章" in task_desc


def test_write_chapter_includes_previous_ending():
    """Non-first chapter should include previous chapter ending."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )
    context.chapter_endings = ["上一章末尾的500字内容"]
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500),
        ChapterOutline(number=2, title="深入", summary="深入", mood="紧张", word_target=500),
    ]

    with patch.object(agent, "_run_agent", return_value="章节内容") as mock_run:
        agent.write_chapter(context, context.outline[1])

    task_desc = mock_run.call_args[0][0]
    assert "上一章末尾的500字内容" in task_desc
    assert "Previous Chapter Ending" in task_desc


def test_write_chapter_appends_chapter_ending():
    """write_chapter should append last 500 chars to chapter_endings."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    long_text = "字" * 1000
    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500),
    ]

    with patch.object(agent, "_run_agent", return_value=long_text):
        agent.write_chapter(context, context.outline[0])

    assert len(context.chapter_endings) == 1
    assert len(context.chapter_endings[0]) == 500
