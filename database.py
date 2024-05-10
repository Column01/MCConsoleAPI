import secrets
import sqlite3


class SQLiteDB:
    def __init__(self, db_name: str, *args, **kwargs):
        self.conn = sqlite3.connect(db_name, *args, **kwargs)
        self.cursor = self.conn.cursor()

    def setup_database(self):
        self.cursor.execute('CREATE TABLE IF NOT EXISTS api_keys (api_key TEXT PRIMARY KEY, name TEXT)')

        # Try to get the Admin API key from the database.
        self.cursor.execute('SELECT * from api_keys WHERE name = "admin"')
        admin = self.cursor.fetchone()
        if admin is None:
            new_api_key = secrets.token_urlsafe(16)
            self.cursor.execute('INSERT INTO api_keys (api_key, name) VALUES (?, ?)', (new_api_key, 'admin'))
            print("WARNING! New Admin API key was generated! Use this to create a new user or if you are lazy. DO NOT LOSE THIS!")
            print("\n\n")
            print("=" * 16)
            print(f"ADMIN API KEY: {new_api_key}")
            print("=" * 16)
            print("\n\n")

        print("Connection to Database established.")

    def has_api_key(self, api_key: str) -> bool:
        self.cursor.execute('SELECT * from api_keys WHERE api_key = ?', [api_key])
        user = self.cursor.fetchone()
        if user is not None:
            return True
        return False