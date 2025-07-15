class SSEEvent(str):
    def __new__(self, event_type, data):
        new = f"event: {event_type}\ndata: {data}\n\n"
        return super().__new__(self, new)


class ServerOutput(SSEEvent):
    """Sent when connecting and contains all previous and future console output lines.
    Typical Data Format:
        ServerOutput({"message": "A Console Line", "timestamp": "iso_format_timestamp"})
    """

    def __new__(self, data):
        return super().__new__(self, "serverOutput", data)


class ServerInput(SSEEvent):
    """Sent when something was sent to the server's STDIN (by another user or yourself)
    Typical Data Format:
        ServerInput({"message": "The Sent command", "result": "The result (the next line recieved after sending it.)", "timestamp": "iso_format_timestamp"})
    """

    def __new__(self, data):
        return super().__new__(self, "serverInput", data)


class ServerRestarting(SSEEvent):
    """Sent when the server is restarting.
    Typical Data Format:
        ServerRestarting({"message": "{server_name} is being restarted.", "timestamp": "iso_format_timestamp"})
    """

    def __new__(self, data):
        return super().__new__(self, "serverRestarting", data)


class ServerStopping(SSEEvent):
    """Unused"""

    def __new__(self, data):
        return super().__new__(self, "serverStoping", data)


class ServerStopped(SSEEvent):
    """Sent when the server has stopped and will not be restarted.
    Typical Data Format:
        ServerStopped({"message": "{server_name} has stopped with exit code: {exit_code}", "timestamp": "iso_format_timestamp"})
    """

    def __new__(self, data):
        return super().__new__(self, "serverStopped", data)


class PlayerChat(SSEEvent):
    """Sent when a player sends a chat message. Triggered by the regex in the server's config, so it is not reliable unless confirmed working
    Typical Data Format:
        PlayerChat({"message": "player's chat message", "username": "Username42069", "timestamp": "iso_format_timestamp"})
    """

    def __new__(self, data):
        return super().__new__(self, "playerChat", data)


class PlayerList(SSEEvent):
    """Sent when a player connects or disconnects from the server. Triggered by multiple regexes in the server's config, so it is not reliable unless confirmed working
    Typical Data Format:
        PlayerList({"players": ["Player1", "Player2"], "timestamp": "iso_format_timestamp"})
    """

    def __new__(self, data):
        return super().__new__(self, "playerList", data)


class UserAttach(SSEEvent):
    """Sent when you or another user of the MCConsoleAPI attaches to the server console via SSE
    Typical Data Format:
        UserAttach({"message": "{user} attached to the console", "username": user})
    """

    def __new__(self, data):
        return super().__new__(self, "userAttach", data)


class UserDetach(SSEEvent):
    """Sent when you or another user of the MCConsoleAPI detaches from the server console via SSE
    Typical Data Format:
        UserDetach({"message": "{user} attached to the console", "username": user})
    """

    def __new__(self, data):
        return super().__new__(self, "userDetach", data)
