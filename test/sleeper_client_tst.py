from typing import Any

import requests


class SleeperClient:
    BASE_URL = "https://api.sleeper.app/v1"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, endpoint: str) -> Any:
        """
        Make a GET request to the Sleeper API.
        """

        url = f"{self.BASE_URL}{endpoint}"

        response = self.session.get(
            url,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def get_user(self, username_or_user_id: str) -> dict:
        """
        Get a Sleeper user by username or user_id.
        """

        return self._get(
            f"/user/{username_or_user_id}"
        )

    def get_user_leagues(
        self,
        user_id: str,
        season: int,
    ) -> list[dict]:
        """
        Get all NFL leagues for a user for a given season.
        """

        return self._get(
            f"/user/{user_id}/leagues/nfl/{season}"
        )
if __name__ == "__main__":

    client = SleeperClient()

    username = "Zeke11111"

    print("\nLooking up Sleeper user...")

    user = client.get_user(username)

    print("\nUSER")
    print("----")
    print(f"Username: {user.get('username')}")
    print(f"Display Name: {user.get('display_name')}")
    print(f"User ID: {user.get('user_id')}")

    user_id = user["user_id"]

    print("\nLooking up 2026 leagues...")

    leagues = client.get_user_leagues(
        user_id=user_id,
        season=2026,
    )

    print("\n2026 LEAGUES")
    print("------------")

    for league in leagues:

        print(
            f"{league.get('name')} | "
            f"League ID: {league.get('league_id')} | "
            f"Teams: {league.get('total_rosters')} | "
            f"Status: {league.get('status')}"
        )