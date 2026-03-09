import json
from datetime import datetime
from io import BytesIO
from typing import Any

import streamlit as st

from export.pdf_exporter import PDFExporter
from models.story_context import StoryContext
from llm.config import load_config, get_agent_config
from llm.logging import setup_logging, CoCLLMLogger
from llm.provider import get_llm_for_agent
from ui.crew_progress import crew_progress


def init_session():
    """Initialize session state."""
    if "context" not in st.session_state:
        st.session_state.context = StoryContext()
    if "stage" not in st.session_state:
        st.session_state.stage = "brainstorm"
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


SAVE_VERSION = 1
VALID_STAGES = {"brainstorm", "world", "outline", "writing", "review", "complete"}


def build_save_data(
    context: StoryContext, stage: str, chat_history: list[dict[str, str]]
) -> dict[str, Any]:
    """Build a save-file dictionary from current session state."""
    return {
        "version": SAVE_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "context": context.to_dict(),
        "chat_history": chat_history,
    }


def parse_save_data(raw: bytes) -> tuple[StoryContext, str, list[dict[str, str]]]:
    """Parse and validate a save file. Raises ValueError on invalid data."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"无效的 JSON 文件: {e}") from e

    for key in ("version", "stage", "context", "chat_history"):
        if key not in data:
            raise ValueError(f"存档缺少必要字段: {key}")

    stage = data["stage"]
    if stage not in VALID_STAGES:
        raise ValueError(f"无效的阶段: {stage}")

    try:
        context = StoryContext.from_dict(data["context"])
    except Exception as e:
        raise ValueError(f"无法解析存档数据: {e}") from e

    return context, stage, data["chat_history"]


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
            st.write(f"地点: {', '.join(loc.name for loc in context.world.locations[:3])}")

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

        # Save/Load
        st.divider()
        st.subheader("存档管理")

        save_data = build_save_data(
            st.session_state.context,
            st.session_state.stage,
            st.session_state.chat_history,
        )
        st.download_button(
            "保存进度",
            data=json.dumps(save_data, ensure_ascii=False, indent=2),
            file_name="coc_story_save.json",
            mime="application/json",
        )

        uploaded = st.file_uploader("读取存档", type=["json"])
        if uploaded is not None:
            file_id = f"{uploaded.name}_{uploaded.size}"
            if st.session_state.get("_last_loaded_save") != file_id:
                try:
                    context, stage, chat_history = parse_save_data(uploaded.read())
                    st.session_state.context = context
                    st.session_state.stage = stage
                    st.session_state.chat_history = chat_history
                    # Clear transient UI state
                    for key in [
                        "pending_review",
                        "pending_chapter_num",
                        "pending_review_re_review",
                        "review_cycle",
                        "auto_writing_in_progress",
                        "show_world_feedback",
                        "show_outline_feedback",
                        "final_review_result",
                    ]:
                        st.session_state.pop(key, None)
                    st.session_state._last_loaded_save = file_id
                    st.rerun()
                except (ValueError, Exception) as e:
                    st.error(f"存档读取失败: {e}")


def render_brainstorm_stage():
    """Render brainstorm stage UI."""
    st.header("故事构思")
    st.write(
        "你好！我是你的克苏鲁故事创作助手。我会在接下来的对话中引导你构思故事，一次问你一个问题。请告诉我你想创作什么样的故事，或者输入'开始'让我来引导你。"
    )

    # Chat interface
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Input
    user_input = st.chat_input("请输入你的想法...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 立刻显示用户消息
        with st.chat_message("user"):
            st.write(user_input)

        # assistant 气泡 + spinner
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                config = load_config()
                llm_config = get_agent_config(config, "brainstorm")
                llm = get_llm_for_agent(llm_config)
                from agents.brainstorm import BrainstormAgent

                agent = BrainstormAgent(llm)
                # 恢复之前的对话历史（排除刚追加的当前用户消息，chat() 会自行追加）
                agent.conversation_history = list(st.session_state.chat_history[:-1])
                response = agent.chat(user_input, st.session_state.context)
            st.write(response)

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

    # 完成检查放在 user_input 块外，确保按钮在 rerun 后仍能渲染
    required_keys = ["theme", "era", "atmosphere", "protagonist", "writing_style"]
    if all(k in st.session_state.context.seed for k in required_keys):
        st.success("故事构思完成！")

        # Seed编辑区域
        with st.expander("编辑故事种子", expanded=False):
            seed = st.session_state.context.seed

            col1, col2 = st.columns(2)
            with col1:
                theme = st.text_input("主题", value=seed.get("theme", ""))
                era = st.text_input("时代背景", value=seed.get("era", ""))
                atmosphere = st.text_input("氛围", value=seed.get("atmosphere", ""))
            with col2:
                mythos = st.text_area(
                    "神话元素 (用逗号分隔)", value=", ".join(seed.get("mythos_elements", []))
                )
                writing_style_style = st.selectbox(
                    "文风",
                    ["朴实", "华丽"],
                    index=0 if seed.get("writing_style", {}).get("style", "朴实") == "朴实" else 1,
                )
                writing_style_narration = st.selectbox(
                    "叙事方式",
                    ["描写为主", "对话为主"],
                    index=(
                        0
                        if seed.get("writing_style", {}).get("narration", "描写为主") == "描写为主"
                        else 1
                    ),
                )

            notes = st.text_area("其他备注", value=seed.get("notes", ""))

            if st.button("保存修改"):
                st.session_state.context.seed["theme"] = theme
                st.session_state.context.seed["era"] = era
                st.session_state.context.seed["atmosphere"] = atmosphere
                st.session_state.context.seed["mythos_elements"] = [
                    e.strip() for e in mythos.split(",") if e.strip()
                ]
                st.session_state.context.seed["notes"] = notes
                st.session_state.context.seed["writing_style"] = {
                    "style": writing_style_style,
                    "narration": writing_style_narration,
                    "notes": notes,
                }
                st.success("已保存！")
                st.rerun()

        if st.button("进入世界观构建"):
            st.session_state.stage = "world"
            st.rerun()


def render_world_stage():
    """Render world building stage UI."""
    st.header("世界观构建")

    context = st.session_state.context

    # Generate world if not exists
    if context.world is None:
        st.info("正在生成世界观...")

        config = load_config()
        llm_config = get_agent_config(config, "worldbuilder")
        llm = get_llm_for_agent(llm_config)

        from agents.worldbuilder import WorldbuilderAgent

        agent = WorldbuilderAgent(llm)

        # Get feedback if exists
        feedback = st.session_state.pop("world_feedback", None)

        with crew_progress("AI 正在构建世界观..."):
            agent.build_world(context, feedback=feedback)

        st.rerun()
    else:
        # Check for pending feedback — revise existing world
        feedback = st.session_state.pop("world_feedback", None)
        if feedback:
            config = load_config()
            llm_config = get_agent_config(config, "worldbuilder")
            llm = get_llm_for_agent(llm_config)
            from agents.worldbuilder import WorldbuilderAgent

            agent = WorldbuilderAgent(llm)
            with crew_progress("AI 正在根据反馈修改世界观..."):
                agent.build_world(context, feedback=feedback)
            st.rerun()

        # Display world setting
        st.subheader("时代背景")
        st.write(context.world.era)

        st.subheader("地点")
        for loc in context.world.locations:
            st.write(f"- **{loc.name}**: {loc.description}")

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

        # Confirmation and feedback buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("确认并继续"):
                st.session_state.stage = "outline"
                st.rerun()
        with col2:
            if st.button("重新生成"):
                st.session_state.show_world_feedback = True
                st.rerun()

        # Feedback input for regeneration
        if st.session_state.get("show_world_feedback", False):
            st.divider()
            st.subheader("重新生成")
            feedback = st.text_area(
                "请输入修改意见（例如：增加更多神秘氛围、修改主角设定等）",
                key="world_feedback_input",
            )
            col3, col4 = st.columns(2)
            with col3:
                if st.button("根据意见重新生成"):
                    st.session_state.world_feedback = feedback
                    st.session_state.show_world_feedback = False
                    st.rerun()
            with col4:
                if st.button("取消"):
                    st.session_state.show_world_feedback = False
                    st.rerun()


def render_outline_stage():
    """Render outline stage UI."""
    st.header("故事大纲")

    context = st.session_state.context

    if not context.outline:
        # Check if there's feedback from previous regeneration attempt
        feedback = st.session_state.pop("outline_feedback", None)
        target_chapters = st.session_state.pop("outline_target_chapters", 10)

        if feedback:
            # Regenerating with feedback
            st.info("正在根据反馈重新生成大纲...")

            config = load_config()
            llm_config = get_agent_config(config, "outliner")
            llm = get_llm_for_agent(llm_config)

            from agents.outliner import OutlinerAgent

            agent = OutlinerAgent(llm)

            with crew_progress("AI 正在根据反馈重新生成大纲..."):
                agent.create_outline(context, target_chapters, feedback=feedback)

            st.rerun()
        else:
            # Chapter count selector
            target_chapters = st.slider("章节数", min_value=5, max_value=20, value=target_chapters)

            if st.button("生成大纲"):
                config = load_config()
                llm_config = get_agent_config(config, "outliner")
                llm = get_llm_for_agent(llm_config)

                from agents.outliner import OutlinerAgent

                agent = OutlinerAgent(llm)

                with crew_progress("AI 正在生成大纲..."):
                    agent.create_outline(context, target_chapters)

                st.rerun()
    else:
        # Check for pending feedback — revise existing outline
        feedback = st.session_state.pop("outline_feedback", None)
        target_chapters = st.session_state.pop("outline_target_chapters", None)
        if feedback:
            config = load_config()
            llm_config = get_agent_config(config, "outliner")
            llm = get_llm_for_agent(llm_config)
            from agents.outliner import OutlinerAgent

            agent = OutlinerAgent(llm)
            with crew_progress("AI 正在根据反馈修改大纲..."):
                agent.create_outline(
                    context,
                    target_chapters or len(context.outline),
                    feedback=feedback,
                )
            st.rerun()

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

        # Confirmation and feedback buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("确认并继续"):
                st.session_state.stage = "writing"
                st.rerun()
        with col2:
            if st.button("重新生成"):
                st.session_state.show_outline_feedback = True
                st.rerun()

        # Feedback input for regeneration
        if st.session_state.get("show_outline_feedback", False):
            st.divider()
            st.subheader("重新生成")
            feedback = st.text_area(
                "请输入修改意见（例如：调整章节节奏、增加更多伏笔等）", key="outline_feedback_input"
            )
            target_chapters = st.slider(
                "章节数",
                min_value=5,
                max_value=20,
                value=len(context.outline) if context.outline else 10,
                key="outline_feedback_chapters",
            )
            col3, col4 = st.columns(2)
            with col3:
                if st.button("根据意见重新生成"):
                    st.session_state.outline_feedback = feedback
                    st.session_state.outline_target_chapters = target_chapters
                    st.session_state.show_outline_feedback = False
                    st.rerun()
            with col4:
                if st.button("取消"):
                    st.session_state.show_outline_feedback = False
                    st.rerun()


def _write_review_one_chapter(writer, reviewer, context, chapter):
    """Run write → review → revise loop for a single chapter.

    Returns (chapter_text, pending_review_or_None).
    If pending_review is not None, a major issue needs user decision.
    """
    with crew_progress(f"正在写作第{chapter.number}章..."):
        chapter_text = writer.write_chapter(context, chapter)

    max_revisions = 3
    for revision in range(max_revisions):
        with crew_progress(f"审核第{chapter.number}章（第{revision + 1}轮）..."):
            review = reviewer.review_chapter(context, chapter.number, chapter_text)

        if review.passed:
            st.success(f"第{chapter.number}章审核通过！")
            return chapter_text, None

        major_issues = review.get_major_issues()
        minor_issues = review.get_minor_issues()

        if major_issues:
            return chapter_text, review

        if minor_issues:
            if revision < max_revisions - 1:
                st.info(f"第{revision + 1}轮: 发现 {len(minor_issues)} 个小问题，自动修订中...")
                with crew_progress("自动修订中..."):
                    chapter_text = writer.revise_chapter(
                        context, chapter, chapter_text, minor_issues
                    )
            else:
                st.warning("3轮自动修订仍未通过，升级为需要用户决策")
                return chapter_text, review

    return chapter_text, None


def _summarize_if_needed(writer, context, chapter_num):
    """Generate summary for a chapter if it's missing.

    Handles the case where a chapter was written but its summary was not
    generated (e.g. major issue interrupted the flow).
    """
    idx = chapter_num - 1
    if len(context.chapter_summaries) <= idx and idx < len(context.chapters):
        chapter = context.outline[idx]
        chapter_text = context.chapters[idx]
        with crew_progress(f"正在生成第{chapter.number}章摘要..."):
            summary = writer.summarize_chapter(chapter, chapter_text)
        context.chapter_summaries.append(summary)


def render_writing_stage():
    """Render writing stage UI.

    Implements auto-advancing chapter writing:
    - Click once to generate all chapters automatically
    - Processes ONE chapter per Streamlit run cycle (avoids WebSocket timeout)
    - Major issues pause for user decision, then resume
    - After all chapters, auto-advance to final review
    """
    st.header("章节写作")

    context = st.session_state.context

    # Initialize state
    if "pending_review" not in st.session_state:
        st.session_state.pending_review = None
    if "auto_writing_in_progress" not in st.session_state:
        st.session_state.auto_writing_in_progress = False

    # Progress
    total_chapters = len(context.outline)
    completed = len(context.chapters)
    st.progress(completed / total_chapters if total_chapters else 0)
    st.write(f"进度: {completed}/{total_chapters} 章")

    # Handle pending major issues that need user decision
    if st.session_state.pending_review is not None:
        review = st.session_state.pending_review
        chapter_num = st.session_state.pending_chapter_num

        st.warning(f"第{chapter_num}章审核发现大问题，需要你的决策：")

        # Task 4: Show full chapter content
        with st.expander("查看完整章节内容", expanded=False):
            chapter_text = context.chapters[chapter_num - 1]
            st.text_area(
                "章节内容",
                value=chapter_text,
                height=400,
                disabled=True,
                label_visibility="collapsed",
            )

        # Task 5: Allow selective acceptance and modification of issues
        st.subheader("请选择要处理的问题并修改建议：")

        major_issues = review.get_major_issues()
        selected_issues = []

        for i, issue in enumerate(major_issues):
            col_checkbox, col_details = st.columns([1, 10])
            with col_checkbox:
                selected = st.checkbox("选择", key=f"issue_checkbox_{chapter_num}_{i}", value=True)
            with col_details:
                st.error(f"**[{issue['category']}]** {issue['description']}")
                modified_suggestion = st.text_area(
                    "修改建议 (可编辑)",
                    value=issue["suggestion"],
                    key=f"issue_suggestion_{chapter_num}_{i}",
                    height=60,
                )
                if selected:
                    selected_issues.append(
                        {
                            "category": issue["category"],
                            "severity": issue["severity"],
                            "description": issue["description"],
                            "suggestion": modified_suggestion,
                        }
                    )

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("接受选中建议并修改"):
                if not selected_issues:
                    st.error("请至少选择一个要处理的问题")
                else:
                    config = load_config()
                    writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                    from agents.writer import WriterAgent

                    writer = WriterAgent(writer_llm)

                    chapter_text = context.chapters[chapter_num - 1]
                    current_chapter = context.outline[chapter_num - 1]

                    with crew_progress("按建议修改中..."):
                        writer.revise_chapter(
                            context, current_chapter, chapter_text, selected_issues
                        )

                    # Task 6: Increment review cycle and set flag to re-review
                    st.session_state.pending_review = None
                    st.session_state.review_cycle = st.session_state.get("review_cycle", 0) + 1
                    st.session_state.pending_review_re_review = True
                    st.rerun()
        with col2:
            user_guidance = st.text_area("你的修改指导", key=f"user_guidance_{chapter_num}")
            if st.button("按我的指导修改"):
                if user_guidance:
                    config = load_config()
                    writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                    from agents.writer import WriterAgent

                    writer = WriterAgent(writer_llm)

                    chapter_text = context.chapters[chapter_num - 1]
                    current_chapter = context.outline[chapter_num - 1]
                    custom_issues = [
                        {
                            "category": "user",
                            "description": user_guidance,
                            "suggestion": user_guidance,
                        }
                    ]

                    with crew_progress("按指导修改中..."):
                        writer.revise_chapter(context, current_chapter, chapter_text, custom_issues)

                    # Task 6: Increment review cycle and set flag to re-review
                    st.session_state.pending_review = None
                    st.session_state.review_cycle = st.session_state.get("review_cycle", 0) + 1
                    st.session_state.pending_review_re_review = True
                    st.rerun()
        with col3:
            if st.button("忽略，继续下一章"):
                config = load_config()
                writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                from agents.writer import WriterAgent

                writer = WriterAgent(writer_llm)
                _summarize_if_needed(writer, context, chapter_num)
                st.session_state.pending_review = None
                st.session_state.review_cycle = 0  # Reset cycle for next chapter
                st.rerun()
        return

    # Task 6: Handle re-review after user revision
    if st.session_state.get("pending_review_re_review", False):
        chapter_num = st.session_state.pending_chapter_num
        review_cycle = st.session_state.get("review_cycle", 1)

        # Max 3 review cycles
        if review_cycle >= 3:
            st.warning(f"已达到最大审核循环次数({review_cycle}轮)，继续下一章")
            config = load_config()
            writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
            from agents.writer import WriterAgent

            writer = WriterAgent(writer_llm)
            _summarize_if_needed(writer, context, chapter_num)
            st.session_state.pending_review_re_review = False
            st.session_state.pending_review = None
            st.session_state.review_cycle = 0
            st.rerun()
            return

        config = load_config()
        review_llm = get_llm_for_agent(get_agent_config(config, "reviewer"))
        from agents.reviewer import ReviewerAgent

        reviewer = ReviewerAgent(review_llm)
        current_chapter = context.outline[chapter_num - 1]
        chapter_text = context.chapters[chapter_num - 1]

        st.info(f"第{chapter_num}章修改后重新审核中（第{review_cycle + 1}轮）...")

        with crew_progress(f"重新审核第{chapter_num}章..."):
            review = reviewer.review_chapter(context, chapter_num, chapter_text)

        if review.passed:
            st.success(f"第{chapter_num}章重新审核通过！")
            config = load_config()
            writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
            from agents.writer import WriterAgent

            writer = WriterAgent(writer_llm)
            _summarize_if_needed(writer, context, chapter_num)
            st.session_state.pending_review_re_review = False
            st.session_state.pending_review = None
            st.session_state.review_cycle = 0
            st.rerun()
        else:
            major_issues = review.get_major_issues()
            if major_issues:
                # Still has major issues, show decision UI again
                st.session_state.pending_review = review
                st.session_state.pending_review_re_review = False
                st.rerun()
            else:
                # Only minor issues, auto-revise
                minor_issues = review.get_minor_issues()
                if minor_issues:
                    st.info(
                        f"第{review_cycle + 1}轮: 发现 {len(minor_issues)} 个小问题，自动修订中..."
                    )
                    config = load_config()
                    writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                    from agents.writer import WriterAgent

                    writer = WriterAgent(writer_llm)

                    with crew_progress("自动修订中..."):
                        writer.revise_chapter(context, current_chapter, chapter_text, minor_issues)

                    # Re-review again
                    st.session_state.review_cycle = review_cycle + 1
                    st.rerun()
                else:
                    # No issues
                    st.success(f"第{chapter_num}章重新审核通过！")
                    config = load_config()
                    writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
                    from agents.writer import WriterAgent

                    writer = WriterAgent(writer_llm)
                    _summarize_if_needed(writer, context, chapter_num)
                    st.session_state.pending_review_re_review = False
                    st.session_state.pending_review = None
                    st.session_state.review_cycle = 0
                    st.rerun()
        return

    # Auto-writing: process ONE chapter per Streamlit run, then rerun
    if st.session_state.auto_writing_in_progress and completed < total_chapters:
        config = load_config()
        writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
        review_llm = get_llm_for_agent(get_agent_config(config, "reviewer"))

        from agents.writer import WriterAgent
        from agents.reviewer import ReviewerAgent

        writer = WriterAgent(writer_llm)
        reviewer = ReviewerAgent(review_llm)

        current_chapter = context.outline[completed]
        st.subheader(f"正在写作: 第{current_chapter.number}章 {current_chapter.title}")

        chapter_text, pending = _write_review_one_chapter(
            writer, reviewer, context, current_chapter
        )

        if pending is not None:
            st.session_state.pending_review = pending
            st.session_state.pending_chapter_num = current_chapter.number
            st.rerun()
            return

        # Generate summary for the completed chapter
        with crew_progress(f"正在生成第{current_chapter.number}章摘要..."):
            summary = writer.summarize_chapter(current_chapter, chapter_text)
        context.chapter_summaries.append(summary)

        # Check if all chapters done
        if len(context.chapters) >= total_chapters:
            st.session_state.auto_writing_in_progress = False
            st.session_state.stage = "review"

        # Rerun to update UI and process next chapter (or enter review)
        st.rerun()
        return

    if completed < total_chapters:
        current_chapter = context.outline[completed]
        st.subheader(f"待写作: 第{current_chapter.number}章 {current_chapter.title}")

        if st.button("开始自动生成所有章节"):
            st.session_state.auto_writing_in_progress = True
            st.rerun()
    else:
        st.success("所有章节写作完成！")
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
        config = load_config()

        # Back-fill missing chapter summaries (e.g. from legacy save files)
        if len(context.chapter_summaries) < len(context.chapters):
            st.info("正在补充生成缺失的章节摘要...")
            writer_llm = get_llm_for_agent(get_agent_config(config, "writer"))
            from agents.writer import WriterAgent

            writer = WriterAgent(writer_llm)
            for idx in range(len(context.chapter_summaries), len(context.chapters)):
                chapter = context.outline[idx]
                chapter_text = context.chapters[idx]
                with crew_progress(f"正在生成第{chapter.number}章摘要..."):
                    summary = writer.summarize_chapter(chapter, chapter_text)
                context.chapter_summaries.append(summary)

        st.info("正在进行全文终审...")

        review_llm = get_llm_for_agent(get_agent_config(config, "reviewer"))

        from agents.reviewer import ReviewerAgent

        reviewer = ReviewerAgent(review_llm)

        with crew_progress(
            "Reviewer 正在进行全文终审（伏笔回收、角色弧线、氛围连贯、首尾呼应）..."
        ):
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
        md_text = f"# {context.seed.get('theme', '克苏鲁故事')}\n\n"
        for i, text in enumerate(context.chapters):
            md_text += f"## 第{i+1}章: {context.outline[i].title}\n\n{text}\n\n"
        st.download_button(
            "导出为 Markdown",
            md_text,
            file_name="coc_story.md",
            mime="text/markdown",
        )

    with col2:
        try:
            pdf_buffer = BytesIO()
            exporter = PDFExporter()
            exporter.export(context, pdf_buffer)
            pdf_buffer.seek(0)

            st.download_button(
                "导出为 PDF",
                pdf_buffer,
                file_name="coc_story.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"PDF生成失败: {str(e)}")
            st.caption("提示: 请确保系统已安装中文字体")


def render_settings():
    """Render settings page."""
    st.header("设置")

    # Load current config
    config = load_config()
    providers = config.llm.get("providers", {})
    provider_names = list(providers.keys())
    type_options = ["openai_compatible", "anthropic_compatible"]
    agent_names = ["brainstorm", "worldbuilder", "outliner", "writer", "reviewer"]

    st.subheader("LLM Provider 配置")

    # Collect edits per provider
    provider_edits = {}
    for name in provider_names:
        pcfg = providers[name]
        with st.expander(name):
            p_type = st.selectbox(
                "Type",
                type_options,
                index=type_options.index(pcfg.get("type", "openai_compatible")),
                key=f"type_{name}",
            )
            p_base_url = st.text_input(
                "Base URL",
                value=pcfg.get("base_url", ""),
                key=f"base_url_{name}",
            )
            p_api_key = st.text_input(
                "API Key",
                value=pcfg.get("api_key", ""),
                type="password",
                key=f"api_key_{name}",
            )
            p_model = st.text_input(
                "Model",
                value=pcfg.get("model", ""),
                key=f"model_{name}",
            )
            provider_edits[name] = {
                "type": p_type,
                "base_url": p_base_url,
                "api_key": p_api_key,
                "model": p_model,
            }

    st.subheader("Default Provider")
    default_provider = st.selectbox(
        "Default Provider",
        provider_names,
        index=(
            provider_names.index(config.llm.get("default_provider", provider_names[0]))
            if config.llm.get("default_provider") in provider_names
            else 0
        ),
        key="default_provider",
    )

    st.subheader("Agent Provider 分配")
    agent_edits = {}
    for agent in agent_names:
        current = config.agents.get(agent, {}).get("provider", default_provider)
        agent_edits[agent] = st.selectbox(
            f"{agent.capitalize()} Agent",
            provider_names,
            index=provider_names.index(current) if current in provider_names else 0,
            key=f"agent_{agent}",
        )

    if st.button("保存设置"):
        import os
        import yaml

        # Save api keys to environment for current session
        for name, edits in provider_edits.items():
            if edits["api_key"]:
                os.environ[f"COC_{name.upper()}_API_KEY"] = edits["api_key"]

        # Persist to config.yaml
        config_path = "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        data.setdefault("llm", {})["default_provider"] = default_provider
        data["llm"]["providers"] = provider_edits
        data["agents"] = {agent: {"provider": prov} for agent, prov in agent_edits.items()}

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        st.success("设置已保存到 config.yaml")

    st.info(
        "配置优先级: 环境变量 > config.yaml > UI 设置页。\n"
        "环境变量: COC_{NAME}_API_KEY, COC_{NAME}_BASE_URL, COC_{NAME}_MODEL"
    )


def main():
    """Main app entry point."""
    st.set_page_config(
        page_title="CoC Story Generator",
        page_icon="🦑",
        layout="wide",
    )

    import litellm

    setup_logging()
    if not any(isinstance(cb, CoCLLMLogger) for cb in litellm.callbacks):
        litellm.callbacks.append(CoCLLMLogger())

    # Navigation
    st.sidebar.title("导航")
    page = st.sidebar.radio("选择页面", ["创作", "设置"])

    if page == "设置":
        render_settings()
        return

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
