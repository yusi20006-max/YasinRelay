import yaml
from pathlib import Path


class Settings:


    def __init__(self, path=None):

        if path is None:
            path = (
                Path(__file__)
                .parent
                / "default.yaml"
            )

        self.path = path
        self.data = self.load()


    def load(self):

        with open(
            self.path,
            "r",
            encoding="utf-8"
        ) as file:

            return yaml.safe_load(file)


    def get(self, key, default=None):

        keys = key.split(".")

        value = self.data

        for item in keys:

            if isinstance(value, dict):

                value = value.get(
                    item,
                    default
                )

            else:
                return default

        return value
