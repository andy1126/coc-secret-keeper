import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import NarrativeIssue

logger = logging.getLogger("coc.llm")


class NarrativeReviewResult:
    """Narrative review result with issue classification and routing."""

    def __init__(self, data: dict):
        self.passed = data.get("passed", False)
        self.issues = [NarrativeIssue(**i) for i in data.get("issues", [])]
        self.strengths = data.get("strengths", [])

    def get_major_issues(self) -> list[NarrativeIssue]:
        return [i for i in self.issues if i.severity == "major"]

    def get_minor_issues(self) -> list[NarrativeIssue]:
        return [i for i in self.issues if i.severity == "minor"]

    def get_world_issues(self) -> list[NarrativeIssue]:
        return [i for i in self.issues if i.target in ("world", "both")]

    def get_outline_issues(self) -> list[NarrativeIssue]:
        return [i for i in self.issues if i.target == "outline"]

    def get_conflict_issues(self) -> list[NarrativeIssue]:
        return [i for i in self.issues if i.target == "conflict"]


class NarrativeReviewerAgent:
    """Agent for auditing narrative quality across 6 dimensions."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        from agents.prompt_loader import load_prompt_with_skills

        return load_prompt_with_skills("prompts/narrative_reviewer.md", "narrative_reviewer")

    def _extract_review(self, text: str) -> NarrativeReviewResult:
        """Extract narrative review from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)
        if data:
            return NarrativeReviewResult(data)
        raise ValueError("Could not extract narrative review from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Narrative Reviewer",
            goal="Audit narrative quality and identify structural issues",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted narrative review",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("NarrativeReviewerAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("NarrativeReviewerAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def review_narrative(self, context: StoryContext) -> NarrativeReviewResult:
        """Review world + conflict design + outline across 6 narrative dimensions."""
        world_dict = context.world.model_dump() if context.world else {}
        conflict_dict = context.conflict_design.model_dump() if context.conflict_design else {}
        outline_dict = [ch.model_dump() for ch in context.outline]

        task_desc = f"""
请对以下故事设计进行叙事质量审查。

世界设定:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

冲突设计:
{json.dumps(conflict_dict, ensure_ascii=False, indent=2)}

章节大纲:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

请从以下7个维度进行审查：
1. tension_sufficiency（张力充分性）：每2-3章是否有明确的冲突驱动？有没有"空"章节？
2. information_asymmetry（信息不对称）：读者与角色之间是否有有意义的信息差？秘密揭示节奏是否合理？
3. reversal_space（反转空间）：熔炉区（crucible）是否包含至少一个反转节拍？反转是否有铺垫区伏笔支撑？
4. asset_utilization（资产利用率）：世界设定中的地点/角色/实体/暗流是否在大纲中实际使用？有没有"道具"？
5. character_agency（角色能动性）：熔炉区是否包含主角主动选择的节拍？剧情是否由选择→后果驱动？
6. multi_thread（多线编织）：是否至少有一条副线？主副线是否交汇？
7. thread_utilization（冲突线索利用率）：冲突设计中的所有线索是否都在节拍中被推进？各线索分布是否合理？

对每个发现的问题，请标注修改目标 target：
- "world"：需要修改世界设定
- "conflict"：需要修改冲突设计
- "outline"：需要修改大纲
- "both"：需要同时修改世界设定和大纲

输出JSON格式:
```json
{{
  "passed": true/false,
  "issues": [
    {{
      "dimension": "审查维度",
      "severity": "minor或major",
      "description": "问题描述",
      "suggestion": "修改建议",
      "target": "world/conflict/outline/both"
    }}
  ],
  "strengths": ["优点1", "优点2"]
}}
```

只有当存在 major 问题时 passed 才为 false。
"""
        from agents.json_utils import run_with_retry

        return run_with_retry(
            lambda: self._run_agent(task_desc),
            self._extract_review,
            label="NarrativeReviewerAgent",
        )
