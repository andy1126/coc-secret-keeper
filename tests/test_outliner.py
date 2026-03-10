from unittest.mock import Mock, patch
from agents.outliner import OutlinerAgent
from models.story_context import StoryContext
from models.schemas import (
    ChapterOutline,
    ConflictDesign,
    WorldSetting,
    Location,
    Entity,
    Character,
)


def test_outliner_creation():
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    assert agent is not None


def test_create_outline():
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查", "atmosphere": "悬疑"}
    context.world = None  # Would have world data

    mock_result = """
```json
{
  "chapters": [
    {"number": 1, "title": "神秘来信", "summary": "主角收到奇怪的信", "mood": "悬疑", "word_target": 3000, "foreshadowing": ["信上的符号"], "payoffs": []}
  ],
  "total_word_estimate": 25000,
  "narrative_arc": "渐进式恐怖"
}
```
"""

    with patch.object(agent, "_run_agent", return_value=mock_result):
        outline = agent.create_outline(context, target_chapters=6)

    assert len(outline) == 1
    assert isinstance(outline[0], ChapterOutline)


def test_create_outline_with_conflict_design():
    """Outliner should include conflict_design in task description."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext(seed={"theme": "调查", "target_chapters": 10})
    context.world = WorldSetting(
        era="1924",
        locations=[Location(name="图书馆", description="禁书")],
        entities=[Entity(name="奈亚", description="外神", influence="化身")],
        forbidden_knowledge="真相",
        rules=["规则"],
        characters=[
            Character(
                name="李教授",
                background="考古",
                personality="严谨",
                motivation="求知",
                arc="堕落",
                relationships=[],
            )
        ],
    )
    context.conflict_design = ConflictDesign(
        inner_conflict="渴望vs恐惧",
        outer_conflict="馆长阻止",
        inciting_incident="发现笔记",
        midpoint_reversal="盟友是邪教",
        all_is_lost="精神病院",
        dark_night_of_soul="怀疑自己",
        climax="直面仪式",
        resolution="真相掩埋",
    )

    mock_outline_json = """
```json
{
  "chapters": [
    {"number": 1, "title": "抵达", "summary": "来到小镇", "mood": "不安", "word_target": 3000, "foreshadowing": ["钟声"], "payoffs": [], "pov": "主角", "information_reveal": ["失踪案"], "twist": null, "subplot": null}
  ]
}
```
"""
    with patch.object(agent, "_run_agent", return_value=mock_outline_json) as mock_run:
        agent.create_outline(context, 10)

    task_desc = mock_run.call_args[0][0]
    assert "冲突" in task_desc or "conflict" in task_desc.lower()
