"""PDF导出器测试。"""

from io import BytesIO
from unittest.mock import patch, MagicMock

from export.pdf_exporter import PDFExporter
from models.schemas import Character, ChapterOutline, Entity, Location, WorldSetting
from models.story_context import StoryContext


class TestFontLoading:
    """测试跨平台字体加载。"""

    @patch("export.pdf_exporter.pdfmetrics.registerFont")
    @patch("export.pdf_exporter.TTFont")
    @patch("sys.platform", "darwin")
    def test_register_font_macos(self, mock_ttfont: MagicMock, mock_register: MagicMock) -> None:
        """测试macOS字体加载。"""
        exporter = PDFExporter()
        assert exporter.font_name in ["PingFang-SC-Regular", "Heiti-TC-Medium"]

    @patch("export.pdf_exporter.pdfmetrics.registerFont")
    @patch("export.pdf_exporter.TTFont")
    @patch("sys.platform", "win32")
    def test_register_font_windows(self, mock_ttfont: MagicMock, mock_register: MagicMock) -> None:
        """测试Windows字体加载。"""
        exporter = PDFExporter()
        assert exporter.font_name == "Microsoft-YaHei"

    @patch("export.pdf_exporter.pdfmetrics.registerFont")
    @patch("export.pdf_exporter.TTFont")
    @patch("sys.platform", "linux")
    def test_register_font_linux(self, mock_ttfont: MagicMock, mock_register: MagicMock) -> None:
        """测试Linux字体加载。"""
        exporter = PDFExporter()
        assert exporter.font_name == "Noto-Sans-CJK-SC"

    @patch("export.pdf_exporter.pdfmetrics.registerFont")
    def test_font_fallback_on_error(self, mock_register: MagicMock) -> None:
        """测试字体加载失败时的fallback。"""
        mock_register.side_effect = Exception("Font not found")
        exporter = PDFExporter()
        assert exporter.font_name == "Helvetica"


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
        assert len(pdf_content) > 1000


def _make_outline(number: int, title: str) -> ChapterOutline:
    """Helper to create a ChapterOutline with defaults."""
    return ChapterOutline(
        number=number,
        title=title,
        summary="s",
        mood="m",
        word_target=1000,
        foreshadowing=[],
        payoffs=[],
    )


class TestEdgeCases:
    """测试边界情况。"""

    def test_export_empty_chapters(self) -> None:
        """测试空章节处理。"""
        context = StoryContext()
        context.seed = {"theme": "测试"}
        context.outline = [_make_outline(1, "空章节")]
        context.chapters = [""]

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)
        assert buffer.tell() > 0

    def test_export_missing_theme(self) -> None:
        """测试缺失主题。"""
        context = StoryContext()
        context.seed = {}
        context.outline = []
        context.chapters = []

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)
        assert buffer.tell() > 0

    def test_export_special_characters(self) -> None:
        """测试特殊字符处理。"""
        context = StoryContext()
        context.seed = {"theme": "测试\n换行"}
        context.outline = [_make_outline(1, "特殊字符<>&")]
        context.chapters = ["包含特殊字符：<>&\"'"]

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)
        assert buffer.tell() > 0

    def test_export_incomplete_chapters(self) -> None:
        """测试章节数量不匹配。"""
        context = StoryContext()
        context.seed = {"theme": "测试"}
        context.outline = [_make_outline(1, "第一章"), _make_outline(2, "第二章")]
        context.chapters = ["第一章内容"]

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)
        assert buffer.tell() > 0


class TestIntegration:
    """集成测试。"""

    def test_full_export_workflow(self) -> None:
        """测试完整的导出流程。"""
        context = StoryContext()
        context.seed = {
            "theme": "深海之谜",
            "era": "1920年代",
            "atmosphere": "恐怖",
        }

        context.world = WorldSetting(
            era="1924年，阿卡姆镇",
            locations=[Location(name="密斯卡托尼克大学", description="大学")],
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

        exporter = PDFExporter()
        buffer = BytesIO()
        exporter.export(context, buffer)

        buffer.seek(0)
        pdf_data = buffer.read()

        assert len(pdf_data) > 5000
        assert pdf_data.startswith(b"%PDF")
