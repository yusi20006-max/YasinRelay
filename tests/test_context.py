import threading
import pytest
from yasin_core.context import Context


def test_context_basic_operations():
    ctx = Context()

    ctx.set("name", "Yasin")
    assert ctx.get("name") == "Yasin"
    assert ctx.get("non_existent") is None
    assert ctx.get("non_existent", "fallback") == "fallback"

    assert ctx.has("name") is True
    assert ctx.has("non_existent") is False

    ctx.delete("name")
    assert ctx.has("name") is False


def test_context_hierarchical_scopes():
    parent = Context(initial_data={"global_setting": True, "override_me": 1})
    child = parent.child(initial_data={"override_me": 2, "local_setting": "yes"})

    # Check that child can read parent values
    assert child.get("global_setting") is True
    # Check that child overrides parent values
    assert child.get("override_me") == 2
    # Check parent still has its original value
    assert parent.get("override_me") == 1
    # Check that parent cannot read child local values
    assert parent.get("local_setting") is None
    assert child.get("local_setting") == "yes"


def test_context_dict_interface():
    ctx = Context()
    ctx["a"] = 100
    assert ctx["a"] == 100
    assert "a" in ctx

    with pytest.raises(KeyError):
        _ = ctx["non_existent"]

    del ctx["a"]
    assert "a" not in ctx

    with pytest.raises(KeyError):
        del ctx["a"]


def test_context_attribute_interface():
    ctx = Context()
    ctx.host = "localhost"
    assert ctx.host == "localhost"

    with pytest.raises(AttributeError):
        _ = ctx.non_existent_attribute


def test_context_manager_and_active_context():
    assert Context.get_current() is None

    ctx1 = Context(initial_data={"id": 1})
    with ctx1 as active_ctx:
        assert active_ctx is ctx1
        assert Context.get_current() is ctx1
        assert Context.get_current().get("id") == 1

        ctx2 = Context(initial_data={"id": 2})
        with ctx2:
            assert Context.get_current() is ctx2
            assert Context.get_current().get("id") == 2

        assert Context.get_current() is ctx1

    assert Context.get_current() is None


def test_context_thread_safety_and_isolation():
    results = {}

    def thread_worker(name, value):
        with Context(initial_data={name: value}) as ctx:
            # Let's verify that other thread values are not present in this thread's context
            current = Context.get_current()
            results[name] = current.get(name)

    t1 = threading.Thread(target=thread_worker, args=("thread1_key", "val1"))
    t2 = threading.Thread(target=thread_worker, args=("thread2_key", "val2"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["thread1_key"] == "val1"
    assert results["thread2_key"] == "val2"
