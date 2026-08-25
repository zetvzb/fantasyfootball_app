from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Mapping,
    Optional,
    Sequence,
)


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
