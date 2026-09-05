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
from typing import Dict, List, Mapping, Optional
from urllib.request import Request, urlopen

from src.fantasypros_intelligence import FantasyProsPlayerIntelligence
from src.projections import PlayerProjection, SCORING_STAT_MAP, score_offensive_projection

_FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
_VORP_POSITIONS = {"QB", "RB", "WR", "TE"}
_UNRANKED = 5000.0


def _norm_position(value: object) -> str:
    position = str(value or "").upper()
    return "DEF" if position in {"DST", "D/ST"} else position


def fetch_sleeper_projections(season: int, timeout: int = 20) -> Dict[str, Dict[str, float]]:
    """``{sleeper_player_id: raw_season_stat_projections}``.

    Sleeper's projections endpoint returns full per-stat season lines (pass
    yards, receptions, rush TDs, etc.), not just a single aggregate point
    total -- keeping the whole stats dict (rather than just
    ``pts_half_ppr``) is what lets `build_projections` re-score under the
    league's *actual* scoring settings instead of a generic half-PPR proxy.
    """
    url = (
        "https://api.sleeper.app/projections/nfl/{0}?season_type=regular".format(season)
    )
    request = Request(url, headers={"User-Agent": "fantasyfootball-app"})
    with urlopen(request, timeout=timeout) as response:
        rows = json.loads(response.read().decode("utf-8"))
    projections: Dict[str, Dict[str, float]] = {}
    for row in rows or []:
        stats = row.get("stats") or {}
        value = stats.get("pts_half_ppr")
        player_id = str(row.get("player_id") or "")
        if player_id and isinstance(value, (int, float)) and value > 0:
            projections[player_id] = stats
    return projections


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


def _translate_to_fantasypros_stats(raw_stats: Mapping[str, object]) -> Dict[str, float]:
    """Sleeper's native stat keys (``rec``, ``pass_yd``, ...) -> the
    FantasyPros-style keys `score_offensive_projection` expects (``rec_rec``,
    ``pass_yds``, ...), reusing the same `SCORING_STAT_MAP` the FantasyPros
    path scores real projections with.
    """
    translated: Dict[str, float] = {}
    for sleeper_key, fp_key in SCORING_STAT_MAP.items():
        value = raw_stats.get(sleeper_key)
        if isinstance(value, (int, float)):
            translated[fp_key] = float(value)
    return translated


def build_projections(
    sleeper_players: Mapping[str, Mapping[str, object]],
    projection_stats: Mapping[str, Mapping[str, float]],
    scoring_settings: Optional[Dict[str, float]] = None,
) -> List[PlayerProjection]:
    """Build league-scored `PlayerProjection` rows from raw Sleeper stat
    projections. When `scoring_settings` is omitted, falls back to Sleeper's
    own generic half-PPR point total (the old behavior) rather than erroring
    -- a missing league scoring config shouldn't break the draft board.
    """
    projections: List[PlayerProjection] = []
    for player_id, raw_stats in projection_stats.items():
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

        half_ppr_points = float(raw_stats.get("pts_half_ppr") or 0.0)
        fp_stats = _translate_to_fantasypros_stats(raw_stats)

        if scoring_settings and fp_stats:
            custom_points, breakdown, warnings = score_offensive_projection(
                stats=fp_stats, scoring_settings=scoring_settings
            )
            exact = not warnings
        else:
            custom_points, breakdown, warnings, exact = half_ppr_points, {}, [], False

        projections.append(
            PlayerProjection(
                fantasypros_id="sleeper-{0}".format(player_id),
                player_name=name,
                position=position,
                nfl_team=(player.get("team") or None),
                stats=fp_stats or {"pts_half_ppr": half_ppr_points},
                fantasypros_half_points=half_ppr_points,
                custom_points=custom_points,
                custom_scoring_exact=exact,
                scoring_breakdown=breakdown,
                scoring_warnings=warnings,
            )
        )
    return projections


def build_fallback_bundle(
    season: int,
    sleeper_players: Mapping[str, Mapping[str, object]],
    scoring_settings: Optional[Dict[str, float]] = None,
) -> dict:
    """A ``load_fantasypros_data``-shaped dict built entirely from Sleeper."""
    try:
        projection_stats = fetch_sleeper_projections(season)
    except Exception:  # noqa: BLE001 - projections are best-effort
        projection_stats = {}
    intelligence = build_intelligence(sleeper_players)
    projections = build_projections(sleeper_players, projection_stats, scoring_settings)
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
