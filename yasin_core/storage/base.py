from abc import ABC, abstractmethod
from typing import Any, List


class BaseStorage(ABC):

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
    def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    def list_keys(self) -> List[str]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass
