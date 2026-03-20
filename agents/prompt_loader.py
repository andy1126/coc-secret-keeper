"""Shared prompt loading utilities for agents."""

import logging
from pathlib import Path

logger = logging.getLogger("coc.agents")

SKILLS_DIR = Path("prompts") / "skills"


def load_prompt_with_skills(base_prompt_path: str, agent_name: str) -> str:
    """Load an agent's base prompt and append all skill files from its skill folder.

    Args:
        base_prompt_path: Relative path to the base prompt file.
        agent_name: Agent identifier matching the skill subfolder name.

    Returns:
        Combined prompt string: base prompt + all skills appended with headers.
        If no skill folder exists or it is empty, returns the base prompt unchanged.
    """
    with open(base_prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    skill_dir = SKILLS_DIR / agent_name
    if not skill_dir.is_dir():
        return base_prompt

    skill_files = sorted(skill_dir.glob("*.md"))
    if not skill_files:
        return base_prompt

    skill_sections: list[str] = []
    for skill_file in skill_files:
        content = skill_file.read_text(encoding="utf-8").strip()
        if content:
            skill_name = skill_file.stem.replace("_", " ")
            skill_sections.append(f"## Skill: {skill_name}\n\n{content}")
            logger.debug("Loaded skill '%s' for agent '%s'", skill_file.name, agent_name)

    if not skill_sections:
        return base_prompt

    logger.info("Loaded %d skill(s) for agent '%s'", len(skill_sections), agent_name)
    return base_prompt + "\n\n---\n\n" + "\n\n".join(skill_sections)
