from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Mapping,
    Optional,
    Sequence,
)


LEAGUE_SETUP_VIEW = "🏠 League Setup"
PRE_DRAFT_VIEW = "🧭 Pre-Draft"
DRAFT_MODE_VIEW = "🚨 Draft Mode"
DRAFT_HISTORY_VIEW = "📚 Draft History"


@dataclass(frozen=True)
class ViewRuntimeRequirements:
    """Services and derived state that an active view is allowed to build."""

    setup: bool = False
    pre_draft_intelligence: bool = False
    live_draft: bool = False
    history: bool = False


VIEW_RUNTIME_REQUIREMENTS = {
    LEAGUE_SETUP_VIEW: ViewRuntimeRequirements(setup=True),
    PRE_DRAFT_VIEW: ViewRuntimeRequirements(
        setup=True,
        pre_draft_intelligence=True,
    ),
    DRAFT_MODE_VIEW: ViewRuntimeRequirements(
        setup=True,
        pre_draft_intelligence=True,
        live_draft=True,
    ),
    DRAFT_HISTORY_VIEW: ViewRuntimeRequirements(history=True),
}


def requirements_for_view(view_name: str) -> ViewRuntimeRequirements:
    """Return the explicit runtime contract for a registered view."""

    try:
        return VIEW_RUNTIME_REQUIREMENTS[view_name]
    except KeyError:
        raise ValueError("Unknown app view: {0}".format(view_name))


@dataclass
class AppRuntimeContext:
    """
    Explicit runtime contract between app.py and the Streamlit
    view layer.

    The view modules no longer reach into app.py through
    globals(). Every dependency required to render a view is
    passed through this object instead.

    Domain-heavy values are intentionally typed as Any in this
    transitional version to avoid introducing circular imports
    while the existing auction engine remains unchanged.
    """

    # -----------------------------------------------------
    # Active league identity / configuration
    # -----------------------------------------------------
    ACTIVE_DRAFT_ID: str
    ACTIVE_LEAGUE_PROFILE: Any
    ACTIVE_MANAGERS: Mapping[str, Any]
    ACTIVE_MY_MANAGER_ID: str
    selected_league: Any
    runtime_identity: Any
    strategy_profile: Optional[Any]
    strategy_profile_store: Optional[Any]

    # -----------------------------------------------------
    # Setup / pre-draft state
    # -----------------------------------------------------
    league_data: Any
    league_setup_data: Any
    league_setup_store: Any
    manual_setup_data: Optional[Any]
    manual_setup_loaded: bool
    persisted_setup: Mapping[str, Any]
    setup_locked: bool
    setup_rows: Sequence[Mapping[str, Any]]
    setup_source_summary: Mapping[str, int]
    workbook_loaded: bool
    keeper_recommendations: Sequence[Any]
    keeper_recommendation_warnings: Sequence[str]
    keeper_optimization_result: Optional[Any]
    keeper_trade_candidate_result: Optional[Any]
    college_promotion_recommendation_result: Optional[Any]
    pre_draft_readiness: Optional[Any]
    ranking_ensemble: Optional[Any]

    # -----------------------------------------------------
    # Persistent services / stores
    # -----------------------------------------------------
    context_store: Any
    draft_store: Any

    # -----------------------------------------------------
    # Static / derived player data
    # -----------------------------------------------------
    sleeper_players: Mapping[str, Any]
    fantasypros_data: Mapping[str, Any]
    fantasypros_index: Mapping[str, Any]
    projection_index: Mapping[str, Any]
    player_value_index: Mapping[str, Any]
    player_values: Sequence[Any]
    auction_value_index: Mapping[str, Any]
    market_value_index: Mapping[str, Any]
    historical_market_model: Any

    # -----------------------------------------------------
    # Context / depth-chart state
    # -----------------------------------------------------
    depth_chart_documents: Sequence[Any]
    depth_chart_error: Optional[str]
    depth_movement_error: Optional[str]
    depth_movement_result: Optional[Any]

    # -----------------------------------------------------
    # Auction pool / team state
    # -----------------------------------------------------
    pool_result: Any
    team_setups: Mapping[str, Any]
    available_players: Sequence[Any]
    live_sales: Sequence[Any]
    live_team_setups: Mapping[str, Any]
    team_need_profiles: Mapping[str, Any]
    my_live_setup: Optional[Any]
    my_need_profile: Optional[Any]
    starting_total_auction_cash: int
    live_total_cash: int
    live_open_spots: int
    live_discretionary: int
    room_spend_index: Optional[float]
    inflation_v2: Optional[Any]

    # -----------------------------------------------------
    # Recommendation / live-learning state
    # -----------------------------------------------------
    live_calibration: Any
    recommendations: Sequence[Any]
    recommendation_index: Mapping[str, Any]
    nomination_recommendations: Sequence[Any]
    nomination_index: Mapping[str, Any]
    threat_index: Mapping[str, Any]
    optimization_candidates: Sequence[Any]
    optimal_roster_plan: Optional[Any]

    # -----------------------------------------------------
    # Engine / integration callables used by the views
    # -----------------------------------------------------
    SleeperClient: Callable[..., Any]
    add_live_sale: Callable[..., Any]
    calculate_context_valuation_adjustment: Callable[..., Any]
    calculate_roster_aware_ceiling: Callable[..., Any]
    compare_buy_vs_pass: Callable[..., Any]
    get_targeted_player_context: Callable[..., Any]
    normalize_player_name: Callable[..., Any]
    render_league_setup_editor: Callable[..., Any]
    run_draft_simulation: Callable[..., Any]
    sync_next_sleeper_sale: Callable[..., Any]


def build_view_runtime(**values: Any) -> AppRuntimeContext:
    """Build a view context with inert defaults for unrequested services."""

    defaults = {
        "ACTIVE_DRAFT_ID": "",
        "ACTIVE_LEAGUE_PROFILE": None,
        "ACTIVE_MANAGERS": {},
        "ACTIVE_MY_MANAGER_ID": "",
        "selected_league": None,
        "runtime_identity": None,
        "strategy_profile": None,
        "strategy_profile_store": None,
        "league_data": None,
        "league_setup_data": None,
        "league_setup_store": None,
        "manual_setup_data": None,
        "manual_setup_loaded": False,
        "persisted_setup": {},
        "setup_locked": False,
        "setup_rows": [],
        "setup_source_summary": {},
        "workbook_loaded": False,
        "keeper_recommendations": [],
        "keeper_recommendation_warnings": [],
        "keeper_optimization_result": None,
        "keeper_trade_candidate_result": None,
        "college_promotion_recommendation_result": None,
        "pre_draft_readiness": None,
        "ranking_ensemble": None,
        "context_store": None,
        "draft_store": None,
        "sleeper_players": {},
        "fantasypros_data": {},
        "fantasypros_index": {},
        "projection_index": {},
        "player_value_index": {},
        "player_values": [],
        "auction_value_index": {},
        "market_value_index": {},
        "historical_market_model": None,
        "depth_chart_documents": [],
        "depth_chart_error": None,
        "depth_movement_error": None,
        "depth_movement_result": None,
        "pool_result": None,
        "team_setups": {},
        "available_players": [],
        "live_sales": [],
        "live_team_setups": {},
        "team_need_profiles": {},
        "my_live_setup": None,
        "my_need_profile": None,
        "starting_total_auction_cash": 0,
        "live_total_cash": 0,
        "live_open_spots": 0,
        "live_discretionary": 0,
        "room_spend_index": None,
        "inflation_v2": None,
        "live_calibration": None,
        "recommendations": [],
        "recommendation_index": {},
        "nomination_recommendations": [],
        "nomination_index": {},
        "threat_index": {},
        "optimization_candidates": [],
        "optimal_roster_plan": None,
        "SleeperClient": None,
        "add_live_sale": None,
        "calculate_context_valuation_adjustment": None,
        "calculate_roster_aware_ceiling": None,
        "compare_buy_vs_pass": None,
        "get_targeted_player_context": None,
        "normalize_player_name": None,
        "render_league_setup_editor": None,
        "run_draft_simulation": None,
        "sync_next_sleeper_sale": None,
    }
    defaults.update(values)
    return AppRuntimeContext(**defaults)
