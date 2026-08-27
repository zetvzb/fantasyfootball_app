from __future__ import annotations

from typing import Any, Dict, Tuple

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF", "DST"}


def searchable_sleeper_players(
    sleeper_players: Dict[str, Any],
    *,
    positions: frozenset = frozenset(FANTASY_POSITIONS),
) -> Tuple[Tuple[str, str, Dict[str, Any]], ...]:
    """Every distinct active Sleeper player, ready for a name-search picker.

    Excludes inactive/historical Sleeper records -- these are frequently
    stale duplicate IDs (e.g. a second, retired entry sharing a real
    player's name) that only confuse a picker with no way to tell which
    is real. Returns (player_name, sleeper_id, raw_player_dict) sorted by
    name, deduped by (name, position) so a genuine same-name/same-position
    collision still surfaces every distinct id rather than silently
    hiding one.
    """

    options = []
    seen = set()
    for player_id, player in sleeper_players.items():
        position = str(player.get("position") or "").upper()
        name = str(player.get("full_name") or "").strip()
        if not name or position not in positions:
            continue
        if player.get("active") is False:
            continue
        identity = (name.lower(), position)
        if identity in seen:
            continue
        seen.add(identity)
        options.append((name, str(player_id), player))
    return tuple(sorted(options, key=lambda item: item[0].lower()))


def sleeper_player_option_label(name: str, player: Dict[str, Any]) -> str:
    return "{0} · {1} · {2}".format(
        name,
        str(player.get("position") or "-").upper(),
        player.get("team") or "FA",
    )
