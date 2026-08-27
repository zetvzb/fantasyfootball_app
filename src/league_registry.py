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
        checkpoint_callback=None,
    ):
        self.root = Path(root)
        self.checkpoint_callback = checkpoint_callback
        self.root.mkdir(parents=True, exist_ok=True)

    def _checkpoint(self) -> None:
        if self.checkpoint_callback is not None:
            self.checkpoint_callback()

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
        self._checkpoint()
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
            self._checkpoint()

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


def delete_league_data(
    *,
    league_key: str,
    league_registry: "LeagueRegistry",
    setup_store,
    draft_state_directory: Union[str, Path],
) -> List[str]:
    """Remove every local trace of a league: its profile, its setup data
    (budgets/keepers/history), and any per-league draft-state databases.

    Returns a short description of what was actually removed, for UI
    confirmation. Never touches the shared legacy `draft_state.db` -- only
    per-league files under `draft_state_directory` matching this league's
    sanitized key are deleted.
    """

    removed: List[str] = []

    if league_registry.exists(league_key):
        league_registry.delete(league_key)
        removed.append("league profile")

    if setup_store.exists(league_key):
        setup_store.delete(league_key)
        removed.append("league setup data")

    directory = Path(draft_state_directory)
    safe_key = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in str(league_key)
    ).strip("_") or "league"

    draft_db_paths = (
        sorted(directory.glob(f"{safe_key}_*.db")) if directory.exists() else []
    )
    for db_path in draft_db_paths:
        db_path.unlink()
    if draft_db_paths:
        removed.append(
            "{0} draft state database(s)".format(len(draft_db_paths))
        )

    return removed
