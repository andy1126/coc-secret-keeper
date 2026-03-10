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
    phases = []

    def progress(phase: str, status: str) -> None:
        if on_progress:
            on_progress(phase, status)

    # Phase 1: Planning & Questioning
    progress("research_questions", "running")
    worldbuilder.generate_questions(context)
    phases.append("research_questions")
    progress("research_questions", "done")

    # Phase 2: Multi-Source Research
    progress("research", "running")
    researcher.research(context)
    phases.append("research")
    progress("research", "done")

    # Phase 3: World Building + Conflict Design
    progress("world_building", "running")
    worldbuilder.build_world(context)
    phases.append("world_building")
    progress("world_building", "done")

    progress("conflict_design", "running")
    conflict_architect.design_conflicts(context)
    phases.append("conflict_design")
    progress("conflict_design", "done")

    # Phase 4: Outline + Review Loop
    progress("outline", "running")
    outliner.create_outline(context, target_chapters)
    phases.append("outline")
    progress("outline", "done")

    review = None
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
        review=review,
        iterations=iteration,
        phases_completed=phases,
    )
