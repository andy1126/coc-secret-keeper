import os
from llm.config import load_config, get_agent_config


def test_config_loading() -> None:
    config = load_config("config.yaml")
    assert config.llm is not None
    assert "default_provider" in config.llm
    for provider_config in config.llm["providers"].values():
        assert "type" in provider_config


def test_provider_override_from_env() -> None:
    os.environ["COC_OPENAI_API_API_KEY"] = "test-key"
    config = load_config("config.yaml")
    assert config.llm["providers"]["openai_api"]["api_key"] == "test-key"
    del os.environ["COC_OPENAI_API_API_KEY"]


def test_model_override_from_env() -> None:
    os.environ["COC_ANTHROPIC_API_MODEL"] = "claude-opus-4-6"
    config = load_config("config.yaml")
    assert config.llm["providers"]["anthropic_api"]["model"] == "claude-opus-4-6"
    del os.environ["COC_ANTHROPIC_API_MODEL"]


def test_get_agent_config_returns_type() -> None:
    config = load_config("config.yaml")
    agent_cfg = get_agent_config(config, "brainstorm")
    assert "type" in agent_cfg
    assert agent_cfg["type"] in ("openai_compatible", "anthropic_compatible")
