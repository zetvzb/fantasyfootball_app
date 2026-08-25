from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class MyGuysPreferences:
    league_key: str
    user_key: str
    player_names: Tuple[str, ...] = ()
    premium: int = 0

    def __post_init__(self) -> None:
        if self.premium < 0:
            raise ValueError("My Guys premium cannot be negative.")

    def includes(self, player_name: str) -> bool:
        key = normalize_player_name(player_name)
        return key in {normalize_player_name(name) for name in self.player_names}

    def adjusted_cap(self, player_name: str, base_cap: int, legal_max: int) -> int:
        premium = self.premium if self.includes(player_name) else 0
        return min(int(legal_max), int(base_cap) + premium)


class MyGuysStore:
    def __init__(
        self,
        root: Union[str, Path] = "data/my_guys",
        checkpoint_callback=None,
    ):
        self.root = Path(root)
        self.checkpoint_callback = checkpoint_callback

    def _path(self, league_key: str, user_key: str) -> Path:
        identity = "{0}\0{1}".format(league_key, user_key)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        return self.root / "{0}.json".format(digest)

    def load(self, league_key: str, user_key: str) -> Optional[MyGuysPreferences]:
        path = self._path(league_key, user_key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = MyGuysPreferences(
            league_key=str(payload["league_key"]),
            user_key=str(payload["user_key"]),
            player_names=tuple(payload.get("player_names", ())),
            premium=int(payload.get("premium", 0)),
        )
        if result.league_key != league_key or result.user_key != user_key:
            raise ValueError("Stored My Guys identity does not match.")
        return result

    def save(self, preferences: MyGuysPreferences) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(preferences.league_key, preferences.user_key)
        temporary = path.with_suffix(".tmp")
        payload = asdict(preferences)
        payload["player_names"] = list(preferences.player_names)
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)
        if self.checkpoint_callback is not None:
            self.checkpoint_callback()
        return path
