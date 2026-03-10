from typing import Any
from crewai import LLM


def create_llm(
    type: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> LLM:
    """Create LLM instance based on provider type."""
    api_key = api_key or None

    if type == "anthropic_compatible":
        return LLM(
            model=f"anthropic/{model or 'claude-sonnet-4-6-20250514'}",
            api_key=api_key,
            base_url=base_url,
            max_tokens=8000,
            **kwargs,
        )
    elif type == "openai_compatible":
        return LLM(
            model=f"openai/{model or 'gpt-4o'}",
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
    else:
        raise ValueError(f"Unknown provider type: {type}")


def get_llm_for_agent(config: dict[str, Any]) -> LLM:
    """Create LLM from agent config."""
    return create_llm(
        type=config["type"],
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        model=config.get("model"),
    )


def get_litellm_stream_params(config: dict[str, Any]) -> dict[str, Any]:
    """Build litellm.completion() params for streaming from agent config."""
    if config["type"] == "anthropic_compatible":
        model = f"anthropic/{config.get('model') or 'claude-sonnet-4-6-20250514'}"
        params: dict[str, Any] = {"model": model, "max_tokens": 8000, "stream": True}
    elif config["type"] == "openai_compatible":
        model = f"openai/{config.get('model') or 'gpt-4o'}"
        params = {"model": model, "stream": True}
    else:
        raise ValueError(f"Unknown provider type: {config['type']}")

    if config.get("api_key"):
        params["api_key"] = config["api_key"]
    if config.get("base_url"):
        params["base_url"] = config["base_url"]
    return params
