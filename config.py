import asyncio
import os
import toml
from collections import OrderedDict


class TomlConfig(OrderedDict):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.lock = asyncio.Lock()
        self.load_toml()

    def load_toml(self):
        if os.path.isfile(self.file_path):
            with open(self.file_path, "r") as fp:
                data = toml.load(fp)
                self.update(data)
        else:
            raise FileNotFoundError(
                f"Could not find config file at path {self.file_path}! Is this a server directory?"
            )

    async def reload(self):
        async with self.lock:
            self.clear()  # Clear the existing data in the OrderedDict
            self.load_toml()  # Reload the TOML file from disk
