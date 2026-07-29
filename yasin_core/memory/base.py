from abc import ABC, abstractmethod
from typing import Any, List


class BaseMemory(ABC):

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class ShortTermMemory(BaseMemory, ABC):
    """Abstract base class for short-term/ephemeral memory."""
    pass


class LongTermMemory(BaseMemory, ABC):
    """Abstract base class for long-term/persistent or searchable memory."""

    @abstractmethod
    def search(self, query: str) -> List[Any]:
        """Search memory for items containing or matching the query."""
        pass
