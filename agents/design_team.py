"""Four-phase design team orchestration with iteration loop."""

import logging
from dataclasses import dataclass, field
from typing import Callable

from agents.narrative_reviewer import NarrativeReviewResult, NarrativeReviewerAgent
from agents.worldbuilder import WorldbuilderAgent
from agents.researcher import ResearcherAgent
from agents.conflict_architect import ConflictArchitectAgent
from agents.outliner import OutlinerAgent
from models.schemas import NarrativeIssue
from models.story_context import StoryContext

logger = logging.getLogger("coc.design_team")


def detect_resume_point(context: StoryContext) -> int:
    """Return the index of the first incomplete design phase (0-4), or 5 if all done.

    Waterfall check: if an earlier phase is missing, all later phases are re-run
    even if they appear populated (prevents inconsistent state).
    """
    if not context.research_questions:
        return 0
    if not context.research_notes:
        return 1
    if context.world is None:
        return 2
    if context.conflict_design is None:
        return 3
    if not context.outline:
        return 4
    return 5


@dataclass
class DesignResult:
    context: StoryContext
    review: NarrativeReviewResult
    iterations: int
    phases_completed: list[str] = field(default_factory=list)


def format_issues(issues: list[NarrativeIssue]) -> str:
    """Format narrative issues into feedback text for agents."""
    lines = []
    for i in issues:
        lines.append(f"- [{i.dimension}] {i.severity}: {i.description} → {i.suggestion}")
    return "\n".join(lines)


def run_design_team(
    context: StoryContext,
    worldbuilder: WorldbuilderAgent,
    researcher: ResearcherAgent,
    conflict_architect: ConflictArchitectAgent,
    outliner: OutlinerAgent,
    reviewer: NarrativeReviewerAgent,
    max_rounds: int = 2,
    on_progress: Callable[[str, str], None] | None = None,
) -> DesignResult:
    """Run the four-phase design team workflow.

    Phase 1: Worldbuilder generates research questions
    Phase 2: Researcher answers questions
    Phase 3: Worldbuilder builds world + Conflict Architect designs conflicts
    Phase 4: Outliner creates outline + NarrativeReviewer audits (with iteration)

    Args:
        context: StoryContext with seed (incl. target_chapters)
        worldbuilder: WorldbuilderAgent instance
        researcher: ResearcherAgent instance
        conflict_architect: ConflictArchitectAgent instance
        outliner: OutlinerAgent instance
        reviewer: NarrativeReviewerAgent instance
        max_rounds: Maximum iteration rounds for phase 4
        on_progress: Optional callback(phase_name, status) for UI progress
    """
    target_chapters = context.seed.get("target_chapters", 10)
    phases: list[str] = []
    resume_from = detect_resume_point(context)

    def progress(phase: str, status: str) -> None:
        if on_progress:
            on_progress(phase, status)

    # Phase 0: Planning & Questioning
    if resume_from <= 0:
        progress("research_questions", "running")
        worldbuilder.generate_questions(context)
        progress("research_questions", "done")
    else:
        progress("research_questions", "skipped")
    phases.append("research_questions")

    # Phase 1: Multi-Source Research
    if resume_from <= 1:
        progress("research", "running")
        researcher.research(context)
        progress("research", "done")
    else:
        progress("research", "skipped")
    phases.append("research")

    # Phase 2: World Building
    if resume_from <= 2:
        progress("world_building", "running")
        worldbuilder.build_world(context)
        progress("world_building", "done")
    else:
        progress("world_building", "skipped")
    phases.append("world_building")

    # Phase 3: Conflict Design
    if resume_from <= 3:
        progress("conflict_design", "running")
        conflict_architect.design_conflicts(context)
        progress("conflict_design", "done")
    else:
        progress("conflict_design", "skipped")
    phases.append("conflict_design")

    # Phase 4: Outline + Review Loop
    if resume_from <= 4:
        progress("outline", "running")
        outliner.create_outline(context, target_chapters)
        progress("outline", "done")
    else:
        progress("outline", "skipped")
    phases.append("outline")

    review: NarrativeReviewResult | None = None
    iteration = 0
    for iteration in range(max_rounds + 1):
        progress("review", "running")
        review = reviewer.review_narrative(context)
        progress("review", "done")

        if review.passed or iteration >= max_rounds:
            break

        major = review.get_major_issues()
        if not major:
            break

        world_issues = [i for i in major if i.target in ("world", "both")]
        conflict_issues = [i for i in major if i.target == "conflict"]
        outline_issues = [i for i in major if i.target == "outline"]

        if world_issues:
            progress("world_building", "running")
            worldbuilder.build_world(
                context,
                feedback=format_issues(world_issues + conflict_issues + outline_issues),
            )
            progress("world_building", "done")

            progress("conflict_design", "running")
            conflict_architect.design_conflicts(context, feedback=format_issues(major))
            progress("conflict_design", "done")

            progress("outline", "running")
            outliner.create_outline(context, target_chapters, feedback=format_issues(major))
            progress("outline", "done")
        elif conflict_issues:
            progress("conflict_design", "running")
            conflict_architect.design_conflicts(context, feedback=format_issues(conflict_issues))
            progress("conflict_design", "done")

            progress("outline", "running")
            outliner.create_outline(
                context,
                target_chapters,
                feedback=format_issues(conflict_issues + outline_issues),
            )
            progress("outline", "done")
        elif outline_issues:
            progress("outline", "running")
            outliner.create_outline(
                context, target_chapters, feedback=format_issues(outline_issues)
            )
            progress("outline", "done")

    return DesignResult(
        context=context,
        review=review,  # type: ignore[arg-type]
        iterations=iteration,
        phases_completed=phases,
    )
