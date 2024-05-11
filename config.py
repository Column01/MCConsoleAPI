import json
import os
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
            exit(f"Could not find config file at path {self.file_path}! Is this a server directory?")
