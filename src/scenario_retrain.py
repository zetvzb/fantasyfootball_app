"""Refit the scenario-price model mid-draft from the live partial auction.

This is a break-glass tool. The live-learning calibration layer already adapts
the blend to in-draft behaviour on every rerun; retraining only helps when the
room is behaving so differently from history that the model itself is wrong.
The current partial draft is appended to the 583 historical sales for one
full refit -- it never touches the walk-forward evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.auction_pool import normalize_player_name
from src.historical_auction_state import read_csv_rows, replay_auction_states
from src.historical_price_baseline import attach_historical_ranks
from src.ml_history_dataset import canonical_league_key
from src.scenario_market_values import _as_list
from src.scenario_price_inference import (
    DEFAULT_ARTIFACT_PATH,
    ScenarioPriceInferenceService,
    save_model_artifact,
)
from src.scenario_price_model import train_quantile_models

_CANONICAL = Path(__file__).resolve().parents[1] / "data" / "ml_pipeline" / "canonical"
_METADATA_PATH = DEFAULT_ARTIFACT_PATH.with_suffix(".metadata.json")


@dataclass(frozen=True)
class RetrainResult:
    model_version: str
    historical_rows: int
    live_rows: int
    matched_live_sales: int


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def build_live_training_rows(
    live_sales: Sequence[Any],
    team_setups: Any,
    fantasypros_index: Mapping[str, Any],
    *,
    league_key: str,
    season: int,
) -> list[dict]:
    """Replay the live partial draft into leakage-safe feature rows, ranked from
    the live FantasyPros index."""
    canonical_key = canonical_league_key(league_key)
    opening_states = [
        {
            "league_key": canonical_key,
            "season": season,
            "manager_id": str(getattr(setup, "manager_id", "")),
            "opening_cash": _num(
                getattr(setup, "starting_auction_cash", getattr(setup, "auction_cash", 0))
            ),
            "opening_roster_spots": _num(
                getattr(setup, "starting_open_roster_spots", getattr(setup, "open_roster_spots", 0))
            ),
            "minimum_bid": max(1, int(_num(getattr(setup, "minimum_auction_bid", 1), 1))),
        }
        for setup in _as_list(team_setups)
    ]
    canonical_sales = [
        {
            "league_key": canonical_key,
            "season": season,
            "overall_order": index + 1,
            "player_name": getattr(sale, "player_name", ""),
            "sleeper_player_id": "",
            "position": str(getattr(sale, "position", "") or "").upper(),
            "winning_manager_id": str(getattr(sale, "manager_id", "")),
            "winning_price": int(_num(getattr(sale, "price", 0))),
        }
        for index, sale in enumerate(
            sorted(live_sales, key=lambda s: _num(getattr(s, "sale_number", 0)))
        )
    ]
    replay = replay_auction_states(canonical_sales, opening_states)
    rows: list[dict] = []
    for feature in replay.features:
        fp = fantasypros_index.get(normalize_player_name(feature.get("player_name", "")))
        rank = getattr(fp, "half_ecr", None) if fp else None
        if rank in (None, ""):
            continue
        rows.append(
            {
                **dict(feature),
                "historical_overall_rank": rank,
                "historical_position_rank": (
                    getattr(fp, "half_position_rank", None) if fp else None
                ),
            }
        )
    return rows


def retrain_with_live_draft(
    live_sales: Sequence[Any],
    team_setups: Any,
    fantasypros_index: Mapping[str, Any],
    *,
    league_key: str,
    season: int,
    canonical_dir: Path = _CANONICAL,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    metadata_path: Path = _METADATA_PATH,
) -> RetrainResult:
    features = read_csv_rows(canonical_dir / "auction_state_features.csv")
    rankings = read_csv_rows(canonical_dir / "rankings.csv")
    historical, _unmatched = attach_historical_ranks(features, rankings)

    live_rows = build_live_training_rows(
        live_sales, team_setups, fantasypros_index, league_key=league_key, season=season
    )
    training = list(historical) + live_rows
    models = train_quantile_models(training)
    metadata = save_model_artifact(Path(artifact_path), models, training)
    metadata["live_partial_draft_rows"] = len(live_rows)
    Path(metadata_path).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    # Drop the cached artifact so the next predict() picks up the new file.
    ScenarioPriceInferenceService._load.cache_clear()

    return RetrainResult(
        model_version=str(metadata["model_version"]),
        historical_rows=len(historical),
        live_rows=len(live_rows),
        matched_live_sales=len(live_rows),
    )
