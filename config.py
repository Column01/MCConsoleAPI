import json
import os
import tomllib
from collections import OrderedDict


class JsonConfig(OrderedDict):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

        if os.path.isfile(self.file_path):
            with open(self.file_path, "r") as fp:
                data = json.load(fp)
                for k, v in data.items():
                    self[k] = v
                fp.close()
        else:
            exit(
                f"Could not find config file at path {self.file_path}! Is this a server directory?"
            )


class TomlConfig(OrderedDict):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.load_toml()

    def load_toml(self):
        if os.path.isfile(self.file_path):
            with open(self.file_path, "rb") as fp:
                data = tomllib.load(fp)
                for k, v in data.items():
                    self[k] = v
                fp.close()
        else:
            exit(
                f"Could not find config file at path {self.file_path}! Is this a server directory?"
            )

    def reload(self):
        self.clear()  # Clear the existing data in the OrderedDict
        self.load_toml()  # Reload the TOML file from disk
