from yasin_core.utils.logger import get_logger


class YasinRuntime:

    def __init__(self):

        self.logger = get_logger(
            "CORE"
        )

        self.running = False


    def start(self):

        self.logger.info(
            "Yasin Core Runtime started"
        )

        self.running = True


    def stop(self):

        self.logger.info(
            "Yasin Core Runtime stopped"
        )

        self.running = False


    def status(self):

        return {
            "name": "Yasin Core",
            "running": self.running,
            "version": "0.1.0"
        }
