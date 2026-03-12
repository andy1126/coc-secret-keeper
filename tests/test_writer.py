from unittest.mock import Mock, patch, MagicMock
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


# -- Helper extraction tests --


def test_build_write_task_desc():
    """Extracted helper should produce same task_desc content."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=[Location(name="阿卡姆", description="小镇")],
        characters=[],
    )
    context.chapter_endings = ["上一章结尾"]

    chapter = ChapterOutline(
        number=2,
        title="深入",
        summary="主角深入调查",
        mood="悬疑",
        word_target=500,
        key_beats=["发现线索", "遭遇危险"],
        foreshadowing=["暗示"],
        payoffs=["回收"],
    )

    task_desc = agent._build_write_task_desc(context, chapter)
    assert "Key Beats Checklist" in task_desc
    assert "发现线索" in task_desc
    assert "上一章结尾" in task_desc
    assert "Previous Chapter Ending" in task_desc
    assert "chapter 2" in task_desc.lower()


def test_build_revise_task_desc():
    """Extracted helper should include issues list."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    chapter = ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500)
    issues = [
        {"category": "pacing", "description": "节奏太慢", "suggestion": "加快节奏"},
        {"category": "dialogue", "description": "对话生硬", "suggestion": "更自然"},
    ]

    task_desc = agent._build_revise_task_desc(context, chapter, "原文内容", issues)
    assert "节奏太慢" in task_desc
    assert "对话生硬" in task_desc
    assert "加快节奏" in task_desc
    assert "原文内容" in task_desc


# -- Streaming tests --


def _make_fake_chunks(texts):
    """Create fake litellm streaming chunks."""
    chunks = []
    for text in texts:
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = text
        chunks.append(chunk)
    return chunks


def test_write_chapter_stream():
    """write_chapter_stream should yield content chunks from litellm."""
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
    ]

    fake_chunks = _make_fake_chunks(["张三", "走进了", "图书馆", None, "。"])
    litellm_params = {"model": "anthropic/test", "stream": True}

    with patch("agents.writer.litellm.completion", return_value=fake_chunks) as mock_comp:
        result = list(agent.write_chapter_stream(context, context.outline[0], litellm_params))

    assert result == ["张三", "走进了", "图书馆", "。"]
    mock_comp.assert_called_once()
    call_kwargs = mock_comp.call_args
    assert call_kwargs.kwargs["model"] == "anthropic/test"
    assert call_kwargs.kwargs["stream"] is True


def test_finalize_write_chapter():
    """finalize_write_chapter should update context.chapters and chapter_endings."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    chapter = ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500)

    long_text = "字" * 1000
    agent.finalize_write_chapter(long_text, context, chapter)

    assert len(context.chapters) == 1
    assert context.chapters[0] == long_text
    assert len(context.chapter_endings) == 1
    assert len(context.chapter_endings[0]) == 500


def test_finalize_write_chapter_replace():
    """finalize_write_chapter should replace existing chapter slot."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.chapters = ["old content"]
    context.chapter_endings = ["old ending"]
    chapter = ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500)

    agent.finalize_write_chapter("new content", context, chapter)

    assert context.chapters[0] == "new content"
    assert context.chapter_endings[0] == "new content"


def test_finalize_revise_chapter():
    """finalize_revise_chapter should replace chapter and ending."""
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.chapters = ["原始内容"]
    context.chapter_endings = ["原始结尾"]
    chapter = ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=500)

    long_text = "修" * 800
    agent.finalize_revise_chapter(long_text, context, chapter)

    assert context.chapters[0] == long_text
    assert len(context.chapter_endings[0]) == 500


def test_write_chapter_still_works():
    """Original non-streaming write_chapter should still work correctly."""
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
    ]

    mock_result = "完整的章节内容"
    with patch.object(agent, "_run_agent", return_value=mock_result):
        result = agent.write_chapter(context, context.outline[0])

    assert result == mock_result
    assert context.chapters == [mock_result]
    assert context.chapter_endings == [mock_result]
