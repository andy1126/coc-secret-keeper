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
  "inner_conflict": "渴望真相 vs 恐惧疯狂",
  "outer_conflict": "馆长阻止调查",
  "inciting_incident": "发现失踪教授的笔记",
  "midpoint_reversal": "盟友是邪教成员",
  "all_is_lost": "被关入精神病院",
  "dark_night_of_soul": "怀疑自己是否疯了",
  "climax": "直面古神仪式",
  "resolution": "真相被掩埋"
}
```
"""

    self_eval = """
```json
{
  "evaluation": "内外冲突呼应不够紧密",
  "improvements": ["让外在冲突直接威胁内在冲突"]
}
```
"""

    refined_design = """
```json
{
  "inner_conflict": "渴望真相 vs 恐惧疯狂——每一次发现都让他更接近真相也更接近崩溃",
  "outer_conflict": "馆长利用李教授的求知欲引导他完成仪式",
  "inciting_incident": "发现失踪教授的笔记，其中提到了自己的名字",
  "midpoint_reversal": "馆长并非阻止者而是引导者——李教授一直在被利用",
  "all_is_lost": "意识到自己的研究成果就是仪式的最后一环",
  "dark_night_of_soul": "选择：销毁研究（背叛一生追求）还是完成仪式（毁灭世界）",
  "climax": "试图销毁研究时发现知识已经改变了他的本质",
  "resolution": "知识无法被遗忘，他带着诅咒般的认知继续活着"
}
```
"""

    with patch.object(agent, "_run_agent", side_effect=[initial_design, self_eval, refined_design]):
        design = agent.design_conflicts(context)

    assert isinstance(design, ConflictDesign)
    assert "利用" in design.outer_conflict  # refined version
    assert context.conflict_design is design
