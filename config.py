import os
import tomllib
from collections import OrderedDict


class TomlConfig(OrderedDict):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.load_toml()

    def load_toml(self):
        if os.path.isfile(self.file_path):
            with open(self.file_path, "rb") as fp:
                data = tomllib.load(fp)
                self.update(data)
        else:
            exit(
                f"Could not find config file at path {self.file_path}! Is this a server directory?"
            )

    def reload(self):
        self.clear()  # Clear the existing data in the OrderedDict
        self.load_toml()  # Reload the TOML file from disk
