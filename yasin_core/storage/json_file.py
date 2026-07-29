import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from yasin_core.storage.base import BaseStorage
from yasin_core.utils.logger import get_logger

logger = get_logger("STORAGE")


class JSONFileStorage(BaseStorage):

    def __init__(self, filepath: Optional[str] = None) -> None:
        if filepath is None:
            filepath = "storage.json"
        self.filepath = Path(filepath)
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.filepath.exists():
                self._data = {}
                return
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        self._data = {}
                    else:
                        self._data = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load storage from {self.filepath}: {e}")
                self._data = {}

    def _save(self) -> None:
        # Assumes self._lock is already held by the caller
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save storage to {self.filepath}: {e}")

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save()

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def list_keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._save()
