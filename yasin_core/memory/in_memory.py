from typing import Any, List, Dict
from yasin_core.memory.base import ShortTermMemory, LongTermMemory


class InMemoryShortTermMemory(ShortTermMemory):

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]

    def clear(self) -> None:
        self._data.clear()


class InMemoryLongTermMemory(LongTermMemory):

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]

    def clear(self) -> None:
        self._data.clear()

    def search(self, query: str) -> List[Any]:
        results: List[Any] = []
        query_lower = query.lower()

        for key, val in self._data.items():
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
