"""Walk-forward tuning helpers for the scenario-price model.

Two sweeps, both chronological (every season predicted from earlier seasons only):

  --hyperparams : GradientBoosting grid, ranked by mean seasonal MAE.
  --blend       : ML-vs-rankings blend weight, ranked by MAE against the
                  actual winning price (rank-neighbour baseline as the
                  rankings proxy).

Run from canonical CSVs:
  python scripts/tune_scenario_price_model.py --blend
  python scripts/tune_scenario_price_model.py --hyperparams
"""

from __future__ import annotations

import argparse
import csv
import itertools
import statistics
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.historical_auction_state import read_csv_rows
from src.historical_price_baseline import attach_historical_ranks, evaluate_rank_price_baseline
from src.scenario_price_model import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    _frame,
    _number,
)

CANONICAL = PROJECT_ROOT / "data" / "ml_pipeline" / "canonical"


def _season(row) -> int:
    return int(float(row.get("season") or 0))


def _load():
    features = read_csv_rows(CANONICAL / "auction_state_features.csv")
    rankings = read_csv_rows(CANONICAL / "rankings.csv")
    joined, _ = attach_historical_ranks(features, rankings)
    return joined, rankings, sorted({_season(r) for r in joined})


def _mae(pred, actual) -> float:
    return float(np.mean(np.abs(np.asarray(pred) - np.asarray(actual))))


def sweep_hyperparams() -> None:
    joined, _rankings, seasons = _load()
    grid = itertools.product([120, 180, 300], [0.03, 0.05, 0.08], [2, 3], [6, 10, 15])
    results = []
    for ne, lr, md, msl in grid:
        maes = []
        for test in seasons:
            train = [r for r in joined if _season(r) < test]
            hold = [r for r in joined if _season(r) == test]
            if len(train) < 30 or not hold:
                continue
            pre = ColumnTransformer(
                [
                    ("c", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(CATEGORICAL_FEATURES)),
                    ("n", SimpleImputer(strategy="median"), list(NUMERIC_FEATURES)),
                ]
            )
            model = Pipeline(
                [
                    ("p", pre),
                    ("r", GradientBoostingRegressor(loss="quantile", alpha=0.5, n_estimators=ne, learning_rate=lr, max_depth=md, min_samples_leaf=msl, random_state=42)),
                ]
            )
            model.fit(_frame(train), np.asarray([_number(r.get("winning_price")) for r in train]))
            pred = model.predict(_frame(hold))
            legal = np.asarray([max(1.0, _number(r.get("team_legal_max_before"))) for r in hold])
            pred = np.clip(pred, 1.0, legal)
            maes.append(_mae(pred, [_number(r.get("winning_price")) for r in hold]))
        results.append((statistics.mean(maes), ne, lr, md, msl, [round(m, 2) for m in maes]))
    results.sort()
    print("mean_MAE  n_estimators  lr    max_depth  min_leaf  per_season")
    for mean_mae, ne, lr, md, msl, per in results[:12]:
        print(f"{mean_mae:7.3f}  {ne:>11}  {lr:<5} {md:>8}  {msl:>7}  {per}")


def sweep_blend() -> None:
    joined, rankings, _seasons = _load()
    baseline = {
        (int(float(r["season"])), r["player_name"]): float(r["baseline_predicted_price"])
        for r in evaluate_rank_price_baseline(joined, rankings).predictions
    }
    from src.scenario_price_model import evaluate_scenario_price_model

    predictions = evaluate_scenario_price_model(joined, rankings).predictions
    rows = [p for p in predictions if (int(float(p["season"])), p["player_name"]) in baseline]
    actual = [_number(p["winning_price"]) for p in rows]
    ml = [_number(p["scenario_predicted_price"]) for p in rows]
    rank = [baseline[(int(float(p["season"])), p["player_name"])] for p in rows]
    print(f"n={len(rows)} ranked sales")
    print("ml_weight  MAE")
    for weight in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0):
        blend = [weight * m + (1.0 - weight) * b for m, b in zip(ml, rank)]
        print(f"{weight:>9.1f}  {_mae(blend, actual):.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyperparams", action="store_true")
    parser.add_argument("--blend", action="store_true")
    args = parser.parse_args()
    if not (args.hyperparams or args.blend):
        parser.error("pass --hyperparams and/or --blend")
    if args.hyperparams:
        sweep_hyperparams()
    if args.blend:
        sweep_blend()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
