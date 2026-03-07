"""Shared JSON extraction utilities for agents."""

import json
import logging
import re

logger = logging.getLogger("coc.llm")


def _try_parse_json(raw: str) -> dict | None:
    """Try to parse JSON, with fallback cleanup for common LLM quirks."""
    # Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Cleanup: remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    # Cleanup: remove single-line comments
    cleaned = re.sub(r"//[^\n]*", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _find_json_by_braces(text: str) -> dict | None:
    """Find a JSON object using brace counting, handling strings correctly."""
    pos = 0
    while pos < len(text):
        start = text.find("{", pos)
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    result = _try_parse_json(candidate)
                    if result is not None:
                        return result
                    # This block failed, try next '{' after current start
                    pos = start + 1
                    break
        else:
            # Loop finished without depth reaching 0
            return None

    return None


def extract_json_object(text: str) -> dict | None:
    """Extract the first complete JSON object from LLM response text.

    Strategy:
    1. Try ```json ... ``` fenced block first (with cleanup for trailing commas/comments)
    2. Fallback: find '{' and use brace counting to locate the matching '}'
    3. Log the raw text on failure for debugging
    """
    # Strategy 1: fenced code block
    fence_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if fence_match:
        raw = fence_match.group(1).strip()
        result = _try_parse_json(raw)
        if result is not None:
            return result
        logger.warning("Fenced JSON block found but failed to parse, trying fallback")

    # Strategy 2: brace-counting scan
    result = _find_json_by_braces(text)
    if result is not None:
        return result

    # All strategies failed — log raw text for debugging
    logger.error("Failed to extract JSON from LLM response. Raw text:\n%s", text[:2000])
    return None
