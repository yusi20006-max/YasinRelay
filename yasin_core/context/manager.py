import contextvars
import threading
from typing import Any, Dict, List, Optional

_current_context = contextvars.ContextVar("current_context", default=None)


class Context:

    def __init__(self, parent: Optional["Context"] = None, initial_data: Optional[Dict[str, Any]] = None) -> None:
        self._parent = parent
        self._data: Dict[str, Any] = initial_data.copy() if initial_data else {}
        self._lock = threading.Lock()
        self._tokens: List[contextvars.Token] = []

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                return self._data[key]
            if self._parent:
                return self._parent.get(key, default)
            return default

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]

    def has(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                return True
            if self._parent:
                return self._parent.has(key)
            return False

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def child(self, initial_data: Optional[Dict[str, Any]] = None) -> "Context":
        return Context(parent=self, initial_data=initial_data)

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and not self.has(key):
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        if not self.has(key):
            raise KeyError(key)
        self.delete(key)

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        val = self.get(name)
        if val is None and not self.has(name):
            raise AttributeError(f"'Context' object has no attribute '{name}'")
        return val

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self.set(name, value)

    def __enter__(self) -> "Context":
        token = _current_context.set(self)
        with self._lock:
            self._tokens.append(token)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        token = None
        with self._lock:
            if self._tokens:
                token = self._tokens.pop()
        if token:
            _current_context.reset(token)

    @classmethod
    def get_current(cls) -> Optional["Context"]:
        return _current_context.get()
