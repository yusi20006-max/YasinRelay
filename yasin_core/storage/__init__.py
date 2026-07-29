import threading
from typing import Optional
from yasin_core.storage.base import BaseStorage
from yasin_core.storage.json_file import JSONFileStorage

_storage_instance: Optional[BaseStorage] = None
_storage_lock = threading.Lock()


def get_storage(filepath: Optional[str] = None) -> BaseStorage:
    global _storage_instance
    with _storage_lock:
        if _storage_instance is None:
            _storage_instance = JSONFileStorage(filepath)
        return _storage_instance


def set_storage(storage: BaseStorage) -> None:
    global _storage_instance
    with _storage_lock:
        _storage_instance = storage


__all__ = ["BaseStorage", "JSONFileStorage", "get_storage", "set_storage"]
