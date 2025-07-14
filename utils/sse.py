class SSEEvent(str):
    def __new__(self, event_type, data):
        new = f"event: {event_type}\ndata: {data}\n\n"
        return super().__new__(self, new)


class ServerOutput(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "serverOutput", data)


class ServerInput(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "serverInput", data)


class ServerRestarting(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "serverRestarting", data)


class ServerStopping(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "serverStoping", data)


class ServerStopped(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "serverStopped", data)


class PlayerChat(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "playerChat", data)


class PlayerList(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "playerList", data)


class UserAttach(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "userAttach", data)


class ConfigReloaded(SSEEvent):
    def __new__(self, data):
        return super().__new__(self, "configReloaded", data)
