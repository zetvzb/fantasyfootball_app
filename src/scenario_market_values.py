"""Apply the ML+rankings fair-value blend to the market-value list.

This runs inside ``build_simulation_state`` *before* live-market calibration, so
the blend is the prior that the live-learning layer then corrects from in-draft
sales.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.auction_pool import normalize_player_name
from src.scenario_fair_value import blend_fair_value
from src.scenario_price_inference import ScenarioPriceInferenceService


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def _as_list(team_setups: Any) -> list:
    """``build_live_team_setups`` returns a ``{manager_id: setup}`` dict; callers
    sometimes pass the raw dict."""
    if hasattr(team_setups, "values"):
        return list(team_setups.values())
    return list(team_setups)


def contender_state(team_setups: Sequence[Any]) -> Dict[str, float]:
    """A representative cash-rich bidder: the team at the ~75th percentile of
    cash-per-open-spot among teams that can still buy. The ML target is the
    *winner's* pre-buy state, and winners skew rich, so this beats "my team"
    or the league average as an inference-time proxy."""
    live = [
        setup
        for setup in _as_list(team_setups)
        if _num(getattr(setup, "open_roster_spots", 0)) >= 1
    ]
    if not live:
        return {"cash": 200.0, "spots": 1.0, "legal_max": 200.0}
    ranked = sorted(
        live,
        key=lambda s: _num(getattr(s, "live_cash", getattr(s, "auction_cash", 0)))
        / max(1.0, _num(getattr(s, "open_roster_spots", 1))),
    )
    index = min(len(ranked) - 1, int(round(0.75 * (len(ranked) - 1))))
    pick = ranked[index]
    return {
        "cash": _num(getattr(pick, "live_cash", getattr(pick, "auction_cash", 0))),
        "spots": max(1.0, _num(getattr(pick, "open_roster_spots", 1))),
        "legal_max": _num(getattr(pick, "max_bid", 0)),
    }


def build_scenario_feature_rows(
    available_players: Sequence[Any],
    team_setups: Any,
    sales: Sequence[Any],
    fantasypros_index: Mapping[str, Any],
    *,
    proxy: Optional[Mapping[str, float]] = None,
) -> Dict[str, dict]:
    """Per-available-player feature rows matching the training contract in
    ``src.scenario_price_model._feature_row``."""
    teams = _as_list(team_setups)
    proxy = proxy or contender_state(teams)
    sales = tuple(sales)
    expected_total = sum(
        max(0.0, _num(getattr(s, "starting_open_roster_spots", 0))) for s in teams
    ) or float(len(sales) + len(available_players))
    stage = len(sales) / expected_total if expected_total else 0.0

    league_cash = sum(
        _num(getattr(s, "live_cash", getattr(s, "auction_cash", 0))) for s in teams
    )
    league_spots = sum(
        _num(getattr(s, "open_roster_spots", 0)) for s in teams
    )
    league_discretionary = sum(
        _num(getattr(s, "discretionary_cash", 0)) for s in teams
    )

    position_sales: Dict[str, int] = {}
    position_spend: Dict[str, float] = {}
    for sale in sales:
        pos = str(getattr(sale, "position", "") or "").upper()
        position_sales[pos] = position_sales.get(pos, 0) + 1
        position_spend[pos] = position_spend.get(pos, 0.0) + _num(getattr(sale, "price", 0))

    rows: Dict[str, dict] = {}
    for player in available_players:
        key = normalize_player_name(player.player_name)
        fp = fantasypros_index.get(key)
        rank = getattr(fp, "half_ecr", None) if fp else None
        if rank in (None, ""):
            continue
        position = str(getattr(player, "position", "") or "UNKNOWN").upper()
        sold = position_sales.get(position, 0)
        spent = position_spend.get(position, 0.0)
        rows[key] = {
            "historical_overall_rank": rank,
            "historical_position_rank": (
                getattr(fp, "half_position_rank", None) if fp else None
            ),
            "position": position,
            "auction_stage": stage,
            "team_cash_before": proxy["cash"],
            "team_open_spots_before": proxy["spots"],
            "team_legal_max_before": proxy["legal_max"] or proxy["cash"],
            "league_cash_before": max(1.0, league_cash),
            "league_open_spots_before": max(1.0, league_spots),
            "league_discretionary_cash_before": league_discretionary,
            "position_sales_before": sold,
            "position_spend_before": spent,
            "position_average_price_before": (spent / sold) if sold else 0.0,
        }
    return rows


def apply_scenario_fair_values(
    market_values: Sequence[Any],
    feature_rows: Mapping[str, dict],
    *,
    ml_weight: float,
    service: Optional[ScenarioPriceInferenceService] = None,
) -> Tuple[List[Any], Dict[str, dict]]:
    """Return market values with ``expected_market_value`` replaced by the
    ML+rankings blend, plus a per-player index of the raw prediction for the
    shadow display. A missing model is a silent no-op."""
    service = service or ScenarioPriceInferenceService()
    if not feature_rows or not service.artifact_path.is_file():
        return list(market_values), {}

    blended: List[Any] = []
    index: Dict[str, dict] = {}
    for market in market_values:
        key = normalize_player_name(market.player_name)
        row = feature_rows.get(key)
        prediction = service.predict(row) if row is not None else None
        if prediction is None:
            blended.append(market)
            continue
        rankings_value = _num(market.expected_market_value, 1.0)
        fair = blend_fair_value(
            prediction.predicted_price, rankings_value, ml_weight=ml_weight
        )
        blended.append(replace(market, expected_market_value=round(fair, 2)))
        index[key] = {
            "ml_low": prediction.low,
            "ml_predicted_price": prediction.predicted_price,
            "ml_high": prediction.high,
            "rankings_value": round(rankings_value, 2),
            "blended_value": round(fair, 2),
            "ml_weight": round(float(ml_weight), 3),
            "model_version": prediction.model_version,
        }
    return blended, index
