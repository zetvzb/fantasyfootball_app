from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple, Union


@dataclass(frozen=True)
class SavedBudgetBand:
    position: str
    minimum: int
    target: int
    maximum: int


@dataclass(frozen=True)
class SavedPriorityTier:
    label: str
    player_names: Tuple[str, ...]


@dataclass(frozen=True)
class PlanningPreferences:
    league_key: str
    user_key: str
    manager_id: str
    recommended_strategy: str
    budget_bands: Tuple[SavedBudgetBand, ...] = ()
    priority_tiers: Tuple[SavedPriorityTier, ...] = ()
    nomination_plan: str = ""
    fallback_plan: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.league_key or not self.user_key or not self.manager_id:
            raise ValueError("Planning state requires league, user, and manager identity.")

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["budget_bands"] = [asdict(value) for value in self.budget_bands]
        payload["priority_tiers"] = [
            {
                "label": value.label,
                "player_names": list(value.player_names),
            }
            for value in self.priority_tiers
        ]
        payload["fallback_plan"] = list(self.fallback_plan)
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "PlanningPreferences":
        return cls(
            league_key=str(payload["league_key"]),
            user_key=str(payload["user_key"]),
            manager_id=str(payload["manager_id"]),
            recommended_strategy=str(payload.get("recommended_strategy") or ""),
            budget_bands=tuple(
                SavedBudgetBand(
                    position=str(value["position"]),
                    minimum=int(value["minimum"]),
                    target=int(value["target"]),
                    maximum=int(value["maximum"]),
                )
                for value in payload.get("budget_bands", ())
            ),
            priority_tiers=tuple(
                SavedPriorityTier(
                    label=str(value["label"]),
                    player_names=tuple(value.get("player_names", ())),
                )
                for value in payload.get("priority_tiers", ())
            ),
            nomination_plan=str(payload.get("nomination_plan") or ""),
            fallback_plan=tuple(payload.get("fallback_plan", ())),
        )


class PlanningPreferencesStore:
    """Persist a user's private pre-draft plan by league and manager."""

    def __init__(
        self,
        root: Union[str, Path] = "data/planning_preferences",
        checkpoint_callback=None,
    ):
        self.root = Path(root)
        self.checkpoint_callback = checkpoint_callback

    def _path(self, league_key: str, user_key: str, manager_id: str) -> Path:
        identity = "{0}\0{1}\0{2}".format(league_key, user_key, manager_id)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.root / "{0}.json".format(digest[:20])

    def load(
        self,
        league_key: str,
        user_key: str,
        manager_id: str,
    ) -> Optional[PlanningPreferences]:
        path = self._path(league_key, user_key, manager_id)
        if not path.exists():
            return None
        try:
            result = PlanningPreferences.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Stored planning preferences are invalid.") from error
        expected = (str(league_key), str(user_key), str(manager_id))
        actual = (result.league_key, result.user_key, result.manager_id)
        if actual != expected:
            raise ValueError("Stored planning identity does not match the request.")
        return result

    def save(self, preferences: PlanningPreferences) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(
            preferences.league_key,
            preferences.user_key,
            preferences.manager_id,
        )
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(preferences.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)
        if self.checkpoint_callback is not None:
            self.checkpoint_callback()
        return path
