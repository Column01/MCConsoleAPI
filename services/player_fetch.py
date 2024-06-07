from typing import List, Optional

import aiohttp


class PlayerFetcher:
    def __init__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "MCConsoleAPI by Column01"}
        )

        self.url_template = "https://playerdb.co/api/player/minecraft/{username}"
        self.cache = {}

    async def get_player_data(self, username) -> Optional[dict]:
        # Check our UUID cache for the user, return it if it exists
        if username in self.cache:
            return self.cache[username]
        async with aiohttp.ClientSession() as session:
            url = self.url_template.format(username=username)
            data = await self.fetch_player_data(session, url)
            if data:
                self.cache[username] = data
                return data

    async def get_players_data(self, player_list) -> List[dict]:
        player_data = []
        for username in player_list:
            data = await self.get_player_data(username)
            if data:
                player_data.append(data)
        return player_data

    async def fetch_player_data(self, session, url) -> Optional[dict]:
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


# Shared class reference
player_fetcher = PlayerFetcher()
