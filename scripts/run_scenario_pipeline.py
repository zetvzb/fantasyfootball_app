"""Rebuild the scenario-price model and its evaluation reports in one command.

Starts from the curated canonical CSVs in ``data/ml_pipeline/canonical/``
(``sales.csv``, ``rankings.csv``, ``opening_team_states.csv``) -- the
xlsx -> canonical conversion and the Sleeper-reconciled opening team states are
upstream manual steps (see docs/PRICE_BLEND.md).

Stages:
  1. replay historical auction states  -> auction_state_features.csv
  2. rank-neighbour price baseline      -> baseline_predictions.csv / .json
  3. walk-forward scenario evaluation   -> scenario_model_predictions.csv / report
  4. final full-history model fit       -> models/scenario_price_model.joblib

Pass ``--live-sales <csv>`` to append a partial in-progress draft to the
training rows (mid-draft "retrain now"); those rows are used for the final fit
only, never for the walk-forward evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.historical_auction_state import read_csv_rows, replay_auction_states, write_feature_csv
from src.historical_price_baseline import attach_historical_ranks, evaluate_rank_price_baseline
from src.scenario_price_inference import save_model_artifact
from src.scenario_price_model import compare_with_baseline, evaluate_scenario_price_model
from src.scenario_price_model import train_quantile_models


DEFAULT_CANONICAL = PROJECT_ROOT / "data" / "ml_pipeline" / "canonical"
DEFAULT_MODELS = PROJECT_ROOT / "data" / "ml_pipeline" / "models"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    parser.add_argument(
        "--live-sales",
        type=Path,
        help="Optional canonical-shaped CSV of the current partial draft's sales.",
    )
    args = parser.parse_args()

    canonical: Path = args.canonical
    sales = read_csv_rows(canonical / "sales.csv")
    rankings = read_csv_rows(canonical / "rankings.csv")
    opening_states = read_csv_rows(canonical / "opening_team_states.csv")

    # 1. Replay historical auction states.
    replay = replay_auction_states(sales, opening_states)
    write_feature_csv(canonical / "auction_state_features.csv", replay.features)
    _write_json(
        canonical / "auction_state_issues.json",
        [issue.__dict__ for issue in replay.issues],
    )
    features = list(replay.features)

    # 2. Rank-neighbour baseline.
    baseline = evaluate_rank_price_baseline(features, rankings)
    write_feature_csv(canonical / "baseline_predictions.csv", baseline.predictions)
    _write_json(
        canonical / "baseline_metrics.json",
        {"metrics": list(baseline.metrics), "unmatched_sales": baseline.unmatched_sales},
    )

    # 3. Walk-forward scenario evaluation (history only -- never the live draft).
    evaluation = evaluate_scenario_price_model(features, rankings)
    write_feature_csv(
        canonical / "scenario_model_predictions.csv", evaluation.predictions
    )
    _write_json(
        canonical / "scenario_model_report.json",
        {
            "metrics": list(evaluation.metrics),
            "app_comparison": list(evaluation.app_comparison),
            "baseline_comparison": list(
                compare_with_baseline(evaluation.metrics, baseline.metrics)
            ),
            "unmatched_sales": evaluation.unmatched_sales,
        },
    )

    # 4. Final fit on all history (+ optional live partial draft).
    training_features = list(features)
    live_row_count = 0
    if args.live_sales and args.live_sales.is_file():
        live_sales = read_csv_rows(args.live_sales)
        live_replay = replay_auction_states(live_sales, opening_states)
        training_features.extend(live_replay.features)
        live_row_count = len(live_replay.features)

    joined, unmatched = attach_historical_ranks(training_features, rankings)
    models = train_quantile_models(joined)
    metadata = save_model_artifact(
        args.models / "scenario_price_model.joblib", models, joined
    )
    metadata["unmatched_sales_excluded"] = unmatched
    metadata["live_partial_draft_rows"] = live_row_count
    _write_json(args.models / "scenario_price_model.metadata.json", metadata)

    print(
        json.dumps(
            {
                "feature_rows": len(features),
                "training_rows": len(joined),
                "live_partial_draft_rows": live_row_count,
                "model_version": metadata["model_version"],
                "seasonal_mae": {
                    str(m["season"]): m["mean_absolute_error"]
                    for m in evaluation.metrics
                },
                "app_comparison": list(evaluation.app_comparison),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
