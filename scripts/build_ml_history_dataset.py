from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ml_history_dataset import build_canonical_history_dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build formula-free historical auction modeling tables."
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    report = build_canonical_history_dataset(args.workbook, args.output_directory)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ready_for_price_training else 1


if __name__ == "__main__":
    raise SystemExit(main())
