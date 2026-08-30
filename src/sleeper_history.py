"""Pull prior-season auction results straight from Sleeper.

Sleeper auction drafts expose the winning bid on every pick
(``metadata.amount``), and ``league.previous_league_id`` chains a league
back through its earlier seasons. Walking that chain gives the historical
market model real "what this room actually pays" data with no manual
entry -- the single biggest lever on price accuracy.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from src.league_setup_data import HistoricalSale, SourceInfo


SLEEPER_HISTORY_SOURCE = SourceInfo(
    source="sleeper",
    confidence=0.9,
    inferred=False,
    detail="Sleeper prior-season auction results",
)

_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
_COMPLETED_DRAFT_STATUSES = {"complete", "paused", "drafting"}


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _pick_price(pick: dict) -> Optional[int]:
    metadata = pick.get("metadata") or {}
    for raw in (
        metadata.get("amount"),
        metadata.get("price"),
        metadata.get("bid"),
        pick.get("amount"),
    ):
        if raw in (None, ""):
            continue
        try:
            cleaned = str(raw).replace("$", "").replace(",", "").strip()
            price = int(round(float(cleaned)))
        except (TypeError, ValueError):
            continue
        if price >= 1:
            return price
    return None


def _pick_player_name(pick: dict, sleeper_players: Optional[dict]) -> Optional[str]:
    player_id = str(pick.get("player_id") or "")
    record = (sleeper_players or {}).get(player_id) or {}
    full_name = record.get("full_name")
    if not full_name:
        parts = [record.get("first_name"), record.get("last_name")]
        full_name = " ".join(part for part in parts if part).strip()
    if not full_name:
        metadata = pick.get("metadata") or {}
        parts = [metadata.get("first_name"), metadata.get("last_name")]
        full_name = " ".join(part for part in parts if part).strip()
    return full_name or None


def _pick_position(pick: dict, sleeper_players: Optional[dict]) -> Optional[str]:
    metadata = pick.get("metadata") or {}
    position = str(metadata.get("position") or "").upper()
    if position in _POSITIONS:
        return position
    player_id = str(pick.get("player_id") or "")
    record = (sleeper_players or {}).get(player_id) or {}
    position = str(record.get("position") or "").upper()
    return position if position in _POSITIONS else None


def _manager_labels(client: Any, league_id: str) -> Tuple[dict, dict]:
    """(user_id -> label, roster_id -> label) for one prior-season league."""

    try:
        rosters = client.get_league_rosters(league_id) or []
        users = client.get_league_users(league_id) or []
    except Exception:  # noqa: BLE001 - a missing prior season is not fatal
        return {}, {}

    by_user = {}
    for user in users:
        user_id = str(user.get("user_id") or "")
        metadata = user.get("metadata") or {}
        by_user[user_id] = (
            metadata.get("team_name")
            or user.get("display_name")
            or user_id
        )

    by_roster = {}
    for roster in rosters:
        roster_id = str(roster.get("roster_id") or "")
        owner_id = str(roster.get("owner_id") or "")
        by_roster[roster_id] = by_user.get(owner_id, owner_id or roster_id)
    return by_user, by_roster


def fetch_sleeper_auction_history(
    client: Any,
    league_id: str,
    *,
    current_season: Optional[int] = None,
    max_seasons: int = 4,
    sleeper_players: Optional[dict] = None,
) -> Tuple[List[HistoricalSale], List[str]]:
    """Collect completed auction sales from a Sleeper league's past seasons.

    Walks ``previous_league_id`` up to ``max_seasons`` back. The current
    season's draft is skipped so an in-progress auction is never folded
    back in as its own history.
    """

    sales: List[HistoricalSale] = []
    warnings: List[str] = []
    seen = set()

    league_id = str(league_id or "").strip()
    visited = set()
    hops = 0

    while league_id and league_id not in visited and hops <= max_seasons:
        visited.add(league_id)
        hops += 1

        try:
            league = client.get_league(league_id) or {}
        except Exception as error:  # noqa: BLE001
            warnings.append(
                "Could not read Sleeper league {0}: {1}".format(league_id, error)
            )
            break

        season = _to_int(league.get("season"))
        previous_league_id = str(league.get("previous_league_id") or "").strip()

        is_past_season = current_season is None or (
            season is not None and season < int(current_season)
        )

        if is_past_season:
            try:
                drafts = client.get_league_drafts(league_id) or []
            except Exception as error:  # noqa: BLE001
                warnings.append(
                    "Could not read drafts for league {0}: {1}".format(
                        league_id, error
                    )
                )
                drafts = []

            owner_names = None
            for draft in drafts:
                if str(draft.get("type") or "").lower() != "auction":
                    continue
                if str(draft.get("status") or "").lower() not in _COMPLETED_DRAFT_STATUSES:
                    continue

                draft_id = str(draft.get("draft_id") or "")
                if not draft_id:
                    continue
                draft_year = _to_int(draft.get("season")) or season or 0

                try:
                    picks = client.get_draft_picks(draft_id) or []
                except Exception as error:  # noqa: BLE001
                    warnings.append(
                        "Could not read picks for draft {0}: {1}".format(
                            draft_id, error
                        )
                    )
                    continue

                if owner_names is None:
                    labels_by_user, labels_by_roster = _manager_labels(
                        client, league_id
                    )
                    owner_names = (labels_by_user, labels_by_roster)

                labels_by_user, labels_by_roster = owner_names
                for pick in picks:
                    if pick.get("is_keeper"):
                        continue
                    price = _pick_price(pick)
                    name = _pick_player_name(pick, sleeper_players)
                    if price is None or not name:
                        continue

                    picked_by = str(pick.get("picked_by") or "")
                    roster_id = str(pick.get("roster_id") or "")
                    manager_raw = (
                        labels_by_user.get(picked_by)
                        or labels_by_roster.get(roster_id)
                    )

                    key = (draft_year, name.lower(), (manager_raw or "").lower())
                    if key in seen:
                        continue
                    seen.add(key)

                    sales.append(
                        HistoricalSale(
                            year=int(draft_year),
                            player_name=name,
                            price=int(price),
                            manager_raw=manager_raw,
                            position=_pick_position(pick, sleeper_players),
                            source=SLEEPER_HISTORY_SOURCE,
                        )
                    )

        if not previous_league_id or previous_league_id == league_id:
            break
        league_id = previous_league_id

    return sales, warnings
