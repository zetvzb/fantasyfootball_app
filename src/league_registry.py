from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Union

from src.league_profile import LeagueProfile


class LeagueRegistry:
    """Persist normalized league profiles independently of the workbook."""

    def __init__(
        self,
        root: Union[str, Path] = "data/leagues",
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, league_key: str) -> Path:
        safe = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in league_key
        ).strip("_")
        if not safe:
            raise ValueError("league_key cannot be empty")
        return self.root / f"{safe}.json"

    def save(self, profile: LeagueProfile) -> Path:
        path = self._path(profile.league_key)
        path.write_text(
            json.dumps(profile.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def load(self, league_key: str) -> LeagueProfile:
        path = self._path(league_key)
        if not path.exists():
            raise FileNotFoundError(f"League profile not found: {league_key}")
        return LeagueProfile.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def exists(self, league_key: str) -> bool:
        return self._path(league_key).exists()

    def delete(self, league_key: str) -> None:
        path = self._path(league_key)
        if path.exists():
            path.unlink()

    def list_profiles(self) -> List[LeagueProfile]:
        profiles: List[LeagueProfile] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                profiles.append(
                    LeagueProfile.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return profiles
