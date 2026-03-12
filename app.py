import json
from datetime import datetime
from io import BytesIO
from typing import Any

import streamlit as st

from export.pdf_exporter import PDFExporter
from models.story_context import StoryContext
from llm.config import load_config, get_agent_config
from llm.logging import setup_logging, CoCLLMLogger
from llm.provider import get_llm_for_agent, get_litellm_stream_params
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
VALID_STAGES = {"brainstorm", "design", "writing", "review", "complete"}


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
        stages = ["brainstorm", "design", "writing", "review", "complete"]
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

        # Conflict design summary
        if context.conflict_design:
            st.subheader("冲突设计")
            st.write(f"策略: {context.conflict_design.narrative_strategy[:50]}...")
            st.write(f"线索: {len(context.conflict_design.threads)} 条")

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

        is_generating = st.session_state.get("_design_generating", False) or st.session_state.get(
            "auto_writing_in_progress", False
        )

        uploaded = st.file_uploader("读取存档", type=["json"], disabled=is_generating)
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
                        "show_design_feedback",
                        "design_review_result",
                        "final_review_result",
                        "_design_auto_resume",
                        "_design_generating",
                        "_design_pending_feedback",
                    ]:
                        st.session_state.pop(key, None)

                    # Auto-resume partial design on load
                    if stage == "design":
                        from agents.design_team import detect_resume_point

                        rp = detect_resume_point(context)
                        if 0 < rp < 5:
                            st.session_state._design_auto_resume = True

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

        # assistant 气泡 — 流式输出（token 本身即为反馈，无需 spinner）
        with st.chat_message("assistant"):
            config = load_config()
            llm_config = get_agent_config(config, "brainstorm")
            litellm_params = get_litellm_stream_params(llm_config)
            llm = get_llm_for_agent(llm_config)
            from agents.brainstorm import BrainstormAgent

            agent = BrainstormAgent(llm)
            # 恢复之前的对话历史（排除刚追加的当前用户消息，chat_stream() 会自行追加）
            agent.conversation_history = list(st.session_state.chat_history[:-1])
            stream = agent.chat_stream(user_input, st.session_state.context, litellm_params)
            response = st.write_stream(stream)
            agent.finalize_stream(response, st.session_state.context)

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

    # 完成检查放在 user_input 块外，确保按钮在 rerun 后仍能渲染
    required_keys = [
        "theme",
        "era",
        "atmosphere",
        "protagonist",
        "writing_style",
        "target_chapters",
    ]
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
                writing_style_style = st.text_input(
                    "文风",
                    value=seed.get("writing_style", {}).get("style", ""),
                )
                writing_style_narration = st.text_input(
                    "叙事方式",
                    value=seed.get("writing_style", {}).get("narration", ""),
                )

            writing_style_notes = st.text_area(
                "风格要求",
                value=seed.get("writing_style", {}).get("writing_style_notes", ""),
            )
            target_chapters = st.slider(
                "目标章节数",
                min_value=5,
                max_value=20,
                value=seed.get("target_chapters", 10),
            )
            notes = st.text_area("其他备注", value=seed.get("notes", ""))

            if st.button("保存修改"):
                st.session_state.context.seed["theme"] = theme
                st.session_state.context.seed["era"] = era
                st.session_state.context.seed["atmosphere"] = atmosphere
                st.session_state.context.seed["mythos_elements"] = [
                    e.strip() for e in mythos.split(",") if e.strip()
                ]
                st.session_state.context.seed["target_chapters"] = target_chapters
                st.session_state.context.seed["notes"] = notes
                st.session_state.context.seed["writing_style"] = {
                    "style": writing_style_style,
                    "narration": writing_style_narration,
                    "writing_style_notes": writing_style_notes,
                }
                st.success("已保存！")
                st.rerun()

        if st.button("进入故事设计"):
            st.session_state.stage = "design"
            st.rerun()


def render_design_stage():
    """Render the unified design stage UI (world + conflict + outline)."""
    st.header("故事设计")

    context = st.session_state.context

    # Check if design is already complete (world + conflict + outline all exist)
    design_complete = context.world and context.conflict_design and context.outline

    if not design_complete:
        from agents.design_team import detect_resume_point

        # Auto-resume generation interrupted by rerun (e.g. sidebar interaction)
        if st.session_state.get("_design_generating"):
            _run_design_generation(
                context, feedback=st.session_state.get("_design_pending_feedback")
            )
            return

        # Check for pending feedback regeneration
        feedback = st.session_state.pop("design_feedback", None)
        if feedback:
            _run_design_generation(context, feedback=feedback)
            return

        # Auto-resume from loaded save (one-shot trigger)
        if st.session_state.pop("_design_auto_resume", False):
            _run_design_generation(context)
            return

        resume_point = detect_resume_point(context)
        has_partial = resume_point > 0

        if has_partial:
            phase_labels = ["生成研究问题", "深度研究", "构建世界观", "设计冲突结构", "生成大纲"]
            st.info("检测到设计进度，将从断点继续：")
            for i, label in enumerate(phase_labels):
                st.write(f"  {'✅' if i < resume_point else '⬜'} {label}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("继续设计"):
                    _run_design_generation(context)
            with col2:
                if st.button("从头开始"):
                    context.research_questions = []
                    context.research_notes = []
                    context.world = None
                    context.conflict_design = None
                    context.outline = []
                    _run_design_generation(context)
        else:
            st.write("点击下方按钮，AI 将自动完成以下流程：")
            st.write(
                "1. 生成研究问题 → 2. 深度研究 → 3. 构建世界观 + 设计冲突 → 4. 生成大纲 + 叙事审查"
            )

            if st.button("开始设计"):
                _run_design_generation(context)
    else:
        # Check for pending feedback
        feedback = st.session_state.pop("design_feedback", None)
        if feedback:
            _run_design_generation(context, feedback=feedback)
            return

        # Display results in 4 tabs
        tab_world, tab_conflict, tab_outline, tab_review = st.tabs(
            ["世界设定", "冲突设计", "故事大纲", "审查意见"]
        )

        with tab_world:
            _render_world_tab(context)

        with tab_conflict:
            _render_conflict_tab(context)

        with tab_outline:
            _render_outline_tab(context)

        with tab_review:
            _render_review_tab()

        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("确认并继续"):
                st.session_state.stage = "writing"
                st.rerun()
        with col2:
            if st.button("重新生成"):
                st.session_state.show_design_feedback = True
                st.rerun()

        if st.session_state.get("show_design_feedback", False):
            st.divider()
            st.subheader("重新生成")
            feedback = st.text_area(
                "请输入修改意见（将重新运行完整设计流程）",
                key="design_feedback_input",
            )
            col3, col4 = st.columns(2)
            with col3:
                if st.button("根据意见重新生成"):
                    # Clear existing design data for full regeneration
                    context.world = None
                    context.conflict_design = None
                    context.outline = []
                    context.research_questions = []
                    context.research_notes = []
                    st.session_state.design_feedback = feedback
                    st.session_state.show_design_feedback = False
                    st.rerun()
            with col4:
                if st.button("取消"):
                    st.session_state.show_design_feedback = False
                    st.rerun()


def _run_design_generation(context, feedback=None):
    """Run the full design team pipeline."""
    st.session_state._design_generating = True
    st.session_state._design_pending_feedback = feedback

    try:
        config = load_config()

        from agents.worldbuilder import WorldbuilderAgent
        from agents.researcher import ResearcherAgent
        from agents.conflict_architect import ConflictArchitectAgent
        from agents.outliner import OutlinerAgent
        from agents.narrative_reviewer import NarrativeReviewerAgent
        from agents.design_team import run_design_team

        worldbuilder = WorldbuilderAgent(
            get_llm_for_agent(get_agent_config(config, "worldbuilder"))
        )
        researcher = ResearcherAgent(get_llm_for_agent(get_agent_config(config, "researcher")))
        conflict_architect = ConflictArchitectAgent(
            get_llm_for_agent(get_agent_config(config, "conflict_architect"))
        )
        outliner = OutlinerAgent(get_llm_for_agent(get_agent_config(config, "outliner")))
        reviewer = NarrativeReviewerAgent(
            get_llm_for_agent(get_agent_config(config, "narrative_reviewer"))
        )

        # If feedback provided, inject into seed temporarily
        if feedback:
            context.seed["_design_feedback"] = feedback

        # Progress display
        progress_placeholder = st.empty()
        phase_status = {}

        def on_progress(phase, status):
            phase_labels = {
                "research_questions": "生成研究问题",
                "research": "深度研究",
                "world_building": "构建世界观",
                "conflict_design": "设计冲突结构",
                "outline": "生成大纲",
                "review": "叙事审查",
            }
            phase_status[phase] = status
            lines = []
            for p, label in phase_labels.items():
                if p in phase_status:
                    if phase_status[p] == "done":
                        icon = "✅"
                    elif phase_status[p] == "skipped":
                        icon = "⏩"
                    else:
                        icon = "⏳"
                    lines.append(f"{icon} {label}")
                else:
                    lines.append(f"⬜ {label}")
            progress_placeholder.markdown("\n\n".join(lines))

        with crew_progress("AI 设计团队正在协作..."):
            result = run_design_team(
                context,
                worldbuilder,
                researcher,
                conflict_architect,
                outliner,
                reviewer,
                on_progress=on_progress,
            )

        # Clean up temp feedback
        context.seed.pop("_design_feedback", None)

        # Store review result for display
        st.session_state.design_review_result = {
            "passed": result.review.passed,
            "issues": [i.model_dump() for i in result.review.issues],
            "strengths": result.review.strengths,
            "iterations": result.iterations,
        }
    finally:
        st.session_state.pop("_design_generating", None)
        st.session_state.pop("_design_pending_feedback", None)

    st.rerun()


def _render_world_tab(context):
    """Render world setting tab."""
    world = context.world
    st.subheader("时代背景")
    st.write(world.era)

    st.subheader("地点")
    for loc in world.locations:
        st.write(f"- **{loc.name}**: {loc.description}")

    st.subheader("神话实体")
    for entity in world.entities:
        with st.expander(entity.name):
            st.write(entity.description)
            st.write(f"影响: {entity.influence}")

    st.subheader("角色")
    for char in world.characters:
        with st.expander(char.name):
            st.write(f"背景: {char.background}")
            st.write(f"性格: {char.personality}")
            st.write(f"动机: {char.motivation}")
            st.write(f"弧线: {char.arc}")

    if world.secrets:
        st.subheader("隐藏秘密")
        for secret in world.secrets:
            layer_label = {1: "表面线索", 2: "中层真相", 3: "核心真相"}.get(
                secret.layer, f"层级{secret.layer}"
            )
            st.write(f"- **[{layer_label}]** {secret.content}")
            st.caption(f"知情者: {', '.join(secret.known_by)}")

    if world.tensions:
        st.subheader("暗流")
        for tension in world.tensions:
            st.write(f"- **{' vs '.join(tension.parties)}** — {tension.nature} ({tension.status})")

    if world.timeline:
        st.subheader("前史")
        for event in world.timeline:
            st.write(f"- **{event.when}**: {event.event}")
            st.caption(f"影响: {event.consequences}")


def _render_conflict_tab(context):
    """Render conflict design tab."""
    cd = context.conflict_design
    st.subheader("叙事策略")
    st.write(cd.narrative_strategy)

    st.divider()
    st.subheader("冲突线索")
    for thread in cd.threads:
        type_labels = {
            "epistemic": "认知",
            "ontological": "存在",
            "moral": "道德",
            "relational": "关系",
            "survival": "生存",
            "cosmic": "宇宙",
            "societal": "社会",
        }
        label = type_labels.get(thread.thread_type, thread.thread_type)
        with st.expander(f"{thread.name} ({label})"):
            st.write(thread.description)
            st.caption(f"风险: {thread.stakes}")

    st.divider()
    zone_labels = {"setup": "铺垫区", "crucible": "熔炉区", "aftermath": "余波区"}
    st.subheader("叙事区域")
    for zone_key in ("setup", "crucible", "aftermath"):
        zone_beats = [b for b in cd.beats if b.zone == zone_key]
        with st.expander(zone_labels.get(zone_key, zone_key)):
            for beat in zone_beats:
                thread_tags = ", ".join(beat.threads)
                st.write(f"**{beat.name}**: {beat.description}")
                st.caption(f"推进线索: {thread_tags}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("张力曲线")
        st.write(cd.tension_shape)
    with col2:
        st.subheader("主题贯穿线")
        st.write(cd.thematic_throughline)


def _render_outline_tab(context):
    """Render outline tab."""
    for chapter in context.outline:
        with st.expander(f"第{chapter.number}章: {chapter.title}"):
            st.write(f"**摘要**: {chapter.summary}")
            st.write(f"**情绪**: {chapter.mood}")
            st.write(f"**字数**: {chapter.word_target}")
            if chapter.pov:
                st.write(f"**视角**: {chapter.pov}")
            if chapter.foreshadowing:
                st.write(f"**伏笔**: {', '.join(chapter.foreshadowing)}")
            if chapter.payoffs:
                st.write(f"**回收**: {', '.join(chapter.payoffs)}")
            if chapter.information_reveal:
                st.write(f"**揭示信息**: {', '.join(chapter.information_reveal)}")
            if chapter.twist:
                st.write(f"**反转**: {chapter.twist}")
            if chapter.subplot:
                st.write(f"**副线**: {chapter.subplot}")
            if chapter.key_beats:
                st.write(f"**关键节拍**: {', '.join(chapter.key_beats)}")


def _render_review_tab():
    """Render narrative review tab."""
    review_data = st.session_state.get("design_review_result")
    if not review_data:
        st.info("暂无审查结果")
        return

    if review_data["passed"]:
        st.success(f"叙事审查通过！（迭代 {review_data['iterations']} 轮）")
    else:
        st.warning(f"叙事审查发现问题（迭代 {review_data['iterations']} 轮）")

    if review_data["issues"]:
        st.subheader("问题")
        for issue in review_data["issues"]:
            severity_icon = "🔴" if issue["severity"] == "major" else "🟡"
            st.write(f"{severity_icon} **[{issue['dimension']}]** {issue['description']}")
            st.caption(f"建议: {issue['suggestion']} (目标: {issue['target']})")

    if review_data["strengths"]:
        st.subheader("亮点")
        for s in review_data["strengths"]:
            st.write(f"- {s}")


def _write_review_one_chapter(writer, reviewer, context, chapter, litellm_params):
    """Run write → review → revise loop for a single chapter.

    Returns (chapter_text, pending_review_or_None).
    If pending_review is not None, a major issue needs user decision.
    """
    chapter_text = st.write_stream(writer.write_chapter_stream(context, chapter, litellm_params))
    writer.finalize_write_chapter(chapter_text, context, chapter)

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
                chapter_text = st.write_stream(
                    writer.revise_chapter_stream(
                        context, chapter, chapter_text, minor_issues, litellm_params
                    )
                )
                writer.finalize_revise_chapter(chapter_text, context, chapter)
            else:
                st.warning("3轮自动修订仍未通过，升级为需要用户决策")
                return chapter_text, review
        elif review.issues:
            # Issues exist but severity didn't match "minor"/"major" exactly;
            # treat as major to avoid silently skipping review
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
                    writer_config = get_agent_config(config, "writer")
                    writer_llm = get_llm_for_agent(writer_config)
                    litellm_params = get_litellm_stream_params(writer_config)
                    from agents.writer import WriterAgent

                    writer = WriterAgent(writer_llm)

                    chapter_text = context.chapters[chapter_num - 1]
                    current_chapter = context.outline[chapter_num - 1]

                    revised = st.write_stream(
                        writer.revise_chapter_stream(
                            context,
                            current_chapter,
                            chapter_text,
                            selected_issues,
                            litellm_params,
                        )
                    )
                    writer.finalize_revise_chapter(revised, context, current_chapter)

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
                    writer_config = get_agent_config(config, "writer")
                    writer_llm = get_llm_for_agent(writer_config)
                    litellm_params = get_litellm_stream_params(writer_config)
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

                    revised = st.write_stream(
                        writer.revise_chapter_stream(
                            context,
                            current_chapter,
                            chapter_text,
                            custom_issues,
                            litellm_params,
                        )
                    )
                    writer.finalize_revise_chapter(revised, context, current_chapter)

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
                minor_issues = review.get_minor_issues()
                if minor_issues:
                    # Only minor issues, auto-revise
                    st.info(
                        f"第{review_cycle + 1}轮: 发现 {len(minor_issues)} 个小问题，自动修订中..."
                    )
                    config = load_config()
                    writer_config = get_agent_config(config, "writer")
                    writer_llm = get_llm_for_agent(writer_config)
                    litellm_params = get_litellm_stream_params(writer_config)
                    from agents.writer import WriterAgent

                    writer = WriterAgent(writer_llm)

                    revised = st.write_stream(
                        writer.revise_chapter_stream(
                            context,
                            current_chapter,
                            chapter_text,
                            minor_issues,
                            litellm_params,
                        )
                    )
                    writer.finalize_revise_chapter(revised, context, current_chapter)

                    # Re-review again
                    st.session_state.review_cycle = review_cycle + 1
                    st.rerun()
                elif review.issues:
                    # Issues exist but severity didn't match "minor"/"major";
                    # treat as major to avoid silently skipping review
                    st.session_state.pending_review = review
                    st.session_state.pending_review_re_review = False
                    st.rerun()
                else:
                    # Genuinely no issues
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
        writer_config = get_agent_config(config, "writer")
        writer_llm = get_llm_for_agent(writer_config)
        litellm_params = get_litellm_stream_params(writer_config)
        review_llm = get_llm_for_agent(get_agent_config(config, "reviewer"))

        from agents.writer import WriterAgent
        from agents.reviewer import ReviewerAgent

        writer = WriterAgent(writer_llm)
        reviewer = ReviewerAgent(review_llm)

        current_chapter = context.outline[completed]
        st.subheader(f"正在写作: 第{current_chapter.number}章 {current_chapter.title}")

        chapter_text, pending = _write_review_one_chapter(
            writer, reviewer, context, current_chapter, litellm_params
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
    agent_names = [
        "brainstorm",
        "worldbuilder",
        "researcher",
        "conflict_architect",
        "outliner",
        "narrative_reviewer",
        "writer",
        "reviewer",
    ]

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
    elif stage == "design":
        render_design_stage()
    elif stage == "writing":
        render_writing_stage()
    elif stage == "review":
        render_review_stage()


if __name__ == "__main__":
    main()
