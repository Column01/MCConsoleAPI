import secrets
import sqlite3
from sqlite3 import Cursor
from typing import Any, List, Optional

from ..utils.logging import get_logger

logger = get_logger("database")


class SQLiteDB:
    def __init__(self, db_name: str, *args, **kwargs):
        self.conn = sqlite3.connect(db_name, *args, **kwargs)
        self.cursor = self.conn.cursor()

    def execute_query(self, query: str, params: tuple = ()) -> Cursor:
        self.cursor.execute(query, params)

    def fetch_one(self, query: str, params: tuple = ()) -> Any:
        self.execute_query(query, params)
        return self.cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> List[Any]:
        self.execute_query(query, params)
        return self.cursor.fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


class ApiDB(SQLiteDB):
    def setup_database(self):
        self.execute_query(
            "CREATE TABLE IF NOT EXISTS api_keys (api_key TEXT PRIMARY KEY, name TEXT UNIQUE)"
        )

        # Try to get the Admin API key from the database
        admin_api_key = self.get_api_key_by_name("admin")
        if admin_api_key is None:
            api_key = self.add_api_key("admin")
            if api_key is None:
                exit(
                    "Error when generating an Admin API key. The DB failed to create an Admin API key despite one not existing. This should NEVER happen!"
                )
            logger.info(
                "WARNING! New Admin API key was generated! Use this to create a new user or if you are lazy. DO NOT LOSE THIS!"
            )
            logger.info("\n\n")
            msg = f"ADMIN API KEY: {api_key}"
            logger.info("=" * len(msg))
            logger.info(msg)
            logger.info("=" * len(msg))
            logger.info("\n\n")

        logger.info("Connection to Database established.")

    def has_api_key(self, api_key: str) -> bool:
        result = self.fetch_one("SELECT * from api_keys WHERE api_key = ?", (api_key,))
        return result is not None

    def add_api_key(self, name: str) -> Optional[str]:
        # Generate a new API key
        new_api_key = secrets.token_urlsafe(32)
        try:
            # Insert the new API key and name into the database
            self.execute_query(
                "INSERT INTO api_keys (api_key, name) VALUES (?, ?)",
                (new_api_key, name),
            )
            self.commit()
            logger.info(f"New API key '{new_api_key}' added for '{name}'.")
            return new_api_key
        except sqlite3.IntegrityError:
            logger.error(f"An API key with the name '{name}' already exists.")
            return None

    def get_api_key_by_name(self, name: str) -> Optional[str]:
        result = self.fetch_one("SELECT api_key from api_keys WHERE name = ?", (name,))
        if result is not None:
            return result[0]

    def get_api_key_name(self, api_key: str) -> Optional[str]:
        result = self.fetch_one(
            "SELECT name from api_keys WHERE api_key = ?", (api_key,)
        )
        if result is not None:
            return result[0]

    def is_admin_api_key(self, api_key: str) -> bool:
        admin_api_key = self.get_api_key_by_name("admin")
        if admin_api_key is not None:
            return secrets.compare_digest(api_key, admin_api_key)
        return False


class ServerAnalyticsDB(SQLiteDB):
    def __init__(self, *args, **kwargs):
        super().__init__("server_analytics.db", *args, **kwargs)

    def setup_database(self, server_name):
        self.execute_query(
            f"""
            CREATE TABLE IF NOT EXISTS {server_name}_player_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                player_count INTEGER,
                player_list TEXT
            )
        """
        )
        self.commit()
        logger.info("Connection to Server Analytics Database established.")


class PlayerAnalyticsDB(SQLiteDB):
    def __init__(self, *args, **kwargs):
        super().__init__("player_analytics.db", *args, **kwargs)

    def setup_database(self):
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS player_sessions (
                uuid TEXT,
                username TEXT,
                ip TEXT,
                server_name TEXT,
                connect_time DATETIME,
                disconnect_time DATETIME,
                session_len INTEGER
            )
            """
        )
        self.commit()
        logger.info("Connection to Player Analytics Database established.")

    async def insert_player_entry(
        self,
        uuid: str,
        username: str,
        ip: str,
        server_name: str,
        connect_time: str,
        disconnect_time: str,
        session_len: int,
    ):
        try:
            self.execute_query(
                """
                INSERT INTO player_sessions (
                    uuid, username, ip, server_name, connect_time, disconnect_time, session_len
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid,
                    username,
                    ip,
                    server_name,
                    connect_time,
                    disconnect_time,
                    session_len,
                ),
            )
            self.commit()
            logger.info(f"Player entry inserted for UUID: {uuid}")
        except sqlite3.IntegrityError:
            logger.info(f"Error: Player entry with UUID {uuid} already exists.")

    async def get_player_sessions(
        self,
        uuid: str,
        server_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Optional[dict]]:
        query = "SELECT * FROM player_sessions WHERE uuid = ?"
        params = (uuid,)

        if server_name:
            query += " AND server_name = ?"
            params += (server_name,)

        if start_time and end_time:
            query += " AND connect_time BETWEEN ? AND ?"
            params += (start_time, end_time)
        elif start_time:
            query += " AND connect_time >= ?"
            params += (start_time,)
        elif end_time:
            query += " AND connect_time <= ?"
            params += (end_time,)

        rows = self.fetch_all(query, params)

        player_sessions = []
        for row in rows:
            session = {
                "uuid": row[0],
                "username": row[1],
                "ip": row[2],
                "server_name": row[3],
                "connect_time": row[4],
                "disconnect_time": row[5],
                "session_len": row[6],
            }
            player_sessions.append(session)

        return player_sessions
