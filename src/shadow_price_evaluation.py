from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name


@dataclass(frozen=True)
class ShadowPriceResult:
    sale_number: int
    player_name: str
    actual_price: int
    app_target_value: int
    shadow_low: float
    shadow_predicted_price: float
    shadow_high: float
    app_error: float
    shadow_error: float
    interval_hit: bool
    model_version: str
    blend_preview_target: Optional[int] = None
    blend_preview_error: Optional[float] = None


@dataclass(frozen=True)
class ShadowPriceEvaluation:
    results: Tuple[ShadowPriceResult, ...]
    app_mean_absolute_error: Optional[float]
    shadow_mean_absolute_error: Optional[float]
    app_bias: Optional[float]
    shadow_bias: Optional[float]
    shadow_median_absolute_error: Optional[float]
    interval_coverage: Optional[float]
    blend_preview_mean_absolute_error: Optional[float] = None
    blend_preview_bias: Optional[float] = None


def _number(value: object) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def evaluate_shadow_prices(
    sales: Sequence[object],
    snapshots: Sequence[object],
) -> ShadowPriceEvaluation:
    """Compare latest eligible decision-time shadow estimates to final sales."""
    snapshots_by_player = {}
    for snapshot in snapshots:
        shadow = getattr(snapshot, "context_state", {}).get("scenario_price_shadow")
        if not isinstance(shadow, Mapping):
            continue
        snapshots_by_player.setdefault(
            normalize_player_name(snapshot.player_name), []
        ).append(snapshot)

    results = []
    for sale in sales:
        eligible = []
        for snapshot in snapshots_by_player.get(
            normalize_player_name(sale.player_name), []
        ):
            sale_count = _number(getattr(snapshot, "roster_state", {}).get("sale_count"))
            if sale_count is None or sale_count < int(sale.sale_number):
                eligible.append(snapshot)
        if not eligible:
            continue
        snapshot = eligible[-1]
        shadow = snapshot.context_state["scenario_price_shadow"]
        predicted = _number(shadow.get("predicted_price"))
        low = _number(shadow.get("low"))
        high = _number(shadow.get("high"))
        if predicted is None or low is None or high is None:
            continue
        actual = int(sale.price)
        unblended_target = _number(shadow.get("unblended_target_value"))
        app_target = (
            int(round(unblended_target))
            if unblended_target is not None else int(snapshot.target_value)
        )
        blend_target_value = _number(shadow.get("blend_target_value"))
        blend_target = (
            int(round(blend_target_value)) if blend_target_value is not None else None
        )
        results.append(
            ShadowPriceResult(
                sale_number=int(sale.sale_number),
                player_name=str(sale.player_name),
                actual_price=actual,
                app_target_value=app_target,
                shadow_low=low,
                shadow_predicted_price=predicted,
                shadow_high=high,
                app_error=round(app_target - actual, 2),
                shadow_error=round(predicted - actual, 2),
                interval_hit=low <= actual <= high,
                model_version=str(shadow.get("model_version") or "unknown"),
                blend_preview_target=blend_target,
                blend_preview_error=(
                    round(blend_target - actual, 2)
                    if blend_target is not None else None
                ),
            )
        )

    if not results:
        return ShadowPriceEvaluation(
            tuple(), None, None, None, None, None, None, None, None
        )
    app_errors = [item.app_error for item in results]
    shadow_errors = [item.shadow_error for item in results]
    count = len(results)
    blend_errors = [
        item.blend_preview_error
        for item in results
        if item.blend_preview_error is not None
    ]
    return ShadowPriceEvaluation(
        results=tuple(results),
        app_mean_absolute_error=round(sum(abs(value) for value in app_errors) / count, 2),
        shadow_mean_absolute_error=round(
            sum(abs(value) for value in shadow_errors) / count, 2
        ),
        app_bias=round(sum(app_errors) / count, 2),
        shadow_bias=round(sum(shadow_errors) / count, 2),
        shadow_median_absolute_error=round(
            median(abs(value) for value in shadow_errors), 2
        ),
        interval_coverage=round(sum(item.interval_hit for item in results) / count, 3),
        blend_preview_mean_absolute_error=(
            round(sum(abs(value) for value in blend_errors) / len(blend_errors), 2)
            if blend_errors else None
        ),
        blend_preview_bias=(
            round(sum(blend_errors) / len(blend_errors), 2)
            if blend_errors else None
        ),
    )
