import secrets
import sqlite3


class SQLiteDB:
    def __init__(self, db_name: str, *args, **kwargs):
        self.conn = sqlite3.connect(db_name, *args, **kwargs)
        self.cursor = self.conn.cursor()

    def setup_database(self):
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS api_keys (api_key TEXT PRIMARY KEY, name TEXT UNIQUE)"
        )

        # Try to get the Admin API key from the database.
        self.cursor.execute('SELECT * from api_keys WHERE name = "admin"')
        admin = self.cursor.fetchone()
        if admin is None:
            api_key = self.add_api_key("admin")
            if api_key is None:
                exit(
                    "Error when generating an Admin API key. The DB failed to create an Admin API key despite one not existing. This should NEVER happen!"
                )
            print(
                "WARNING! New Admin API key was generated! Use this to create a new user or if you are lazy. DO NOT LOSE THIS!"
            )
            print("\n\n")
            print("=" * 16)
            print(f"ADMIN API KEY: {api_key}")
            print("=" * 16)
            print("\n\n")

        print("Connection to Database established.")

    def has_api_key(self, api_key: str) -> bool:
        self.cursor.execute("SELECT * from api_keys WHERE api_key = ?", (api_key,))
        user = self.cursor.fetchone()
        if user is not None:
            return True
        return False

    def add_api_key(self, name: str) -> str:
        # Generate a new API key
        new_api_key = secrets.token_urlsafe(16)
        try:
            # Insert the new API key and name into the database
            self.cursor.execute(
                "INSERT INTO api_keys (api_key, name) VALUES (?, ?)",
                (new_api_key, name),
            )
            print(f"New API key '{new_api_key}' added for '{name}'.")
            return new_api_key
        except sqlite3.IntegrityError:
            print(f"ERROR: An API key with the name '{name}' already exists.")
            return None
