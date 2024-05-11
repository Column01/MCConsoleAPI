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
