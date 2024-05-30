import json
from datetime import datetime

import aiohttp

from utils.database import SQLiteDB


class ServerAnalytics:
    def __init__(self, server_name):
        self.server_name = server_name
        self.db = SQLiteDB("server_analytics.db", autocommit=True)
        self.cursor = self.db.cursor
        self.create_table()
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "MCConsoleAPI by Column01"}
        )

        self.url_template = "https://playerdb.co/api/player/minecraft/{username}"

    async def close(self):
        await self.session.close()

    def create_table(self):
        self.cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.server_name}_player_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                player_count INTEGER,
                player_list TEXT
            )
        """
        )

    async def log_player_count(self, player_count, player_list):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        player_data = await self.get_player_data(player_list)
        player_list_str = json.dumps(player_data)

        self.cursor.execute(
            f"""
            INSERT INTO {self.server_name}_player_counts (timestamp, player_count, player_list)
            VALUES (?, ?, ?)
        """,
            (timestamp, player_count, player_list_str),
        )

    async def get_player_data(self, player_list):
        player_data = []
        async with aiohttp.ClientSession() as session:
            for username in player_list:
                url = self.url_template.format(username=username)
                data = await self.fetch_player_data(session, url)
                if data:
                    player_data.append(data)
        return player_data

    async def fetch_player_data(self, session, url):
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("success"):
                    ret = {
                        "name": data["data"]["player"]["username"],
                        "uuid": data["data"]["player"]["id"],
                    }
                    return ret
            print(
                f"Failed to retrieve data for player: {url}. Status code: {response.status}"
            )
            return None

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
