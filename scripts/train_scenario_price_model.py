from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.historical_price_baseline import attach_historical_ranks
from src.scenario_price_inference import save_model_artifact
from src.scenario_price_model import train_quantile_models


def _rows(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    args = parser.parse_args()
    joined, unmatched = attach_historical_ranks(_rows(args.features), _rows(args.rankings))
    models = train_quantile_models(joined)
    metadata = save_model_artifact(args.output, models, joined)
    metadata["unmatched_sales_excluded"] = unmatched
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
