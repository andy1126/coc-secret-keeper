from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger("coc.llm")


def setup_logging() -> None:
    """Configure coc.llm logger with console and file handlers.

    Idempotent: skips if handlers already attached (prevents duplicates on Streamlit rerun).
    """
    if logger.handlers:
        return

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "coc.log"),
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text for log readability."""
    s = str(text)
    return s[:max_len] + "..." if len(s) > max_len else s


class CoCLLMLogger(CustomLogger):
    """litellm callback logger for CoC LLM interactions."""

    def log_pre_api_call(
        self, model: str, messages: list[dict[str, Any]], kwargs: dict[str, Any]
    ) -> None:
        summary = _truncate(str(messages[-1]["content"])) if messages else ""
        logger.info("LLM REQUEST  model=%s messages=%d last=%s", model, len(messages), summary)

    def log_success_event(
        self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        if kwargs.get("stream"):
            return  # Streaming chunks logged by agent after full response collected
        model = kwargs.get("model", "unknown")
        duration = round(end_time - start_time, 2) if isinstance(start_time, float) else "N/A"
        # Handle both litellm response objects and raw dicts
        try:
            content = response_obj.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            content = str(response_obj)
        logger.info(
            "LLM RESPONSE model=%s duration=%ss response=%s",
            model,
            duration,
            _truncate(content),
        )

    def log_failure_event(
        self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        model = kwargs.get("model", "unknown")
        duration = round(end_time - start_time, 2) if isinstance(start_time, float) else "N/A"
        error = kwargs.get("exception", response_obj)
        logger.error("LLM FAILURE  model=%s duration=%ss error=%s", model, duration, error)
