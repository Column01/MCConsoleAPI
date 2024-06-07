from datetime import datetime

from services.player_fetch import player_fetcher
from utils.database import PlayerAnalyticsDB


class PlayerAnalytics:
    def __init__(self):
        self.db = PlayerAnalyticsDB()
        self.db.setup_database()
        self.temp_lookup = {}

    async def on_player_connect(self, username: str, server_name: str, ip: str):
        """Called when a player connects to a server to track the start of their session and some other info

        Args:
            username (str): The player who connected
            server_name (str): The server's name
            ip (str): The player's IP address
        """
        player_data = await player_fetcher.get_player_data(username)
        if player_data is None:
            print(f"Player {username} not found. Skipping tracking.")
            return

        uuid = player_data["uuid"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.temp_lookup[username] = {
            "uuid": uuid,
            "server_name": server_name,
            "ip": ip,
            "connect_time": timestamp,
        }
        print(f"Player {username} with UUID {uuid} connected at {timestamp}")

    async def on_player_disconnect(self, username: str):
        """Called when a player disconnects from the server to log their play session

        Args:
            username (str): The player who disconnected
        """
        if username in self.temp_lookup:
            disconnect_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ip = self.temp_lookup[username]["ip"]
            uuid = self.temp_lookup[username]["uuid"]
            server_name = self.temp_lookup[username]["server_name"]
            connect_time = self.temp_lookup[username]["connect_time"]
            session_len = (
                datetime.strptime(disconnect_time, "%Y-%m-%d %H:%M:%S")
                - datetime.strptime(connect_time, "%Y-%m-%d %H:%M:%S")
            ).total_seconds()

            self.db.insert_player_entry(
                uuid=uuid,
                username=username,
                ip=ip,
                server_name=server_name,
                connect_time=connect_time,
                disconnect_time=disconnect_time,
                session_len=int(session_len),
            )
            self.temp_lookup.pop(uuid, None)
            # Invalidate the player's cached UUID to fix issues regarding name changes
            # Lowers the cache's effectiveness a lot but makes the code safer
            await player_fetcher.invalidate_player_cache(username)
            print(
                f"Player {username} with UUID {uuid} disconnected at {disconnect_time}"
            )
        else:
            print(
                f"Player {username} with UUID {uuid} not found in temporary lookup. Skipping tracking."
            )

    async def server_stopping(self):
        """Called when the server stops to make sure we log all player sessions as server is stopping"""
        for username in self.temp_lookup:
            await self.on_player_disconnect(username)
