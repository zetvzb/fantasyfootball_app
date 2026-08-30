from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import joblib

from src.scenario_price_model import QUANTILES, predict_quantiles


ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ml_pipeline"
    / "models"
    / "scenario_price_model.joblib"
)


@dataclass(frozen=True)
class ScenarioPricePrediction:
    low: float
    predicted_price: float
    high: float
    model_version: str

    def to_dict(self) -> dict:
        return {
            "low": self.low,
            "predicted_price": self.predicted_price,
            "high": self.high,
            "model_version": self.model_version,
            "mode": "shadow",
        }


def dataset_fingerprint(rows: Sequence[Mapping[str, object]]) -> str:
    encoded = json.dumps(
        [dict(row) for row in rows], sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def save_model_artifact(
    path: Path,
    models: Mapping[str, object],
    training_rows: Sequence[Mapping[str, object]],
) -> dict:
    fingerprint = dataset_fingerprint(training_rows)
    metadata = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "model_version": "scenario-gbr-v2-{0}".format(fingerprint[:12]),
        "training_row_count": len(training_rows),
        "training_data_sha256": fingerprint,
        "quantiles": [alpha for _, alpha in QUANTILES],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"metadata": metadata, "models": dict(models)}, path)
    return metadata


class ScenarioPriceInferenceService:
    def __init__(self, artifact_path: Path = DEFAULT_ARTIFACT_PATH):
        self.artifact_path = Path(artifact_path)

    @staticmethod
    @lru_cache(maxsize=4)
    def _load(path: str, modified_ns: int) -> Mapping[str, object]:
        del modified_ns
        artifact = joblib.load(path)
        metadata = artifact.get("metadata", {})
        if metadata.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("Unsupported scenario model artifact schema.")
        if not all(label in artifact.get("models", {}) for label in ("low", "median", "high")):
            raise ValueError("Scenario model artifact is missing quantile models.")
        return artifact

    def predict(self, row: Mapping[str, object]) -> Optional[ScenarioPricePrediction]:
        if not self.artifact_path.is_file():
            return None
        artifact = self._load(
            str(self.artifact_path.resolve()), self.artifact_path.stat().st_mtime_ns
        )
        low, predicted, high = predict_quantiles(artifact["models"], row)
        return ScenarioPricePrediction(
            low=low,
            predicted_price=predicted,
            high=high,
            model_version=str(artifact["metadata"]["model_version"]),
        )


def _numeric(value: object, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def _field(value: object, *names: str) -> object:
    for name in names:
        candidate = value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
        if candidate not in (None, ""):
            return candidate
    return None


def build_live_feature_row(context: Any, state: Any) -> Optional[dict]:
    """Adapt the explicit live runtime state to the historical feature contract."""
    ranking = _field(state.fp, "half_ecr", "dynasty_ecr", "ecr", "rank", "overall_rank")
    if ranking in (None, ""):
        return None
    position = str(state.recommendation.position or "UNKNOWN")
    position_rank = _field(state.fp, "position_rank", "pos_rank") or ""
    sales = tuple(context.live_sales)
    position_sales = [sale for sale in sales if str(getattr(sale, "position", "")) == position]
    position_spend = sum(_numeric(getattr(sale, "price", 0)) for sale in position_sales)
    open_spots = max(1.0, _numeric(context.live_open_spots, 1.0))
    return {
        "historical_overall_rank": ranking,
        "historical_position_rank": position_rank,
        "position": position,
        "auction_stage": len(sales) / max(1.0, len(sales) + open_spots),
        "team_cash_before": _numeric(getattr(context.my_live_setup, "live_cash", 0)),
        "team_open_spots_before": max(
            1.0, _numeric(getattr(context.my_live_setup, "open_roster_spots", 1), 1.0)
        ),
        "team_legal_max_before": _numeric(state.recommendation.legal_max_bid, 1.0),
        "league_cash_before": max(1.0, _numeric(context.live_total_cash, 1.0)),
        "league_open_spots_before": open_spots,
        "league_discretionary_cash_before": _numeric(context.live_discretionary),
        "position_sales_before": len(position_sales),
        "position_average_price_before": (
            position_spend / len(position_sales) if position_sales else 0.0
        ),
        "position_spend_before": position_spend,
    }
