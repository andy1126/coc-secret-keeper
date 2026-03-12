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

    def _find_best_json_block(self, text: str, required_keys: set[str]) -> dict | None:
        """Scan all JSON blocks in text, return the one with most required keys."""
        import re
        from agents.json_utils import _try_parse_json

        best: dict | None = None
        best_score = 0

        for m in re.finditer(r"```json\s*([\s\S]*?)\s*```", text):
            parsed = _try_parse_json(m.group(1).strip())
            if parsed:
                score = len(required_keys & parsed.keys())
                if score > best_score:
                    best = parsed
                    best_score = score

        return best if best_score > 0 else None

    def _extract_conflict(self, text: str) -> ConflictDesign:
        """Extract conflict design from agent response."""
        from agents.json_utils import extract_json_object

        data = extract_json_object(text)
        if data:
            # Handle nested structure if wrapped in a key
            if "conflict_design" in data:
                data = data["conflict_design"]
            # If first extraction doesn't contain key fields, rescan for better block
            required = {"narrative_strategy", "threads"}
            if not required.issubset(data.keys()):
                better = self._find_best_json_block(text, required)
                if better:
                    data = better
            self._normalize_conflict_data(data)
            return ConflictDesign(**data)
        raise ValueError("Could not extract conflict design from response")

    @staticmethod
    def _normalize_conflict_data(data: dict) -> None:
        """Normalize LLM output quirks before Pydantic validation."""
        # A. Flatten zones nested format (LLM may output it)
        if "zones" in data and "beats" not in data:
            flat_beats = []
            for zone_obj in data.pop("zones"):
                zone_name = zone_obj.get("zone", "setup")
                for beat in zone_obj.get("beats", []):
                    beat["zone"] = zone_name
                    flat_beats.append(beat)
            data["beats"] = flat_beats

        # B. beat.threads string → list
        for beat in data.get("beats", []):
            if isinstance(beat.get("threads"), str):
                beat["threads"] = [beat["threads"]]

        # C. Ensure all 3 zones have at least one beat
        existing_zones = {b.get("zone") for b in data.get("beats", [])}
        for required in ("setup", "crucible", "aftermath"):
            if required not in existing_zones:
                logger.warning("Missing zone '%s' in beats, adding placeholder", required)
                data.setdefault("beats", []).append(
                    {
                        "zone": required,
                        "name": f"（{required}待补充）",
                        "description": "待补充",
                        "threads": [],
                    }
                )

        # D. thread_type Chinese → English aliases
        type_aliases = {
            "认知": "epistemic",
            "存在": "ontological",
            "道德": "moral",
            "关系": "relational",
            "生存": "survival",
            "宇宙": "cosmic",
            "社会": "societal",
        }
        for thread in data.get("threads", []):
            t = thread.get("thread_type", "")
            if t in type_aliases:
                thread["thread_type"] = type_aliases[t]

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

请设计完整的冲突结构，选择 1-6 种冲突类型编织线索，用三区（setup/crucible/aftermath）组织节拍。
⚠️ 必须包含所有 5 个顶层字段: narrative_strategy, threads, beats, tension_shape, thematic_throughline
输出JSON格式:
```json
{{
  "narrative_strategy": "一句话叙事策略",
  "threads": [
    {{
      "name": "求知之祸",
      "thread_type": "epistemic",
      "description": "渴望真相 vs 恐惧疯狂",
      "stakes": "理智崩溃"
    }}
  ],
  "beats": [
    {{"zone": "setup", "name": "发现笔记", "description": "发现失踪教授的笔记", "threads": ["求知之祸"]}},
    {{"zone": "crucible", "name": "盟友背叛", "description": "可信赖的盟友其实是邪教成员", "threads": ["求知之祸"]}},
    {{"zone": "crucible", "name": "直面仪式", "description": "直面古神仪式现场", "threads": ["求知之祸"]}},
    {{"zone": "aftermath", "name": "真相掩埋", "description": "真相被掩埋", "threads": ["求知之祸"]}}
  ],
  "tension_shape": "慢炖型：长时间不安积累后猛然爆发",
  "thematic_throughline": "知识即诅咒"
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

⚠️ 必须包含所有 5 个顶层字段: narrative_strategy, threads, beats, tension_shape, thematic_throughline
请输出优化后的完整冲突设计，JSON格式同上。
```json
{{
  "narrative_strategy": "...",
  "threads": [...],
  "beats": [
    {{"zone": "setup", "name": "...", "description": "...", "threads": ["..."]}},
    {{"zone": "crucible", "name": "...", "description": "...", "threads": ["..."]}},
    {{"zone": "aftermath", "name": "...", "description": "...", "threads": ["..."]}}
  ],
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
