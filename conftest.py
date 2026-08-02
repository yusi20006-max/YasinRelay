import os
import sys
from types import ModuleType

# Insert repository root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create mock yasin_core package and yasin_core.sdk module if missing
try:
    import yasin_core
except ImportError:
    yasin_core_mock = ModuleType("yasin_core")
    sys.modules["yasin_core"] = yasin_core_mock

    yasin_core_sdk_mock = ModuleType("yasin_core.sdk")
    sys.modules["yasin_core.sdk"] = yasin_core_sdk_mock

    # Implement Context Mock
    class MockContext:
        def __init__(self, initial_data=None):
            self.data = initial_data or {}

        def get(self, key, default=None):
            return self.data.get(key, default)

        def set(self, key, val):
            self.data[key] = val

    _current_context = MockContext()

    # Implement active_context context manager mock
    class ActiveContext:
        def __init__(self, ctx):
            self.ctx = ctx
            self.prev_ctx = None

        def __enter__(self):
            global _current_context
            self.prev_ctx = _current_context
            _current_context = self.ctx
            return self.ctx

        def __exit__(self, exc_type, exc_val, exc_tb):
            global _current_context
            _current_context = self.prev_ctx

    def active_context(ctx):
        return ActiveContext(ctx)

    def get_current_context():
        return _current_context

    # Implement YasinCoreClient mock
    class YasinCoreClient:
        def __init__(self):
            self.version = "1.0.0"
            self.memories = {}
            self.tools = {}

        def create_context(self, initial_data=None):
            return MockContext(initial_data)

        def save_memory(self, key, val, category="short-term"):
            self.memories[(key, category)] = val

        def get_memory(self, key, category="short-term"):
            return self.memories.get((key, category))

        def register_tool(self, func):
            name = getattr(func, "tool_name", func.__name__)
            self.tools[name] = func

        def list_tools(self):
            return list(self.tools.keys())

        def get_tool(self, name):
            return self.tools.get(name)

        def execute_tool(self, name, **kwargs):
            tool_func = self.get_tool(name)
            if tool_func:
                return tool_func(**kwargs)
            raise ValueError(f"Tool {name} not found")

    # Implement tool decorator
    def tool(name=None, description=None):
        def decorator(func):
            func.tool_name = name or func.__name__
            func.tool_description = description
            return func
        return decorator

    # Attach everything to the sdk mock module
    yasin_core_sdk_mock.YasinCoreClient = YasinCoreClient
    yasin_core_sdk_mock.active_context = active_context
    yasin_core_sdk_mock.get_current_context = get_current_context
    yasin_core_sdk_mock.tool = tool
