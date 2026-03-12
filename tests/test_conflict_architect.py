from unittest.mock import Mock, patch
from agents.conflict_architect import ConflictArchitectAgent
from models.story_context import StoryContext
from models.schemas import (
    WorldSetting,
    Location,
    Entity,
    Character,
    Secret,
    Tension,
    TimelineEvent,
    ConflictDesign,
    ResearchNote,
)


def _make_context_with_world():
    ctx = StoryContext(
        seed={"theme": "调查", "era": "1920年代", "target_chapters": 10},
        research_notes=[
            ResearchNote(topic="genre", findings="渐进揭示模式", sources=["《克苏鲁的呼唤》"]),
        ],
    )
    ctx.world = WorldSetting(
        era="1924年",
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
        secrets=[Secret(content="祭坛", known_by=["馆长"], layer=2)],
        tensions=[Tension(parties=["李教授", "馆长"], nature="秘密", status="潜伏")],
        timeline=[TimelineEvent(when="1920", event="失踪", consequences="封锁")],
    )
    return ctx


def test_conflict_architect_creation():
    agent = ConflictArchitectAgent(llm=Mock())
    assert agent is not None


def test_design_conflicts_with_self_iteration():
    agent = ConflictArchitectAgent(llm=Mock())
    context = _make_context_with_world()

    initial_design = """
```json
{
  "narrative_strategy": "通过图书馆调查逐步揭示被操纵的真相",
  "threads": [
    {"name": "求知之祸", "thread_type": "epistemic", "description": "渴望真相 vs 恐惧疯狂", "stakes": "理智崩溃"},
    {"name": "邪教操控", "thread_type": "societal", "description": "馆长阻止调查", "stakes": "生命"}
  ],
  "beats": [
    {"zone": "setup", "name": "发现笔记", "description": "发现失踪教授的笔记", "threads": ["求知之祸"]},
    {"zone": "crucible", "name": "盟友背叛", "description": "盟友是邪教成员", "threads": ["邪教操控"]},
    {"zone": "crucible", "name": "直面仪式", "description": "直面古神仪式", "threads": ["求知之祸", "邪教操控"]},
    {"zone": "aftermath", "name": "真相掩埋", "description": "真相被掩埋", "threads": ["求知之祸"]}
  ],
  "tension_shape": "慢炖型",
  "thematic_throughline": "知识即诅咒"
}
```
"""

    self_eval = """
```json
{
  "evaluation": "线索交织不够紧密",
  "improvements": ["让馆长利用求知欲引导完成仪式"]
}
```
"""

    refined_design = """
```json
{
  "narrative_strategy": "通过图书馆调查逐步揭示被操纵的真相",
  "threads": [
    {"name": "求知之祸", "thread_type": "epistemic", "description": "每一次发现都更接近崩溃", "stakes": "理智"},
    {"name": "邪教操控", "thread_type": "societal", "description": "馆长利用李教授的求知欲引导他完成仪式", "stakes": "生命"}
  ],
  "beats": [
    {"zone": "setup", "name": "发现笔记", "description": "发现失踪教授的笔记，其中提到了自己的名字", "threads": ["求知之祸"]},
    {"zone": "crucible", "name": "引导者揭露", "description": "馆长并非阻止者而是引导者", "threads": ["求知之祸", "邪教操控"]},
    {"zone": "crucible", "name": "仪式之环", "description": "研究成果就是仪式的最后一环", "threads": ["求知之祸", "邪教操控"]},
    {"zone": "crucible", "name": "销毁抉择", "description": "销毁研究时发现知识已改变本质", "threads": ["求知之祸"]},
    {"zone": "aftermath", "name": "诅咒认知", "description": "知识无法被遗忘，带着诅咒般的认知继续活着", "threads": ["求知之祸"]}
  ],
  "tension_shape": "慢炖后爆发",
  "thematic_throughline": "知识即诅咒"
}
```
"""

    with patch.object(agent, "_run_agent", side_effect=[initial_design, self_eval, refined_design]):
        design = agent.design_conflicts(context)

    assert isinstance(design, ConflictDesign)
    assert "利用" in design.threads[1].description  # refined version
    assert context.conflict_design is design


def test_normalize_thread_type_aliases():
    """Chinese thread_type values are mapped to English."""
    data = {
        "narrative_strategy": "x",
        "threads": [
            {"name": "t1", "thread_type": "认知", "description": "d", "stakes": "s"},
            {"name": "t2", "thread_type": "道德", "description": "d", "stakes": "s"},
        ],
        "beats": [
            {"zone": "setup", "name": "a", "description": "a", "threads": ["t1"]},
            {"zone": "crucible", "name": "b", "description": "b", "threads": ["t1"]},
            {"zone": "aftermath", "name": "c", "description": "c", "threads": ["t1"]},
        ],
        "tension_shape": "x",
        "thematic_throughline": "x",
    }
    ConflictArchitectAgent._normalize_conflict_data(data)
    assert data["threads"][0]["thread_type"] == "epistemic"
    assert data["threads"][1]["thread_type"] == "moral"


def test_normalize_zones_to_flat_beats():
    """Old zones format in normalize_conflict_data gets flattened."""
    data = {
        "zones": [
            {"zone": "setup", "beats": [{"name": "a", "description": "a", "threads": ["t"]}]},
            {
                "zone": "crucible",
                "beats": [{"name": "b", "description": "b", "threads": ["t"]}],
            },
            {
                "zone": "aftermath",
                "beats": [{"name": "c", "description": "c", "threads": ["t"]}],
            },
        ],
        "threads": [],
    }
    ConflictArchitectAgent._normalize_conflict_data(data)
    assert "zones" not in data
    assert len(data["beats"]) == 3
    assert data["beats"][0]["zone"] == "setup"
    assert data["beats"][2]["zone"] == "aftermath"


def test_extract_conflict_finds_best_block():
    """When first JSON block doesn't have required keys, rescan finds better one."""
    agent = ConflictArchitectAgent(llm=Mock())

    text = """Here's the evaluation:
```json
{"evaluation": "ok", "improvements": []}
```

And here's the conflict design:
```json
{
  "narrative_strategy": "test",
  "threads": [
    {"name": "t", "thread_type": "moral", "description": "d", "stakes": "s"}
  ],
  "beats": [
    {"zone": "setup", "name": "a", "description": "a", "threads": ["t"]},
    {"zone": "crucible", "name": "b", "description": "b", "threads": ["t"]},
    {"zone": "aftermath", "name": "c", "description": "c", "threads": ["t"]}
  ],
  "tension_shape": "x",
  "thematic_throughline": "x"
}
```
"""
    design = agent._extract_conflict(text)
    assert isinstance(design, ConflictDesign)
    assert design.narrative_strategy == "test"
