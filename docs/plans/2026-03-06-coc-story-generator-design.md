# CoC Secret Keeper - Design Document

## Overview

A multi-agent Cthulhu-themed short/medium novel generation tool. Users brainstorm story ideas through a conversational interface, and a pipeline of AI agents collaboratively builds worldview, outline, chapters, and reviews to produce a coherent 8,000-30,000 字 Chinese story.

## Tech Stack

- **Language:** Python 3.11+
- **Agent Framework:** CrewAI
- **LLM Backends:** OpenAI-compatible + Anthropic (per-agent configurable)
- **Web UI:** Streamlit
- **Data Validation:** Pydantic
- **Config:** YAML + environment variables

## Architecture

### Pipeline

```
用户输入 (Brainstorm) → 世界观构建 → 故事大纲 → 章节写作 → 审核/修订
```

### 5 Agents (with merged responsibilities)

| Agent | 核心职责 | 合并职责 |
|-------|----------|----------|
| **Brainstorm** | 对话收集故事种子（主题、氛围、恐怖类型、时代） | + 角色构想收集 |
| **Worldbuilder** | 构建克苏鲁世界观（神话体系、地点、实体） | + 完整角色档案 + 洛夫克拉夫特神话体系校验 |
| **Outliner** | 分章节大纲（摘要、情绪曲线、字数分配） | + 伏笔埋设点与回收点规划 |
| **Writer** | 逐章撰写正文，保持连续性 | + 克苏鲁氛围渲染（感官细节、心理恐惧递进） |
| **Reviewer** | 审核一致性、氛围、节奏 | + 神话设定一致性检查 + 伏笔回收检查 |

### Shared State: StoryContext

All agents read from and write to a shared `StoryContext` object:

```python
class Character(BaseModel):
    name: str
    background: str
    personality: str
    motivation: str
    arc: str
    relationships: list[str]

class Entity(BaseModel):
    name: str
    description: str
    influence: str

class WorldSetting(BaseModel):
    era: str
    locations: list[str]
    entities: list[Entity]
    forbidden_knowledge: str
    rules: list[str]
    characters: list[Character]

class ChapterOutline(BaseModel):
    number: int
    title: str
    summary: str
    mood: str
    word_target: int
    foreshadowing: list[str]
    payoffs: list[str]

class StoryContext(BaseModel):
    seed: dict
    world: WorldSetting
    outline: list[ChapterOutline]
    chapters: list[str]
    review_notes: list[str]
```

## Review Mechanism

### Classification

| 检查项 | 分类 | 处理方式 |
|--------|------|----------|
| 措辞/语法/节奏 | 小问题 | 自动回传 Writer 修订，最多 3 轮 |
| 氛围不足/恐惧递进断裂 | 小问题 | 自动修订 |
| 情节矛盾/逻辑漏洞 | 大问题 | 暂停，展示给用户决策 |
| 世界观/神话设定冲突 | 大问题 | 暂停，展示给用户决策 |

### Flow

```
Writer 完成一章
    ↓
Reviewer 审核 → 无问题 → 通过，进入下一章
    ↓ 有问题
    ├─ 小问题 → 自动生成修改建议 → Writer 修订 → 再审（≤3轮）
    │                                    ↓ 3轮仍未通过
    │                              升级为大问题，交给用户
    └─ 大问题 → UI 展示问题描述 + 修改建议
                    ↓
              用户选择：接受建议 / 自己指导 / 忽略
                    ↓
              Writer 按指示修订 → Reviewer 再审
```

### Final Review

所有章节完成后，Reviewer 做全文级别终审：
- 伏笔是否全部回收
- 角色弧线是否完整
- 整体氛围是否连贯
- 结局是否呼应开篇

## Project Structure

```
coc_scripts/
├── app.py                  # Streamlit 入口
├── config.yaml             # LLM 配置文件
├── agents/
│   ├── brainstorm.py       # 用户对话收集故事种子
│   ├── worldbuilder.py     # 世界观构建
│   ├── outliner.py         # 章节大纲生成
│   ├── writer.py           # 章节撰写
│   └── reviewer.py         # 审核与修订
├── models/
│   ├── story_context.py    # 共享状态
│   └── schemas.py          # Pydantic 数据模型
├── llm/
│   ├── provider.py         # LLM 工厂：根据配置创建客户端
│   └── config.py           # 配置加载与校验
├── prompts/
│   └── *.md                # 各 Agent 的系统提示词模板
├── docs/plans/
└── pyproject.toml
```

## LLM Configuration

```yaml
llm:
  default_provider: openai
  providers:
    openai:
      api_key: "sk-xxx"
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o"
    anthropic:
      api_key: "sk-ant-xxx"
      model: "claude-sonnet-4-6-20250514"

agents:
  brainstorm:
    provider: anthropic
  worldbuilder:
    provider: openai
  outliner:
    provider: openai
  writer:
    provider: anthropic
  reviewer:
    provider: anthropic
```

Configuration priority: Environment variables > config.yaml > UI settings page.

## UI Design

### Layout

```
┌─────────────────────────────────────────────┐
│  CoC Secret Keeper                [设置]  │
├──────────────────────┬──────────────────────┤
│                      │                      │
│   对话区域            │   侧边栏             │
│                      │   - 当前阶段指示器    │
│   Brainstorm 对话     │   - 世界观摘要       │
│   ↓                  │   - 大纲预览         │
│   世界观展示/确认      │   - 角色列表         │
│   ↓                  │   - 伏笔追踪         │
│   大纲展示/调整       │                      │
│   ↓                  │                      │
│   章节生成进度        │                      │
│   ↓                  │                      │
│   审核结果/用户决策    │                      │
│                      │                      │
├──────────────────────┴──────────────────────┤
│  [导出全文 TXT]  [导出 Markdown]            │
└─────────────────────────────────────────────┘
```

### Interaction Flow

1. **设置页** — 首次使用配置 LLM provider 和 API key
2. **Brainstorm** — 聊天界面，Agent 逐个提问，侧边栏实时更新
3. **世界观 & 大纲** — 生成后展示，用户逐项确认或要求修改
4. **章节写作** — 逐章生成，进度条显示，每章可预览
5. **审核** — 小问题自动修复显示记录；大问题请用户决策
6. **导出** — TXT 或 Markdown

每个阶段之间都有用户确认环节，用户始终掌握主导权。

## Non-Goals

- No database — StoryContext in memory, export to file on completion
- No vector store/RAG — context fits within LLM window for this length range
- No LangChain — CrewAI handles LLM calls natively
