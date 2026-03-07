import pytest
from unittest.mock import Mock, patch
from agents.writer import WriterAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline, WorldSetting, Character


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
        locations=["阿卡姆"],
        characters=[Character(name="张三", background="学者", personality="好奇", motivation="求知", arc="堕落", relationships=[])],
    )

    chapter_outline = ChapterOutline(
        number=1,
        title="开端",
        summary="主角开始调查",
        mood="悬疑",
        word_target=500,
        foreshadowing=["奇怪的符号"],
        payoffs=[],
    )

    mock_result = "张三拿起那本古老的书...（省略）"

    with patch.object(agent, '_run_agent', return_value=mock_result):
        chapter = agent.write_chapter(context, chapter_outline)

    assert chapter == mock_result
    assert len(context.chapters) == 1
