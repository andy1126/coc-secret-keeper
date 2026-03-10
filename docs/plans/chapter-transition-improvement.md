# Plan: 改善章节大纲覆盖与章节间衔接

## Context

Writer 生成章节时经常出现两个问题：

1. **章节结尾未完全按大纲生成** — 大纲的 `summary` 是 150-200 字的散文，Writer 容易在前半段铺陈太多，后半段丢失情节点。缺少结构化的情节节拍（scene beats）作为执行清单。
2. **章节间衔接不自然** — Writer 只有上一章的压缩摘要，丢失了结尾的具体场景细节；也不知道下一章需要什么，无法"留口"。

## 改动总览

| # | 改动 | 解决问题 |
|---|------|---------|
| 1 | ChapterOutline 新增 `key_beats` 字段 | 大纲覆盖 |
| 2 | Outliner prompt/输出 生成 key_beats | 大纲覆盖 |
| 3 | Writer task_desc 中按 key_beats 逐条要求 | 大纲覆盖 |
| 4 | Reviewer 对照 key_beats 逐条检查 | 大纲覆盖 |
| 5 | Writer task_desc 传入下一章大纲预览 | 衔接 |
| 6 | Writer task_desc 传入上一章末尾原文 | 衔接 |
| 7 | StoryContext 新增 `chapter_endings` + Writer 写入末尾原文 | 衔接 |
| 8 | Reviewer task_desc 传入上一章末尾 + 检查衔接 | 衔接 |
| 9 | Writer/Reviewer prompt 更新 | 两者 |
| 10 | 大纲 UI 展示 key_beats | UI 适配 |

---

## 详细设计

### 1. ChapterOutline 新增 `key_beats` 字段

**文件**: `models/schemas.py`

```python
class ChapterOutline(BaseModel):
    number: int = Field(description="章节序号")
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要")
    mood: str = Field(description="情绪基调")
    word_target: int = Field(description="目标字数")
    foreshadowing: list[str] = Field(default_factory=list, description="伏笔列表")
    payoffs: list[str] = Field(default_factory=list, description="回收点列表")
    pov: str = Field(default="", description="主要叙述视角")
    information_reveal: list[str] = Field(default_factory=list, description="本章揭示的信息")
    twist: str | None = Field(default=None, description="本章反转")
    subplot: str | None = Field(default=None, description="本章推进的副线")
    key_beats: list[str] = Field(default_factory=list, description="关键情节节拍")  # NEW
```

使用 `default_factory=list` 保持向后兼容（旧存档没有此字段也能正常加载）。

### 2. Outliner prompt/输出格式 生成 key_beats

**文件**: `prompts/outliner.md`

在职责中增加：
```
7. 为每章设计3-5个关键情节节拍（key_beats），每个节拍是一个必须在章节中发生的具体事件或场景
```

在输出格式的 JSON 示例中增加 `key_beats` 字段：
```json
{
  "number": 1,
  "title": "章节标题",
  "summary": "章节摘要（150字左右）",
  "mood": "情绪基调",
  "word_target": 2000,
  "foreshadowing": ["伏笔1"],
  "payoffs": ["回收1"],
  "key_beats": ["主角在图书馆发现古籍", "与馆长的对话揭示失踪事件", "夜间独自翻阅时听到低语"]
}
```

在设计原则中增加：
```
- key_beats 应按时间顺序排列，覆盖章节从开头到结尾的关键节点
- 每个 beat 是一句话描述的具体事件，不是抽象描述
```

### 3. Writer: 按 key_beats 逐条要求

**文件**: `agents/writer.py` — `write_chapter()` 方法

在 task_desc 中，将 key_beats 作为显式清单传入：

```python
beats_checklist = ""
if chapter.key_beats:
    beats_list = "\n".join(f"  {i+1}. {beat}" for i, beat in enumerate(chapter.key_beats))
    beats_checklist = f"""
Key Beats Checklist (MUST cover ALL of these in order):
{beats_list}
"""
```

在 task_desc 末尾追加强指令：
```
IMPORTANT: You MUST cover every key beat listed above. Do not conclude the chapter
until all beats have been addressed. Check this list before writing your ending.
```

### 4. Reviewer: 对照 key_beats 逐条检查

**文件**: `agents/reviewer.py` — `review_chapter()` 方法

在 task_desc 的 IMPORTANT 检查项中新增：

```python
beats_check = ""
if chapter_outline and chapter_outline.get("key_beats"):
    beats_list = "\n".join(f"  - {b}" for b in chapter_outline["key_beats"])
    beats_check = f"""
4. Check each key beat below. Report ANY missing beat as category "completeness" severity "major":
{beats_list}
"""
```

### 5. Writer: 传入下一章大纲预览

**文件**: `agents/writer.py` — `write_chapter()` 方法

```python
next_chapter_info = "这是最后一章，请确保给出合适的结局。"
if chapter.number < len(context.outline):
    next_ch = context.outline[chapter.number]  # chapter.number 是 1-indexed，正好是下一章的 0-indexed
    next_chapter_info = (
        f"下一章：第{next_ch.number}章「{next_ch.title}」\n"
        f"情绪基调：{next_ch.mood}\n"
        f"摘要：{next_ch.summary}"
    )
```

task_desc 追加：
```
Next Chapter Preview:
{next_chapter_info}

Ensure the chapter ending naturally sets up the transition to the next chapter.
```

### 6. Writer: 传入上一章末尾原文

**文件**: `agents/writer.py` — `write_chapter()` 方法

从 `chapter_endings` 读取（由第 7 项写入），避免每次从完整章节文本截取：

```python
previous_ending = "无（这是第一章）"
if context.chapter_endings:
    previous_ending = context.chapter_endings[-1]
```

task_desc 追加：
```
Previous Chapter Ending (last 500 chars):
{previous_ending}

The opening of this chapter must naturally continue from the above ending.
```

### 7. StoryContext 新增 `chapter_endings` + Writer 写入末尾原文

将末尾原文存为独立字段而非嵌入摘要，避免摘要膨胀（摘要会在后续所有章节中累积传入，token 消耗翻倍）。末尾原文只需传给相邻章节。

**文件**: `models/story_context.py`

```python
class StoryContext(BaseModel):
    # ... existing fields ...
    chapter_endings: list[str] = Field(default_factory=list, description="各章末尾原文（最后500字）")
```

**文件**: `agents/writer.py` — `write_chapter()` 方法

在 `context.chapters.append(result)` 之后追加：
```python
ending = result[-500:] if len(result) > 500 else result
context.chapter_endings.append(ending)
```

**文件**: `agents/writer.py` — `write_chapter()` 方法（上一章末尾来源改用 chapter_endings）

将第 6 项的上一章末尾取值改为：
```python
previous_ending = "无（这是第一章）"
if context.chapter_endings:
    previous_ending = context.chapter_endings[-1]
```

**文件**: `agents/reviewer.py` — `review_chapter()` 方法（同理改用 chapter_endings）

```python
previous_ending = ""
if chapter_number > 1 and chapter_number - 2 < len(context.chapter_endings):
    previous_ending = f"\nPrevious Chapter Ending (last 500 chars):\n{context.chapter_endings[chapter_number - 2]}"
```

### 8. Reviewer: 传入上一章末尾 + 检查衔接

**文件**: `agents/reviewer.py` — `review_chapter()` 方法

在构建 `previous_text` 之后，额外传入上一章末尾原文（取自 `chapter_endings`，已在第 7 项中实现）：

```python
previous_ending = ""
if chapter_number > 1 and chapter_number - 2 < len(context.chapter_endings):
    previous_ending = (
        f"\nPrevious Chapter Ending (last 500 chars):\n"
        f"{context.chapter_endings[chapter_number - 2]}"
    )
```

在 IMPORTANT 检查项中追加衔接检查（第 4 或第 5 条）：
```
Does the chapter opening naturally connect to the previous chapter's ending?
Check for scene continuity, emotional flow, and logical progression.
If there is a jarring disconnect, report as category "completeness" severity "major".
```

### 9. Prompt 更新

**文件**: `prompts/writer.md` — 连贯性部分增加：
```
- 章节开头自然衔接上一章末尾（场景、情绪、语气连贯）
- 章节结尾为下一章铺路（参考下一章大纲预览）
- 必须覆盖 key_beats 中的所有节拍，写结尾前核对清单
```

**文件**: `prompts/reviewer.md` — 大问题分类中增加：
```
- key_beats 中的情节节拍被遗漏
- 章节开头与上一章结尾衔接断裂（场景、情绪、逻辑不连贯）
```

### 10. 大纲 UI 展示 key_beats

**文件**: `app.py` — `_render_outline_tab()` 函数中大纲展示部分

在 subplot 展示之后增加：
```python
if chapter.key_beats:
    st.write(f"**关键节拍**: {', '.join(chapter.key_beats)}")
```

---

## 涉及文件

| 文件 | 改动内容 |
|------|---------|
| `models/schemas.py` | ChapterOutline 加 `key_beats` 字段 |
| `models/story_context.py` | StoryContext 加 `chapter_endings` 字段 |
| `prompts/outliner.md` | 职责 + 输出格式 + 设计原则 加 key_beats |
| `agents/writer.py` | `write_chapter()` 加 key_beats 清单 + 下一章预览 + 上一章末尾 + 写入 chapter_endings |
| `agents/reviewer.py` | `review_chapter()` 加 key_beats 逐条检查 + 上一章末尾（从 chapter_endings 读取）+ 衔接检查 |
| `prompts/writer.md` | 连贯性部分加 key_beats + 衔接指引 |
| `prompts/reviewer.md` | 大问题分类加 key_beats 遗漏 + 衔接断裂 |
| `app.py` | `_render_outline_tab()` 加 key_beats 显示 |
| `tests/test_schemas.py` | key_beats 默认值测试 |
| `tests/test_writer.py` | key_beats/下一章预览/上一章末尾 出现在 task_desc 中的测试 |
| `tests/test_reviewer.py` | key_beats 检查 + 衔接检查 出现在 task_desc 中的测试 |

## 验证

### 单元测试（新增）

**文件**: `tests/test_schemas.py`

```python
def test_chapter_outline_key_beats_default():
    """key_beats 默认空列表，向后兼容。"""
    chapter = ChapterOutline(number=1, title="开端", summary="摘要", mood="悬疑", word_target=3000)
    assert chapter.key_beats == []


def test_chapter_outline_with_key_beats():
    chapter = ChapterOutline(
        number=1, title="开端", summary="摘要", mood="悬疑", word_target=3000,
        key_beats=["发现古籍", "与馆长对话", "听到低语"],
    )
    assert len(chapter.key_beats) == 3
```

**文件**: `tests/test_writer.py`

```python
def test_write_chapter_includes_key_beats():
    """key_beats 应作为清单出现在 task_desc 中。"""
    # Mock _run_agent, 验证 call_args 中包含 "Key Beats Checklist"
    # 和每个 beat 文本


def test_write_chapter_includes_next_chapter_preview():
    """非最后一章时应包含下一章预览。"""
    # 构建 context.outline 含 2 章, 写第 1 章
    # 验证 task_desc 包含第 2 章标题


def test_write_chapter_includes_previous_ending():
    """非第一章时应包含上一章末尾原文。"""
    # context.chapter_endings = ["...上一章末尾..."]
    # 验证 task_desc 包含该文本


def test_write_chapter_appends_chapter_ending():
    """write_chapter 应将末尾 500 字写入 chapter_endings。"""
    # 验证 context.chapter_endings 长度增加 1
```

**文件**: `tests/test_reviewer.py`

```python
def test_review_includes_key_beats_check():
    """Reviewer task_desc 应包含 key_beats 逐条检查。"""
    # 构建含 key_beats 的 outline, 验证 task_desc


def test_review_includes_previous_ending():
    """非第一章时 Reviewer 应包含上一章末尾。"""
    # context.chapter_endings = ["...末尾..."]
    # 验证 task_desc 包含该文本
```

### 自动化检查

1. `uv run pytest tests/` — 所有测试通过（含新增测试）
2. `uv run ruff check .` — 无 lint 错误
3. `uv run black --check .` — 格式正确

### 手动验证

4. 加载旧存档确认 ChapterOutline 无 key_beats 时不报错
5. `uv run streamlit run app.py` 走完 design → writing 流程确认 key_beats 展示和覆盖效果
