# Design Team: Deep Research Story Design with Multi-Agent Collaboration

**Date**: 2026-03-10
**Status**: Approved (Rev 2)

## Problem

Generated plots are too linear — mostly "protagonist goes somewhere, meets someone, encounters something." Root causes:

1. **Worldbuilder produces static scenery**: locations/characters/entities listed without hidden agendas, conflicts, or history
2. **Outliner plans linearly**: one-shot generation without structural tension analysis
3. **No feedback loop**: Worldbuilder → Outliner is one-way; outliner can't request richer world elements
4. **No research phase**: world building relies entirely on LLM's generic knowledge, defaulting to cliche genre tropes
5. **No proactive conflict design**: dramatic structure is an afterthought, not a deliberate architectural decision

## Solution

Merge the `world` and `outline` stages into a single `design` stage. Introduce a multi-agent "Design Team" that follows a **"Plan → Research → Create → Review"** four-phase deep research workflow:

- **Researcher** gathers structured creative material (genre patterns, psychology, history, dramaturgy)
- **Conflict Architect** proactively designs dramatic structure before outlining
- **NarrativeReviewer** audits the combined output and routes feedback for iterative refinement

## Architecture

```
Brainstorm (modified: adds target_chapters to seed)
    ↓ context.seed (incl. target_chapters)
Design Team Stage
    ┌──────────────────────────────────────────────────┐
    │  Phase 1: Worldbuilder.generate_questions()      │
    │       ↓ research_questions                       │
    │  Phase 2: Researcher.research()                  │
    │       ↓ research_notes                           │
    │  Phase 3: Worldbuilder.build_world()             │
    │           ConflictArchitect.design_conflicts()   │
    │       ↓ world + conflict_design                  │
    │  Phase 4: Outliner.create_outline()              │
    │           NarrativeReviewer.review()              │
    │       ↑       │                                  │
    │       └───────┘ iterate (max 2 rounds)           │
    └──────────────────────────────────────────────────┘
    ↓ context.world + context.conflict_design + context.outline
Writer ↔ Reviewer (unchanged)
```

### Four-Phase Flow

**Phase 1 — Planning & Questioning**
- Worldbuilder analyzes seed, generates 4-6 research questions across dimensions: genre, psychology, history, dramaturgy
- Stored in `context.research_questions`

**Phase 2 — Multi-Source Research**
- Researcher (LLM-based, no external tools) answers each question with structured findings
- Output: `context.research_notes` with topic, findings, sources per question

**Phase 3 — World Building + Conflict Design**
- Worldbuilder builds world using seed + research_notes (with secrets/tensions/timeline)
- Conflict Architect designs dramatic structure using seed + world + research_notes
- Conflict Architect self-iterates 1 round (generate → self-evaluate → optimize)
- Output: `context.world` + `context.conflict_design`

**Phase 4 — Outline + Narrative Review**
- Outliner generates chapter outline using world + conflict_design as skeleton
- NarrativeReviewer audits everything; if major issues found, routes feedback:
  - `target="world"` or `"both"` → rebuild world → conflict architect → outliner
  - `target="conflict"` → rebuild conflict design → outliner
  - `target="outline"` → rebuild outline only
  - Researcher is NOT re-run (research notes depend on seed, which doesn't change)
- Max 2 auto-iteration rounds; then present to user

### Agent Roles

| Agent | Role | Analogy |
|-------|------|---------|
| Worldbuilder | Decompose seed into research questions; build world with research material | Lead Writer / Planner |
| Researcher | Systematically retrieve LLM knowledge on genre, psychology, history, dramaturgy | Research Assistant |
| Conflict Architect | Design core conflicts, character motivations, dramatic beats; self-iterate | Drama Consultant |
| Outliner | Arrange chapters using world + conflict design as skeleton | Story Architect |
| NarrativeReviewer | Audit narrative quality across 6 dimensions; route feedback | Quality Auditor |

## Schema Changes

### New Models

```python
class Secret(BaseModel):
    content: str          # secret content
    known_by: list[str]   # which characters know this
    layer: int            # depth (1=surface clue, 2=mid truth, 3=core truth)

class Tension(BaseModel):
    parties: list[str]    # involved characters/factions
    nature: str           # conflict type (interest, belief, secret, survival)
    status: str           # current state (latent, escalating, about to erupt)

class TimelineEvent(BaseModel):
    when: str             # time description
    event: str            # what happened
    consequences: str     # impact on current situation

class ResearchQuestion(BaseModel):
    topic: str            # "genre" / "psychology" / "history" / "dramaturgy"
    question: str         # specific question

class ResearchNote(BaseModel):
    topic: str            # corresponding research topic
    findings: str         # structured findings summary
    sources: list[str]    # reference sources (works, theories, etc.)

class ConflictDesign(BaseModel):
    inner_conflict: str         # protagonist's internal conflict (desire vs fear)
    outer_conflict: str         # main external conflict (opposing forces)
    inciting_incident: str      # inciting incident
    midpoint_reversal: str      # midpoint reversal
    all_is_lost: str            # all-is-lost moment
    dark_night_of_soul: str     # dark night of the soul
    climax: str                 # climax
    resolution: str             # resolution / denouement

class NarrativeIssue(BaseModel):
    dimension: str    # one of 6 review dimensions
    severity: str     # "minor" | "major"
    description: str
    suggestion: str
    target: str       # "world" | "conflict" | "outline" | "both"
```

### WorldSetting Additions

```python
class WorldSetting(BaseModel):
    # existing fields unchanged
    secrets: list[Secret]
    tensions: list[Tension]
    timeline: list[TimelineEvent]
```

### ChapterOutline Additions

```python
class ChapterOutline(BaseModel):
    # existing fields unchanged
    pov: str                       # whose perspective
    information_reveal: list[str]  # what reader learns this chapter
    twist: str | None              # reversal/surprise if any
    subplot: str | None            # subplot advanced if any
```

### StoryContext Additions

```python
class StoryContext(BaseModel):
    # existing fields unchanged
    research_questions: list[ResearchQuestion] = []
    research_notes: list[ResearchNote] = []
    conflict_design: ConflictDesign | None = None
```

### Seed Additions

```python
# context.seed now includes:
{
    # existing fields...
    "target_chapters": 10  # user-specified chapter count
}
```

## NarrativeReviewer: 6 Review Dimensions

| Dimension | Checks |
|-----------|--------|
| Tension sufficiency | Every 2-3 chapters have clear conflict driver; no "empty" chapters |
| Information asymmetry | Meaningful info gaps between reader and characters; secrets revealed at good pace |
| Reversal space | At least one mid-story and one climax reversal; reversals supported by earlier foreshadowing |
| Asset utilization | World locations/characters/entities/tensions actually used in outline; no "props" |
| Character agency | Plot driven by character choices → consequences, not passive encounters |
| Multi-thread weaving | At least one subplot exists; main and subplot intersect |

## UI Changes

### Brainstorm Stage

- `prompts/brainstorm.md` adds a question about story length / target chapters
- `required_keys` adds `"target_chapters"`
- Seed editor gains a chapter count slider

### Stage List

Before: `brainstorm → world → outline → writing → review → complete` (6 stages)
After: `brainstorm → design → writing → review → complete` (5 stages)

### Design Stage Layout

- Single "Generate" button (chapter count comes from seed)
- Progress indicators for each phase (research → world building → conflict design → outlining → narrative review)
- Four tabs for results: World Setting, Conflict Design, Story Outline, Review Notes
- World tab shows new fields (secrets, tensions, timeline)
- Conflict tab shows dramatic structure (inner/outer conflict, 6 dramatic beats)
- Outline tab shows new fields (pov, info reveal, twist, subplot) per chapter
- Review tab shows NarrativeReviewer assessment and remaining minor issues
- Unified feedback input for regeneration

### No Backward Compatibility

Old save files are not supported. Save/load follows new schema only.

## File Changes

| File | Change |
|------|--------|
| `models/schemas.py` | Add `Secret`, `Tension`, `TimelineEvent`, `ResearchQuestion`, `ResearchNote`, `ConflictDesign`, `NarrativeIssue`; extend `WorldSetting` and `ChapterOutline` |
| `models/story_context.py` | Add `research_questions`, `research_notes`, `conflict_design` fields |
| `prompts/brainstorm.md` | Add chapter count question |
| `prompts/worldbuilder.md` | Add research question generation guidance + secrets/tensions/timeline guidance |
| `prompts/researcher.md` | **New**: four-dimension research guidance |
| `prompts/conflict_architect.md` | **New**: conflict design + self-evaluation guidance |
| `prompts/outliner.md` | Add conflict_design as input; pov/twist/subplot guidance |
| `prompts/narrative_reviewer.md` | **New**: 6-dimension review with "conflict" target |
| `agents/worldbuilder.py` | Add `generate_questions()`; `build_world()` uses research_notes; `_extract_world()` for new fields |
| `agents/researcher.py` | **New**: LLM-based research agent |
| `agents/conflict_architect.py` | **New**: conflict design with 1-round self-iteration |
| `agents/narrative_reviewer.py` | **New**: narrative quality review |
| `agents/outliner.py` | `create_outline()` uses conflict_design; adapt for new fields |
| `agents/design_team.py` | **New**: four-phase orchestration + iteration loop |
| `app.py` | Remove `render_world_stage()` + `render_outline_stage()`; add `render_design_stage()`; update brainstorm for target_chapters; stage list to 5; settings adds new agents |
| `config.yaml` | Add `researcher`, `conflict_architect`, `narrative_reviewer` configs |

## Out of Scope

- Writer/Reviewer stage changes
- Old save file backward compatibility
- Web search integration (future enhancement: Researcher can be extended with CrewAI tools)
