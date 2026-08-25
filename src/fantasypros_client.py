import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv


load_dotenv()


class FantasyProsClient:
    BASE_URL = "https://api.fantasypros.com/public/v2/json"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 20):
        self.api_key = api_key or os.getenv("FANTASYPROS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FantasyPros API key not found. Set FANTASYPROS_API_KEY in .env."
            )
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        response = self.session.get(
            f"{self.BASE_URL}{endpoint}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("FantasyPros returned an unexpected non-object response.")
        return payload

    def get_consensus_rankings(
        self,
        season: int,
        position: str = "ALL",
        scoring: str = "HALF",
        ranking_type: str = "DRAFT",
        week: int = 0,
    ) -> dict:
        return self._get(
            f"/nfl/{season}/consensus-rankings",
            params={
                "position": position,
                "scoring": scoring,
                "type": ranking_type,
                "week": week,
                "experts": "show",
            },
        )

    def get_dynasty_rankings(
        self,
        season: int,
        position: str = "ALL",
    ) -> dict:
        return self.get_consensus_rankings(
            season=season,
            position=position,
            scoring="HALF",
            ranking_type="DYNASTY",
        )

    def get_projections(
        self,
        season: int,
        position: str,
    ) -> dict:
        return self._get(
            f"/nfl/{season}/projections",
            params={
                "position": position,
                "week": 0,
                "type": "preseason",
            },
        )

    def get_rankings(self, season: int, week: int = 0) -> dict:
        return self._get(
            f"/nfl/{season}/rankings",
            params={"week": week, "range": "true", "rankstats": "true"},
        )

    def get_players_with_ecr(self) -> dict:
        return self._get(
            "/nfl/players",
            params={"ecr": "included", "show": "pos_rank"},
        )
    
    def get_preseason_projections(self, season: int) -> dict:
        return self._get(
            f"/nfl/{season}/projections",
            params={
                "positions": "QB:RB:WR:TE:K:DST",
                "week": 0,
                "type": "preseason",
            },
        )

    def get_news(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        fpid: Optional[int] = None,
    ) -> dict:
        params = {
            "limit": min(int(limit), 100),
            "order_by": "created",
        }

        if category:
            params["category"] = category

        if fpid:
            params["fpid"] = int(fpid)

        return self._get(
            "/nfl/news",
            params=params,
        )

    def get_injuries(
        self,
        season: int,
        week: Optional[int] = None,
        player_ids: Optional[Any] = None,
    ) -> dict:
        params = {"year": int(season)}

        if week is not None:
            params["week"] = int(week)

        if player_ids:
            if isinstance(player_ids, (list, tuple, set)):
                params["player_ids"] = ":".join(
                    str(player_id) for player_id in player_ids
                )
            else:
                params["player_ids"] = str(player_ids)

        return self._get(
            "/nfl/injuries",
            params=params,
        )
