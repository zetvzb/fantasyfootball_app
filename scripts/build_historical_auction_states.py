from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.historical_auction_state import (
    read_csv_rows,
    replay_auction_states,
    write_feature_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay historical auction state.")
    parser.add_argument("sales", type=Path)
    parser.add_argument("opening_states", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--issues", type=Path)
    args = parser.parse_args()
    result = replay_auction_states(
        read_csv_rows(args.sales),
        read_csv_rows(args.opening_states),
    )
    write_feature_csv(args.output, result.features)
    if args.issues:
        args.issues.write_text(
            json.dumps([asdict(issue) for issue in result.issues], indent=2),
            encoding="utf-8",
        )
    print(json.dumps({"feature_rows": len(result.features), "valid": result.valid}))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
