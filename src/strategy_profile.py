from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union


class StrategyMode(str, Enum):
    WIN_NOW = "win_now"
    HYBRID = "hybrid"
    WIN_LATER = "win_later"

    @property
    def label(self) -> str:
        return {
            StrategyMode.WIN_NOW: "Win Now",
            StrategyMode.HYBRID: "Hybrid",
            StrategyMode.WIN_LATER: "Win Later",
        }[self]


STRATEGY_PRESET_WEIGHTS: Dict[StrategyMode, Tuple[float, float]] = {
    StrategyMode.WIN_NOW: (0.75, 0.25),
    StrategyMode.HYBRID: (0.50, 0.50),
    StrategyMode.WIN_LATER: (0.25, 0.75),
}


@dataclass(frozen=True)
class StrategyProfile:
    league_key: str
    user_key: str
    mode: StrategyMode
    current_weight: float
    future_weight: float

    def __post_init__(self) -> None:
        if not self.league_key:
            raise ValueError("Strategy league key cannot be empty.")
        if not self.user_key:
            raise ValueError("Strategy user key cannot be empty.")
        if not isinstance(self.mode, StrategyMode):
            raise ValueError("Unknown strategy mode: {0}".format(self.mode))
        if not 0.0 <= self.current_weight <= 1.0:
            raise ValueError("Current-season weight must be between 0 and 1.")
        if not 0.0 <= self.future_weight <= 1.0:
            raise ValueError("Future-value weight must be between 0 and 1.")
        if abs((self.current_weight + self.future_weight) - 1.0) > 1e-9:
            raise ValueError("Strategy weights must total 1.0.")

    @classmethod
    def for_mode(
        cls,
        league_key: str,
        user_key: str,
        mode: StrategyMode,
    ) -> "StrategyProfile":
        current_weight, future_weight = STRATEGY_PRESET_WEIGHTS[mode]
        return cls(
            league_key=str(league_key),
            user_key=str(user_key),
            mode=mode,
            current_weight=current_weight,
            future_weight=future_weight,
        )

    @classmethod
    def from_league_defaults(
        cls,
        league_profile: Any,
        user_key: str,
    ) -> "StrategyProfile":
        model_rules = league_profile.model
        current_weight = float(model_rules.current_season_weight)
        future_weight = float(model_rules.future_value_weight)
        total = current_weight + future_weight
        if total <= 0:
            current_weight, future_weight = STRATEGY_PRESET_WEIGHTS[
                StrategyMode.HYBRID
            ]
        else:
            current_weight /= total
            future_weight /= total
        return cls(
            league_key=str(league_profile.league_key),
            user_key=str(user_key),
            mode=StrategyMode.HYBRID,
            current_weight=current_weight,
            future_weight=future_weight,
        )

    def with_current_weight(self, current_weight: float) -> "StrategyProfile":
        normalized_current = float(current_weight)
        return StrategyProfile(
            league_key=self.league_key,
            user_key=self.user_key,
            mode=self.mode,
            current_weight=normalized_current,
            future_weight=1.0 - normalized_current,
        )

    def to_dict(self) -> dict:
        return {
            "league_key": self.league_key,
            "user_key": self.user_key,
            "mode": self.mode.value,
            "current_weight": self.current_weight,
            "future_weight": self.future_weight,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "StrategyProfile":
        return cls(
            league_key=str(payload["league_key"]),
            user_key=str(payload["user_key"]),
            mode=StrategyMode(str(payload["mode"])),
            current_weight=float(payload["current_weight"]),
            future_weight=float(payload["future_weight"]),
        )


class StrategyProfileStore:
    """Persist private strategy preferences by league and current user."""

    def __init__(
        self,
        root: Union[str, Path] = "data/strategy_profiles",
        checkpoint_callback=None,
    ):
        self.root = Path(root)
        self.checkpoint_callback = checkpoint_callback

    @staticmethod
    def _safe_part(value: str) -> str:
        safe = "".join(
            character
            if character.isalnum() or character in {"-", "_"}
            else "_"
            for character in str(value)
        ).strip("_")
        return safe or "unknown"

    def _path(self, league_key: str, user_key: str) -> Path:
        identity = "{0}\0{1}".format(league_key, user_key)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        filename = "{0}--{1}--{2}.json".format(
            self._safe_part(league_key),
            self._safe_part(user_key),
            digest,
        )
        return self.root / filename

    def load(
        self,
        league_key: str,
        user_key: str,
    ) -> Optional[StrategyProfile]:
        path = self._path(league_key, user_key)
        if not path.exists():
            return None
        try:
            profile = StrategyProfile.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("Stored strategy profile is invalid.") from error
        if (
            profile.league_key != str(league_key)
            or profile.user_key != str(user_key)
        ):
            raise ValueError(
                "Stored strategy identity does not match the requested user and league."
            )
        return profile

    def save(self, profile: StrategyProfile) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(profile.league_key, profile.user_key)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(profile.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        if self.checkpoint_callback is not None:
            self.checkpoint_callback()
        return path
