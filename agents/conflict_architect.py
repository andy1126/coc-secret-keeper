import json
import logging
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ConflictDesign

logger = logging.getLogger("coc.llm")


class ConflictArchitectAgent:
    """Agent for designing dramatic conflict structure with self-iteration."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/conflict_architect.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_conflict(self, text: str) -> ConflictDesign:
        """Extract conflict design from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)
        if data:
            # Handle nested structure if wrapped in a key
            if "conflict_design" in data:
                data = data["conflict_design"]
            self._normalize_conflict_data(data)
            return ConflictDesign(**data)
        raise ValueError("Could not extract conflict design from response")

    @staticmethod
    def _normalize_conflict_data(data: dict) -> None:
        """Normalize LLM output quirks before Pydantic validation."""
        # Normalize beats.threads: string → [string]
        for zone in data.get("zones", []):
            for beat in zone.get("beats", []):
                if isinstance(beat.get("threads"), str):
                    beat["threads"] = [beat["threads"]]

        # Ensure all 3 zones exist
        existing_zones = {z.get("zone") for z in data.get("zones", [])}
        for required in ("setup", "crucible", "aftermath"):
            if required not in existing_zones:
                logger.warning("Missing zone '%s', adding empty placeholder", required)
                data.setdefault("zones", []).append({"zone": required, "beats": []})

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Conflict Architect",
            goal="Design compelling dramatic conflict structures",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted conflict design",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        logger.info("ConflictArchitectAgent: crew.kickoff() starting")
        result = str(crew.kickoff())
        logger.info("ConflictArchitectAgent: crew.kickoff() done (%d chars)", len(result))
        return result

    def design_conflicts(
        self, context: StoryContext, feedback: str | None = None
    ) -> ConflictDesign:
        """Design dramatic conflict structure with 1-round self-iteration.

        3 LLM calls: generate → self-evaluate → refine.
        """
        world_dict = context.world.model_dump() if context.world else {}
        research_text = ""
        if context.research_notes:
            research_text = f"""
研究笔记:
{json.dumps([n.model_dump() for n in context.research_notes], ensure_ascii=False, indent=2)}
"""

        feedback_section = ""
        if feedback:
            feedback_section = f"""
审查反馈（请根据以下反馈重新设计冲突）:
{feedback}
"""

        # Step 1: Generate initial conflict design
        generate_desc = f"""
基于以下信息，设计故事的多线冲突结构。

故事种子:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

世界设定:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}
{research_text}
{feedback_section}

请设计完整的冲突结构，选择 2-4 种冲突类型编织线索，用三区（setup/crucible/aftermath）组织节拍。
输出JSON格式:
```json
{{
  "narrative_strategy": "一句话叙事策略",
  "threads": [
    {{
      "name": "线索名称",
      "thread_type": "epistemic/ontological/moral/relational/survival/cosmic/societal",
      "description": "线索描述",
      "stakes": "风险描述"
    }}
  ],
  "zones": [
    {{
      "zone": "setup",
      "beats": [
        {{"name": "节拍名称", "description": "具体内容", "threads": ["推进的线索名称"]}}
      ]
    }},
    {{
      "zone": "crucible",
      "beats": [...]
    }},
    {{
      "zone": "aftermath",
      "beats": [...]
    }}
  ],
  "tension_shape": "张力曲线形状描述",
  "thematic_throughline": "主题贯穿线"
}}
```
"""
        from agents.json_utils import run_with_retry

        initial_design = run_with_retry(
            lambda: self._run_agent(generate_desc),
            self._extract_conflict,
            label="ConflictArchitectAgent.initial",
        )

        # Step 2: Self-evaluate
        eval_desc = f"""
请评估以下冲突设计的质量：

{json.dumps(initial_design.model_dump(), ensure_ascii=False, indent=2)}

评估标准：
1. 冲突线索是否交织？（不同线索的节拍是否交替出现，而非各自独立？）
2. 熔炉区是否包含反转？（反转是否有铺垫区的伏笔支撑？）
3. 主角是否有主动选择？（而非被动遭遇一连串事件？）
4. 张力曲线是否有变化？（非单调递增？）
5. 余波区是否体现代价？（而非简单收束？）

请输出JSON格式:
```json
{{
  "evaluation": "整体评估",
  "improvements": ["具体改进建议1", "具体改进建议2"]
}}
```
"""
        eval_result = self._run_agent(eval_desc)

        # Step 3: Refine based on self-evaluation
        refine_desc = f"""
基于以下自我评估，优化冲突设计。

原始设计:
{json.dumps(initial_design.model_dump(), ensure_ascii=False, indent=2)}

自我评估:
{eval_result}

请输出优化后的完整冲突设计，JSON格式同上（narrative_strategy, threads, zones, tension_shape, thematic_throughline）。
```json
{{
  "narrative_strategy": "...",
  "threads": [...],
  "zones": [...],
  "tension_shape": "...",
  "thematic_throughline": "..."
}}
```
"""
        refined_design = run_with_retry(
            lambda: self._run_agent(refine_desc),
            self._extract_conflict,
            label="ConflictArchitectAgent.refined",
        )

        context.conflict_design = refined_design
        return refined_design
