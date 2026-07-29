from abc import ABC, abstractmethod


class AIProvider(ABC):


    name = "base"


    @abstractmethod
    def generate(
        self,
        prompt
    ):

        pass
