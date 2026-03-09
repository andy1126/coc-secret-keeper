# PDF导出功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 添加专业的PDF导出功能，采用书籍排版风格（目录、页眉页脚、页码），并移除TXT导出。

**Architecture:** 创建独立的`export`模块封装PDF生成逻辑，使用ReportLab生成书籍风格PDF。在`app.py`的review阶段集成PDF导出按钮，删除TXT导出。跨平台字体加载支持macOS/Windows/Linux。

**Tech Stack:** ReportLab 4.0+, Python 3.11+, Streamlit

---

## Task 1: 添加依赖和创建模块结构

**Files:**
- Modify: `pyproject.toml:6-12`
- Create: `export/__init__.py`
- Create: `export/pdf_exporter.py`

**Step 1: 添加reportlab依赖**

修改 `pyproject.toml`，在 dependencies 数组中添加 reportlab：

```toml
dependencies = [
    "crewai[anthropic,litellm]>=1.10.0",
    "streamlit>=1.30.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "reportlab>=4.0.0",
]
```

**Step 2: 安装依赖**

```bash
uv sync
```

预期输出：Successfully installed reportlab-4.x.x

**Step 3: 创建export模块**

创建 `export/__init__.py`：

```python
from export.pdf_exporter import PDFExporter

__all__ = ["PDFExporter"]
```

**Step 4: 创建PDFExporter骨架**

创建 `export/pdf_exporter.py`：

```python
"""PDF导出器模块，用于生成书籍风格的PDF文档。"""

import sys
from io import BytesIO
from typing import BinaryIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.story_context import StoryContext


class PDFExporter:
    """PDF导出器，生成包含目录、页眉页脚的书籍风格PDF。"""

    def __init__(self) -> None:
        """初始化PDF导出器。"""
        self.font_name = self._register_font()

    def _register_font(self) -> str:
        """注册跨平台中文字体。

        Returns:
            str: 注册的字体名称
        """
        # 占位实现，后续完成
        return "Helvetica"

    def export(self, context: StoryContext, output: BinaryIO) -> None:
        """导出StoryContext为PDF。

        Args:
            context: 故事上下文
            output: 输出流（BytesIO或文件对象）
        """
        # 占位实现，后续完成
        pass
```

**Step 5: 提交**

```bash
git add pyproject.toml export/
git commit -m "feat: add reportlab dependency and export module skeleton"
```

---

## Task 2: 实现跨平台字体加载

**Files:**
- Modify: `export/pdf_exporter.py:15-20`
- Create: `tests/test_pdf_exporter.py`

**Step 1: 编写字体加载测试**

创建 `tests/test_pdf_exporter.py`：

```python
"""PDF导出器测试。"""

from unittest.mock import patch, MagicMock
import sys
import pytest

from export.pdf_exporter import PDFExporter


class TestFontLoading:
    """测试跨平台字体加载。"""

    @patch("sys.platform", "darwin")
    def test_register_font_macos(self) -> None:
        """测试macOS字体加载。"""
        exporter = PDFExporter()
        assert exporter.font_name in ["PingFang-SC-Regular", "Heiti-TC-Medium"]

    @patch("sys.platform", "win32")
    def test_register_font_windows(self) -> None:
        """测试Windows字体加载。"""
        exporter = PDFExporter()
        assert exporter.font_name == "Microsoft-YaHei"

    @patch("sys.platform", "linux")
    def test_register_font_linux(self) -> None:
        """测试Linux字体加载。"""
        exporter = PDFExporter()
        assert exporter.font_name == "Noto-Sans-CJK-SC"

    @patch("export.pdf_exporter.pdfmetrics.registerFont")
    def test_font_fallback_on_error(self, mock_register: MagicMock) -> None:
        """测试字体加载失败时的fallback。"""
        mock_register.side_effect = Exception("Font not found")
        exporter = PDFExporter()
        assert exporter.font_name == "Helvetica"
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_pdf_exporter.py::TestFontLoading -v
```

预期输出：4 failed（字体加载逻辑未实现）

**Step 3: 实现字体加载逻辑**

修改 `export/pdf_exporter.py` 的 `_register_font` 方法：

```python
def _register_font(self) -> str:
    """注册跨平台中文字体。

    Returns:
        str: 注册的字体名称，如果失败则返回Helvetica
    """
    try:
        font_name = self._get_system_font_name()
        # 尝试注册字体（系统字体由系统路径自动查找）
        pdfmetrics.registerFont(TTFont(font_name, font_name))
        return font_name
    except Exception:
        # Fallback到Helvetica（不支持中文，但不会崩溃）
        return "Helvetica"

def _get_system_font_name(self) -> str:
    """根据平台返回系统字体名称。

    Returns:
        str: 字体名称
    """
    if sys.platform == "darwin":  # macOS
        # 尝试PingFang SC，fallback到Heiti TC
        try:
            pdfmetrics.registerFont(TTFont("PingFang-SC-Regular", "PingFang SC"))
            return "PingFang-SC-Regular"
        except Exception:
            return "Heiti-TC-Medium"
    elif sys.platform == "win32":  # Windows
        return "Microsoft-YaHei"
    else:  # Linux
        return "Noto-Sans-CJK-SC"
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/test_pdf_exporter.py::TestFontLoading -v
```

预期输出：4 passed（如果在对应平台）或部分passed（跨平台测试需要mock）

**Step 5: 提交**

```bash
git add export/pdf_exporter.py tests/test_pdf_exporter.py
git commit -m "feat: implement cross-platform font loading for PDF export"
```

---

## Task 3: 实现PDF样式配置

**Files:**
- Modify: `export/pdf_exporter.py:9-30`

**Step 1: 添加样式创建方法**

在 `PDFExporter` 类中添加样式配置方法：

```python
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


def __init__(self) -> None:
    """初始化PDF导出器。"""
    self.font_name = self._register_font()
    self.styles = self._create_styles()

def _create_styles(self) -> dict:
    """创建PDF样式。

    Returns:
        dict: 样式字典
    """
    base_styles = getSampleStyleSheet()

    # 目录标题样式
    toc_title_style = ParagraphStyle(
        "TOCTitle",
        parent=base_styles["Heading1"],
        fontName=self.font_name,
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=20 * mm,
        spaceBefore=10 * mm,
    )

    # 章节标题样式
    chapter_title_style = ParagraphStyle(
        "ChapterTitle",
        parent=base_styles["Heading1"],
        fontName=self.font_name,
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=15 * mm,
        spaceBefore=10 * mm,
        leading=24,
    )

    # 正文样式
    body_style = ParagraphStyle(
        "Body",
        parent=base_styles["Normal"],
        fontName=self.font_name,
        fontSize=11,
        firstLineIndent=22,  # 2字符缩进
        leading=16.5,  # 1.5倍行距
        alignment=TA_JUSTIFY,
    )

    # 目录条目样式
    toc_entry_style = ParagraphStyle(
        "TOCEntry",
        parent=base_styles["Normal"],
        fontName=self.font_name,
        fontSize=11,
        leading=18,
    )

    return {
        "toc_title": toc_title_style,
        "chapter_title": chapter_title_style,
        "body": body_style,
        "toc_entry": toc_entry_style,
    }
```

**Step 2: 提交**

```bash
git add export/pdf_exporter.py
git commit -m "feat: add PDF styles configuration"
```

---

## Task 4: 实现目录生成

**Files:**
- Modify: `export/pdf_exporter.py:50-100`
- Modify: `tests/test_pdf_exporter.py:40-80`

**Step 1: 编写目录生成测试**

在 `tests/test_pdf_exporter.py` 中添加：

```python
from io import BytesIO
from models.story_context import StoryContext
from models.schemas import ChapterOutline


class TestTOCGeneration:
    """测试目录生成。"""

    def test_generate_toc_with_chapters(self) -> None:
        """测试包含章节的目录生成。"""
        context = StoryContext()
        context.seed = {"theme": "测试故事"}
        context.outline = [
            ChapterOutline(
                number=1,
                title="第一章标题",
                summary="摘要1",
                mood="悬疑",
                word_target=1000,
                foreshadowing=[],
                payoffs=[],
            ),
            ChapterOutline(
                number=2,
                title="第二章标题",
                summary="摘要2",
                mood="恐怖",
                word_target=1000,
                foreshadowing=[],
                payoffs=[],
            ),
        ]
        context.chapters = ["第一章内容", "第二章内容"]

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        # 验证PDF生成成功
        assert buffer.tell() > 0
        buffer.seek(0)
        pdf_content = buffer.read()
        assert len(pdf_content) > 1000  # PDF文件大小合理
```

**Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_pdf_exporter.py::TestTOCGeneration -v
```

预期输出：FAILED（export方法未实现）

**Step 3: 实现目录和文档生成**

在 `export/pdf_exporter.py` 中实现 `export` 方法：

```python
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    PageBreak,
    Spacer,
    TableOfContents,
    KeepTogether,
)


def export(self, context: StoryContext, output: BinaryIO) -> None:
    """导出StoryContext为PDF。

    Args:
        context: 故事上下文
        output: 输出流（BytesIO或文件对象）
    """
    # 创建PDF文档
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    # 构建文档内容
    story = []

    # 1. 目录页
    story.extend(self._build_toc(context))
    story.append(PageBreak())

    # 2. 章节内容
    story.extend(self._build_chapters(context))

    # 生成PDF
    doc.build(story)

def _build_toc(self, context: StoryContext) -> list:
    """构建目录。

    Args:
        context: 故事上下文

    Returns:
        list: 目录元素列表
    """
    elements = []

    # 目录标题
    title = context.seed.get("theme", "未命名故事")
    elements.append(Paragraph(title, self.styles["toc_title"]))
    elements.append(Spacer(1, 10 * mm))

    # 章节列表
    for i, chapter in enumerate(context.outline):
        # 简单的目录条目（不使用TableOfContents，避免复杂性）
        entry_text = f"第{chapter.number}章 {chapter.title}"
        elements.append(Paragraph(entry_text, self.styles["toc_entry"]))
        elements.append(Spacer(1, 5 * mm))

    return elements

def _build_chapters(self, context: StoryContext) -> list:
    """构建章节内容。

    Args:
        context: 故事上下文

    Returns:
        list: 章节元素列表
    """
    elements = []

    for i, chapter in enumerate(context.outline):
        if i >= len(context.chapters):
            # 跳过未生成的章节
            continue

        chapter_text = context.chapters[i]
        if not chapter_text.strip():
            # 跳过空章节
            continue

        # 章节标题
        title = f"第{chapter.number}章 {chapter.title}"
        title_para = Paragraph(title, self.styles["chapter_title"])

        # 章节正文（分段）
        paragraphs = chapter_text.split("\n\n")
        body_elements = [
            Paragraph(para.strip(), self.styles["body"])
            for para in paragraphs
            if para.strip()
        ]

        # 保持标题和首段在一起
        elements.append(KeepTogether([title_para, Spacer(1, 5 * mm)] + body_elements[:1]))
        elements.extend(body_elements[1:])
        elements.append(PageBreak())

    return elements
```

**Step 4: 运行测试验证通过**

```bash
uv run pytest tests/test_pdf_exporter.py::TestTOCGeneration -v
```

预期输出：PASSED

**Step 5: 提交**

```bash
git add export/pdf_exporter.py tests/test_pdf_exporter.py
git commit -m "feat: implement TOC and chapter content generation"
```

---

## Task 5: 实现页眉页脚

**Files:**
- Modify: `export/pdf_exporter.py:80-150`

**Step 1: 添加页眉页脚回调**

在 `export/pdf_exporter.py` 中添加页眉页脚处理：

```python
from reportlab.platypus import PageTemplate, Frame
from reportlab.lib.colors import grey


class PDFExporter:
    def __init__(self) -> None:
        """初始化PDF导出器。"""
        self.font_name = self._register_font()
        self.styles = self._create_styles()
        self.current_chapter_title = ""
        self.story_theme = ""
        self.toc_page_count = 1  # 目录页数（初始估计）

    def export(self, context: StoryContext, output: BinaryIO) -> None:
        """导出StoryContext为PDF。

        Args:
            context: 故事上下文
            output: 输出流（BytesIO或文件对象）
        """
        # 保存主题用于页眉
        self.story_theme = context.seed.get("theme", "未命名故事")

        # 创建PDF文档（使用自定义页面模板）
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=25 * mm,
            rightMargin=25 * mm,
            topMargin=25 * mm,  # 增加顶部边距为页眉留空间
            bottomMargin=25 * mm,
        )

        # 设置页面模板
        frame = Frame(
            25 * mm,
            25 * mm,
            A4[0] - 50 * mm,
            A4[1] - 50 * mm,
            id="normal",
        )
        template = PageTemplate(id="main", frames=[frame], onPage=self._add_header_footer)
        doc.addPageTemplates([template])

        # 构建文档内容
        story = []

        # 1. 目录页
        toc_elements = self._build_toc(context)
        story.extend(toc_elements)
        # 估算目录页数（粗略）
        self.toc_page_count = max(1, len(context.outline) // 20)
        story.append(PageBreak())

        # 2. 章节内容
        story.extend(self._build_chapters(context))

        # 生成PDF
        doc.build(story)

    def _add_header_footer(self, canvas, doc) -> None:
        """添加页眉页脚的回调函数。

        Args:
            canvas: ReportLab画布对象
            doc: 文档对象
        """
        canvas.saveState()

        # 页码
        page_num = canvas.getPageNumber()

        # 页眉（跳过目录页）
        if page_num > self.toc_page_count:
            canvas.setFont(self.font_name, 9)
            canvas.setFillColor(grey)

            # 左侧：当前章节标题（如果有）
            if self.current_chapter_title:
                canvas.drawString(25 * mm, A4[1] - 15 * mm, self.current_chapter_title)

            # 右侧：故事主题
            canvas.drawRightString(A4[0] - 25 * mm, A4[1] - 15 * mm, self.story_theme)

        # 页脚：页码（所有页）
        canvas.setFont(self.font_name, 9)
        canvas.setFillColor(grey)
        canvas.drawCentredString(A4[0] / 2, 15 * mm, str(page_num))

        canvas.restoreState()
```

**Step 2: 更新章节构建以跟踪当前章节**

修改 `_build_chapters` 方法，在生成章节时更新 `current_chapter_title`：

注意：由于 ReportLab 的限制，页眉中的章节标题需要通过回调机制更新。这里采用简化方案：页眉只显示固定的故事主题，不显示动态章节标题（避免复杂的状态管理）。

实际修改：移除页眉中的章节标题，只保留故事主题。

```python
def _add_header_footer(self, canvas, doc) -> None:
    """添加页眉页脚的回调函数。

    Args:
        canvas: ReportLab画布对象
        doc: 文档对象
    """
    canvas.saveState()

    # 页码
    page_num = canvas.getPageNumber()

    # 页眉（跳过目录页）
    if page_num > self.toc_page_count:
        canvas.setFont(self.font_name, 9)
        canvas.setFillColor(grey)

        # 居中显示故事主题
        canvas.drawCentredString(A4[0] / 2, A4[1] - 15 * mm, self.story_theme)

    # 页脚：页码（所有页）
    canvas.setFont(self.font_name, 9)
    canvas.setFillColor(grey)
    canvas.drawCentredString(A4[0] / 2, 15 * mm, str(page_num))

    canvas.restoreState()
```

并移除不需要的 `current_chapter_title` 属性。

**Step 3: 提交**

```bash
git add export/pdf_exporter.py
git commit -m "feat: add header and footer to PDF pages"
```

---

## Task 6: 集成到app.py并删除TXT导出

**Files:**
- Modify: `app.py:715-740`
- Modify: `app.py:1-10` (添加import)

**Step 1: 删除TXT导出并添加PDF导出**

修改 `app.py` 中的 `render_review_stage` 函数导出部分：

找到第715-740行的导出代码，替换为：

```python
from io import BytesIO
from export.pdf_exporter import PDFExporter

# ... 在render_review_stage函数中 ...

st.divider()

# Export buttons
st.subheader("导出")
col1, col2 = st.columns(2)

with col1:
    # Markdown导出（保留）
    md_text = f"# {context.seed.get('theme', '克苏鲁故事')}\n\n"
    for i, text in enumerate(context.chapters):
        md_text += f"## 第{i+1}章: {context.outline[i].title}\n\n{text}\n\n"
    st.download_button(
        "导出为Markdown",
        md_text,
        file_name="coc_story.md",
        mime="text/markdown",
    )

with col2:
    # PDF导出（新增）
    try:
        pdf_buffer = BytesIO()
        exporter = PDFExporter()
        exporter.export(context, pdf_buffer)
        pdf_buffer.seek(0)

        st.download_button(
            "导出为PDF",
            pdf_buffer,
            file_name="coc_story.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(f"PDF生成失败: {str(e)}")
        st.caption("提示: 请确保系统已安装中文字体")
```

**Step 2: 手动测试**

```bash
uv run streamlit run app.py
```

操作步骤：
1. 完成一个完整的故事创作流程（或使用测试数据）
2. 到达review阶段
3. 确认只显示"导出为Markdown"和"导出为PDF"两个按钮
4. 点击"导出为PDF"，下载并打开PDF
5. 验证PDF包含目录、章节、页眉页脚、页码

预期结果：PDF正确生成并可下载

**Step 3: 提交**

```bash
git add app.py
git commit -m "feat: integrate PDF export and remove TXT export"
```

---

## Task 7: 添加边界情况处理

**Files:**
- Modify: `export/pdf_exporter.py:100-150`
- Modify: `tests/test_pdf_exporter.py:80-150`

**Step 1: 编写边界情况测试**

在 `tests/test_pdf_exporter.py` 中添加：

```python
class TestEdgeCases:
    """测试边界情况。"""

    def test_export_empty_chapters(self) -> None:
        """测试空章节处理。"""
        context = StoryContext()
        context.seed = {"theme": "测试"}
        context.outline = [
            ChapterOutline(
                number=1,
                title="空章节",
                summary="空",
                mood="测试",
                word_target=1000,
                foreshadowing=[],
                payoffs=[],
            ),
        ]
        context.chapters = [""]  # 空内容

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        # 应该只生成目录，没有正文
        assert buffer.tell() > 0

    def test_export_missing_theme(self) -> None:
        """测试缺失主题。"""
        context = StoryContext()
        context.seed = {}  # 无theme
        context.outline = []
        context.chapters = []

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        # 应该使用默认主题
        assert buffer.tell() > 0

    def test_export_special_characters(self) -> None:
        """测试特殊字符处理。"""
        context = StoryContext()
        context.seed = {"theme": "测试\n换行"}
        context.outline = [
            ChapterOutline(
                number=1,
                title="特殊字符<>&",
                summary="测试",
                mood="测试",
                word_target=1000,
                foreshadowing=[],
                payoffs=[],
            ),
        ]
        context.chapters = ["包含特殊字符：<>&\"'"]

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        # 应该正确处理特殊字符
        assert buffer.tell() > 0

    def test_export_incomplete_chapters(self) -> None:
        """测试章节数量不匹配。"""
        context = StoryContext()
        context.seed = {"theme": "测试"}
        context.outline = [
            ChapterOutline(
                number=1,
                title="第一章",
                summary="1",
                mood="测试",
                word_target=1000,
                foreshadowing=[],
                payoffs=[],
            ),
            ChapterOutline(
                number=2,
                title="第二章",
                summary="2",
                mood="测试",
                word_target=1000,
                foreshadowing=[],
                payoffs=[],
            ),
        ]
        context.chapters = ["第一章内容"]  # 只有一章

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        # 应该只导出第一章
        assert buffer.tell() > 0
```

**Step 2: 运行测试**

```bash
uv run pytest tests/test_pdf_exporter.py::TestEdgeCases -v
```

预期输出：大部分测试应该通过（现有实现已经处理了部分边界情况）

**Step 3: 增强边界情况处理**

如果测试失败，修改 `export/pdf_exporter.py` 中的相关方法：

```python
def _build_toc(self, context: StoryContext) -> list:
    """构建目录。

    Args:
        context: 故事上下文

    Returns:
        list: 目录元素列表
    """
    elements = []

    # 目录标题（处理缺失和特殊字符）
    title = context.seed.get("theme", "未命名故事")
    # 移除换行符
    title = title.replace("\n", " ").replace("\r", " ")
    elements.append(Paragraph(title, self.styles["toc_title"]))
    elements.append(Spacer(1, 10 * mm))

    # 章节列表
    for i, chapter in enumerate(context.outline):
        # HTML转义特殊字符
        from xml.sax.saxutils import escape
        safe_title = escape(chapter.title)
        entry_text = f"第{chapter.number}章 {safe_title}"
        elements.append(Paragraph(entry_text, self.styles["toc_entry"]))
        elements.append(Spacer(1, 5 * mm))

    return elements

def _build_chapters(self, context: StoryContext) -> list:
    """构建章节内容。

    Args:
        context: 故事上下文

    Returns:
        list: 章节元素列表
    """
    from xml.sax.saxutils import escape

    elements = []

    for i, chapter in enumerate(context.outline):
        if i >= len(context.chapters):
            # 跳过未生成的章节
            continue

        chapter_text = context.chapters[i]
        if not chapter_text or not chapter_text.strip():
            # 跳过空章节
            continue

        # 章节标题（转义特殊字符）
        safe_title = escape(chapter.title)
        title = f"第{chapter.number}章 {safe_title}"
        title_para = Paragraph(title, self.styles["chapter_title"])

        # 章节正文（分段，转义特殊字符）
        paragraphs = chapter_text.split("\n\n")
        body_elements = []
        for para in paragraphs:
            if para.strip():
                safe_para = escape(para.strip())
                body_elements.append(Paragraph(safe_para, self.styles["body"]))

        if not body_elements:
            # 如果没有有效段落，跳过该章节
            continue

        # 保持标题和首段在一起
        elements.append(KeepTogether([title_para, Spacer(1, 5 * mm)] + body_elements[:1]))
        elements.extend(body_elements[1:])
        elements.append(PageBreak())

    return elements
```

**Step 4: 重新运行测试验证通过**

```bash
uv run pytest tests/test_pdf_exporter.py::TestEdgeCases -v
```

预期输出：4 passed

**Step 5: 提交**

```bash
git add export/pdf_exporter.py tests/test_pdf_exporter.py
git commit -m "feat: add edge case handling for PDF export"
```

---

## Task 8: 完整测试和文档

**Files:**
- Modify: `tests/test_pdf_exporter.py:150-200`
- Create: `export/README.md`

**Step 1: 添加集成测试**

在 `tests/test_pdf_exporter.py` 中添加完整的集成测试：

```python
class TestIntegration:
    """集成测试。"""

    def test_full_export_workflow(self) -> None:
        """测试完整的导出流程。"""
        # 构建完整的Story Context
        from models.schemas import Character, Entity, WorldSetting

        context = StoryContext()
        context.seed = {
            "theme": "深海之谜",
            "era": "1920年代",
            "atmosphere": "恐怖",
        }

        context.world = WorldSetting(
            era="1924年，阿卡姆镇",
            locations=["密斯卡托尼克大学"],
            entities=[Entity(name="克苏鲁", description="沉睡的神", influence="梦境")],
            forbidden_knowledge="人类渺小",
            rules=["不可直视"],
            characters=[
                Character(
                    name="李教授",
                    background="考古学家",
                    personality="严谨",
                    motivation="求知",
                    arc="堕落",
                    relationships=[],
                )
            ],
        )

        context.outline = [
            ChapterOutline(
                number=1,
                title="开端",
                summary="主角发现手稿",
                mood="悬疑",
                word_target=1000,
                foreshadowing=["手稿符号"],
                payoffs=[],
            ),
            ChapterOutline(
                number=2,
                title="调查",
                summary="深入研究",
                mood="紧张",
                word_target=1500,
                foreshadowing=["梦境"],
                payoffs=["手稿符号"],
            ),
            ChapterOutline(
                number=3,
                title="真相",
                summary="发现真相",
                mood="恐怖",
                word_target=2000,
                foreshadowing=[],
                payoffs=["梦境"],
            ),
        ]

        context.chapters = [
            "第一章内容：李教授在大学图书馆发现了一本古老的手稿。\n\n手稿上布满了神秘的符号。",
            "第二章内容：他开始深入研究这些符号，夜晚做了奇怪的梦。\n\n梦境中出现了深海的景象。",
            "第三章内容：最终他意识到，这些符号指向了沉睡在深海的克苏鲁。\n\n但为时已晚。",
        ]

        # 导出PDF
        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        # 验证
        buffer.seek(0)
        pdf_data = buffer.read()

        # 基本验证
        assert len(pdf_data) > 5000  # PDF应该有合理大小
        assert pdf_data.startswith(b"%PDF")  # PDF文件头

        # 可选：写入文件用于手动检查
        # with open("/tmp/test_output.pdf", "wb") as f:
        #     f.write(pdf_data)
```

**Step 2: 运行全部测试**

```bash
uv run pytest tests/test_pdf_exporter.py -v
```

预期输出：All tests passed

**Step 3: 创建模块文档**

创建 `export/README.md`：

```markdown
# Export模块

PDF导出功能模块，用于将生成的克苏鲁故事导出为专业的书籍风格PDF。

## 功能特性

- **跨平台字体支持**：自动检测并使用系统中文字体（macOS/Windows/Linux）
- **书籍排版**：包含目录、章节分页、页眉页脚、页码
- **边界情况处理**：空章节、特殊字符、缺失数据等
- **Streamlit集成**：内存流式导出，无需临时文件

## 使用方法

```python
from io import BytesIO
from export.pdf_exporter import PDFExporter
from models.story_context import StoryContext

# 创建导出器
exporter = PDFExporter()

# 导出到内存
buffer = BytesIO()
exporter.export(context, buffer)

# 在Streamlit中提供下载
buffer.seek(0)
st.download_button("导出PDF", buffer, "story.pdf", "application/pdf")
```

## PDF结构

1. **目录页**：标题 + 章节列表
2. **正文页**：每章独立分页，包含章节标题和正文
3. **页眉**：故事主题（居中）
4. **页脚**：页码（居中）

## 系统字体

- **macOS**: PingFang SC / Heiti TC
- **Windows**: Microsoft YaHei
- **Linux**: Noto Sans CJK SC
- **Fallback**: Helvetica（仅英文）

## 测试

```bash
# 运行所有测试
uv run pytest tests/test_pdf_exporter.py -v

# 运行特定测试
uv run pytest tests/test_pdf_exporter.py::TestFontLoading -v
```

## 依赖

- `reportlab>=4.0.0`：PDF生成库
- Python 3.11+

## 注意事项

- 字体加载失败时会fallback到Helvetica，中文可能显示为方框
- PDF生成时间取决于章节数量和长度（通常<5秒）
- 支持特殊字符自动转义
```

**Step 4: 提交**

```bash
git add tests/test_pdf_exporter.py export/README.md
git commit -m "test: add integration tests and module documentation"
```

---

## Task 9: 最终验证和清理

**Files:**
- Run full test suite
- Manual testing

**Step 1: 运行所有测试**

```bash
# 运行所有测试
uv run pytest tests/ -v

# 运行type checking
uv run mypy .

# 运行linting
uv run ruff check .
uv run black --check .
```

预期输出：All tests passed, no type errors, no linting issues

**Step 2: 修复任何linting/type问题**

如果有类型错误或格式问题：

```bash
# 自动修复格式
uv run black .
uv run ruff check --fix .

# 提交修复
git add .
git commit -m "chore: fix linting and type issues"
```

**Step 3: 手动端到端测试**

```bash
uv run streamlit run app.py
```

完整测试流程：
1. 创建一个新故事（或使用已有测试数据）
2. 完成所有阶段（brainstorm → world → outline → writing → review）
3. 在review阶段，验证：
   - 只显示"导出为Markdown"和"导出为PDF"两个按钮
   - TXT导出按钮已删除
4. 点击"导出为PDF"
5. 下载PDF并打开验证：
   - 目录页包含所有章节
   - 每章独立分页
   - 页眉显示故事主题
   - 页脚显示页码
   - 中文字符正确显示
   - 段落首行缩进正确
6. 尝试边界情况：
   - 超长章节（>5000字）- 应该自动分页
   - 包含特殊字符的标题 - 应该正确转义

**Step 4: 最终提交**

```bash
git add .
git commit -m "chore: final verification and cleanup for PDF export feature"
```

**Step 5: 更新主README（可选）**

如果项目根目录有README，添加PDF导出功能说明：

```bash
# 编辑README.md，添加：
## 导出功能

- **Markdown**: 导出为Markdown格式文本文件
- **PDF**: 导出为书籍排版风格的PDF，包含目录、页眉页脚、页码

git add README.md
git commit -m "docs: update README with PDF export feature"
```

---

## 完成标准

- [x] Task 1: 添加reportlab依赖和模块结构
- [x] Task 2: 实现跨平台字体加载
- [x] Task 3: 实现PDF样式配置
- [x] Task 4: 实现目录生成
- [x] Task 5: 实现页眉页脚
- [x] Task 6: 集成到app.py并删除TXT导出
- [x] Task 7: 添加边界情况处理
- [x] Task 8: 完整测试和文档
- [x] Task 9: 最终验证和清理

**验证清单**：
- [ ] PDF包含目录，显示所有章节
- [ ] 正文每章独立分页，有页眉页脚
- [ ] 中文字符正确显示
- [ ] 页码连续且正确
- [ ] 文件大小合理（< 10MB）
- [ ] 导出时间 < 5秒
- [ ] 在macOS/Windows/Linux上成功生成
- [ ] app.py中TXT导出已删除
- [ ] 所有测试通过
- [ ] 无类型错误和linting问题

---

## 预估时间

- Task 1-3: 30分钟（基础设施）
- Task 4-5: 45分钟（核心功能）
- Task 6: 15分钟（集成）
- Task 7-8: 30分钟（测试和文档）
- Task 9: 20分钟（验证）

**总计**: ~2.5小时

---

## 回滚计划

如果遇到不可解决的问题：

```bash
# 回滚到开始状态
git log --oneline  # 找到开始前的commit
git reset --hard <commit-hash>

# 或者只删除export模块
rm -rf export/
git checkout pyproject.toml app.py
```

---

## 参考资料

- [ReportLab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [ReportLab中文字体配置](https://stackoverflow.com/questions/1846948/reportlab-and-unicode)
- 设计文档: `docs/plans/2026-03-09-pdf-export-design.md`
