from typing import List, Optional

import aiohttp

from ..utils.logging import get_logger

logger = get_logger("PlayerFetcher")

class PlayerFetcher:
    def __init__(self):
        self.url_template = "https://playerdb.co/api/player/minecraft/{username}"
        self.cache = {}

    async def get_player_data(self, username: str) -> Optional[dict]:
        """Gets a player's UUID and name given their username. Caches results if called more than once

        Args:
            username (str): The username to get the UUID for

        Returns:
            Optional[dict]: The player's UUID and name data
        """
        # Check our UUID cache for the user, return it if it exists
        data = self.cache.get(username, None)
        if data:
            return data
        async with aiohttp.ClientSession() as session:
            url = self.url_template.format(username=username)
            data = await self.fetch_player_data(session, url)
            if data:
                self.cache[username] = data
                return data

    async def get_players_data(self, player_list: List[str]) -> List[dict]:
        """Gets the UUID info for every player in player_list

        Args:
            player_list (List[str]): A list of player names

        Returns:
            List[dict]: A list of dicts containing the players and their info
        """
        player_data = []
        for username in player_list:
            data = await self.get_player_data(username)
            if data:
                player_data.append(data)
        return player_data

    async def fetch_player_data(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[dict]:
        """Fetches the UUID and name data for a given player name formatted into the URL using the session passed

        Args:
            session (aiohttp.ClientSession): The session to use
            url (str): The url to get with the player's name formatted into it

        Returns:
            Optional[dict]: The player's UUID and name data
        """
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("success"):
                    ret = {
                        "name": data["data"]["player"]["username"],
                        "uuid": data["data"]["player"]["id"],
                    }
                    return ret
            logger.warning(
                f"Failed to retrieve data for player: {url}. Status code: {response.status}"
            )
            return None

    async def invalidate_player_cache(self, username: str):
        """Invalidate a player's cached UUID. Called when they disconnect to ensure no messed up UUID mappings

        Args:
            username (str): The username to invalidate the cache of
        """
        self.cache.pop(username, None)


# Shared class reference
player_fetcher = PlayerFetcher()
