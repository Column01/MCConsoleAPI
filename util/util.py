import glob


class LimitedList(list):
    """ Custom class for a list that has a max length to it """
    @property
    def maxlen(self):
        return self._maxlen

    def __init__(self, *args, **kwargs):
        self._maxlen = kwargs.pop("maxlen")
        list.__init__(self, *args, **kwargs)

    def _truncate(self):
        dif = len(self) - self._maxlen
        if dif > 0:
            self[:dif] = []

    def append(self, x):
        list.append(self, x)
        self._truncate()

    def insert(self, *args):
        list.insert(self, *args)
        self._truncate()

    def extend(self, x):
        list.extend(self, x)
        self._truncate()

    def __setitem__(self, *args):
        list.__setitem__(self, *args)
        self._truncate()

    def __setslice__(self, *args):
        list.__setslice__(self, *args)
        self._truncate()


def find_files(pattern):
    return glob.glob(pattern)


def find_jar(pattern):
    files = find_files(pattern)
    print(files)
    if len(files) == 0:
        return None
    else:
        return files[0]


def generate_time_message(interval: int) -> str:
    hours, remainder = divmod(interval, 3600)
    minutes, seconds = divmod(remainder, 60)

    msg_parts = []
    if hours > 0:
        msg_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        msg_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0:
        msg_parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")

    return ", ".join(msg_parts)
