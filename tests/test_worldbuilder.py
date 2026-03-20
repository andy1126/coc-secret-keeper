from unittest.mock import Mock, patch
from agents.worldbuilder import WorldbuilderAgent
from models.story_context import StoryContext
from models.schemas import WorldSetting, ResearchQuestion


def test_worldbuilder_creation() -> None:
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    assert agent is not None


def test_build_world() -> None:
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)

    context = StoryContext(seed={"theme": "调查", "era": "1920年代", "atmosphere": "心理恐怖"})

    # Mock the crew result
    mock_result = """
```json
{
  "era": "1924年，马萨诸塞州阿卡姆镇",
  "locations": ["密斯卡托尼克大学图书馆", "废弃的教堂"],
  "entities": [{"name": "奈亚拉托提普", "description": "外神", "influence": "化身行走人间"}],
  "forbidden_knowledge": "人类的历史只有几千年",
  "rules": ["直视古神会导致疯狂"],
  "characters": [{"name": "李教授", "background": "考古学", "personality": "严谨", "motivation": "求知", "arc": "堕落", "relationships": []}]
}
```
"""

    with patch.object(agent, "_run_agent", return_value=mock_result):
        world = agent.build_world(context)

    assert isinstance(world, WorldSetting)
    assert "阿卡姆" in world.era


def test_generate_questions() -> None:
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    context = StoryContext(seed={"theme": "调查", "era": "1920年代", "atmosphere": "心理恐怖"})

    mock_result = """
```json
{
  "questions": [
    {"topic": "genre", "question": "调查类克苏鲁的经典叙事模式？"},
    {"topic": "psychology", "question": "面对不可名状恐惧的心理反应？"},
    {"topic": "history", "question": "1920年代新英格兰的社会状况？"},
    {"topic": "dramaturgy", "question": "如何在调查叙事中设计递增冲突？"}
  ]
}
```
"""
    with patch.object(agent, "_run_agent", return_value=mock_result):
        questions = agent.generate_questions(context)

    assert len(questions) == 4
    assert isinstance(questions[0], ResearchQuestion)
    assert questions[0].topic == "genre"
    assert len(context.research_questions) == 4


def test_build_world_with_new_fields() -> None:
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    context = StoryContext(seed={"theme": "调查", "era": "1920年代", "atmosphere": "心理恐怖"})

    mock_result = """
```json
{
  "era": "1924年，阿卡姆镇",
  "locations": [{"name": "图书馆", "description": "藏有禁书"}],
  "entities": [{"name": "奈亚拉托提普", "description": "外神", "influence": "化身"}],
  "forbidden_knowledge": "人类渺小",
  "rules": ["直视古神会疯狂"],
  "characters": [{"name": "李教授", "background": "考古", "personality": "严谨", "motivation": "求知", "arc": "堕落", "relationships": []}],
  "secrets": [{"content": "地下祭坛", "known_by": ["馆长"], "layer": 2}],
  "tensions": [{"parties": ["李教授", "馆长"], "nature": "秘密", "status": "潜伏"}],
  "timeline": [{"when": "1920年", "event": "前任馆长失踪", "consequences": "禁书区封锁"}]
}
```
"""
    with patch.object(agent, "_run_agent", return_value=mock_result):
        world = agent.build_world(context)

    assert len(world.secrets) == 1
    assert world.secrets[0].layer == 2
    assert len(world.tensions) == 1
    assert len(world.timeline) == 1
