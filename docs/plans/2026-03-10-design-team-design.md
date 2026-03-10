# Design Team: Worldbuilder + Outliner Merge with Narrative Review

**Date**: 2026-03-10
**Status**: Approved

## Problem

Generated plots are too linear — mostly "protagonist goes somewhere, meets someone, encounters something." Root causes:

1. **Worldbuilder produces static scenery**: locations/characters/entities listed without hidden agendas, conflicts, or history
2. **Outliner plans linearly**: one-shot generation without structural tension analysis
3. **No feedback loop**: Worldbuilder → Outliner is one-way; outliner can't request richer world elements

## Solution

Merge the `world` and `outline` stages into a single `design` stage. Introduce a **NarrativeReviewer** agent that audits the combined output and routes feedback for iterative refinement.

## Architecture

```
Brainstorm (unchanged)
    ↓ context.seed
Design Team Stage (new)
    ┌─────────────────────────────────────┐
    │  Worldbuilder ──→ Outliner          │
    │       ↑               │             │
    │       │               ↓             │
    │       └── NarrativeReviewer ──→ User│
    └─────────────────────────────────────┘
    ↓ context.world + context.outline
Writer ↔ Reviewer (unchanged)
```

### Iteration Flow

1. Worldbuilder generates world (with secrets/tensions/timeline)
2. Outliner generates outline (with pov/information_reveal/twist/subplot)
3. NarrativeReviewer audits both
4. If major issues found, routes feedback by `target` field:
   - `target="world"` or `"both"` → rebuild world, then rebuild outline
   - `target="outline"` → rebuild outline only
5. Max 2 auto-iteration rounds; then present to user with remaining issues
6. User feedback triggers a full new cycle

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

### NarrativeReviewer Output

```python
class NarrativeIssue(BaseModel):
    dimension: str    # one of 6 review dimensions
    severity: str     # "minor" | "major"
    description: str
    suggestion: str
    target: str       # "world" | "outline" | "both"

class NarrativeReviewResult(BaseModel):
    passed: bool
    issues: list[NarrativeIssue]
    strengths: list[str]
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

### Stage List

Before: `brainstorm → world → outline → writing → review → complete` (6 stages)
After: `brainstorm → design → writing → review → complete` (5 stages)

### Design Stage Layout

- Single "Generate" button + chapter count slider
- Progress indicators for each sub-step (world building, outlining, narrative review rounds)
- Three tabs for results: World Setting, Story Outline, Review Notes
- World tab shows new fields (secrets, tensions, timeline) in addition to existing content
- Outline tab shows new fields (pov, info reveal, twist, subplot) per chapter
- Review tab shows NarrativeReviewer assessment and any remaining minor issues
- Unified feedback input for regeneration (no need to target world vs outline separately)

### No Backward Compatibility

Old save files with `"world"` / `"outline"` stages are not supported. Save/load follows new schema only.

## File Changes

| File | Change |
|------|--------|
| `models/schemas.py` | Add `Secret`, `Tension`, `TimelineEvent`, `NarrativeIssue`, `NarrativeReviewResult`; extend `WorldSetting` and `ChapterOutline` |
| `prompts/worldbuilder.md` | Add guidance and examples for secrets/tensions/timeline |
| `prompts/outliner.md` | Add guidance for pov/information_reveal/twist/subplot |
| `prompts/narrative_reviewer.md` | New prompt defining 6 review dimensions |
| `agents/narrative_reviewer.py` | New agent implementing narrative review |
| `agents/worldbuilder.py` | Adapt `_extract_world()` for new fields |
| `agents/outliner.py` | Adapt `_extract_outline()` for new fields |
| `agents/design_team.py` | New orchestration: Worldbuilder → Outliner → Reviewer loop |
| `app.py` | Remove `render_world_stage()` + `render_outline_stage()`, add `render_design_stage()`; update stage list |
| `config.yaml` | Add `narrative_reviewer` LLM config |

## Out of Scope

- Writer/Reviewer stage changes
- Old save file backward compatibility
