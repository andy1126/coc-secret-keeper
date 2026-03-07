"""Real-time CrewAI execution progress in Streamlit UI."""

import threading
from contextlib import contextmanager

import streamlit as st
from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.agent_events import (
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
)
from crewai.events.types.crew_events import (
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
)
from crewai.events.types.task_events import TaskCompletedEvent, TaskStartedEvent
from streamlit.runtime.scriptrunner_utils.script_run_context import (
    add_script_run_ctx,
    get_script_run_ctx,
)


def _inject_ctx(ctx):
    """Attach Streamlit script-run context to the current thread."""
    if ctx is not None:
        add_script_run_ctx(threading.current_thread(), ctx)


@contextmanager
def crew_progress(label: str):
    """Context manager that shows CrewAI execution events inside an st.status container.

    Usage::

        with crew_progress("AI 正在构建世界观..."):
            agent.build_world(context)
    """
    status = st.status(label, expanded=True)
    ctx = get_script_run_ctx()

    # -- handler definitions (closures over status & ctx) --

    def on_crew_started(source, event: CrewKickoffStartedEvent):
        _inject_ctx(ctx)
        status.update(label=f"{label} - 启动中")

    def on_agent_started(source, event: AgentExecutionStartedEvent):
        _inject_ctx(ctx)
        role = getattr(event.agent, "role", "Agent")
        status.write(f"**{role}** 工作中...")

    def on_task_started(source, event: TaskStartedEvent):
        _inject_ctx(ctx)
        desc = ""
        task = getattr(event, "task", None)
        if task is not None:
            desc = getattr(task, "description", "") or ""
        if desc:
            status.write(f"任务: {desc[:80]}...")

    def on_task_completed(source, event: TaskCompletedEvent):
        _inject_ctx(ctx)
        status.write("任务完成 ✓")

    def on_agent_error(source, event: AgentExecutionErrorEvent):
        _inject_ctx(ctx)
        status.write(f"错误: {event.error}")

    def on_crew_failed(source, event: CrewKickoffFailedEvent):
        _inject_ctx(ctx)
        status.update(state="error", label=f"{label} - 失败")

    # -- register --
    handlers = [
        (CrewKickoffStartedEvent, on_crew_started),
        (AgentExecutionStartedEvent, on_agent_started),
        (TaskStartedEvent, on_task_started),
        (TaskCompletedEvent, on_task_completed),
        (AgentExecutionErrorEvent, on_agent_error),
        (CrewKickoffFailedEvent, on_crew_failed),
    ]
    for event_type, handler in handlers:
        crewai_event_bus.register_handler(event_type, handler)

    try:
        yield status
    finally:
        # Unregister all handlers to prevent accumulation across Streamlit reruns
        for event_type, handler in handlers:
            crewai_event_bus.off(event_type, handler)
        status.update(state="complete")
