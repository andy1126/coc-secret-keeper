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
uv sync --extra dev
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
uv run streamlit run app.py
```

## 架构

```
用户输入 → Brainstorm → Worldbuilder → Outliner → Writer → Reviewer → 导出
```

## 开发

```bash
uv run pytest tests/
```
