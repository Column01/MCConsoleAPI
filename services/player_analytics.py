from datetime import datetime

from services.player_fetch import player_fetcher
from utils.database import PlayerAnalyticsDB


class PlayerAnalytics:
    def __init__(self):
        self.db = PlayerAnalyticsDB()
        self.db.setup_database()
        self.temp_lookup = {}

    async def on_player_connect(self, username: str, server_name: str, ip: str):
        player_data = await player_fetcher.get_player_data(username)
        if player_data is None:
            print(f"Player {username} not found. Skipping tracking.")
            return

        uuid = player_data["uuid"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.temp_lookup[uuid] = {
            "username": username,
            "server_name": server_name,
            "ip": ip,
            "connect_time": timestamp,
        }
        print(f"Player {username} with UUID {uuid} connected at {timestamp}")

    async def on_player_disconnect(self, username: str):
        player_data = await player_fetcher.get_player_data(username)
        if player_data is None:
            print(f"Player {username} not found. Skipping tracking.")
            return

        uuid = player_data["uuid"]
        disconnect_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if uuid in self.temp_lookup:
            ip = self.temp_lookup[uuid]["ip"]
            server_name = self.temp_lookup[uuid]["server_name"]
            connect_time = self.temp_lookup[uuid]["connect_time"]
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
            print(
                f"Player {username} with UUID {uuid} disconnected at {disconnect_time}"
            )
        else:
            print(
                f"Player {username} with UUID {uuid} not found in temporary lookup. Skipping tracking."
            )
