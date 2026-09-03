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

# Create mock yasinai package with canonical public contract if missing
try:
    import yasinai
    try:
        from yasinai import GenerationRequest, GenerationService
    except ImportError:
        from yasinai.contracts import GenerationRequest
        from yasinai.services import GenerationService
except ImportError:
    yasinai_mock = ModuleType("yasinai")
    yasinai_mock.__version__ = "1.1.4"
    sys.modules["yasinai"] = yasinai_mock

    yasinai_contracts_mock = ModuleType("yasinai.contracts")
    class GenerationRequest:
        def __init__(self, prompt, model=None, max_tokens=2048, temperature=0.7, system_prompt=None, provider=None, metadata=None):
            self.prompt = prompt
            self.model = model
            self.max_tokens = max_tokens
            self.temperature = temperature
            self.system_prompt = system_prompt
            self.provider = provider
            self.metadata = metadata or {}
    yasinai_contracts_mock.GenerationRequest = GenerationRequest
    sys.modules["yasinai.contracts"] = yasinai_contracts_mock

    yasinai_services_mock = ModuleType("yasinai.services")
    class GenerationService:
        def generate(self, request):
            from types import SimpleNamespace
            return SimpleNamespace(
                success=True,
                text=f"[Yasin-AI processed] {request.prompt}",
                error=None,
                model=request.model or "gpt-4o-mini",
                provider=request.provider or "openai",
            )
    yasinai_services_mock.GenerationService = GenerationService
    sys.modules["yasinai.services"] = yasinai_services_mock

    yasinai_mock.GenerationRequest = GenerationRequest
    yasinai_mock.GenerationService = GenerationService
