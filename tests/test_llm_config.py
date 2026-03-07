import os
from llm.config import load_config


def test_config_loading():
    config = load_config("config.yaml")
    assert config.llm is not None
    assert "default_provider" in config.llm


def test_provider_override_from_env():
    os.environ["COC_OPENAI_API_KEY"] = "test-key"
    config = load_config("config.yaml")
    assert config.llm["providers"]["openai"]["api_key"] == "test-key"
    del os.environ["COC_OPENAI_API_KEY"]
