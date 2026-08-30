from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.historical_auction_state import read_csv_rows, write_feature_csv
from src.scenario_price_model import compare_with_baseline, evaluate_scenario_price_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate scenario-aware auction model.")
    parser.add_argument("auction_features", type=Path)
    parser.add_argument("rankings", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--baseline-report", type=Path)
    args = parser.parse_args()
    result = evaluate_scenario_price_model(
        read_csv_rows(args.auction_features),
        read_csv_rows(args.rankings),
    )
    write_feature_csv(args.predictions, result.predictions)
    baseline_comparison = ()
    if args.baseline_report:
        baseline_payload = json.loads(args.baseline_report.read_text(encoding="utf-8"))
        baseline_comparison = compare_with_baseline(
            result.metrics,
            baseline_payload.get("metrics", ()),
        )
    args.report.write_text(
        json.dumps(
            {
                "metrics": list(result.metrics),
                "app_comparison": list(result.app_comparison),
                "baseline_comparison": list(baseline_comparison),
                "unmatched_sales": result.unmatched_sales,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(args.report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
