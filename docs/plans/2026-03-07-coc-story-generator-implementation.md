# CoC Secret Keeper - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-agent Cthulhu-themed novel generation tool with 5 agents (Brainstorm, Worldbuilder, Outliner, Writer, Reviewer) using CrewAI and Streamlit.

**Architecture:** Pipeline-based architecture where agents pass a shared `StoryContext` object through stages. Each agent has specific responsibilities and can read/write to the context. Review mechanism handles small issues automatically and escalates large issues to user.

**Tech Stack:** Python 3.11+, CrewAI, OpenAI/Anthropic LLMs, Streamlit UI, Pydantic models, YAML config

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "coc-story-generator"
version = "0.1.0"
description = "Multi-agent Cthulhu-themed novel generation tool"
requires-python = ">=3.11,<3.14"
dependencies = [
    "crewai[anthropic]>=1.10.0",
    "streamlit>=1.30.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true
```

**Step 2: Create .gitignore**

```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.env
.venv
env/
venv/
ENV/
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store
outputs/
*.txt
!requirements.txt
```

**Step 3: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: All dependencies installed successfully

**Step 4: Create directory structure**

Run:
```bash
mkdir -p agents models llm prompts tests
touch agents/__init__.py models/__init__.py llm/__init__.py tests/__init__.py
```

**Step 5: Commit**

```bash
git add pyproject.toml .gitignore agents/__init__.py models/__init__.py llm/__init__.py tests/__init__.py
git commit -m "chore: project setup with dependencies and structure"
```

---

## Task 2: Pydantic Data Models

**Files:**
- Create: `models/schemas.py`
- Create: `models/story_context.py`

**Step 1: Write tests for schemas**

Create: `tests/test_schemas.py`

```python
import pytest
from models.schemas import Character, Entity, WorldSetting, ChapterOutline


def test_character_creation():
    char = Character(
        name="张三",
        background="考古学家",
        personality="好奇、固执",
        motivation="寻找失落的真相",
        arc="从怀疑到疯狂",
        relationships=["李四：同事", "王五：导师"],
    )
    assert char.name == "张三"
    assert len(char.relationships) == 2


def test_entity_creation():
    entity = Entity(
        name="古老者",
        description="来自星际的古老生物",
        influence="通过梦境影响人类心智",
    )
    assert entity.name == "古老者"


def test_world_setting_creation():
    world = WorldSetting(
        era="1920年代",
        locations=["阿卡姆镇", "密斯卡托尼克大学"],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="人类并非万物之主",
        rules=["不可直视古神", "知识带来疯狂"],
        characters=[Character(name="张三", background="学者", personality="好奇", motivation="求知", arc="堕落", relationships=[])],
    )
    assert len(world.locations) == 2
    assert len(world.characters) == 1


def test_chapter_outline_creation():
    chapter = ChapterOutline(
        number=1,
        title="开端",
        summary="主角发现神秘手稿",
        mood="悬疑、不安",
        word_target=3000,
        foreshadowing=["手稿上的符号", "奇怪的梦境"],
        payoffs=[],
    )
    assert chapter.number == 1
    assert chapter.word_target == 3000
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_schemas.py -v`
Expected: ImportError or module not found

**Step 3: Implement schemas.py**

Create: `models/schemas.py`

```python
from pydantic import BaseModel, Field


class Character(BaseModel):
    name: str = Field(description="角色姓名")
    background: str = Field(description="角色背景")
    personality: str = Field(description="角色性格")
    motivation: str = Field(description="核心动机")
    arc: str = Field(description="角色弧线")
    relationships: list[str] = Field(default_factory=list, description="人物关系")


class Entity(BaseModel):
    name: str = Field(description="神话实体名称")
    description: str = Field(description="实体描述")
    influence: str = Field(description="对人类的影响方式")


class WorldSetting(BaseModel):
    era: str = Field(description="故事时代背景")
    locations: list[str] = Field(default_factory=list, description="故事地点")
    entities: list[Entity] = Field(default_factory=list, description="神话实体")
    forbidden_knowledge: str = Field(default="", description="禁忌知识")
    rules: list[str] = Field(default_factory=list, description="世界观规则")
    characters: list[Character] = Field(default_factory=list, description="角色列表")


class ChapterOutline(BaseModel):
    number: int = Field(description="章节序号")
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要")
    mood: str = Field(description="情绪基调")
    word_target: int = Field(description="目标字数")
    foreshadowing: list[str] = Field(default_factory=list, description="伏笔列表")
    payoffs: list[str] = Field(default_factory=list, description="回收点列表")


class ReviewIssue(BaseModel):
    category: str = Field(description="问题类别: wording/grammar/atmosphere/plot/worldview")
    severity: str = Field(description="严重程度: minor/major")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
```

**Step 4: Implement story_context.py**

Create: `models/story_context.py`

```python
from pydantic import BaseModel, Field
from models.schemas import WorldSetting, ChapterOutline


class StoryContext(BaseModel):
    seed: dict = Field(default_factory=dict, description="故事种子/初始想法")
    world: WorldSetting | None = Field(default=None, description="世界观设定")
    outline: list[ChapterOutline] = Field(default_factory=list, description="章节大纲")
    chapters: list[str] = Field(default_factory=list, description="已生成章节正文")
    review_notes: list[str] = Field(default_factory=list, description="审核记录")
    current_stage: str = Field(default="brainstorm", description="当前阶段")

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "StoryContext":
        return cls.model_validate(data)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_schemas.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add models/ tests/test_schemas.py
git commit -m "feat: add pydantic data models for story context"
```

---

## Task 3: LLM Configuration System

**Files:**
- Create: `llm/config.py`
- Create: `llm/provider.py`
- Create: `config.yaml`

**Step 1: Write tests for config**

Create: `tests/test_llm_config.py`

```python
import os
import pytest
from llm.config import load_config, Config


def test_config_loading():
    config = load_config("config.yaml")
    assert config.llm is not None
    assert "default_provider" in config.llm


def test_provider_override_from_env():
    os.environ["COC_OPENAI_API_KEY"] = "test-key"
    config = load_config("config.yaml")
    assert config.llm["providers"]["openai"]["api_key"] == "test-key"
    del os.environ["COC_OPENAI_API_KEY"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm_config.py -v`
Expected: ImportError or file not found

**Step 3: Implement llm/config.py**

Create: `llm/config.py`

```python
import os
import yaml
from dataclasses import dataclass
from typing import Any


@dataclass
class Config:
    llm: dict[str, Any]
    agents: dict[str, dict[str, str]]


def load_config(path: str = "config.yaml") -> Config:
    """Load config from YAML file with environment variable overrides."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Override with environment variables
    for provider_name, provider_config in data.get("llm", {}).get("providers", {}).items():
        env_key = os.getenv(f"COC_{provider_name.upper()}_API_KEY")
        if env_key:
            provider_config["api_key"] = env_key

        env_base_url = os.getenv(f"COC_{provider_name.upper()}_BASE_URL")
        if env_base_url:
            provider_config["base_url"] = env_base_url

    return Config(
        llm=data.get("llm", {}),
        agents=data.get("agents", {}),
    )


def get_agent_config(config: Config, agent_name: str) -> dict[str, Any]:
    """Get LLM config for a specific agent."""
    agent_cfg = config.agents.get(agent_name, {})
    provider_name = agent_cfg.get("provider", config.llm.get("default_provider", "openai"))
    provider_config = config.llm.get("providers", {}).get(provider_name, {})

    return {
        "provider": provider_name,
        "api_key": provider_config.get("api_key"),
        "base_url": provider_config.get("base_url"),
        "model": provider_config.get("model"),
    }
```

**Step 4: Implement llm/provider.py**

Create: `llm/provider.py`

```python
import os
from typing import Any
from crewai import LLM


def create_llm(
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> LLM:
    """Create LLM instance based on provider."""

    if provider == "anthropic":
        return LLM(
            model=f"anthropic/{model or 'claude-sonnet-4-6-20250514'}",
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=4096,
            **kwargs,
        )
    elif provider == "openai":
        return LLM(
            model=f"openai/{model or 'gpt-4o'}",
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
            **kwargs,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_llm_for_agent(config: dict[str, Any]) -> LLM:
    """Create LLM from agent config."""
    return create_llm(
        provider=config["provider"],
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        model=config.get("model"),
    )
```

**Step 5: Create config.yaml**

Create: `config.yaml`

```yaml
llm:
  default_provider: openai
  providers:
    openai:
      api_key: ""
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o"
    anthropic:
      api_key: ""
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

**Step 6: Run tests**

Run: `pytest tests/test_llm_config.py -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add llm/ config.yaml tests/test_llm_config.py
git commit -m "feat: add LLM configuration system with provider factory"
```

---

## Task 4: Prompt Templates

**Files:**
- Create: `prompts/brainstorm.md`
- Create: `prompts/worldbuilder.md`
- Create: `prompts/outliner.md`
- Create: `prompts/writer.md`
- Create: `prompts/reviewer.md`

**Step 1: Create brainstorm prompt**

Create: `prompts/brainstorm.md`

```markdown
# Brainstorm Agent

你是克苏鲁神话故事创作助手。你的任务是通过对话收集用户的故事构思。

## 职责
1. 引导用户回答以下核心问题：
   - 故事主题是什么？（调查、疯狂、禁忌知识等）
   - 希望什么时代背景？（1920年代、现代、维多利亚等）
   - 想要什么恐怖氛围？（心理恐惧、身体恐怖、宇宙恐怖）
   - 有特别想写的克苏鲁元素吗？（古神、神话生物、邪教徒等）
   - 主角大概是什么人？（职业、性格、动机）

2. 一次只问一个问题，循序渐进
3. 根据用户回答追问细节
4. 当收集足够信息后，总结故事种子给用户确认

## 输出格式

当信息收集完成时，输出如下JSON格式：
```json
{
  "theme": "主题",
  "era": "时代",
  "atmosphere": "氛围",
  "mythos_elements": ["元素1", "元素2"],
  "protagonist": {
    "concept": "主角概念",
    "motivation": "核心动机"
  },
  "notes": "其他备注"
}
```
```

**Step 2: Create worldbuilder prompt**

Create: `prompts/worldbuilder.md`

```markdown
# Worldbuilder Agent

你是克苏鲁神话世界观构建专家。基于用户提供的故事种子，构建完整的世界观设定。

## 职责
1. 设计故事发生的具体地点（城镇、建筑、重要场所）
2. 创造或选用合适的神话实体
3. 设计主要角色档案（主角、配角、反派）
4. 确立世界观规则（什么存在、什么不可能、禁忌知识的边界）
5. 确保符合洛夫克拉夫特神话风格（不可知带来的恐怖）

## 输入
- 故事种子（主题、时代、氛围、元素）

## 输出格式

使用以下JSON结构：
```json
{
  "era": "具体年代",
  "locations": ["地点1", "地点2", "地点3"],
  "entities": [
    {
      "name": "实体名称",
      "description": "描述",
      "influence": "影响方式"
    }
  ],
  "forbidden_knowledge": "禁忌知识的核心内容",
  "rules": ["规则1", "规则2"],
  "characters": [
    {
      "name": "姓名",
      "background": "背景",
      "personality": "性格",
      "motivation": "动机",
      "arc": "弧线",
      "relationships": ["关系1", "关系2"]
    }
  ]
}
```

## 克苏鲁神话原则
- 人类渺小，宇宙冷漠
- 知识带来疯狂
- 古神不可名状、不可理解
- 恐惧源于未知
```

**Step 3: Create outliner prompt**

Create: `prompts/outliner.md`

```markdown
# Outliner Agent

你是克苏鲁小说大纲设计专家。基于世界观设定，设计章节结构和叙事节奏。

## 职责
1. 设计合适的章节数（短篇6-10章，中篇15-25章）
2. 每章规划：标题、摘要、情绪基调、目标字数
3. 设计伏笔埋设点和回收点
4. 确保情绪曲线有起伏：悬疑→紧张→恐惧→高潮→余韵
5. 确保角色弧线完整

## 输入
- 世界观设定（时代、地点、实体、角色）
- 故事种子（主题、氛围）

## 输出格式

```json
{
  "chapters": [
    {
      "number": 1,
      "title": "章节标题",
      "summary": "章节摘要（100字左右）",
      "mood": "情绪基调",
      "word_target": 3000,
      "foreshadowing": ["伏笔1", "伏笔2"],
      "payoffs": ["回收1"]
    }
  ],
  "total_word_estimate": 25000,
  "narrative_arc": "整体叙事弧线说明"
}
```

## 设计原则
- 每章都有清晰的情绪目标
- 伏笔要比回收多（不是所有都要回收）
- 节奏张弛有度
```

**Step 4: Create writer prompt**

Create: `prompts/writer.md`

```markdown
# Writer Agent

你是克苏鲁小说作家。基于大纲撰写章节正文，保持克苏鲁氛围。

## 职责
1. 按大纲撰写章节，达到目标字数
2. 保持克苏鲁氛围（感官细节、心理恐惧、不可名状）
3. 确保与前文章节连贯
4. 埋设伏笔、回收前文伏笔
5. 刻画角色心理变化

## 输入
- 世界观设定
- 完整大纲
- 本章大纲（number, title, summary, mood, word_target, foreshadowing, payoffs）
- 已完成的章节正文（如不是第一章）

## 输出格式

直接输出章节正文，不需要额外格式。正文应该：
- 符合目标字数要求
- 体现指定的情绪基调
- 包含大纲要求的伏笔或回收

## 写作原则

**克苏鲁氛围渲染：**
- 感官细节：奇怪的气味、无法辨认的颜色、不应存在的声音
- 心理描写：从怀疑到不安到恐惧到绝望的渐进
- 暗示而非明示：不可言说的恐惧
- 环境描写：阴郁、衰败、异样的几何结构

**连贯性：**
- 回顾前章结尾确保衔接
- 保持角色口吻一致
- 时间线清晰
```

**Step 5: Create reviewer prompt**

Create: `prompts/reviewer.md`

```markdown
# Reviewer Agent

你是克苏鲁小说编辑。审核章节质量，识别问题并分类。

## 职责
1. 检查措辞、语法、节奏（小问题）
2. 检查氛围渲染、恐惧递进（小问题）
3. 检查情节矛盾、逻辑漏洞（大问题）
4. 检查神话设定一致性（大问题）
5. 检查伏笔回收情况

## 输入
- 世界观设定
- 大纲
- 本章及前文正文
- 已知的审核记录

## 输出格式

```json
{
  "passed": false,
  "issues": [
    {
      "category": "wording|grammar|atmosphere|plot|worldview",
      "severity": "minor|major",
      "description": "问题描述",
      "suggestion": "修改建议"
    }
  ],
  "strengths": ["优点1", "优点2"],
  "overall_assessment": "总体评价"
}
```

## 分类标准

**小问题（自动修复）：**
- 个别句子不通顺
- 某段氛围不够
- 节奏稍快/慢

**大问题（需用户决策）：**
- 情节逻辑矛盾
- 与已确立设定冲突
- 角色行为不合人设
- 伏笔被忽略

## 克苏鲁神话一致性检查
- 古神不应被人类理解或沟通
- 知识应导致疯狂
- 不应出现过于具体的描述
```

**Step 6: Commit**

```bash
git add prompts/
git commit -m "feat: add agent prompt templates"
```

---

## Task 5: Brainstorm Agent

**Files:**
- Create: `agents/brainstorm.py`
- Create: `tests/test_brainstorm.py`

**Step 1: Write test for brainstorm agent**

Create: `tests/test_brainstorm.py`

```python
import pytest
from unittest.mock import Mock, patch
from agents.brainstorm import BrainstormAgent
from models.story_context import StoryContext


def test_brainstorm_agent_creation():
    mock_llm = Mock()
    agent = BrainstormAgent(llm=mock_llm)
    assert agent is not None
    assert agent.conversation_history == []


def test_extract_seed_from_json():
    mock_llm = Mock()
    agent = BrainstormAgent(llm=mock_llm)

    json_str = '''{"theme": "调查", "era": "1920s"}'''
    result = agent._extract_seed(json_str)

    assert result["theme"] == "调查"
    assert result["era"] == "1920s"


def test_chat_maintains_history():
    mock_llm = Mock()
    mock_llm.call.return_value = "你想写什么主题的克苏鲁故事？"

    agent = BrainstormAgent(llm=mock_llm)
    context = StoryContext()

    agent.chat("我想写一个调查类的故事", context)

    assert len(agent.conversation_history) == 2  # user + assistant
    assert agent.conversation_history[0]["role"] == "user"
    assert agent.conversation_history[1]["role"] == "assistant"
    mock_llm.call.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_brainstorm.py -v`
Expected: ImportError

**Step 3: Implement brainstorm agent**

Create: `agents/brainstorm.py`

```python
import json
import re
from crewai import LLM

from models.story_context import StoryContext


class BrainstormAgent:
    """Brainstorm agent for collecting story seeds through conversation.

    NOTE: This agent uses direct LLM calls instead of CrewAI Agent/Task/Crew
    because brainstorming requires multi-turn conversation with history.
    CrewAI Crews are designed for one-shot task execution and would lose
    conversation context between turns.
    """

    def __init__(self, llm: LLM):
        self.llm = llm
        self.prompt = self._load_prompt()
        self.conversation_history: list[dict[str, str]] = []

    def _load_prompt(self) -> str:
        with open("prompts/brainstorm.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_seed(self, text: str) -> dict:
        """Extract JSON seed from agent response."""
        # Try to find JSON block
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find raw JSON
        json_match = re.search(r'\{[\s\S]*"theme"[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group(0))

        return {}

    def chat(self, user_input: str, context: StoryContext) -> str:
        """Process user input and return agent response.

        Uses direct LLM.call() to maintain multi-turn conversation history.
        """
        self.conversation_history.append({"role": "user", "content": user_input})

        messages = [
            {"role": "system", "content": self.prompt},
            *self.conversation_history,
            {"role": "user", "content": f"\n\n当前已收集的故事种子: {json.dumps(context.seed, ensure_ascii=False)}"},
        ]

        result_text = self.llm.call(messages=messages)

        self.conversation_history.append({"role": "assistant", "content": result_text})

        # Try to extract seed if JSON is present
        seed = self._extract_seed(result_text)
        if seed:
            context.seed.update(seed)

        return result_text

    def is_complete(self, context: StoryContext) -> bool:
        """Check if enough information has been gathered."""
        required = ["theme", "era", "atmosphere", "protagonist"]
        return all(k in context.seed for k in required)
```

**Step 4: Run tests**

Run: `pytest tests/test_brainstorm.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add agents/brainstorm.py tests/test_brainstorm.py
git commit -m "feat: implement brainstorm agent with conversation flow"
```

---

## Task 6: Worldbuilder Agent

**Files:**
- Create: `agents/worldbuilder.py`
- Create: `tests/test_worldbuilder.py`

**Step 1: Write test**

Create: `tests/test_worldbuilder.py`

```python
import pytest
from unittest.mock import Mock, patch
from agents.worldbuilder import WorldbuilderAgent
from models.story_context import StoryContext
from models.schemas import WorldSetting


def test_worldbuilder_creation():
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)
    assert agent is not None


def test_build_world():
    mock_llm = Mock()
    agent = WorldbuilderAgent(llm=mock_llm)

    context = StoryContext(seed={
        "theme": "调查",
        "era": "1920年代",
        "atmosphere": "心理恐怖"
    })

    # Mock the crew result
    mock_result = """
```json
{
  "era": "1924年，马萨诸塞州阿卡姆镇",
  "locations": ["密斯卡托尼克大学图书馆", "废弃的教堂"],
  "entities": [{"name": "奈亚拉托提普", "description": "外神", "influence": "化身行走人间"}],
  "forbidden_knowledge": "人类的历史只有几千年",
  "rules": ["直视古神会导致疯狂"],
  "characters": [{"name": "李教授", "background": "考古学", "personality": "严谨", "motivation": "求知", "arc": "堕落", "relationships": []}]
}
```
"""

    with patch.object(agent, '_run_agent', return_value=mock_result):
        world = agent.build_world(context)

    assert isinstance(world, WorldSetting)
    assert "阿卡姆" in world.era
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worldbuilder.py -v`
Expected: ImportError

**Step 3: Implement worldbuilder agent**

Create: `agents/worldbuilder.py`

```python
import json
import re
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import WorldSetting, Character, Entity


class WorldbuilderAgent:
    """Agent for building Cthulhu mythos world settings."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/worldbuilder.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_world(self, text: str) -> WorldSetting:
        """Extract world setting from agent response."""
        # Try to find JSON block with ```json ... ```
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            # Fallback: find raw JSON object
            json_match = re.search(r'\{[\s\S]*"era"[\s\S]*"characters"[\s\S]*\}', text)
            raw = json_match.group(0) if json_match else None

        if raw:
            data = json.loads(raw)

            # Parse entities
            entities = [
                Entity(**e) for e in data.get("entities", [])
            ]

            # Parse characters
            characters = [
                Character(**c) for c in data.get("characters", [])
            ]

            return WorldSetting(
                era=data["era"],
                locations=data.get("locations", []),
                entities=entities,
                forbidden_knowledge=data.get("forbidden_knowledge", ""),
                rules=data.get("rules", []),
                characters=characters,
            )

        raise ValueError("Could not extract world setting from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Worldbuilder",
            goal="Build Cthulhu mythos world settings",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted world setting",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        return str(crew.kickoff())

    def build_world(self, context: StoryContext) -> WorldSetting:
        """Build world setting from story seed."""
        task_desc = f"""
Based on this story seed, create a complete world setting:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

Output a complete world setting following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        world = self._extract_world(result)
        context.world = world
        return world
```

**Step 4: Run tests**

Run: `pytest tests/test_worldbuilder.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add agents/worldbuilder.py tests/test_worldbuilder.py
git commit -m "feat: implement worldbuilder agent"
```

---

## Task 7: Outliner Agent

**Files:**
- Create: `agents/outliner.py`
- Create: `tests/test_outliner.py`

**Step 1: Write test**

Create: `tests/test_outliner.py`

```python
import pytest
from unittest.mock import Mock, patch
from agents.outliner import OutlinerAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline


def test_outliner_creation():
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)
    assert agent is not None


def test_create_outline():
    mock_llm = Mock()
    agent = OutlinerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查", "atmosphere": "悬疑"}
    context.world = None  # Would have world data

    mock_result = """
```json
{
  "chapters": [
    {"number": 1, "title": "神秘来信", "summary": "主角收到奇怪的信", "mood": "悬疑", "word_target": 3000, "foreshadowing": ["信上的符号"], "payoffs": []}
  ],
  "total_word_estimate": 25000,
  "narrative_arc": "渐进式恐怖"
}
```
"""

    with patch.object(agent, '_run_agent', return_value=mock_result):
        outline = agent.create_outline(context, target_chapters=6)

    assert len(outline) == 1
    assert isinstance(outline[0], ChapterOutline)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_outliner.py -v`
Expected: ImportError

**Step 3: Implement outliner agent**

Create: `agents/outliner.py`

```python
import json
import re
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ChapterOutline


class OutlinerAgent:
    """Agent for creating story outlines."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/outliner.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_outline(self, text: str) -> list[ChapterOutline]:
        """Extract chapter outline from agent response."""
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*"chapters"[\s\S]*\}', text)
            raw = json_match.group(0) if json_match else None

        if raw:
            data = json.loads(raw)
            chapters = [
                ChapterOutline(**c) for c in data.get("chapters", [])
            ]
            return chapters

        raise ValueError("Could not extract outline from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Outliner",
            goal="Create compelling story outlines",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted outline with chapters",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        return str(crew.kickoff())

    def create_outline(
        self,
        context: StoryContext,
        target_chapters: int = 10,
    ) -> list[ChapterOutline]:
        """Create chapter outline from world setting."""
        import json

        world_dict = context.world.model_dump() if context.world else {}

        task_desc = f"""
Create a story outline based on:

Story Seed:
{json.dumps(context.seed, ensure_ascii=False, indent=2)}

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Target number of chapters: {target_chapters}

Output a complete outline following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        outline = self._extract_outline(result)
        context.outline = outline
        return outline
```

**Step 4: Run tests**

Run: `pytest tests/test_outliner.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add agents/outliner.py tests/test_outliner.py
git commit -m "feat: implement outliner agent"
```

---

## Task 8: Writer Agent

**Files:**
- Create: `agents/writer.py`
- Create: `tests/test_writer.py`

**Step 1: Write test**

Create: `tests/test_writer.py`

```python
import pytest
from unittest.mock import Mock, patch
from agents.writer import WriterAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline, WorldSetting, Character


def test_writer_creation():
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)
    assert agent is not None


def test_write_chapter():
    mock_llm = Mock()
    agent = WriterAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=["阿卡姆"],
        characters=[Character(name="张三", background="学者", personality="好奇", motivation="求知", arc="堕落", relationships=[])],
    )

    chapter_outline = ChapterOutline(
        number=1,
        title="开端",
        summary="主角开始调查",
        mood="悬疑",
        word_target=500,
        foreshadowing=["奇怪的符号"],
        payoffs=[],
    )

    mock_result = "张三拿起那本古老的书...（省略）"

    with patch.object(agent, '_run_agent', return_value=mock_result):
        chapter = agent.write_chapter(context, chapter_outline)

    assert chapter == mock_result
    assert len(context.chapters) == 1
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_writer.py -v`
Expected: ImportError

**Step 3: Implement writer agent**

Create: `agents/writer.py`

```python
import json
from crewai import Agent, Task, Crew

from models.story_context import StoryContext
from models.schemas import ChapterOutline


class WriterAgent:
    """Agent for writing chapter content."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/writer.md", "r", encoding="utf-8") as f:
            return f.read()

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Writer",
            goal="Write compelling Cthulhu fiction",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="Chapter content in Chinese",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        return str(crew.kickoff())

    def write_chapter(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
    ) -> str:
        """Write a single chapter."""
        world_dict = context.world.model_dump() if context.world else {}
        outline_dict = chapter.model_dump()

        previous_chapters = "\n\n".join(
            f"Chapter {i+1}:\n{text}"
            for i, text in enumerate(context.chapters)
        ) if context.chapters else "无"

        task_desc = f"""
Write chapter {chapter.number}: "{chapter.title}"

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Chapter Outline:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

Previous Chapters Summary:
{previous_chapters}

Write the chapter content in Chinese. Target word count: {chapter.word_target}.
Maintain the mood: {chapter.mood}.
Include foreshadowing: {chapter.foreshadowing}
Include payoffs: {chapter.payoffs}
"""

        result = self._run_agent(task_desc)
        context.chapters.append(result)
        return result

    def revise_chapter(
        self,
        context: StoryContext,
        chapter: ChapterOutline,
        chapter_text: str,
        issues: list[dict],
    ) -> str:
        """Revise a chapter based on review feedback."""
        issues_desc = "\n".join(
            f"- [{i['category']}] {i['description']} → 建议: {i['suggestion']}"
            for i in issues
        )

        task_desc = f"""
Revise chapter {chapter.number}: "{chapter.title}"

Original text:
{chapter_text}

Issues to fix:
{issues_desc}

Rewrite the chapter fixing all listed issues while maintaining the same story flow.
Output the complete revised chapter in Chinese.
"""

        result = self._run_agent(task_desc)
        # Replace the chapter in context
        idx = chapter.number - 1
        if idx < len(context.chapters):
            context.chapters[idx] = result
        return result
```

**Step 4: Run tests**

Run: `pytest tests/test_writer.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add agents/writer.py tests/test_writer.py
git commit -m "feat: implement writer agent"
```

---

## Task 9: Reviewer Agent

**Files:**
- Create: `agents/reviewer.py`
- Create: `tests/test_reviewer.py`

**Step 1: Write test**

Create: `tests/test_reviewer.py`

```python
import pytest
from unittest.mock import Mock, patch
from agents.reviewer import ReviewerAgent
from models.story_context import StoryContext
from models.schemas import ChapterOutline


def test_reviewer_creation():
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)
    assert agent is not None


def test_review_chapter():
    mock_llm = Mock()
    agent = ReviewerAgent(llm=mock_llm)

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=1000, foreshadowing=[], payoffs=[])
    ]

    mock_result = """
```json
{
  "passed": false,
  "issues": [
    {"category": "atmosphere", "severity": "minor", "description": "氛围不够", "suggestion": "加强感官描写"}
  ],
  "strengths": ["情节推进好"],
  "overall_assessment": "基本合格，需要小修"
}
```
"""

    with patch.object(agent, '_run_agent', return_value=mock_result):
        result = agent.review_chapter(context, chapter_number=1, chapter_text="测试文本")

    assert not result.passed
    assert len(result.issues) == 1
    assert result.issues[0]["severity"] == "minor"
    assert len(result.get_minor_issues()) == 1
    assert len(result.get_major_issues()) == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reviewer.py -v`
Expected: ImportError

**Step 3: Implement reviewer agent**

Create: `agents/reviewer.py`

```python
import json
import re
from crewai import Agent, Task, Crew

from models.story_context import StoryContext


class ReviewResult:
    """Review result with issues classification."""

    def __init__(self, data: dict):
        self.passed = data.get("passed", False)
        self.issues = data.get("issues", [])
        self.strengths = data.get("strengths", [])
        self.overall_assessment = data.get("overall_assessment", "")

    def get_minor_issues(self) -> list[dict]:
        return [i for i in self.issues if i.get("severity") == "minor"]

    def get_major_issues(self) -> list[dict]:
        return [i for i in self.issues if i.get("severity") == "major"]


class ReviewerAgent:
    """Agent for reviewing chapter quality."""

    def __init__(self, llm):
        self.llm = llm
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        with open("prompts/reviewer.md", "r", encoding="utf-8") as f:
            return f.read()

    def _extract_review(self, text: str) -> ReviewResult:
        """Extract review result from agent response."""
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*"passed"[\s\S]*\}', text)
            raw = json_match.group(0) if json_match else None

        if raw:
            data = json.loads(raw)
            return ReviewResult(data)

        raise ValueError("Could not extract review from response")

    def _run_agent(self, task_description: str) -> str:
        """Run the agent with given task."""
        agent = Agent(
            role="Reviewer",
            goal="Review story quality and identify issues",
            backstory=self.prompt,
            llm=self.llm,
            verbose=True,
        )

        task = Task(
            description=task_description,
            expected_output="JSON formatted review",
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True,
        )

        return str(crew.kickoff())

    def review_chapter(
        self,
        context: StoryContext,
        chapter_number: int,
        chapter_text: str,
    ) -> ReviewResult:
        """Review a chapter and classify issues."""
        world_dict = context.world.model_dump() if context.world else {}

        # Get outline for this chapter
        chapter_outline = None
        if context.outline and chapter_number <= len(context.outline):
            chapter_outline = context.outline[chapter_number - 1].model_dump()

        previous_text = "\n\n".join(context.chapters) if context.chapters else "无"

        task_desc = f"""
Review chapter {chapter_number}.

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Chapter Outline:
{json.dumps(chapter_outline, ensure_ascii=False, indent=2) if chapter_outline else "N/A"}

Previous Chapters:
{previous_text}

Chapter to Review:
{chapter_text}

Provide a complete review following the format in your instructions.
"""

        result = self._run_agent(task_desc)
        review = self._extract_review(result)

        # Record review
        context.review_notes.append(
            f"Chapter {chapter_number}: {'PASS' if review.passed else 'NEEDS_REVISION'}"
        )

        return review

    def final_review(self, context: StoryContext) -> ReviewResult:
        """Perform full-text final review after all chapters are complete.

        Checks: foreshadowing payoffs, character arcs, atmosphere
        consistency, ending echoes opening.
        """
        world_dict = context.world.model_dump() if context.world else {}
        outline_dict = [ch.model_dump() for ch in context.outline]

        full_text = "\n\n".join(
            f"第{i+1}章: {context.outline[i].title}\n{text}"
            for i, text in enumerate(context.chapters)
        )

        task_description = f"""
Perform a FINAL full-text review of the complete story.

World Setting:
{json.dumps(world_dict, ensure_ascii=False, indent=2)}

Outline:
{json.dumps(outline_dict, ensure_ascii=False, indent=2)}

Full Text:
{full_text}

Check the following specifically:
1. 所有伏笔是否都已回收
2. 所有角色弧线是否完整
3. 整体氛围是否连贯一致
4. 结局是否呼应开篇

Provide a complete review following the format in your instructions.
"""

        result = self._run_agent(task_description)
        review = self._extract_review(result)

        context.review_notes.append(
            f"FINAL REVIEW: {'PASS' if review.passed else 'NEEDS_REVISION'}"
        )

        return review
```

**Step 4: Run tests**

Run: `pytest tests/test_reviewer.py -v`
Expected: Tests pass

**Step 5: Commit**

```bash
git add agents/reviewer.py tests/test_reviewer.py
git commit -m "feat: implement reviewer agent with issue classification"
```

---

## Task 10: Streamlit UI - Main App Structure

**Files:**
- Create: `app.py`

**Step 1: Implement main app**

Create: `app.py`

```python
import streamlit as st
import json

from models.story_context import StoryContext
from llm.config import load_config, get_agent_config
from llm.provider import get_llm_for_agent


def init_session():
    """Initialize session state."""
    if "context" not in st.session_state:
        st.session_state.context = StoryContext()
    if "stage" not in st.session_state:
        st.session_state.stage = "brainstorm"
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def render_sidebar():
    """Render sidebar with story info."""
    with st.sidebar:
        st.header("创作进度")

        context = st.session_state.context

        # Stage indicator
        stages = ["brainstorm", "world", "outline", "writing", "review", "complete"]
        current = stages.index(st.session_state.stage)
        st.progress((current) / len(stages))
        st.write(f"当前阶段: {st.session_state.stage}")

        # World summary (if available)
        if context.world:
            st.subheader("世界观")
            st.write(f"时代: {context.world.era}")
            st.write(f"地点: {', '.join(context.world.locations[:3])}")

        # Character list
        if context.world and context.world.characters:
            st.subheader("角色")
            for char in context.world.characters:
                st.write(f"- {char.name}")

        # Outline preview
        if context.outline:
            st.subheader(f"大纲 ({len(context.outline)}章)")
            for ch in context.outline[:5]:
                st.write(f"{ch.number}. {ch.title}")
            if len(context.outline) > 5:
                st.write("...")

        # Foreshadowing tracker
        if context.outline:
            st.subheader("伏笔追踪")
            all_foreshadowing = []
            all_payoffs = []
            for ch in context.outline:
                all_foreshadowing.extend(ch.foreshadowing)
                all_payoffs.extend(ch.payoffs)
            st.write(f"埋设: {len(all_foreshadowing)}")
            st.write(f"回收: {len(all_payoffs)}")


def render_brainstorm_stage():
    """Render brainstorm stage UI."""
    st.header("故事构思")
    st.write("让我们开始构思你的克苏鲁故事。请回答以下问题...")

    # Chat interface
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Input
    user_input = st.chat_input("请输入你的想法...")

    if user_input:
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Get agent response
        config = load_config()
        llm_config = get_agent_config(config, "brainstorm")
        llm = get_llm_for_agent(llm_config)

        from agents.brainstorm import BrainstormAgent
        agent = BrainstormAgent(llm)

        response = agent.chat(user_input, st.session_state.context)

        # Add assistant message
        st.session_state.chat_history.append({"role": "assistant", "content": response})

        # Check if complete
        if agent.is_complete(st.session_state.context):
            st.success("故事构思完成！")
            if st.button("进入世界观构建"):
                st.session_state.stage = "world"
                st.rerun()
        else:
            st.rerun()


def render_world_stage():
    """Render world building stage UI."""
    st.header("世界观构建")

    context = st.session_state.context

    if context.world is None:
        st.info("正在生成世界观...")

        config = load_config()
        llm_config = get_agent_config(config, "worldbuilder")
        llm = get_llm_for_agent(llm_config)

        from agents.worldbuilder import WorldbuilderAgent
        agent = WorldbuilderAgent(llm)

        with st.spinner("AI 正在构建世界观..."):
            world = agent.build_world(context)

        st.rerun()
    else:
        # Display world setting
        st.subheader("时代背景")
        st.write(context.world.era)

        st.subheader("地点")
        for loc in context.world.locations:
            st.write(f"- {loc}")

        st.subheader("神话实体")
        for entity in context.world.entities:
            with st.expander(entity.name):
                st.write(entity.description)
                st.write(f"影响: {entity.influence}")

        st.subheader("角色")
        for char in context.world.characters:
            with st.expander(char.name):
                st.write(f"背景: {char.background}")
                st.write(f"性格: {char.personality}")
                st.write(f"动机: {char.motivation}")
                st.write(f"弧线: {char.arc}")

        # Confirmation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("确认并继续"):
                st.session_state.stage = "outline"
                st.rerun()
        with col2:
            if st.button("重新生成"):
                context.world = None
                st.rerun()


def render_outline_stage():
    """Render outline stage UI."""
    st.header("故事大纲")

    context = st.session_state.context

    if not context.outline:
        # Chapter count selector
        target_chapters = st.slider("章节数", min_value=6, max_value=25, value=12)

        if st.button("生成大纲"):
            config = load_config()
            llm_config = get_agent_config(config, "outliner")
            llm = get_llm_for_agent(llm_config)

            from agents.outliner import OutlinerAgent
            agent = OutlinerAgent(llm)

            with st.spinner("AI 正在生成大纲..."):
                agent.create_outline(context, target_chapters)

            st.rerun()
    else:
        # Display outline
        for chapter in context.outline:
            with st.expander(f"第{chapter.number}章: {chapter.title}"):
                st.write(f"**摘要**: {chapter.summary}")
                st.write(f"**情绪**: {chapter.mood}")
                st.write(f"**字数**: {chapter.word_target}")
                if chapter.foreshadowing:
                    st.write(f"**伏笔**: {', '.join(chapter.foreshadowing)}")
                if chapter.payoffs:
                    st.write(f"**回收**: {', '.join(chapter.payoffs)}")

        # Confirmation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("确认并继续"):
                st.session_state.stage = "writing"
                st.rerun()
        with col2:
            if st.button("重新生成"):
                context.outline = []
                st.rerun()


def render_writing_stage():
    """Render writing stage UI.

    Implements the revision loop from Design:
    - Writer writes chapter → Reviewer reviews
    - Minor issues → auto-revise (up to 3 rounds)
    - Major issues or 3 rounds exhausted → show to user for decision
    """
    st.header("章节写作")

    context = st.session_state.context

    # Initialize revision state
    if "revision_round" not in st.session_state:
        st.session_state.revision_round = 0
    if "pending_review" not in st.session_state:
        st.session_state.pending_review = None

    # Progress
    total_chapters = len(context.outline)
    completed = len(context.chapters)
    st.progress(completed / total_chapters)
    st.write(f"进度: {completed}/{total_chapters} 章")

    # Handle pending major issues that need user decision
    if st.session_state.pending_review is not None:
        review = st.session_state.pending_review
        chapter_num = st.session_state.pending_chapter_num

        st.warning(f"第{chapter_num}章审核发现大问题，需要你的决策：")
        for issue in review.get_major_issues():
            st.error(f"**[{issue['category']}]** {issue['description']}")
            st.info(f"建议: {issue['suggestion']}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("接受建议并修改"):
                config = load_config()
                writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                from agents.writer import WriterAgent
                writer = WriterAgent(writer_llm)

                chapter_text = context.chapters[chapter_num - 1]
                current_chapter = context.outline[chapter_num - 1]

                with st.spinner("按建议修改中..."):
                    writer.revise_chapter(context, current_chapter, chapter_text, review.issues)

                st.session_state.pending_review = None
                st.session_state.revision_round = 0
                st.rerun()
        with col2:
            user_guidance = st.text_area("你的修改指导", key="user_guidance")
            if st.button("按我的指导修改"):
                if user_guidance:
                    config = load_config()
                    writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                    from agents.writer import WriterAgent
                    writer = WriterAgent(writer_llm)

                    chapter_text = context.chapters[chapter_num - 1]
                    current_chapter = context.outline[chapter_num - 1]
                    custom_issues = [{"category": "user", "description": user_guidance, "suggestion": user_guidance}]

                    with st.spinner("按指导修改中..."):
                        writer.revise_chapter(context, current_chapter, chapter_text, custom_issues)

                    st.session_state.pending_review = None
                    st.session_state.revision_round = 0
                    st.rerun()
        with col3:
            if st.button("忽略，继续下一章"):
                st.session_state.pending_review = None
                st.session_state.revision_round = 0
                st.rerun()
        return

    if completed < total_chapters:
        current_chapter = context.outline[completed]
        st.subheader(f"正在写作: 第{current_chapter.number}章 {current_chapter.title}")

        if st.button("生成章节"):
            config = load_config()
            writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
            review_llm = get_llm_for_agent(get_agent_config(config, "reviewer"))

            from agents.writer import WriterAgent
            from agents.reviewer import ReviewerAgent
            writer = WriterAgent(writer_llm)
            reviewer = ReviewerAgent(review_llm)

            with st.spinner(f"正在写作第{current_chapter.number}章..."):
                chapter_text = writer.write_chapter(context, current_chapter)

            # Revision loop: up to 3 rounds for minor issues
            max_revisions = 3
            for revision in range(max_revisions):
                with st.spinner(f"审核中（第{revision + 1}轮）..."):
                    review = reviewer.review_chapter(
                        context, current_chapter.number, chapter_text
                    )

                if review.passed:
                    st.success(f"第{current_chapter.number}章审核通过！")
                    break

                major_issues = review.get_major_issues()
                minor_issues = review.get_minor_issues()

                if major_issues:
                    # Escalate to user
                    st.session_state.pending_review = review
                    st.session_state.pending_chapter_num = current_chapter.number
                    st.rerun()
                    return

                if minor_issues:
                    if revision < max_revisions - 1:
                        st.info(f"第{revision + 1}轮: 发现 {len(minor_issues)} 个小问题，自动修订中...")
                        with st.spinner("自动修订中..."):
                            chapter_text = writer.revise_chapter(
                                context, current_chapter, chapter_text, minor_issues
                            )
                    else:
                        # 3 rounds exhausted, escalate
                        st.warning("3轮自动修订仍未通过，升级为需要用户决策")
                        st.session_state.pending_review = review
                        st.session_state.pending_chapter_num = current_chapter.number
                        st.rerun()
                        return

            st.rerun()
    else:
        st.success("所有章节写作完成！")
        if st.button("进入终审"):
            st.session_state.stage = "review"
            st.rerun()

    # Display completed chapters
    for i, text in enumerate(context.chapters):
        ch = context.outline[i]
        with st.expander(f"第{ch.number}章: {ch.title}"):
            st.write(text[:500] + "..." if len(text) > 500 else text)


def render_review_stage():
    """Render final review stage UI.

    Performs full-text final review as required by Design:
    - Check all foreshadowing payoffs
    - Check character arc completeness
    - Check atmosphere consistency
    - Check ending echoes opening
    """
    st.header("全文终审")

    context = st.session_state.context

    # Initialize final review state
    if "final_review_result" not in st.session_state:
        st.session_state.final_review_result = None

    # Run final review if not done yet
    if st.session_state.final_review_result is None:
        st.info("正在进行全文终审...")

        config = load_config()
        review_llm = get_llm_for_agent(get_agent_config(config, "reviewer"))

        from agents.reviewer import ReviewerAgent
        reviewer = ReviewerAgent(review_llm)

        with st.spinner("Reviewer 正在进行全文终审（伏笔回收、角色弧线、氛围连贯、首尾呼应）..."):
            review = reviewer.final_review(context)

        st.session_state.final_review_result = review
        st.rerun()

    review = st.session_state.final_review_result

    # Display final review results
    if review.passed:
        st.success("全文终审通过！故事整体质量良好。")
    else:
        st.warning("终审发现以下问题：")
        for issue in review.issues:
            severity_icon = "🔴" if issue.get("severity") == "major" else "🟡"
            st.write(f"{severity_icon} **[{issue['category']}]** {issue['description']}")
            st.caption(f"建议: {issue['suggestion']}")

    if review.strengths:
        st.subheader("亮点")
        for s in review.strengths:
            st.write(f"✅ {s}")

    st.write(f"**总评**: {review.overall_assessment}")

    st.divider()

    # Export buttons
    st.subheader("导出")
    col1, col2 = st.columns(2)

    with col1:
        full_text = "\n\n".join(
            f"第{i+1}章\n{context.outline[i].title}\n\n{text}"
            for i, text in enumerate(context.chapters)
        )
        st.download_button(
            "导出为 TXT",
            full_text,
            file_name="coc_story.txt",
            mime="text/plain",
        )

    with col2:
        md_text = f"# {context.seed.get('theme', '克苏鲁故事')}\n\n"
        for i, text in enumerate(context.chapters):
            md_text += f"## 第{i+1}章: {context.outline[i].title}\n\n{text}\n\n"
        st.download_button(
            "导出为 Markdown",
            md_text,
            file_name="coc_story.md",
            mime="text/markdown",
        )


def main():
    """Main app entry point."""
    st.set_page_config(
        page_title="CoC Secret Keeper",
        page_icon="🦑",
        layout="wide",
    )

    st.title("🦑 CoC Secret Keeper")
    st.caption("克苏鲁神话小说生成器")

    init_session()
    render_sidebar()

    # Render current stage
    stage = st.session_state.stage

    if stage == "brainstorm":
        render_brainstorm_stage()
    elif stage == "world":
        render_world_stage()
    elif stage == "outline":
        render_outline_stage()
    elif stage == "writing":
        render_writing_stage()
    elif stage == "review":
        render_review_stage()


if __name__ == "__main__":
    main()
```

**Step 2: Test the app runs**

Run: `streamlit run app.py --server.headless true`
(Will start server, verify no import errors)

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit UI with all stages"
```

---

## Task 11: Settings Page

**Files:**
- Modify: `app.py` (add settings page)

**Step 1: Add settings page to app.py**

Add to top of app.py after imports:

```python
def render_settings():
    """Render settings page."""
    st.header("设置")

    # Load current config
    config = load_config()

    st.subheader("LLM 配置")

    # OpenAI
    with st.expander("OpenAI"):
        openai_key = st.text_input(
            "API Key",
            value=config.llm.get("providers", {}).get("openai", {}).get("api_key", ""),
            type="password",
            key="openai_key",
        )
        openai_model = st.selectbox(
            "Model",
            ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            index=0,
            key="openai_model",
        )

    # Anthropic
    with st.expander("Anthropic"):
        anthropic_key = st.text_input(
            "API Key",
            value=config.llm.get("providers", {}).get("anthropic", {}).get("api_key", ""),
            type="password",
            key="anthropic_key",
        )
        anthropic_model = st.selectbox(
            "Model",
            ["claude-sonnet-4-6-20250514", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
            index=0,
            key="anthropic_model",
        )

    if st.button("保存设置"):
        import os
        import yaml

        # Save to environment for current session
        if openai_key:
            os.environ["COC_OPENAI_API_KEY"] = openai_key
        if anthropic_key:
            os.environ["COC_ANTHROPIC_API_KEY"] = anthropic_key

        # Persist to config.yaml
        config_path = "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        data.setdefault("llm", {}).setdefault("providers", {})
        if openai_key:
            data["llm"]["providers"].setdefault("openai", {})["api_key"] = openai_key
        data["llm"]["providers"].setdefault("openai", {})["model"] = openai_model
        if anthropic_key:
            data["llm"]["providers"].setdefault("anthropic", {})["api_key"] = anthropic_key
        data["llm"]["providers"].setdefault("anthropic", {})["model"] = anthropic_model

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        st.success("设置已保存到 config.yaml")

    st.info("配置优先级: 环境变量 > config.yaml > UI 设置页。\n"
            "环境变量: COC_OPENAI_API_KEY, COC_ANTHROPIC_API_KEY")
```

Modify main() to add settings navigation:

```python
def main():
    """Main app entry point."""
    st.set_page_config(
        page_title="CoC Secret Keeper",
        page_icon="🦑",
        layout="wide",
    )

    # Navigation
    st.sidebar.title("导航")
    page = st.sidebar.radio("选择页面", ["创作", "设置"])

    if page == "设置":
        render_settings()
        return

    # ... rest of main()
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat: add settings page for LLM configuration"
```

---

## Task 12: Integration Tests

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

Create: `tests/test_integration.py`

```python
import pytest
from unittest.mock import Mock, patch

from models.story_context import StoryContext
from models.schemas import Character, Entity, WorldSetting, ChapterOutline


def test_full_pipeline():
    """Test the full pipeline with mocked LLM."""
    context = StoryContext()

    # Step 1: Brainstorm
    context.seed = {
        "theme": "调查",
        "era": "1920年代",
        "atmosphere": "心理恐怖",
        "mythos_elements": ["古老者"],
        "protagonist": {"concept": "考古学家", "motivation": "寻找真相"},
    }

    # Step 2: World building
    context.world = WorldSetting(
        era="1924年，阿卡姆镇",
        locations=["密斯卡托尼克大学"],
        entities=[Entity(name="古老者", description="外星生物", influence="梦境")],
        forbidden_knowledge="人类渺小",
        rules=["不可直视古神"],
        characters=[
            Character(name="李教授", background="考古学", personality="严谨", motivation="求知", arc="堕落", relationships=[])
        ],
    )

    # Step 3: Outline
    context.outline = [
        ChapterOutline(
            number=1,
            title="开端",
            summary="主角发现神秘手稿",
            mood="悬疑",
            word_target=1000,
            foreshadowing=["手稿符号"],
            payoffs=[],
        ),
        ChapterOutline(
            number=2,
            title="调查",
            summary="主角开始调查",
            mood="紧张",
            word_target=1000,
            foreshadowing=[],
            payoffs=["手稿符号"],
        ),
    ]

    # Step 4: Writing
    context.chapters = ["第一章内容...", "第二章内容..."]

    # Verify
    assert len(context.chapters) == len(context.outline)
    assert context.world is not None
    assert len(context.world.characters) > 0


def test_review_classification():
    """Test review issue classification."""
    from agents.reviewer import ReviewResult

    review_data = {
        "passed": False,
        "issues": [
            {"category": "atmosphere", "severity": "minor", "description": "氛围不足", "suggestion": "加强"},
            {"category": "plot", "severity": "major", "description": "逻辑矛盾", "suggestion": "修改"},
        ],
        "strengths": [],
        "overall_assessment": "需要修订",
    }

    result = ReviewResult(review_data)

    assert len(result.get_minor_issues()) == 1
    assert len(result.get_major_issues()) == 1


def test_revision_loop_minor_issues():
    """Test that minor issues trigger writer revision."""
    from unittest.mock import Mock, patch
    from agents.writer import WriterAgent
    from agents.reviewer import ReviewerAgent, ReviewResult

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=["阿卡姆"],
        characters=[Character(name="张三", background="学者", personality="好奇", motivation="求知", arc="堕落", relationships=[])],
    )
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=1000, foreshadowing=[], payoffs=[])
    ]

    mock_writer_llm = Mock()
    writer = WriterAgent(mock_writer_llm)

    # Simulate: write → review (minor) → revise → review (pass)
    with patch.object(writer, '_run_agent', side_effect=["原始章节内容...", "修订后章节内容..."]):
        original = writer.write_chapter(context, context.outline[0])
        assert original == "原始章节内容..."

        revised = writer.revise_chapter(
            context, context.outline[0], original,
            [{"category": "atmosphere", "description": "氛围不足", "suggestion": "加强"}]
        )
        assert revised == "修订后章节内容..."
        assert context.chapters[0] == "修订后章节内容..."


def test_final_review():
    """Test final full-text review."""
    from unittest.mock import Mock, patch
    from agents.reviewer import ReviewerAgent

    context = StoryContext()
    context.seed = {"theme": "调查"}
    context.world = WorldSetting(
        era="1920s",
        locations=["阿卡姆"],
        characters=[Character(name="张三", background="学者", personality="好奇", motivation="求知", arc="堕落", relationships=[])],
    )
    context.outline = [
        ChapterOutline(number=1, title="开端", summary="开始", mood="悬疑", word_target=1000, foreshadowing=["线索A"], payoffs=[]),
        ChapterOutline(number=2, title="结局", summary="结束", mood="恐惧", word_target=1000, foreshadowing=[], payoffs=["线索A"]),
    ]
    context.chapters = ["第一章内容...", "第二章内容..."]

    mock_llm = Mock()
    reviewer = ReviewerAgent(mock_llm)

    mock_result = '''```json
{
  "passed": true,
  "issues": [],
  "strengths": ["伏笔回收完整", "氛围连贯"],
  "overall_assessment": "整体质量良好"
}
```'''

    with patch.object(reviewer, '_run_agent', return_value=mock_result):
        review = reviewer.final_review(context)

    assert review.passed
    assert "FINAL REVIEW" in context.review_notes[-1]
```

**Step 2: Run tests**

Run: `pytest tests/test_integration.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full pipeline"
```

---

## Task 13: Documentation

**Files:**
- Create: `README.md`

**Step 1: Write README**

Create: `README.md`

```markdown
# CoC Secret Keeper

克苏鲁神话小说生成器 - 多智能体协作的故事创作工具。

## 功能

- **Brainstorm**: 对话式收集故事构思
- **Worldbuilder**: 自动构建克苏鲁世界观
- **Outliner**: 生成章节大纲与伏笔规划
- **Writer**: 逐章撰写正文
- **Reviewer**: 自动审核与分类问题（含逐章修订循环 + 全文终审）

## 安装

```bash
pip install -e ".[dev]"
```

> 需要 Python 3.11+（<3.14）

## 配置

创建 `config.yaml` 或设置环境变量：

```bash
export COC_OPENAI_API_KEY="sk-xxx"
export COC_ANTHROPIC_API_KEY="sk-ant-xxx"
```

## 使用

```bash
streamlit run app.py
```

## 架构

```
用户输入 → Brainstorm → Worldbuilder → Outliner → Writer → Reviewer → 导出
```

## 开发

```bash
pytest tests/
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage instructions"
```

---

## Task 14: Final Verification

**Files:**
- All files

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 2: Verify imports**

Run: `python -c "import app; print('OK')"`
Expected: No import errors

**Step 3: Check code formatting**

Run: `black --check . && ruff check .`
Expected: No issues (or fix them)

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final verification and cleanup"
```

---

## Summary

This implementation plan covers:

1. **Project Setup** - Dependencies (CrewAI 1.10+ with anthropic/openai extras), directory structure with `__init__.py`
2. **Data Models** - Pydantic schemas for story context
3. **LLM Configuration** - Config loading, provider factory (unified `provider/model` format, Anthropic `max_tokens`)
4. **Prompts** - All 5 agent prompts
5. **Brainstorm Agent** - Direct LLM calls for multi-turn conversation (not CrewAI Crew)
6. **4 Pipeline Agents** - Worldbuilder, Outliner, Writer (with `revise_chapter`), Reviewer (with `final_review`)
7. **Streamlit UI** - Full interface with revision loop (minor auto-fix ≤3 rounds, major → user decision) and final review
8. **Settings Page** - LLM configuration UI with config.yaml persistence
9. **Tests** - Unit and integration tests (including revision loop and final review)
10. **Documentation** - README

Total estimated tasks: **14**
