from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.historical_auction_state import read_csv_rows, write_feature_csv
from src.historical_price_baseline import evaluate_rank_price_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate historical rank-price baseline.")
    parser.add_argument("sales", type=Path)
    parser.add_argument("rankings", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("metrics", type=Path)
    args = parser.parse_args()
    result = evaluate_rank_price_baseline(
        read_csv_rows(args.sales),
        read_csv_rows(args.rankings),
    )
    write_feature_csv(args.predictions, result.predictions)
    args.metrics.write_text(
        json.dumps(
            {"metrics": list(result.metrics), "unmatched_sales": result.unmatched_sales},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(args.metrics.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
