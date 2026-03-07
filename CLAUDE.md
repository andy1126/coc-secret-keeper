# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --extra dev

# Run the app
uv run streamlit run app.py

# Lint & format
uv run ruff check .
uv run black --check .

# Type check
uv run mypy .

# Run all tests
uv run pytest tests/

# Run a single test file
uv run pytest tests/test_brainstorm.py

# Run a specific test
uv run pytest tests/test_brainstorm.py::test_function_name -v
```

## Architecture

**Pipeline**: Brainstorm → Worldbuilder → Outliner → Writer ↔ Reviewer → Export

- **app.py** — Streamlit entry point. Single-page app with 6 stages, sidebar progress, session-state persistence. Renders per-stage UI and orchestrates agent calls.
- **agents/** — 5 agents. BrainstormAgent uses direct `LLM.call()` for multi-turn conversation (CrewAI loses history between turns). All others use CrewAI `Agent/Task/Crew` pattern with `crew.kickoff()`.
- **models/story_context.py** — `StoryContext` is the shared mutable state passed through all agents (seed dict → WorldSetting → ChapterOutline[] → chapters[] → review_notes[]).
- **models/schemas.py** — Pydantic models: Character, Entity, WorldSetting, ChapterOutline, ReviewIssue.
- **llm/** — Provider abstraction. `config.py` loads YAML + env overrides (priority: env > config.yaml > UI). `provider.py` creates CrewAI `LLM` instances. `logging.py` provides litellm callback logging.
- **prompts/** — Markdown system prompts for each agent, all Cthulhu-mythos focused.

## LLM Configuration

Per-agent provider assignment in `config.yaml`. Two provider types: `anthropic_compatible` and `openai_compatible`. Environment variable overrides follow pattern `COC_{PROVIDER_NAME}_{FIELD}` (e.g., `COC_ANTHROPIC_API_API_KEY`).

## Review Mechanism

Writer → Reviewer loop: minor issues auto-revise (up to 3 rounds), major issues escalate to user with accept/custom-guide/ignore options. Final review checks foreshadowing payoffs, character arcs, atmosphere consistency, ending-opening echo.

## Conventions

- **Line length**: 100 (Black + Ruff)
- **Type checking**: MyPy strict mode
- **Language**: Chinese in UI text, prompts, and user-facing strings; English in code and comments
- **Commit style**: `type: description` (e.g., `feat: ...`, `fix: ...`, `chore: ...`)
- All agents extract structured JSON from LLM responses using regex (```json blocks with raw JSON fallback)
