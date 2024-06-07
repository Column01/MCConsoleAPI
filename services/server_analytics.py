import json
from datetime import datetime

from services.player_fetch import player_fetcher
from utils.database import ServerAnalyticsDB


class ServerAnalytics:
    def __init__(self, server_name):
        self.server_name = server_name
        self.db = ServerAnalyticsDB(autocommit=True)
        self.cursor = self.db.cursor
        self.db.setup_database(server_name)

    async def log_player_count(self, player_count, player_list):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        players_data = await player_fetcher.get_players_data(player_list)
        player_list_str = json.dumps(players_data)

        self.cursor.execute(
            f"""
            INSERT INTO {self.server_name}_player_counts (timestamp, player_count, player_list)
            VALUES (?, ?, ?)
        """,
            (timestamp, player_count, player_list_str),
        )

    async def get_player_counts(self, start_date=None, end_date=None):
        query = f"SELECT timestamp, player_count, player_list FROM {self.server_name}_player_counts"
        params = []

        if start_date:
            query += " WHERE timestamp >= ?"
            params.append(start_date)

        if end_date:
            if start_date:
                query += " AND timestamp <= ?"
            else:
                query += " WHERE timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp"

        return self.cursor.fetch_all(query, params)
