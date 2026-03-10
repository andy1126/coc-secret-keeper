# Design Team Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge worldbuilder + outliner into a single "design" stage with a 5-agent deep research workflow (Worldbuilder, Researcher, Conflict Architect, Outliner, NarrativeReviewer) to produce richer narrative structures.

**Architecture:** Four-phase flow: Plan → Research → Create → Review. Worldbuilder generates research questions; Researcher gathers material; Worldbuilder builds world + Conflict Architect designs dramatic beats (with 1-round self-iteration); Outliner generates outline; NarrativeReviewer audits with up to 2 iteration rounds.

**Tech Stack:** Python 3.12, Pydantic, CrewAI, Streamlit

**Design doc:** `docs/plans/2026-03-10-design-team-design.md`

---

### Task 1: Add new schema models

**Files:**
- Modify: `models/schemas.py`
- Test: `tests/test_schemas.py`

**Step 1: Write failing tests for all new models**

Add to `tests/test_schemas.py`:

```python
from models.schemas import (
    Secret, Tension, TimelineEvent,
    ResearchQuestion, ResearchNote, ConflictDesign, NarrativeIssue,
)


def test_secret_creation():
    secret = Secret(content="镇长是邪教领袖", known_by=["镇长", "牧师"], layer=2)
    assert secret.layer == 2
    assert len(secret.known_by) == 2


def test_tension_creation():
    tension = Tension(parties=["镇长", "调查员"], nature="秘密", status="潜伏")
    assert tension.nature == "秘密"


def test_timeline_event_creation():
    event = TimelineEvent(when="1920年春", event="矿坑坍塌", consequences="镇民恐慌")
    assert "矿坑" in event.event


def test_research_question_creation():
    q = ResearchQuestion(topic="genre", question="调查类克苏鲁的经典模式？")
    assert q.topic == "genre"


def test_research_note_creation():
    note = ResearchNote(
        topic="psychology",
        findings="面对不可名状恐惧时，人类会经历否认→恐惧→解离三阶段",
        sources=["《恐惧心理学》", "洛夫克拉夫特书信集"],
    )
    assert len(note.sources) == 2


def test_conflict_design_creation():
    cd = ConflictDesign(
        inner_conflict="渴望真相 vs 恐惧疯狂",
        outer_conflict="邪教组织阻止调查",
        inciting_incident="发现失踪教授的笔记",
        midpoint_reversal="可信赖的盟友其实是邪教成员",
        all_is_lost="被关入精神病院",
        dark_night_of_soul="开始怀疑自己是否真的疯了",
        climax="直面古神仪式现场",
        resolution="真相被掩埋，主角带着创伤离开",
    )
    assert "渴望" in cd.inner_conflict


def test_narrative_issue_creation():
    issue = NarrativeIssue(
        dimension="tension_sufficiency", severity="major",
        description="第3-5章缺乏冲突", suggestion="加入对抗", target="outline",
    )
    assert issue.target == "outline"


def test_narrative_issue_conflict_target():
    issue = NarrativeIssue(
        dimension="character_agency", severity="major",
        description="冲突设计被动", suggestion="重设内在冲突", target="conflict",
    )
    assert issue.target == "conflict"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_schemas.py::test_secret_creation tests/test_schemas.py::test_research_question_creation tests/test_schemas.py::test_conflict_design_creation -v`
Expected: FAIL with ImportError

**Step 3: Implement new models in schemas.py**

Add after `Entity` class, before `WorldSetting`:

```python
class Secret(BaseModel):
    content: str = Field(description="秘密内容")
    known_by: list[str] = Field(default_factory=list, description="知情角色")
    layer: int = Field(description="深度层级: 1=表面线索, 2=中层真相, 3=核心真相")


class Tension(BaseModel):
    parties: list[str] = Field(description="涉及角色/势力")
    nature: str = Field(description="冲突性质: 利益/信仰/秘密/生存")
    status: str = Field(description="当前状态: 潜伏/升温/即将爆发")


class TimelineEvent(BaseModel):
    when: str = Field(description="时间描述")
    event: str = Field(description="事件内容")
    consequences: str = Field(description="对当前局面的影响")


class ResearchQuestion(BaseModel):
    topic: str = Field(description="研究主题: genre/psychology/history/dramaturgy")
    question: str = Field(description="具体问题")


class ResearchNote(BaseModel):
    topic: str = Field(description="对应研究主题")
    findings: str = Field(description="研究发现摘要")
    sources: list[str] = Field(default_factory=list, description="参考来源")


class ConflictDesign(BaseModel):
    inner_conflict: str = Field(description="主角内在冲突")
    outer_conflict: str = Field(description="主要外在冲突")
    inciting_incident: str = Field(description="激励事件")
    midpoint_reversal: str = Field(description="中点转折")
    all_is_lost: str = Field(description="一无所有时刻")
    dark_night_of_soul: str = Field(description="灵魂暗夜")
    climax: str = Field(description="高潮")
    resolution: str = Field(description="解决/余韵")


class NarrativeIssue(BaseModel):
    dimension: str = Field(
        description="审查维度: tension_sufficiency/information_asymmetry/"
        "reversal_space/asset_utilization/character_agency/multi_thread"
    )
    severity: str = Field(description="严重程度: minor/major")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
    target: str = Field(description="修改目标: world/conflict/outline/both")
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: ALL PASS


---

### Task 2: Extend WorldSetting with new fields

**Files:**
- Modify: `models/schemas.py:24-48` (WorldSetting class)
- Test: `tests/test_schemas.py`

**Step 1: Write failing tests**

```python
def test_world_setting_with_new_fields():
    world = WorldSetting(
        era="1920年代",
        locations=[Location(name="阿卡姆镇", description="小镇")],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="真相", rules=["规则1"],
        characters=[Character(name="张三", background="学者", personality="好奇",
                              motivation="求知", arc="堕落", relationships=[])],
        secrets=[Secret(content="镇长是邪教领袖", known_by=["镇长"], layer=2)],
        tensions=[Tension(parties=["镇长", "调查员"], nature="秘密", status="潜伏")],
        timeline=[TimelineEvent(when="1920年春", event="矿坑坍塌", consequences="恐慌")],
    )
    assert len(world.secrets) == 1
    assert len(world.tensions) == 1
    assert len(world.timeline) == 1


def test_world_setting_new_fields_default_empty():
    world = WorldSetting(era="1920年代", locations=[], entities=[],
                         forbidden_knowledge="", rules=[], characters=[])
    assert world.secrets == []
    assert world.tensions == []
    assert world.timeline == []
```

**Step 2: Run tests to verify failure, then add fields**

Add to `WorldSetting` after `characters`:

```python
    secrets: list[Secret] = Field(default_factory=list, description="世界中的隐藏秘密")
    tensions: list[Tension] = Field(default_factory=list, description="势力/角色间的暗流")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="前史事件")
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_schemas.py -v`

---

### Task 3: Extend ChapterOutline with new fields

**Files:**
- Modify: `models/schemas.py:51-58` (ChapterOutline class)
- Test: `tests/test_schemas.py`

**Step 1: Write failing tests**

```python
def test_chapter_outline_with_new_fields():
    chapter = ChapterOutline(
        number=1, title="开端", summary="主角发现手稿", mood="悬疑", word_target=3000,
        foreshadowing=["符号"], payoffs=[],
        pov="主角", information_reveal=["失踪案"], twist="手稿伪造", subplot="牧师秘密",
    )
    assert chapter.pov == "主角"
    assert chapter.twist == "手稿伪造"


def test_chapter_outline_new_fields_defaults():
    chapter = ChapterOutline(number=1, title="开端", summary="摘要", mood="悬疑", word_target=3000)
    assert chapter.pov == ""
    assert chapter.information_reveal == []
    assert chapter.twist is None
    assert chapter.subplot is None
```

**Step 2: Add fields to ChapterOutline after `payoffs`**

```python
    pov: str = Field(default="", description="主要叙述视角")
    information_reveal: list[str] = Field(default_factory=list, description="本章揭示的信息")
    twist: str | None = Field(default=None, description="本章反转")
    subplot: str | None = Field(default=None, description="本章推进的副线")
```

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`

---

### Task 4: Extend StoryContext with new fields

**Files:**
- Modify: `models/story_context.py`
- Test: `tests/test_schemas.py`

**Step 1: Write failing test**

```python
from models.story_context import StoryContext
from models.schemas import ResearchQuestion, ResearchNote, ConflictDesign


def test_story_context_new_fields():
    ctx = StoryContext()
    assert ctx.research_questions == []
    assert ctx.research_notes == []
    assert ctx.conflict_design is None
```

**Step 2: Add fields to StoryContext**

In `models/story_context.py`, add imports and fields:

```python
from models.schemas import WorldSetting, ChapterOutline, ResearchQuestion, ResearchNote, ConflictDesign

class StoryContext(BaseModel):
    # existing fields...
    research_questions: list[ResearchQuestion] = Field(default_factory=list, description="研究问题")
    research_notes: list[ResearchNote] = Field(default_factory=list, description="研究笔记")
    conflict_design: ConflictDesign | None = Field(default=None, description="冲突设计")
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v`


---

### Task 5: Update WorldbuilderAgent — add generate_questions + new field extraction

**Files:**
- Modify: `agents/worldbuilder.py`
- Test: `tests/test_worldbuilder.py`

**Step 1: Write failing tests**

Add to `tests/test_worldbuilder.py`:

```python
from models.schemas import ResearchQuestion


def test_generate_questions():
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    context = StoryContext(seed={"theme": "调查", "era": "1920年代", "atmosphere": "心理恐怖"})

    mock_result = '''
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
'''
    with patch.object(agent, "_run_agent", return_value=mock_result):
        questions = agent.generate_questions(context)

    assert len(questions) == 4
    assert isinstance(questions[0], ResearchQuestion)
    assert questions[0].topic == "genre"
    assert len(context.research_questions) == 4


def test_build_world_with_new_fields():
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    context = StoryContext(seed={"theme": "调查", "era": "1920年代", "atmosphere": "心理恐怖"})

    mock_result = '''
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
'''
    with patch.object(agent, "_run_agent", return_value=mock_result):
        world = agent.build_world(context)

    assert len(world.secrets) == 1
    assert world.secrets[0].layer == 2
    assert len(world.tensions) == 1
    assert len(world.timeline) == 1
```

**Step 2: Implement changes in worldbuilder.py**

1. Add imports: `Secret, Tension, TimelineEvent, ResearchQuestion`
2. Add `generate_questions(context)` method — calls `_run_agent` with a task asking for research questions, extracts `ResearchQuestion` list, stores in `context.research_questions`
3. Update `build_world()` — include `context.research_notes` in task description when available
4. Update `_extract_world()` — parse secrets, tensions, timeline from JSON

**Step 3: Run tests**

Run: `uv run pytest tests/test_worldbuilder.py -v`

---

### Task 6: Create ResearcherAgent

**Files:**
- Create: `agents/researcher.py`
- Create: `tests/test_researcher.py`

**Step 1: Write failing test**

```python
from unittest.mock import Mock, patch
from agents.researcher import ResearcherAgent
from models.story_context import StoryContext
from models.schemas import ResearchQuestion, ResearchNote


def test_researcher_creation():
    agent = ResearcherAgent(llm=Mock())
    assert agent is not None


def test_research():
    agent = ResearcherAgent(llm=Mock())
    context = StoryContext(
        seed={"theme": "调查", "era": "1920年代"},
        research_questions=[
            ResearchQuestion(topic="genre", question="调查类克苏鲁的经典模式？"),
            ResearchQuestion(topic="psychology", question="面对恐惧的心理反应？"),
        ],
    )

    mock_result = '''
```json
{
  "notes": [
    {
      "topic": "genre",
      "findings": "经典模式包括：渐进揭示、不可靠叙述者、知识即诅咒",
      "sources": ["《克苏鲁的呼唤》", "《敦威治恐怖事件》"]
    },
    {
      "topic": "psychology",
      "findings": "恐惧反应三阶段：否认、恐慌、解离",
      "sources": ["恐惧心理学研究"]
    }
  ]
}
```
'''
    with patch.object(agent, "_run_agent", return_value=mock_result):
        notes = agent.research(context)

    assert len(notes) == 2
    assert isinstance(notes[0], ResearchNote)
    assert notes[0].topic == "genre"
    assert len(context.research_notes) == 2
```

**Step 2: Implement researcher.py**

Standard CrewAI Agent/Task/Crew pattern. Key points:
- Loads `prompts/researcher.md`
- `research(context)` method reads `context.research_questions`, builds task description asking LLM to answer each question with structured findings
- Extracts `list[ResearchNote]` from JSON response
- Stores in `context.research_notes`

**Step 3: Run tests**

Run: `uv run pytest tests/test_researcher.py -v`

---

### Task 7: Create ConflictArchitectAgent

**Files:**
- Create: `agents/conflict_architect.py`
- Create: `tests/test_conflict_architect.py`

**Step 1: Write failing test**

```python
from unittest.mock import Mock, patch
from agents.conflict_architect import ConflictArchitectAgent
from models.story_context import StoryContext
from models.schemas import (
    WorldSetting, Location, Entity, Character, Secret, Tension, TimelineEvent,
    ConflictDesign, ResearchNote,
)


def _make_context_with_world():
    ctx = StoryContext(
        seed={"theme": "调查", "era": "1920年代", "target_chapters": 10},
        research_notes=[
            ResearchNote(topic="genre", findings="渐进揭示模式", sources=["《克苏鲁的呼唤》"]),
        ],
    )
    ctx.world = WorldSetting(
        era="1924年", locations=[Location(name="图书馆", description="禁书")],
        entities=[Entity(name="奈亚", description="外神", influence="化身")],
        forbidden_knowledge="真相", rules=["规则"],
        characters=[Character(name="李教授", background="考古", personality="严谨",
                              motivation="求知", arc="堕落", relationships=[])],
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

    initial_design = '''
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
'''

    self_eval = '''
```json
{
  "evaluation": "内外冲突呼应不够紧密",
  "improvements": ["让外在冲突直接威胁内在冲突"]
}
```
'''

    refined_design = '''
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
'''

    with patch.object(agent, "_run_agent", side_effect=[initial_design, self_eval, refined_design]):
        design = agent.design_conflicts(context)

    assert isinstance(design, ConflictDesign)
    assert "利用" in design.outer_conflict  # refined version
    assert context.conflict_design is design
```

**Step 2: Implement conflict_architect.py**

Key design:
- Loads `prompts/conflict_architect.md`
- `design_conflicts(context)` method:
  1. Call `_run_agent()` with seed + world + research_notes → initial ConflictDesign
  2. Call `_run_agent()` with initial design for self-evaluation → evaluation
  3. Call `_run_agent()` with initial design + evaluation → refined ConflictDesign
  4. Store refined design in `context.conflict_design`
- 3 LLM calls total (generate, evaluate, refine)

**Step 3: Run tests**

Run: `uv run pytest tests/test_conflict_architect.py -v`

---

### Task 8: Create NarrativeReviewerAgent

**Files:**
- Create: `agents/narrative_reviewer.py`
- Create: `tests/test_narrative_reviewer.py`

**Step 1: Write failing test**

```python
from unittest.mock import Mock, patch
from agents.narrative_reviewer import NarrativeReviewerAgent, NarrativeReviewResult
from models.story_context import StoryContext
from models.schemas import (
    WorldSetting, Location, Entity, Character, Secret, Tension, TimelineEvent,
    ChapterOutline, ConflictDesign, ResearchNote,
)


def _make_full_context():
    ctx = StoryContext(seed={"theme": "调查", "era": "1920年代", "target_chapters": 10})
    ctx.world = WorldSetting(
        era="1924年", locations=[Location(name="图书馆", description="禁书")],
        entities=[Entity(name="奈亚", description="外神", influence="化身")],
        forbidden_knowledge="真相", rules=["规则"],
        characters=[Character(name="李教授", background="考古", personality="严谨",
                              motivation="求知", arc="堕落", relationships=[])],
        secrets=[Secret(content="祭坛", known_by=["馆长"], layer=2)],
        tensions=[Tension(parties=["李教授", "馆长"], nature="秘密", status="潜伏")],
        timeline=[TimelineEvent(when="1920", event="失踪", consequences="封锁")],
    )
    ctx.conflict_design = ConflictDesign(
        inner_conflict="渴望vs恐惧", outer_conflict="馆长阻止",
        inciting_incident="发现笔记", midpoint_reversal="盟友是邪教",
        all_is_lost="精神病院", dark_night_of_soul="怀疑自己",
        climax="直面仪式", resolution="真相掩埋",
    )
    ctx.outline = [ChapterOutline(
        number=1, title="抵达", summary="来到小镇", mood="不安", word_target=3000,
        foreshadowing=["钟声"], payoffs=[], pov="主角",
        information_reveal=["失踪案"], twist=None, subplot=None,
    )]
    return ctx


def test_review_narrative_passed():
    agent = NarrativeReviewerAgent(llm=Mock())
    context = _make_full_context()

    mock_result = '```json\n{"passed": true, "issues": [], "strengths": ["张力充分"]}\n```'
    with patch.object(agent, "_run_agent", return_value=mock_result):
        result = agent.review_narrative(context)

    assert result.passed is True


def test_review_narrative_with_conflict_target():
    agent = NarrativeReviewerAgent(llm=Mock())
    context = _make_full_context()

    mock_result = '''
```json
{
  "passed": false,
  "issues": [{"dimension": "character_agency", "severity": "major",
              "description": "冲突被动", "suggestion": "重设", "target": "conflict"}],
  "strengths": []
}
```
'''
    with patch.object(agent, "_run_agent", return_value=mock_result):
        result = agent.review_narrative(context)

    assert result.passed is False
    assert result.get_major_issues()[0].target == "conflict"
```

**Step 2: Implement narrative_reviewer.py**

Standard CrewAI pattern. Key additions vs original design:
- `review_narrative(context)` now includes `conflict_design` in task description
- `NarrativeReviewResult` has helper methods: `get_major_issues()`, `get_minor_issues()`, `get_world_issues()`, `get_outline_issues()`, `get_conflict_issues()`

**Step 3: Run tests**

Run: `uv run pytest tests/test_narrative_reviewer.py -v`

---

### Task 9: Create design_team orchestration

**Files:**
- Create: `agents/design_team.py`
- Create: `tests/test_design_team.py`

**Step 1: Write failing tests**

```python
from unittest.mock import Mock
from agents.design_team import DesignResult, run_design_team
from agents.narrative_reviewer import NarrativeReviewResult
# ... helper factories for mock agents ...


def test_design_team_full_pipeline_passes():
    """Happy path: all 4 phases run, reviewer passes."""
    # Mock all 5 agents, verify call counts:
    # worldbuilder.generate_questions: 1
    # researcher.research: 1
    # worldbuilder.build_world: 1
    # conflict_architect.design_conflicts: 1
    # outliner.create_outline: 1
    # reviewer.review_narrative: 1


def test_design_team_iterates_on_outline_issue():
    """Outline-only issue: only outliner reruns."""
    # reviewer fails round 1 with target="outline", passes round 2
    # worldbuilder.build_world: 1 (not rebuilt)
    # conflict_architect.design_conflicts: 1 (not rebuilt)
    # outliner.create_outline: 2


def test_design_team_iterates_on_conflict_issue():
    """Conflict issue: conflict architect + outliner rerun."""
    # reviewer fails round 1 with target="conflict", passes round 2
    # worldbuilder.build_world: 1 (not rebuilt)
    # conflict_architect.design_conflicts: 2
    # outliner.create_outline: 2


def test_design_team_iterates_on_world_issue():
    """World issue: world + conflict + outline all rebuild."""
    # reviewer fails round 1 with target="world", passes round 2
    # worldbuilder.build_world: 2
    # conflict_architect.design_conflicts: 2
    # outliner.create_outline: 2


def test_design_team_max_iterations():
    """After 2 failed rounds, stops and returns."""
    # reviewer always fails
    # review_narrative call count: 3 (initial + 2 rounds)
```

Full test implementations follow the same pattern as original Task 10 but with expanded agent set.

**Step 2: Implement design_team.py**

```python
def run_design_team(context, worldbuilder, researcher, conflict_architect,
                    outliner, reviewer, max_rounds=2, on_progress=None):
    target_chapters = context.seed.get("target_chapters", 10)

    # Phase 1: Planning
    worldbuilder.generate_questions(context)

    # Phase 2: Research
    researcher.research(context)

    # Phase 3: World Building + Conflict Design
    worldbuilder.build_world(context)
    conflict_architect.design_conflicts(context)

    # Phase 4: Outline + Review Loop
    outliner.create_outline(context, target_chapters)

    for iteration in range(max_rounds + 1):
        review = reviewer.review_narrative(context)
        if review.passed or iteration >= max_rounds:
            break

        major = review.get_major_issues()
        if not major:
            break

        world_issues = [i for i in major if i.target in ("world", "both")]
        conflict_issues = [i for i in major if i.target == "conflict"]
        outline_issues = [i for i in major if i.target == "outline"]

        if world_issues:
            worldbuilder.build_world(context, feedback=format_issues(world_issues + conflict_issues + outline_issues))
            conflict_architect.design_conflicts(context, feedback=format_issues(major))
            outliner.create_outline(context, target_chapters, feedback=format_issues(major))
        elif conflict_issues:
            conflict_architect.design_conflicts(context, feedback=format_issues(conflict_issues))
            outliner.create_outline(context, target_chapters, feedback=format_issues(conflict_issues + outline_issues))
        elif outline_issues:
            outliner.create_outline(context, target_chapters, feedback=format_issues(outline_issues))

    return DesignResult(context=context, review=review, iterations=iteration)
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_design_team.py -v`


---

### Task 10: Update OutlinerAgent for conflict_design + new fields

**Files:**
- Modify: `agents/outliner.py`
- Test: `tests/test_outliner.py`

**Step 1: Write failing test**

```python
def test_create_outline_with_conflict_design():
    """Outliner should include conflict_design in task description."""
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext(seed={"theme": "调查", "target_chapters": 10})
    context.world = WorldSetting(era="1924", ...)
    context.conflict_design = ConflictDesign(
        inner_conflict="渴望vs恐惧", outer_conflict="馆长阻止",
        inciting_incident="发现笔记", midpoint_reversal="盟友是邪教",
        all_is_lost="精神病院", dark_night_of_soul="怀疑自己",
        climax="直面仪式", resolution="真相掩埋",
    )

    # Capture the task description passed to _run_agent
    with patch.object(agent, "_run_agent", return_value=mock_outline_json) as mock_run:
        agent.create_outline(context, 10)

    task_desc = mock_run.call_args[0][0]
    assert "conflict" in task_desc.lower() or "冲突" in task_desc
```

**Step 2: Update outliner.py**

- In `create_outline()`, add `context.conflict_design.model_dump()` to task description when available
- No changes needed to `_extract_outline()` — Pydantic handles new fields automatically

**Step 3: Run tests**

Run: `uv run pytest tests/test_outliner.py -v`

---

### Task 11: Write all prompts

**Files:**
- Modify: `prompts/brainstorm.md` — add chapter count question
- Modify: `prompts/worldbuilder.md` — add research question generation + secrets/tensions/timeline
- Create: `prompts/researcher.md` — four-dimension research guidance
- Create: `prompts/conflict_architect.md` — conflict design + self-evaluation
- Modify: `prompts/outliner.md` — add conflict_design input + pov/twist/subplot
- Create: `prompts/narrative_reviewer.md` — 6-dimension review

This is a prompt-only task with no code tests. Each prompt follows the existing pattern (Chinese instructions, JSON output format, few-shot examples where helpful).

Key prompt design notes:

**researcher.md**: Guide LLM to systematically search its knowledge across 4 dimensions. Output JSON with `notes` array of `{topic, findings, sources}`.

**conflict_architect.md**: Three-step process in one prompt:
1. Design initial conflict structure
2. Self-evaluation questions ("内外冲突是否呼应？每个节拍是否有因果链？")
3. Output refined design
For the self-iteration flow, the agent code handles 3 separate calls.

**narrative_reviewer.md**: Include `target: "conflict"` as a valid routing option. Check that conflict_design beats are properly mapped to outline chapters.

**Step 1: Write all prompts**


---

### Task 12: Update config.yaml and settings

**Files:**
- Modify: `config.yaml` — add `researcher`, `conflict_architect`, `narrative_reviewer`
- Modify: `app.py` line 900 — add new agents to `agent_names` list in `render_settings()`

**Step 1: Update config and settings**

---

### Task 13: Update app.py — brainstorm stage + design stage + stage routing

This is the largest task. See design doc for detailed UI layout.

**Files:**
- Modify: `app.py`

**Step 1: Update brainstorm stage**

- `VALID_STAGES = {"brainstorm", "design", "writing", "review", "complete"}`
- `required_keys` add `"target_chapters"`
- Seed editor add chapter count slider
- Transition button: `"进入故事设计"` → `stage = "design"`

**Step 2: Delete render_world_stage and render_outline_stage**

Remove both functions entirely.

**Step 3: Create render_design_stage**

New function with:
- Initial state: single "Generate" button (chapter count from seed)
- Generation: creates all 5 agents, calls `run_design_team()`
- Display: 4 tabs (世界设定 / 冲突设计 / 故事大纲 / 审查意见)
- Conflict tab: shows inner/outer conflict + 6 dramatic beats
- Action buttons: confirm / regenerate with feedback

**Step 4: Update main() routing and sidebar**

- Remove `world`/`outline` branches, add `design` branch
- Sidebar: update stage list, add conflict_design display

**Step 5: Run lint + type checks**

Run: `uv run ruff check . && uv run black --check .`

---

### Task 14: Manual smoke test

**Step 1: Run the app**

Run: `uv run streamlit run app.py`

**Step 2: Test full flow**

1. Brainstorm: verify chapter count question is asked, seed includes target_chapters
2. Design stage: click generate, verify 4-phase progress (questions → research → world+conflict → outline+review)
3. Verify 4 tabs: world (with secrets/tensions/timeline), conflict (dramatic beats), outline (with pov/twist/subplot), review notes
4. Test regeneration with feedback
5. Verify "确认并继续" transitions to writing stage
6. Verify writing stage still works with new outline fields

---

### Task 15: Final cleanup

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`

**Step 2: Run linters**

Run: `uv run ruff check . && uv run black --check .`

