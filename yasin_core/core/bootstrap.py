from .runtime import YasinRuntime


class Bootstrap:


    def __init__(self):

        self.runtime = None


    def initialize(self):

        self.runtime = YasinRuntime()

        self.runtime.start()

        return self.runtime
