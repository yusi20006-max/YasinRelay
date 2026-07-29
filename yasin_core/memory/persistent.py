from typing import Any, List, Optional
from yasin_core.memory.base import LongTermMemory


class StorageLongTermMemory(LongTermMemory):

    def __init__(self, storage: Optional[Any] = None) -> None:
        self._storage = storage

    @property
    def storage(self) -> Any:
        if self._storage is None:
            from yasin_core.storage import get_storage
            self._storage = get_storage()
        return self._storage

    def set(self, key: str, value: Any) -> None:
        self.storage.set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self.storage.get(key, default)

    def delete(self, key: str) -> None:
        self.storage.delete(key)

    def clear(self) -> None:
        self.storage.clear()

    def search(self, query: str) -> List[Any]:
        results: List[Any] = []
        query_lower = query.lower()

        for key in self.storage.list_keys():
            val = self.storage.get(key)
            if query_lower in key.lower():
                results.append({"key": key, "value": val})
                continue

            if isinstance(val, str) and query_lower in val.lower():
                results.append({"key": key, "value": val})
                continue

            if isinstance(val, dict):
                matched = False
                for k, v in val.items():
                    if query_lower in str(k).lower() or query_lower in str(v).lower():
                        matched = True
                        break
                if matched:
                    results.append({"key": key, "value": val})
                    continue

            if isinstance(val, list):
                matched = False
                for item in val:
                    if query_lower in str(item).lower():
                        matched = True
                        break
                if matched:
                    results.append({"key": key, "value": val})
                    continue

        return results
