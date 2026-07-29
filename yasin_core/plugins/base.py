from abc import ABC, abstractmethod


class YasinPlugin(ABC):


    name = "base"


    @abstractmethod
    def start(self):

        pass


    @abstractmethod
    def stop(self):

        pass
