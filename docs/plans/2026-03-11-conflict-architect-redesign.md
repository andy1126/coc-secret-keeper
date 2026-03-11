# 冲突架构师重构：三区 + 自由节拍 + 多线冲突

## Context

当前 `ConflictDesign` 使用固定的 8 节拍结构（inner_conflict, outer_conflict, inciting_incident, midpoint_reversal, all_is_lost, dark_night_of_soul, climax, resolution），每个故事都被迫套进同一个戏剧弧线模板。Prompt 中内在冲突只列了 3 种范式。这导致生成的故事在结构和冲突类型上高度雷同。

**目标**：引入"三区 + 自由节拍 + 多线冲突"架构，让每个故事的冲突结构真正独特。

## 方案概述

用 3 个叙事区域（Setup 铺垫 / Crucible 熔炉 / Aftermath 余波）替代固定 8 节拍。区域内节拍数量和内容由 LLM 自由生成。同时引入多线冲突（2-4 条线索，从 7 种冲突类型中选择）和叙事策略描述。

新 `ConflictDesign` 结构：
```python
from typing import Literal

THREAD_TYPE = Literal[
    "epistemic", "ontological", "moral",
    "relational", "survival", "cosmic", "societal",
]

ZONE_TYPE = Literal["setup", "crucible", "aftermath"]

class ConflictThread(BaseModel):
    name: str          # 线索名称
    thread_type: THREAD_TYPE   # 严格枚举，7 种冲突类型
    description: str   # 描述
    stakes: str        # 风险

class DramaticBeat(BaseModel):
    name: str          # 节拍名称（故事专属）
    description: str   # 具体内容
    threads: list[str] # 推进哪些冲突线索

class StoryZone(BaseModel):
    zone: ZONE_TYPE             # 严格枚举，3 种区域
    beats: list[DramaticBeat]   # 该区域的节拍

class ConflictDesign(BaseModel):
    narrative_strategy: str          # 叙事策略
    threads: list[ConflictThread]    # 2-4 条冲突线索
    zones: list[StoryZone]           # 3 个区域
    tension_shape: str               # 张力曲线描述
    thematic_throughline: str        # 主题贯穿线

    @model_validator(mode="after")
    def validate_structure(self):
        """验证结构约束：线索数 2-4，区域恰好 3 个且不重复。"""
        if not (2 <= len(self.threads) <= 4):
            raise ValueError(f"threads 数量需 2-4，实际 {len(self.threads)}")
        zone_names = [z.zone for z in self.zones]
        if sorted(zone_names) != ["aftermath", "crucible", "setup"]:
            raise ValueError(f"zones 必须恰好包含 setup/crucible/aftermath，实际 {zone_names}")
        return self
```

## 实现步骤

### Step 1: 更新 Schema (`models/schemas.py`)

新增 `ConflictThread`、`DramaticBeat`、`StoryZone` 三个模型。替换 `ConflictDesign` 的 8 个固定字段为新字段。

**类型约束**（review 补充）：
- `ConflictThread.thread_type` 使用 `Literal` 而非 `str`，确保 LLM 输出非法类型时 Pydantic 报错
- `StoryZone.zone` 使用 `Literal["setup", "crucible", "aftermath"]`
- `ConflictDesign` 添加 `model_validator(mode="after")` 验证：
  - `threads` 长度 2-4
  - `zones` 恰好 3 个且各不重复

**向后兼容**：添加 `model_validator(mode="before")` 处理旧格式。检测旧格式（含 `inner_conflict` 字段），自动迁移到新格式：
- `inner_conflict` + `outer_conflict` → 2 条 threads
- `inciting_incident` → setup zone 的 beat
- `midpoint_reversal`, `all_is_lost`, `dark_night_of_soul`, `climax` → crucible zone 的 beats
- `resolution` → aftermath zone 的 beat
- 自动填充 `narrative_strategy`、`tension_shape`、`thematic_throughline` 为占位文本

**文件**: `models/schemas.py` L53-61

### Step 2: 重写冲突架构师 Prompt (`prompts/conflict_architect.md`)

完整重写，包含：
- 叙事策略指引（自由描述，给出 2-3 个**完整的**不同风格示例，然后明确"以上仅为示例，不要照抄，根据故事特点自行设计"）
- 7 种冲突类型详细说明（epistemic, ontological, moral, relational, survival, cosmic, societal），每种配有克苏鲁特色解释
- 三区设计指引：
  - Setup（约 20-30%）：2-4 个节拍，建立世界和冲突种子
  - Crucible（约 50-60%）：4-8 个节拍，至少含 1 个反转和 1 个主动选择
  - Aftermath（约 10-20%）：1-3 个节拍，代价与余韵
- 张力曲线指引（给出多种形状：锯齿形、慢炖、双峰、假分解后真恐惧等，明确"不要每次都用单调递增"）
- 新的 JSON 输出格式

**文件**: `prompts/conflict_architect.md`

### Step 3: 更新冲突架构师 Agent (`agents/conflict_architect.py`)

- `design_conflicts()` 中的 `generate_desc`（L84-108）：更新 JSON 模板为新格式
- `_extract_conflict()`（L22-32）：适配新 schema（ConflictThread/StoryZone 嵌套结构）。添加防御性处理：
  - `beats` 中 `threads` 字段如果是单个字符串，自动包装为 `[str]`
  - `zones` 如果缺少某个区域，用空 beats 补全
  - 记录 warning 日志但不抛异常，让 Pydantic validator 做最终校验
- 自我评估步骤（L118-136）：更新评估标准为：
  1. 冲突线索是否交织？（不同线索的节拍是否交替出现？）
  2. 熔炉区是否包含反转？
  3. 主角是否有主动选择（而非被动遭遇）？
  4. 张力曲线是否有变化（非单调递增）？
  5. 余波区是否体现代价（而非简单收束）？
- 精炼步骤（L141-162）：更新 JSON 模板

**文件**: `agents/conflict_architect.py`

### Step 4: 更新 Outliner Prompt (`prompts/outliner.md`)

将第 49 行的固定 8 节拍映射指引替换为区域映射：
- "将 setup 区的节拍映射到前 20-30% 的章节"
- "将 crucible 区的节拍映射到中间 50-60% 的章节"
- "将 aftermath 区的节拍映射到最后 10-20% 的章节"
- "多个节拍可以落在同一章，一个复杂节拍可以跨越多章"
- "确保不同冲突线索的节拍交替出现"

同时更新第 16 行的输入说明：从"冲突设计（如有，请以此作为故事骨架安排章节——将戏剧节拍映射到具体章节）"改为"冲突设计（如有，按三区结构安排章节——将各区域的节拍映射到章节，注意冲突线索交织）"。

**文件**: `prompts/outliner.md` L16, L49

### Step 5: 更新 Outliner Agent (`agents/outliner.py`)

**conflict_section 格式化**（L84-89）：
- 引导文字从"将8个戏剧节拍映射到章节"改为"按三区结构安排章节"
- **关键改动**（review 补充）：不直接 `json.dumps(model_dump())`，而是构建人类可读的结构化文本。新结构嵌套较深（zones → beats → threads），直接 dump JSON 对 LLM 不友好。改为按区域分段展示：

```python
def _format_conflict_for_prompt(conflict: ConflictDesign) -> str:
    lines = [f"叙事策略: {conflict.narrative_strategy}"]
    lines.append(f"主题贯穿线: {conflict.thematic_throughline}")
    lines.append(f"张力曲线: {conflict.tension_shape}")
    lines.append("")
    lines.append("冲突线索:")
    for t in conflict.threads:
        lines.append(f"  - {t.name} ({t.thread_type}): {t.description} [风险: {t.stakes}]")
    lines.append("")
    zone_labels = {"setup": "铺垫区", "crucible": "熔炉区", "aftermath": "余波区"}
    for zone in conflict.zones:
        lines.append(f"【{zone_labels.get(zone.zone, zone.zone)}】")
        for beat in zone.beats:
            thread_tags = ", ".join(beat.threads)
            lines.append(f"  · {beat.name}: {beat.description} → [{thread_tags}]")
    return "\n".join(lines)
```

**文件**: `agents/outliner.py` L84-89

### Step 6: 更新叙事审查员 Prompt + Agent

**Prompt** (`prompts/narrative_reviewer.md`)：
- `reversal_space` 维度（L22-24）：从检查 `midpoint_reversal` 改为检查"crucible 区是否含反转节拍"
- `character_agency` 维度（L32-34）：从检查 `dark_night_of_soul` 改为检查"crucible 区是否含主动选择节拍"
- 新增维度或合并：检查"冲突线索利用率"（threads 是否都在节拍中被推进）

**Agent** (`agents/narrative_reviewer.py`)（review 补充）：
- `review_narrative()` L85 的 `conflict_dict = context.conflict_design.model_dump()` 不需要改动——`model_dump()` 会自动序列化新结构
- L94-95 将新结构 JSON 传给 LLM，但需要同步更新 L100-106 的审查维度描述文本，使其与新 prompt 一致（当前硬编码了"是否至少有一个中段反转"等旧表述）

**文件**: `prompts/narrative_reviewer.md` L22-24, L32-34; `agents/narrative_reviewer.py` L100-106

### Step 7: 更新 UI (`app.py`)

**侧边栏** (L92-95)：
- 从 `inner_conflict[:30]` / `outer_conflict[:30]` 改为显示 `narrative_strategy[:50]` 和线索数

**冲突标签页** `_render_conflict_tab()` (L468-491)：
- 显示叙事策略为标题
- 冲突线索以卡片列表展示（名称 + 类型 + 描述 + 风险）
- 三个区域以 expander 展示，每个区域内列出节拍
- 张力曲线和主题贯穿线展示

**文件**: `app.py` L92-95, L468-491

### Step 8: 确认 `design_team.py` 无需改动

（review 补充）已审查 `agents/design_team.py`，该文件：
- 调用 `conflict_architect.design_conflicts(context)` — 接口不变
- 调用 `reviewer.review_narrative(context)` — 接口不变
- `format_issues()` 只格式化 `NarrativeIssue`（dimension/severity/description/suggestion）— 与 ConflictDesign 无关
- 迭代循环中根据 `issue.target` 路由到不同 agent — 逻辑不变

**结论**：`agents/design_team.py` 无需代码改动。

### Step 9: 更新测试

所有构造 `ConflictDesign` 的测试需要更新为新格式：

- `tests/test_schemas.py` L113-124: `test_conflict_design_creation` 用新字段
- `tests/test_conflict_architect.py` L59-60, L83-84, L98-100: mock JSON 响应和断言
- `tests/test_outliner.py` L70-79: `test_create_outline_with_conflict_design` 中的 ConflictDesign 构造
- `tests/test_design_team.py` L42-52: `_make_conflict()` helper
- `tests/test_narrative_reviewer.py` L39-48: `_make_full_context()` 中的 ConflictDesign 构造

新增测试：
- `test_conflict_design_backward_compat`: 验证旧格式（含 inner_conflict 等 8 字段的 dict）经 `model_validate` 自动迁移为新格式
- `test_conflict_thread_types`: 验证 `thread_type` 的 `Literal` 约束——合法值通过，非法值抛 `ValidationError`
- `test_story_zone_structure`: 验证 3 区域约束——缺少区域 / 重复区域 / 多余区域均抛错
- `test_conflict_design_thread_count`: 验证线索数量约束——0/1/5 条 threads 均抛错
- `test_story_context_roundtrip_with_new_conflict`（review 补充）: 构建含新 ConflictDesign 的 StoryContext，执行 `to_dict()` → `from_dict()` 往返，确认数据完整
- `test_story_context_load_legacy_conflict`（review 补充）: 模拟旧存档中 conflict_design 为 8 字段 dict，经 `StoryContext.from_dict()` 加载后自动迁移为新结构

**文件**: `tests/test_schemas.py`, `tests/test_conflict_architect.py`, `tests/test_outliner.py`, `tests/test_design_team.py`, `tests/test_narrative_reviewer.py`

## 关键设计决策

1. **为什么是 3 区而不是完全自由？** — 3 区（setup/crucible/aftermath）映射到所有已知叙事传统（西方三幕、起承转结、调查结构），JSON 提取可靠（总是 3 个区域），同时区域内节拍完全自由
2. **为什么引入 threads？** — 单线冲突是雷同的最大来源之一。多线冲突让故事可以交织不同类型的张力
3. **向后兼容** — 通过 model_validator 自动迁移旧格式，已保存的 session 不会报错。迁移路径覆盖两个入口：LLM JSON 响应解析 + 存档文件 `from_dict()` 加载
4. **Writer 不需改动** — Writer 只消费 ChapterOutline 的 key_beats，已完全解耦
5. **design_team.py 不需改动** — 只调用 agent 公开接口，不直接访问 ConflictDesign 字段
6. **类型约束使用 Literal** — `thread_type` 和 `zone` 使用 `Literal` 而非 `str`，在 Pydantic 层做严格校验，避免 LLM 输出非法值时静默通过
7. **Outliner 使用人类可读格式传递冲突设计** — 新结构嵌套较深，直接 `json.dumps(model_dump())` 对 LLM 不友好，改为按区域分段的结构化文本

## 验证方案

1. `uv run pytest tests/test_schemas.py` — 确认 schema 变更、类型约束和向后兼容
2. `uv run pytest tests/test_conflict_architect.py` — 确认冲突生成流程
3. `uv run pytest tests/test_outliner.py` — 确认大纲生成适配新冲突结构
4. `uv run pytest tests/test_design_team.py` — 确认设计团队协调流程
5. `uv run pytest tests/test_narrative_reviewer.py` — 确认叙事审查适配
6. `uv run pytest tests/` — 全量回归
7. `uv run mypy .` — 类型检查（Literal 类型应被正确推断）
8. `uv run streamlit run app.py` — 手动验证 UI 渲染和端到端生成
9. 手动测试：加载旧存档文件 → 确认自动迁移 → 冲突设计 tab 正常显示

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| LLM 输出非法 `thread_type` 值 | `Literal` 校验 + `run_with_retry` 重试 |
| LLM 输出不完整的 zones（如缺少 aftermath） | `_extract_conflict()` 中补全缺失 zone |
| 嵌套 JSON 导致 LLM 结构错误率升高 | prompt 中给完整示例 + `_extract_conflict()` 做 normalization |
| 旧存档加载失败 | `model_validator(mode="before")` 兜底 + 集成测试覆盖 |
| Outliner 收到过长的冲突描述 | 使用人类可读格式替代 raw JSON dump |
