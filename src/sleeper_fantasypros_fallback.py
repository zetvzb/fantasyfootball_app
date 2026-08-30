"""Rankings + projections from Sleeper, for when the FantasyPros API is down.

FantasyPros' public tier rate-limits (429) and then blocks (403). When that
happens the draft board loses auction values entirely. Sleeper already gives us
every player's ``search_rank`` (a real consensus ranking) and publishes
season-total half-PPR point projections on a separate open endpoint -- enough to
rebuild ``intelligence`` and per-player VORP without FantasyPros.

The bundle this produces matches ``load_fantasypros_data``'s contract closely
enough that the rest of the app does not care where the numbers came from:
``intelligence`` is a real list, ``projection_response`` is empty, and
``_prebuilt_projections`` carries ``PlayerProjection`` rows the caller runs
through the normal replacement-level / VORP math.
"""

from __future__ import annotations

import json
from typing import Dict, List, Mapping
from urllib.request import Request, urlopen

from src.fantasypros_intelligence import FantasyProsPlayerIntelligence
from src.projections import PlayerProjection

_FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
_VORP_POSITIONS = {"QB", "RB", "WR", "TE"}
_UNRANKED = 5000.0


def _norm_position(value: object) -> str:
    position = str(value or "").upper()
    return "DEF" if position in {"DST", "D/ST"} else position


def fetch_sleeper_projection_points(season: int, timeout: int = 20) -> Dict[str, float]:
    """``{sleeper_player_id: projected_half_ppr_season_points}``."""
    url = (
        "https://api.sleeper.app/projections/nfl/{0}?season_type=regular".format(season)
    )
    request = Request(url, headers={"User-Agent": "fantasyfootball-app"})
    with urlopen(request, timeout=timeout) as response:
        rows = json.loads(response.read().decode("utf-8"))
    points: Dict[str, float] = {}
    for row in rows or []:
        stats = row.get("stats") or {}
        value = stats.get("pts_half_ppr")
        player_id = str(row.get("player_id") or "")
        if player_id and isinstance(value, (int, float)) and value > 0:
            points[player_id] = float(value)
    return points


def _ranked_players(sleeper_players: Mapping[str, Mapping[str, object]]) -> List[tuple]:
    ranked = []
    for player_id, player in sleeper_players.items():
        position = _norm_position(player.get("position"))
        if position not in _FANTASY_POSITIONS:
            continue
        if player.get("active") is False:
            continue
        rank = player.get("search_rank")
        if not isinstance(rank, (int, float)) or rank <= 0 or rank >= 999_999:
            continue
        ranked.append((float(rank), str(player_id), player, position))
    ranked.sort(key=lambda item: item[0])
    return ranked


def build_intelligence(
    sleeper_players: Mapping[str, Mapping[str, object]],
) -> List[FantasyProsPlayerIntelligence]:
    ranked = _ranked_players(sleeper_players)
    position_counts: Dict[str, int] = {}
    intelligence: List[FantasyProsPlayerIntelligence] = []
    for overall_index, (_rank, player_id, player, position) in enumerate(ranked, start=1):
        position_counts[position] = position_counts.get(position, 0) + 1
        name = (
            str(player.get("full_name") or "").strip()
            or "{0} {1}".format(
                player.get("first_name") or "", player.get("last_name") or ""
            ).strip()
        )
        if not name:
            continue
        ecr = float(overall_index)
        intelligence.append(
            FantasyProsPlayerIntelligence(
                fantasypros_id="sleeper-{0}".format(player_id),
                player_name=name,
                position=position,
                nfl_team=(player.get("team") or None),
                half_ecr=ecr,
                half_position_rank=float(position_counts[position]),
                # Sleeper has no separate dynasty consensus; reuse redraft rank
                # so keeper-upside math still has a signal.
                dynasty_ecr=ecr,
                dynasty_position_rank=float(position_counts[position]),
                adp=ecr,
                ecr_min=ecr,
                ecr_max=ecr,
                ecr_avg=ecr,
                ecr_std=0.0,
            )
        )
    return intelligence


def build_projections(
    sleeper_players: Mapping[str, Mapping[str, object]],
    projection_points: Mapping[str, float],
) -> List[PlayerProjection]:
    projections: List[PlayerProjection] = []
    for player_id, points in projection_points.items():
        player = sleeper_players.get(str(player_id))
        if not player:
            continue
        position = _norm_position(player.get("position"))
        if position not in _VORP_POSITIONS:
            continue
        name = (
            str(player.get("full_name") or "").strip()
            or "{0} {1}".format(
                player.get("first_name") or "", player.get("last_name") or ""
            ).strip()
        )
        if not name:
            continue
        projections.append(
            PlayerProjection(
                fantasypros_id="sleeper-{0}".format(player_id),
                player_name=name,
                position=position,
                nfl_team=(player.get("team") or None),
                stats={"pts_half_ppr": float(points)},
                fantasypros_half_points=float(points),
                custom_points=float(points),
                custom_scoring_exact=False,
            )
        )
    return projections


def build_fallback_bundle(
    season: int,
    sleeper_players: Mapping[str, Mapping[str, object]],
) -> dict:
    """A ``load_fantasypros_data``-shaped dict built entirely from Sleeper."""
    try:
        projection_points = fetch_sleeper_projection_points(season)
    except Exception:  # noqa: BLE001 - projections are best-effort
        projection_points = {}
    intelligence = build_intelligence(sleeper_players)
    projections = build_projections(sleeper_players, projection_points)
    return {
        "rankings_response": {},
        "players_response": {},
        "projection_response": {},
        "intelligence": intelligence,
        "_prebuilt_projections": projections,
        "health": None,
        "_errors": {"fantasypros": "FantasyPros unavailable; using Sleeper rankings"},
        "_source": "sleeper_fallback",
    }
