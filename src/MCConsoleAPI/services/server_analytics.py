import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..services.player_fetch import player_fetcher
from ..utils.database import ServerAnalyticsDB


class ServerAnalytics:
    def __init__(self, server_name: str):
        self.server_name = server_name
        self.db = ServerAnalyticsDB(autocommit=True)
        self.cursor = self.db.cursor
        self.db.setup_database(server_name)

    async def log_player_count(self, player_count: int, player_list: List[str]):
        """Logs the player count for the server

        Args:
            player_count (int): Number of players
            player_list (List[str]): List of players connected
        """
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

    async def get_player_counts(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Gets the player counts for a server in the given time range

        Args:
            start_date (Optional[str], optional): A start timestamp that looks like "%Y-%m-%d %H:%M:%S". Defaults to None.
            end_date (Optional[str], optional): An end timestamp that looks like "%Y-%m-%d %H:%M:%S". Defaults to None.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing timestamp, player_count, and online_players
        """
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

        results = self.db.fetch_all(query, params)

        # Convert the results to a list of dictionaries
        player_counts = []
        for result in results:
            timestamp, player_count, player_list_str = result
            player_list = json.loads(
                player_list_str
            )  # Safely convert the player_list string to a list
            player_counts.append(
                {
                    "timestamp": timestamp,
                    "player_count": player_count,
                    "online_players": player_list,
                }
            )

        return player_counts
