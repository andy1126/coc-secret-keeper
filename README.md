# CoC Secret Keeper

克苏鲁神话小说生成器 — 多智能体协作的故事创作工具。

## 功能

- **Brainstorm** — 对话式收集故事构思（主题、时代、氛围、主角等）
- **Worldbuilder** — 自动构建克苏鲁世界观（地点、神话实体、角色），支持基于反馈在已有版本上修改
- **Outliner** — 生成章节大纲，规划伏笔埋设与回收，支持基于反馈在已有版本上修改
- **Writer** — 逐章撰写正文，支持基于审核反馈的修订
- **Reviewer** — 自动审核章节质量，小问题自动修订（最多 3 轮），大问题交由用户决策；完稿后进行全文终审（伏笔回收、角色弧线、氛围连贯、首尾呼应）

## 安装

```bash
uv sync --extra dev
```

> 需要 Python 3.11+（<3.14）

## 使用

```bash
uv run streamlit run app.py
```

创作流程：故事构思 → 世界观构建 → 大纲生成 → 章节写作（含审核修订循环） → 全文终审 → 导出（Markdown / PDF）

世界观和大纲阶段支持"根据意见重新生成"：输入修改意见后，LLM 会在已有版本基础上修改，而非从头创建。

## 配置

### 方式一：UI 设置页

启动应用后在侧边栏选择「设置」页面，可直接配置 Provider 和 Agent 分配。

### 方式二：config.yaml

```yaml
llm:
  default_provider: anthropic_api
  providers:
    anthropic_api:
      type: anthropic_compatible    # 或 openai_compatible
      api_key: sk-xxx
      base_url: https://api.example.com
      model: model-name

agents:
  brainstorm:
    provider: anthropic_api
  worldbuilder:
    provider: anthropic_api
  outliner:
    provider: anthropic_api
  writer:
    provider: anthropic_api
  reviewer:
    provider: anthropic_api
```

### 方式三：环境变量

```bash
export COC_ANTHROPIC_API_API_KEY="sk-xxx"
export COC_ANTHROPIC_API_BASE_URL="https://api.example.com"
export COC_ANTHROPIC_API_MODEL="model-name"
```

命名规则：`COC_{PROVIDER名称大写}_{字段}`，字段为 `API_KEY`、`BASE_URL` 或 `MODEL`。

**优先级**：环境变量 > config.yaml > UI 设置页

## 日志

LLM 交互日志同时输出到控制台和 `logs/coc.log`（5MB 自动轮转，保留 3 份备份）。

## 开发

```bash
# 代码检查
uv run ruff check .
uv run black --check .
uv run mypy .

# 运行测试
uv run pytest tests/
```
