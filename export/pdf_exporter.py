"""PDF导出器模块，用于生成书籍风格的PDF文档。"""

import os
import sys
from typing import Any, BinaryIO
from xml.sax.saxutils import escape

from reportlab.lib.colors import grey  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from models.story_context import StoryContext

# Font candidates per platform: (registered_name, file_path)
_FONT_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "darwin": [
        ("PingFang-SC-Regular", "/System/Library/Fonts/PingFang.ttc"),
        ("Heiti-TC-Medium", "/System/Library/Fonts/STHeiti Medium.ttc"),
    ],
    "win32": [
        (
            "Microsoft-YaHei",
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),
        ),
    ],
    "linux": [
        ("Noto-Sans-CJK-SC", "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
        ("Noto-Sans-CJK-SC", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ("Noto-Sans-CJK-SC", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
        ("WQY-ZenHei", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ],
}


class PDFExporter:
    """PDF导出器，生成包含目录、页眉页脚的书籍风格PDF。"""

    def __init__(self) -> None:
        """初始化PDF导出器。"""
        self.font_name = self._register_font()
        self.styles = self._create_styles()
        self.story_theme = ""
        self.toc_page_count = 1

    def _create_styles(self) -> dict[str, ParagraphStyle]:
        """创建PDF样式。

        Returns:
            dict: 样式字典
        """
        base_styles = getSampleStyleSheet()

        toc_title_style = ParagraphStyle(
            "TOCTitle",
            parent=base_styles["Heading1"],
            fontName=self.font_name,
            fontSize=20,
            alignment=TA_CENTER,
            spaceAfter=20 * mm,
            spaceBefore=10 * mm,
        )

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

        body_style = ParagraphStyle(
            "Body",
            parent=base_styles["Normal"],
            fontName=self.font_name,
            fontSize=11,
            firstLineIndent=22,
            leading=16.5,
            alignment=TA_JUSTIFY,
        )

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

    def _register_font(self) -> str:
        """注册跨平台中文字体。

        Returns:
            str: 注册的字体名称，如果失败则返回Helvetica
        """
        platform = "linux" if sys.platform.startswith("linux") else sys.platform
        candidates = _FONT_CANDIDATES.get(platform, _FONT_CANDIDATES["linux"])

        for font_name, font_path in candidates:
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                return font_name
            except Exception:
                continue

        return "Helvetica"

    def export(self, context: StoryContext, output: BinaryIO) -> None:
        """导出StoryContext为PDF。

        Args:
            context: 故事上下文
            output: 输出流（BytesIO或文件对象）
        """
        self.story_theme = context.seed.get("theme", "未命名故事")

        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=25 * mm,
            rightMargin=25 * mm,
            topMargin=25 * mm,
            bottomMargin=25 * mm,
        )

        frame = Frame(
            25 * mm,
            25 * mm,
            A4[0] - 50 * mm,
            A4[1] - 50 * mm,
            id="normal",
        )
        template = PageTemplate(id="main", frames=[frame], onPage=self._add_header_footer)
        doc.addPageTemplates([template])

        story: list[Any] = []

        # 1. 目录页
        toc_elements = self._build_toc(context)
        story.extend(toc_elements)
        self.toc_page_count = max(1, len(context.outline) // 20)
        story.append(PageBreak())

        # 2. 章节内容
        story.extend(self._build_chapters(context))

        doc.build(story)

    def _add_header_footer(self, canvas, doc) -> None:  # type: ignore[no-untyped-def]
        """添加页眉页脚的回调函数。

        Args:
            canvas: ReportLab画布对象
            doc: 文档对象
        """
        canvas.saveState()

        page_num = canvas.getPageNumber()

        # 页眉（跳过目录页）
        if page_num > self.toc_page_count:
            canvas.setFont(self.font_name, 9)
            canvas.setFillColor(grey)
            canvas.drawCentredString(A4[0] / 2, A4[1] - 15 * mm, self.story_theme)

        # 页脚：页码（所有页）
        canvas.setFont(self.font_name, 9)
        canvas.setFillColor(grey)
        canvas.drawCentredString(A4[0] / 2, 15 * mm, str(page_num))

        canvas.restoreState()

    def _build_toc(self, context: StoryContext) -> list[Any]:
        """构建目录。

        Args:
            context: 故事上下文

        Returns:
            list: 目录元素列表
        """
        elements: list[Any] = []

        title = context.seed.get("theme", "未命名故事")
        title = title.replace("\n", " ").replace("\r", " ")
        elements.append(Paragraph(escape(title), self.styles["toc_title"]))
        elements.append(Spacer(1, 10 * mm))

        for chapter in context.outline:
            entry_text = f"第{chapter.number}章 {escape(chapter.title)}"
            elements.append(Paragraph(entry_text, self.styles["toc_entry"]))
            elements.append(Spacer(1, 5 * mm))

        return elements

    def _build_chapters(self, context: StoryContext) -> list[Any]:
        """构建章节内容。

        Args:
            context: 故事上下文

        Returns:
            list: 章节元素列表
        """
        elements: list[Any] = []

        for i, chapter in enumerate(context.outline):
            if i >= len(context.chapters):
                continue

            chapter_text = context.chapters[i]
            if not chapter_text or not chapter_text.strip():
                continue

            # 章节标题（转义特殊字符）
            title = f"第{chapter.number}章 {escape(chapter.title)}"
            title_para = Paragraph(title, self.styles["chapter_title"])

            # 章节正文（分段，转义特殊字符）
            paragraphs = chapter_text.split("\n\n")
            body_elements = [
                Paragraph(escape(para.strip()), self.styles["body"])
                for para in paragraphs
                if para.strip()
            ]

            if not body_elements:
                continue

            # 保持标题和首段在一起
            elements.append(KeepTogether([title_para, Spacer(1, 5 * mm)] + body_elements[:1]))
            elements.extend(body_elements[1:])
            elements.append(PageBreak())

        return elements
