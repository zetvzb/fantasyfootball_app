from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class RankingObservation:
    source: str
    player_name: str
    rank: float
    position: Optional[str] = None


@dataclass(frozen=True)
class EnsemblePlayerRanking:
    player_name: str
    position: Optional[str]
    ensemble_rank: int
    average_source_rank: float
    source_count: int
    source_ranks: Tuple[Tuple[str, float], ...]
    rank_disagreement: float


@dataclass(frozen=True)
class RankingEnsemble:
    rankings: Tuple[EnsemblePlayerRanking, ...]
    configured_sources: Tuple[str, ...]
    active_sources: Tuple[str, ...]
    warnings: Tuple[str, ...]


def build_ranking_ensemble(
    observations: Sequence[RankingObservation],
    configured_sources: Sequence[str],
) -> RankingEnsemble:
    """Average available source ranks equally; disagreement is informational."""

    configured = tuple(dict.fromkeys(str(source) for source in configured_sources))
    grouped: Dict[str, list] = {}
    names: Dict[str, str] = {}
    positions: Dict[str, Optional[str]] = {}
    active = set()
    for observation in observations:
        if float(observation.rank) <= 0:
            continue
        key = normalize_player_name(observation.player_name)
        if not key:
            continue
        grouped.setdefault(key, []).append(observation)
        names[key] = observation.player_name
        positions[key] = observation.position or positions.get(key)
        active.add(observation.source)

    provisional = []
    for key, player_observations in grouped.items():
        # One vote per source. Later duplicate rows from the same source replace
        # earlier rows deterministically rather than increasing that source's weight.
        by_source = {
            observation.source: float(observation.rank)
            for observation in player_observations
        }
        source_ranks = tuple(sorted(by_source.items()))
        ranks = tuple(rank for _, rank in source_ranks)
        provisional.append(
            (
                sum(ranks) / len(ranks),
                names[key],
                positions[key],
                source_ranks,
                max(ranks) - min(ranks) if len(ranks) > 1 else 0.0,
            )
        )

    provisional.sort(key=lambda value: (value[0], normalize_player_name(value[1])))
    rankings = tuple(
        EnsemblePlayerRanking(
            player_name=player_name,
            position=position,
            ensemble_rank=index,
            average_source_rank=round(average_rank, 2),
            source_count=len(source_ranks),
            source_ranks=source_ranks,
            rank_disagreement=round(disagreement, 2),
        )
        for index, (average_rank, player_name, position, source_ranks, disagreement)
        in enumerate(provisional, start=1)
    )
    missing = tuple(source for source in configured if source not in active)
    warnings = (
        ("Missing ranking source(s): {0}; available sources were reweighted equally.".format(
            ", ".join(missing)
        ),)
        if missing
        else ()
    )
    return RankingEnsemble(
        rankings=rankings,
        configured_sources=configured,
        active_sources=tuple(source for source in configured if source in active),
        warnings=warnings,
    )


def build_repository_ranking_ensemble(
    *,
    sleeper_players: Mapping[str, Mapping[str, Any]],
    imported_rankings: Sequence[Mapping[str, Any]],
    third_party_players: Sequence[Any],
) -> RankingEnsemble:
    observations = []
    for player in sleeper_players.values():
        rank = player.get("search_rank")
        name = player.get("full_name") or player.get("player_name")
        if name and rank is not None:
            observations.append(
                RankingObservation("Sleeper", str(name), float(rank), player.get("position"))
            )
    for player in imported_rankings:
        rank = player.get("rank") or player.get("overall_rank")
        name = player.get("player_name") or player.get("name")
        if name and rank is not None:
            observations.append(
                RankingObservation("Import", str(name), float(rank), player.get("position"))
            )
    for player in third_party_players:
        rank = getattr(player, "half_ecr", None)
        if rank is not None:
            observations.append(
                RankingObservation(
                    "FantasyPros",
                    str(player.player_name),
                    float(rank),
                    getattr(player, "position", None),
                )
            )
    return build_ranking_ensemble(
        observations,
        configured_sources=("Sleeper", "Import", "FantasyPros"),
    )
