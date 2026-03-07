from unittest.mock import Mock
from agents.brainstorm import BrainstormAgent
from models.story_context import StoryContext


def test_brainstorm_agent_creation():
    mock_llm = Mock()
    agent = BrainstormAgent(llm=mock_llm)
    assert agent is not None
    assert agent.conversation_history == []


def test_extract_seed_from_json():
    mock_llm = Mock()
    agent = BrainstormAgent(llm=mock_llm)

    json_str = """{"theme": "调查", "era": "1920s"}"""
    result = agent._extract_seed(json_str)

    assert result["theme"] == "调查"
    assert result["era"] == "1920s"


def test_chat_maintains_history():
    mock_llm = Mock()
    mock_llm.call.return_value = "你想写什么主题的克苏鲁故事？"

    agent = BrainstormAgent(llm=mock_llm)
    context = StoryContext()

    agent.chat("我想写一个调查类的故事", context)

    assert len(agent.conversation_history) == 2  # user + assistant
    assert agent.conversation_history[0]["role"] == "user"
    assert agent.conversation_history[1]["role"] == "assistant"
    mock_llm.call.assert_called_once()
