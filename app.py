import streamlit as st

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
            agent.build_world(context)

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
    - Writer writes chapter -> Reviewer reviews
    - Minor issues -> auto-revise (up to 3 rounds)
    - Major issues or 3 rounds exhausted -> show to user for decision
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
                    custom_issues = [
                        {
                            "category": "user",
                            "description": user_guidance,
                            "suggestion": user_guidance,
                        }
                    ]

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
                    review = reviewer.review_chapter(context, current_chapter.number, chapter_text)

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
                        st.info(
                            f"第{revision + 1}轮: 发现 {len(minor_issues)} 个小问题，自动修订中..."
                        )
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

    # Navigation
    st.sidebar.title("导航")
    page = st.sidebar.radio("选择页面", ["创作", "设置"])

    if page == "设置":
        render_settings()
        return

    st.title("🦑 CoC Story Generator")
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
