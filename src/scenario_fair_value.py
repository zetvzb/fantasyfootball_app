"""Blend the ML scenario price with the rankings-derived value.

Fair value for a player is a weighted blend of two of the three inputs the
recommendation engine reasons about:

  1. ML scenario price  -- how this league historically pays given rank,
     position, roster/cash state and auction stage.
  2. Rankings value     -- the FantasyPros / Sleeper-ECR derived baseline.

The third input, deterministic evidence (need, threat, scarcity, run-hot,
legal-max ceiling, live-market calibration) is applied *on top* of this blend by
the existing engine and is intentionally not touched here.
"""

from __future__ import annotations

import os
from typing import Optional


DEFAULT_ML_WEIGHT = 0.60
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def scenario_pricing_enabled() -> bool:
    """Master kill-switch. Defaults ON; ``SCENARIO_ML_PRICING=0`` disables it."""
    raw = os.environ.get("SCENARIO_ML_PRICING", "").strip().lower()
    if raw in _FALSE:
        return False
    return True


def scenario_ml_weight() -> float:
    """ML share of the fair-value blend, overridable via ``SCENARIO_ML_WEIGHT``."""
    raw = os.environ.get("SCENARIO_ML_WEIGHT", "").strip()
    if not raw:
        return DEFAULT_ML_WEIGHT
    try:
        return _clamp01(float(raw))
    except ValueError:
        return DEFAULT_ML_WEIGHT


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def blend_fair_value(
    ml_price: Optional[float],
    rankings_value: float,
    *,
    ml_weight: float = DEFAULT_ML_WEIGHT,
) -> float:
    """Return ``ml_weight*ml_price + (1-ml_weight)*rankings_value``.

    Falls back to ``rankings_value`` untouched whenever there is no ML price
    (no ranking match, model missing, or pricing disabled).
    """
    rankings_value = float(rankings_value)
    if ml_price is None:
        return rankings_value
    weight = _clamp01(float(ml_weight))
    return weight * float(ml_price) + (1.0 - weight) * rankings_value
