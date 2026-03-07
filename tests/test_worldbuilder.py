import pytest
from unittest.mock import Mock, patch
from agents.worldbuilder import WorldbuilderAgent
from models.story_context import StoryContext
from models.schemas import WorldSetting


def test_worldbuilder_creation():
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    assert agent is not None


def test_build_world():
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)

    context = StoryContext(seed={
        "theme": "调查",
        "era": "1920年代",
        "atmosphere": "心理恐怖"
    })

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

    with patch.object(agent, '_run_agent', return_value=mock_result):
        world = agent.build_world(context)

    assert isinstance(world, WorldSetting)
    assert "阿卡姆" in world.era
