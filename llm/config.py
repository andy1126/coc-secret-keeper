import os
import yaml  # type: ignore[import-untyped]
from dataclasses import dataclass
from typing import Any


@dataclass
class Config:
    llm: dict[str, Any]
    agents: dict[str, dict[str, str]]


def load_config(path: str = "config.yaml") -> Config:
    """Load config from YAML file with environment variable overrides."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Override with environment variables
    for provider_name, provider_config in data.get("llm", {}).get("providers", {}).items():
        env_key = os.getenv(f"COC_{provider_name.upper()}_API_KEY")
        if env_key:
            provider_config["api_key"] = env_key

        env_base_url = os.getenv(f"COC_{provider_name.upper()}_BASE_URL")
        if env_base_url:
            provider_config["base_url"] = env_base_url

        env_model = os.getenv(f"COC_{provider_name.upper()}_MODEL")
        if env_model:
            provider_config["model"] = env_model

    return Config(
        llm=data.get("llm", {}),
        agents=data.get("agents", {}),
    )


def get_agent_config(config: Config, agent_name: str) -> dict[str, Any]:
    """Get LLM config for a specific agent."""
    agent_cfg = config.agents.get(agent_name, {})
    provider_name = agent_cfg.get("provider", config.llm.get("default_provider", "openai"))
    provider_config = config.llm.get("providers", {}).get(provider_name, {})

    return {
        "provider": provider_name,
        "type": provider_config.get("type", "openai_compatible"),
        "api_key": provider_config.get("api_key"),
        "base_url": provider_config.get("base_url"),
        "model": provider_config.get("model"),
    }
