from pathlib import Path

import pytest

from agents.prompt_loader import load_prompt_with_skills


def _setup(tmp_path: Path, base_content: str = "base prompt") -> str:
    """Create a base prompt file and return its path."""
    base = tmp_path / "base.md"
    base.write_text(base_content, encoding="utf-8")
    return str(base)


def test_no_skill_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert result == "base prompt"


def test_empty_skill_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert result == "base prompt"


def test_one_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "atmosphere.md").write_text("atmosphere content", encoding="utf-8")
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert result == "base prompt\n\n---\n\n## Skill: atmosphere\n\natmosphere content"


def test_multiple_skills_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "zen.md").write_text("zen content", encoding="utf-8")
    (skill_dir / "alpha.md").write_text("alpha content", encoding="utf-8")
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert "## Skill: alpha\n\nalpha content" in result
    assert "## Skill: zen\n\nzen content" in result
    assert result.index("alpha") < result.index("zen")


def test_empty_skill_file_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "empty.md").write_text("   \n  ", encoding="utf-8")
    (skill_dir / "real.md").write_text("real content", encoding="utf-8")
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert "empty" not in result
    assert "## Skill: real\n\nreal content" in result


def test_non_md_files_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "notes.txt").write_text("should be ignored", encoding="utf-8")
    (skill_dir / "data.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert result == "base prompt"


def test_underscore_replaced_in_skill_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "skills" / "writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "dark_atmosphere.md").write_text("dark", encoding="utf-8")
    monkeypatch.setattr("agents.prompt_loader.SKILLS_DIR", tmp_path / "skills")
    base_path = _setup(tmp_path)

    result = load_prompt_with_skills(base_path, "writer")

    assert "## Skill: dark atmosphere" in result
