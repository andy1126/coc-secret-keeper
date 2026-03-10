from unittest.mock import Mock, patch
from agents.brainstorm import BrainstormAgent
from llm.provider import get_litellm_stream_params
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


def _make_chunks(texts: list[str]) -> list[Mock]:
    """Build a list of mock streaming chunks."""
    chunks = []
    for text in texts:
        chunk = Mock()
        chunk.choices = [Mock()]
        chunk.choices[0].delta = Mock()
        chunk.choices[0].delta.content = text
        chunks.append(chunk)
    return chunks


@patch("agents.brainstorm.litellm")
def test_chat_stream_yields_chunks(mock_litellm):
    chunks = _make_chunks(["你好", "，", "世界"])
    mock_litellm.completion.return_value = chunks

    agent = BrainstormAgent(llm=Mock())
    context = StoryContext()
    params = {"model": "anthropic/test", "stream": True}

    result = list(agent.chat_stream("hi", context, params))

    assert result == ["你好", "，", "世界"]
    mock_litellm.completion.assert_called_once()


@patch("agents.brainstorm.litellm")
def test_chat_stream_builds_messages(mock_litellm):
    mock_litellm.completion.return_value = _make_chunks(["ok"])

    agent = BrainstormAgent(llm=Mock())
    agent.conversation_history = [{"role": "user", "content": "prev"}]
    context = StoryContext()
    params = {"model": "anthropic/test", "stream": True}

    list(agent.chat_stream("new msg", context, params))

    call_kwargs = mock_litellm.completion.call_args
    messages = call_kwargs.kwargs["messages"]
    # system + 2 user history entries + seed context
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "prev"}
    assert messages[2] == {"role": "user", "content": "new msg"}
    assert "故事种子" in messages[3]["content"]


def test_finalize_stream_updates_history_and_seed():
    agent = BrainstormAgent(llm=Mock())
    context = StoryContext()

    response = '这是回复\n```json\n{"theme": "恐怖", "era": "1920s"}\n```'
    agent.finalize_stream(response, context)

    assert len(agent.conversation_history) == 1
    assert agent.conversation_history[0]["role"] == "assistant"
    assert agent.conversation_history[0]["content"] == response
    assert context.seed["theme"] == "恐怖"
    assert context.seed["era"] == "1920s"


def test_get_litellm_stream_params_anthropic():
    config = {
        "type": "anthropic_compatible",
        "api_key": "sk-test",
        "base_url": "https://api.example.com",
    }
    params = get_litellm_stream_params(config)

    assert params["model"].startswith("anthropic/")
    assert params["stream"] is True
    assert params["max_tokens"] == 8000
    assert params["api_key"] == "sk-test"
    assert params["base_url"] == "https://api.example.com"


def test_get_litellm_stream_params_openai():
    config = {"type": "openai_compatible", "model": "gpt-4o-mini"}
    params = get_litellm_stream_params(config)

    assert params["model"] == "openai/gpt-4o-mini"
    assert params["stream"] is True
    assert "max_tokens" not in params
    assert "api_key" not in params
