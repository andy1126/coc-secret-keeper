# 冲突架构师重构：三区 + 自由节拍 + 多线冲突

## Context

当前 `ConflictDesign` 使用固定的 8 节拍结构（inner_conflict, outer_conflict, inciting_incident, midpoint_reversal, all_is_lost, dark_night_of_soul, climax, resolution），每个故事都被迫套进同一个戏剧弧线模板。Prompt 中内在冲突只列了 3 种范式。这导致生成的故事在结构和冲突类型上高度雷同。

**目标**：引入"三区 + 自由节拍 + 多线冲突"架构，让每个故事的冲突结构真正独特。

## 方案概述

用 3 个叙事区域（Setup 铺垫 / Crucible 熔炉 / Aftermath 余波）替代固定 8 节拍。区域内节拍数量和内容由 LLM 自由生成。同时引入多线冲突（2-4 条线索，从 7 种冲突类型中选择）和叙事策略描述。

新 `ConflictDesign` 结构：
```python
class ConflictThread(BaseModel):
    name: str          # 线索名称
    thread_type: str   # epistemic/ontological/moral/relational/survival/cosmic/societal
    description: str   # 描述
    stakes: str        # 风险

class DramaticBeat(BaseModel):
    name: str          # 节拍名称（故事专属）
    description: str   # 具体内容
    threads: list[str] # 推进哪些冲突线索

class StoryZone(BaseModel):
    zone: str                   # setup/crucible/aftermath
    beats: list[DramaticBeat]   # 该区域的节拍

class ConflictDesign(BaseModel):
    narrative_strategy: str          # 叙事策略
    threads: list[ConflictThread]    # 2-4 条冲突线索
    zones: list[StoryZone]           # 3 个区域
    tension_shape: str               # 张力曲线描述
    thematic_throughline: str        # 主题贯穿线
```

## 实现步骤

### Step 1: 更新 Schema (`models/schemas.py`)

新增 `ConflictThread`、`DramaticBeat`、`StoryZone` 三个模型。替换 `ConflictDesign` 的 8 个固定字段为新字段。

添加 `model_validator(mode="before")` 处理向后兼容：检测旧格式（含 `inner_conflict` 字段），自动迁移到新格式：
- `inner_conflict` + `outer_conflict` → 2 条 threads
- `inciting_incident` → setup zone 的 beat
- `midpoint_reversal`, `all_is_lost`, `dark_night_of_soul`, `climax` → crucible zone 的 beats
- `resolution` → aftermath zone 的 beat

**文件**: `models/schemas.py` L53-61

### Step 2: 重写冲突架构师 Prompt (`prompts/conflict_architect.md`)

完整重写，包含：
- 叙事策略指引（自由描述，给出多样化的示例但明确"不要照抄"）
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
- `_extract_conflict()`（L22-32）：适配新 schema（ConflictThread/StoryZone 嵌套结构）
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

同时更新第 16 行的输入说明。

**文件**: `prompts/outliner.md` L16, L49

### Step 5: 更新 Outliner Agent (`agents/outliner.py`)

L84-89 的 `conflict_section` 格式化文字更新：从"将8个戏剧节拍映射到章节"改为"按三区结构安排章节"。

**文件**: `agents/outliner.py` L84-89

### Step 6: 更新叙事审查员 Prompt (`prompts/narrative_reviewer.md`)

- `reversal_space` 维度（L22-24）：从检查 `midpoint_reversal` 改为检查"crucible 区是否含反转节拍"
- `character_agency` 维度（L32-34）：从检查 `dark_night_of_soul` 改为检查"crucible 区是否含主动选择节拍"
- 新增维度或合并：检查"冲突线索利用率"（threads 是否都在节拍中被推进）

**文件**: `prompts/narrative_reviewer.md` L22-24, L32-34

### Step 7: 更新 UI (`app.py`)

**侧边栏** (L92-95)：
- 从 `inner_conflict[:30]` / `outer_conflict[:30]` 改为显示 `narrative_strategy[:50]` 和线索数

**冲突标签页** `_render_conflict_tab()` (L468-491)：
- 显示叙事策略为标题
- 冲突线索以卡片列表展示（名称 + 类型 + 描述 + 风险）
- 三个区域以 expander 展示，每个区域内列出节拍
- 张力曲线和主题贯穿线展示

**文件**: `app.py` L92-95, L468-491

### Step 8: 更新测试

所有构造 `ConflictDesign` 的测试需要更新为新格式：

- `tests/test_schemas.py` L113-124: `test_conflict_design_creation` 用新字段
- `tests/test_conflict_architect.py` L59-60, L83-84, L98-100: mock JSON 响应和断言
- `tests/test_outliner.py` L47-72: `test_create_outline_with_conflict_design`
- `tests/test_design_team.py` L43-45: `_make_conflict()` helper
- `tests/test_narrative_reviewer.py` L39-41: context 构造

新增测试：
- `test_conflict_design_backward_compat`: 验证旧格式自动迁移
- `test_conflict_thread_types`: 验证 thread_type 枚举
- `test_story_zone_structure`: 验证 3 区域结构

**文件**: `tests/test_schemas.py`, `tests/test_conflict_architect.py`, `tests/test_outliner.py`, `tests/test_design_team.py`, `tests/test_narrative_reviewer.py`

## 关键设计决策

1. **为什么是 3 区而不是完全自由？** — 3 区（setup/crucible/aftermath）映射到所有已知叙事传统（西方三幕、起承转结、调查结构），JSON 提取可靠（总是 3 个区域），同时区域内节拍完全自由
2. **为什么引入 threads？** — 单线冲突是雷同的最大来源之一。多线冲突让故事可以交织不同类型的张力
3. **向后兼容** — 通过 model_validator 自动迁移旧格式，已保存的 session 不会报错
4. **Writer 不需改动** — Writer 只消费 ChapterOutline 的 key_beats，已完全解耦

## 验证方案

1. `uv run pytest tests/test_schemas.py` — 确认 schema 变更和向后兼容
2. `uv run pytest tests/test_conflict_architect.py` — 确认冲突生成流程
3. `uv run pytest tests/test_outliner.py` — 确认大纲生成适配新冲突结构
4. `uv run pytest tests/test_design_team.py` — 确认设计团队协调流程
5. `uv run pytest tests/test_narrative_reviewer.py` — 确认叙事审查适配
6. `uv run pytest tests/` — 全量回归
7. `uv run streamlit run app.py` — 手动验证 UI 渲染和端到端生成
