import json
import time
from pathlib import Path
from typing import Any

import requests


class SleeperClient:
    BASE_URL = "https://api.sleeper.app/v1"

    PLAYER_CACHE_HOURS = 24

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()

        self.cache_dir = Path("data")
        self.cache_dir.mkdir(exist_ok=True)

        self.player_cache_file = (
            self.cache_dir / "sleeper_players.json"
        )

    # -----------------------------------------------------
    # CORE REQUEST METHOD
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    def get_user(
        self,
        username_or_user_id: str,
    ) -> dict:

        return self._get(
            f"/user/{username_or_user_id}"
        )

    # -----------------------------------------------------
    # LEAGUES
    # -----------------------------------------------------

    def get_user_leagues(
        self,
        user_id: str,
        season: int,
    ) -> list[dict]:

        return self._get(
            f"/user/{user_id}/leagues/nfl/{season}"
        )

    def get_league(
        self,
        league_id: str,
    ) -> dict:

        return self._get(
            f"/league/{league_id}"
        )

    def get_league_users(
        self,
        league_id: str,
    ) -> list[dict]:

        return self._get(
            f"/league/{league_id}/users"
        )

    def get_league_rosters(
        self,
        league_id: str,
    ) -> list[dict]:

        return self._get(
            f"/league/{league_id}/rosters"
        )

    # -----------------------------------------------------
    # DRAFTS
    # -----------------------------------------------------

    def get_league_drafts(
        self,
        league_id: str,
    ) -> list[dict]:

        return self._get(
            f"/league/{league_id}/drafts"
        )

    def get_draft(
        self,
        draft_id: str,
    ) -> dict:

        return self._get(
            f"/draft/{draft_id}"
        )

    def get_draft_picks(
        self,
        draft_id: str,
    ) -> list[dict]:

        return self._get(
            f"/draft/{draft_id}/picks"
        )

    # -----------------------------------------------------
    # NFL PLAYER DATABASE
    # -----------------------------------------------------

    def get_players(
        self,
        force_refresh: bool = False,
    ) -> dict:
        """
        Fetch Sleeper's NFL player database.

        Uses a local 24-hour cache so we don't repeatedly
        download the full player dataset.
        """

        if (
            self.player_cache_file.exists()
            and not force_refresh
        ):
            cache_age_seconds = (
                time.time()
                - self.player_cache_file.stat().st_mtime
            )

            cache_age_hours = (
                cache_age_seconds / 3600
            )

            if (
                cache_age_hours
                < self.PLAYER_CACHE_HOURS
            ):
                with open(
                    self.player_cache_file,
                    "r",
                    encoding="utf-8",
                ) as file:
                    return json.load(file)

        players = self._get(
            "/players/nfl"
        )

        with open(
            self.player_cache_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                players,
                file,
            )

        return players

    # -----------------------------------------------------
    # HELPERS
    # -----------------------------------------------------

    @staticmethod
    def get_team_name(user: dict) -> str:
        """
        Try to determine the manager/team name Sleeper
        displays for a user.
        """

        metadata = user.get("metadata") or {}

        return (
            metadata.get("team_name")
            or user.get("display_name")
            or user.get("username")
            or user.get("user_id")
        )

    def build_roster_summary(
        self,
        league_id: str,
    ) -> list[dict]:
        """
        Join league users, rosters, and player metadata.
        """

        users = self.get_league_users(
            league_id
        )

        rosters = self.get_league_rosters(
            league_id
        )

        players = self.get_players()

        users_by_id = {
            user["user_id"]: user
            for user in users
        }

        summaries = []

        for roster in rosters:

            owner_id = roster.get("owner_id")

            user = users_by_id.get(
                owner_id,
                {}
            )

            player_ids = (
                roster.get("players")
                or []
            )

            player_names = []

            for player_id in player_ids:

                player = players.get(
                    player_id,
                    {}
                )

                full_name = (
                    player.get("full_name")
                    or (
                        f"{player.get('first_name', '')} "
                        f"{player.get('last_name', '')}"
                    ).strip()
                    or player_id
                )

                player_names.append(
                    full_name
                )

            summaries.append(
                {
                    "roster_id": roster.get(
                        "roster_id"
                    ),
                    "owner_id": owner_id,
                    "manager_name": (
                        user.get("display_name")
                        or user.get("username")
                        or owner_id
                    ),
                    "team_name": (
                        self.get_team_name(user)
                    ),
                    "player_ids": player_ids,
                    "player_names": player_names,
                    "settings": (
                        roster.get("settings")
                        or {}
                    ),
                }
            )

        return summaries