"""
test_agent_infrastructure.py
تست‌های جامع برای پلتفرم جدید ایجنت شامل هوک‌ها، رویدادها، تنظیمات، حافظه، کانتکست، پلاگین‌ها و ورک‌فلوها.
"""

from __future__ import annotations

import os
import json
import tempfile
import logging
from unittest.mock import Mock, patch

import pytest

from yasinrelay.agent import (
    AgentConfig,
    EventBus,
    TASK_STARTED,
    TASK_FINISHED,
    LifecycleHooks,
    TaskMemory,
    SessionMemory,
    ConversationMemory,
    ContextManager,
    TemplatePlanner,
    StubLLMPlanner,
    Workflow,
    WorkflowStep,
    discover_plugins,
    registry,
)


# ---------------------------------------------------------------------------
# تست‌های Event Bus
# ---------------------------------------------------------------------------

def test_event_bus_pub_sub():
    bus = EventBus()
    calls = []

    def callback(data):
        calls.append(data)

    bus.subscribe(TASK_STARTED, callback)
    bus.publish(TASK_STARTED, data="started")
    assert calls == ["started"]

    bus.unsubscribe(TASK_STARTED, callback)
    bus.publish(TASK_STARTED, data="again")
    assert calls == ["started"]  # تغییر نکرده است


def test_event_bus_robustness():
    bus = EventBus()
    calls = []

    def failing_callback():
        raise RuntimeError("Oops")

    def successful_callback():
        calls.append("success")

    bus.subscribe(TASK_FINISHED, failing_callback)
    bus.subscribe(TASK_FINISHED, successful_callback)

    # نباید به خاطر خطای یک شنونده، کل پایپ‌لاین فرو بپاشد
    bus.publish(TASK_FINISHED)
    assert calls == ["success"]


# ---------------------------------------------------------------------------
# تست‌های Lifecycle Hooks
# ---------------------------------------------------------------------------

def test_lifecycle_hooks_trigger():
    hooks = LifecycleHooks()
    calls = []

    hooks.register("before_plan", lambda task: calls.append(f"plan_{task}"))
    hooks.register("on_success", lambda: calls.append("success"))

    hooks.trigger("before_plan", task="write_code")
    hooks.trigger("on_success")

    assert calls == ["plan_write_code", "success"]


def test_lifecycle_hooks_invalid_name():
    hooks = LifecycleHooks()
    with pytest.raises(ValueError):
        hooks.register("invalid_hook_name", lambda: None)


# ---------------------------------------------------------------------------
# تست‌های سیستم حافظه (Memory System)
# ---------------------------------------------------------------------------

def test_task_memory():
    mem = TaskMemory()
    mem.store("task_id", 42)
    assert mem.retrieve("task_id") == 42
    mem.clear()
    assert mem.retrieve("task_id") is None


def test_session_memory():
    mem = SessionMemory()
    mem.store("user_session", "session_token_123")
    assert mem.retrieve("user_session") == "session_token_123"
    mem.clear()
    assert mem.retrieve("user_session") is None


def test_conversation_memory():
    mem = ConversationMemory()
    mem.store("user", "Hello agent")
    mem.store("assistant", "Hi human!")

    assert mem.retrieve("user") == [{"role": "user", "content": "Hello agent"}]
    assert mem.retrieve("all") == [
        {"role": "user", "content": "Hello agent"},
        {"role": "assistant", "content": "Hi human!"}
    ]
    mem.clear()
    assert len(mem.retrieve("all")) == 0


# ---------------------------------------------------------------------------
# تست‌های Context Manager
# ---------------------------------------------------------------------------

def test_context_manager():
    ctx = ContextManager()
    ctx.set_variable("current_post", "post_data_123")
    ctx.set_metadata("task_type", "translation")
    ctx.log_history_step("plan_created", {"steps": 3})

    assert ctx.get_variable("current_post") == "post_data_123"
    assert ctx.get_metadata("task_type") == "translation"
    assert len(ctx.get_history()) == 1
    assert ctx.get_history()[0]["type"] == "plan_created"

    llm_ctx = ctx.get_llm_context()
    assert llm_ctx["metadata"]["task_type"] == "translation"
    assert llm_ctx["variables"]["current_post"] == "post_data_123"


# ---------------------------------------------------------------------------
# تست‌های تنظیمات (Configuration)
# ---------------------------------------------------------------------------

def test_agent_config_defaults():
    cfg = AgentConfig()
    assert cfg.retry_count == 3
    assert cfg.retry_delay == 1.0
    assert cfg.tool_timeout == 30.0
    assert cfg.planner_timeout == 60.0
    assert cfg.max_parallel_tools == 4
    assert cfg.log_level == "INFO"


@patch.dict(os.environ, {
    "AGENT_RETRY_COUNT": "5",
    "AGENT_RETRY_DELAY": "2.5",
    "AGENT_LOG_LEVEL": "DEBUG",
})
def test_agent_config_env():
    cfg = AgentConfig()
    assert cfg.retry_count == 5
    assert cfg.retry_delay == 2.5
    assert cfg.log_level == "DEBUG"


def test_agent_config_file():
    config_data = {
        "retry_count": 10,
        "retry_delay": 0.5,
        "log_level": "WARNING"
    }
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        cfg = AgentConfig(config_file=config_path)
        assert cfg.retry_count == 10
        assert cfg.retry_delay == 0.5
        assert cfg.log_level == "WARNING"
    finally:
        os.unlink(config_path)


# ---------------------------------------------------------------------------
# تست‌های Planners
# ---------------------------------------------------------------------------

def test_template_planner():
    planner = TemplatePlanner()
    plan = planner.create_plan("Please translate this text", {})
    assert len(plan) == 3
    assert plan[0]["action"] == "fetch"


def test_stub_llm_planner():
    planner = StubLLMPlanner()
    plan = planner.create_plan("Find files on disk", {})
    assert len(plan) == 3
    assert plan[0]["action"] == "llm_analysis"


# ---------------------------------------------------------------------------
# تست‌های ورک‌فلوها (Workflows)
# ---------------------------------------------------------------------------

def test_sequential_workflow():
    wf = Workflow("test_sequential")
    calls = []

    step1 = WorkflowStep("step1", lambda ctx: calls.append(1))
    step2 = WorkflowStep("step2", lambda ctx: calls.append(2))

    wf.add_step(step1)
    wf.add_step(step2)

    wf.execute({})
    assert calls == [1, 2]


def test_conditional_workflow():
    wf = Workflow("test_conditional")
    calls = []

    step1 = WorkflowStep(
        "step1",
        lambda ctx: calls.append(1),
        condition=lambda ctx: ctx.get("run_step1", False)
    )
    step2 = WorkflowStep(
        "step2",
        lambda ctx: calls.append(2),
        condition=lambda ctx: ctx.get("run_step2", True)
    )

    wf.add_step(step1)
    wf.add_step(step2)

    wf.execute({"run_step1": False, "run_step2": True})
    assert calls == [2]


def test_parallel_workflow():
    wf = Workflow("test_parallel")
    parallel_calls = []

    p_step1 = WorkflowStep("p1", lambda ctx: parallel_calls.append("p1_run"))
    p_step2 = WorkflowStep("p2", lambda ctx: parallel_calls.append("p2_run"))

    parent_step = WorkflowStep("parent", lambda ctx: None, parallel_steps=[p_step1, p_step2])
    wf.add_step(parent_step)

    wf.execute({})
    assert "p1_run" in parallel_calls
    assert "p2_run" in parallel_calls
    assert len(parallel_calls) == 2


# ---------------------------------------------------------------------------
# تست‌های پلاگین‌ها (Plugins)
# ---------------------------------------------------------------------------

def test_plugin_discovery_and_registration():
    with tempfile.TemporaryDirectory() as tmpdir:
        # ساخت یک فایل پلاگین آزمایشی
        plugin_code = """
from yasinrelay.agent import register_plugin

@register_plugin("math_plugin")
class MathPlugin:
    def add(self, a, b):
        return a + b
"""
        with open(os.path.join(tmpdir, "math_plugin.py"), "w", encoding="utf-8") as f:
            f.write(plugin_code)

        discover_plugins(plugins_dir=tmpdir)

        # بررسی رجیستری سراسری
        plugin_class = registry.get_plugin("math_plugin")
        assert plugin_class is not None
        instance = plugin_class()
        assert instance.add(10, 20) == 30


def test_plugin_discovery_resilience_to_failures():
    with tempfile.TemporaryDirectory() as tmpdir:
        # ساخت یک پلاگین خراب (دارای خطای سینتکس)
        with open(os.path.join(tmpdir, "broken_plugin.py"), "w", encoding="utf-8") as f:
            f.write("this is completely invalid python syntax %^&*")

        # تلاش برای بارگذاری؛ نباید کرش کند
        discover_plugins(plugins_dir=tmpdir)
        # اگر تا اینجا رسیده، یعنی به خوبی استثنا کنترل شده است.
        assert True
