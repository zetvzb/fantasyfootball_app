from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import (
    SEASON,
    SLEEPER_DRAFT_ID,
    SLEEPER_LEAGUE_ID,
)
from src.ui_theme import (
    inject_global_styles,
    render_product_header,
    render_sidebar_brand,
)
from src.views.how_it_works import render_how_it_works_view

from src.league_config import (
    MANAGERS as LEGACY_MANAGERS,
    MY_MANAGER_ID as LEGACY_MY_MANAGER_ID,
    MINIMUM_AUCTION_BID,
)

from src.league_setup_data import (
    LeagueSetupData,
    LeagueSetupStore,
)
from src.pre_draft_setup_ui import (
    render_league_setup_editor,
)
from src.views import (
    render_active_view,
)
from src.app_runtime import (
    AppRuntimeContext,
    DEPTH_CHARTS_VIEW,
    MANAGER_INTELLIGENCE_VIEW,
    PLAYER_CONTEXT_VIEW,
    SNAKE_DRAFT_VIEW,
    build_view_runtime,
    requirements_for_view,
)
from src.snake_draft import build_snake_draft_state
from src.league_registry import LeagueRegistry, delete_league_data
from src.league_management_ui import (
    render_add_manual_league,
    render_add_sleeper_league,
    render_portfolio_demo_loader,
)
from src.league_profile import (
    infer_league_profile_from_sleeper,
)
from src.manual_league import manual_runtime_ids, permitted_setup_overrides
from src.sleeper_client import SleeperClient
from src.draft_setup import build_team_draft_setup_from_setup_data
from src.workbook_enrichment import enrich_setup_from_optional_workbook
from src.pre_draft_readiness import build_pre_draft_readiness
from src.ranking_ensemble import build_repository_ranking_ensemble
from src.runtime_identity import (
    private_state_key,
    resolve_runtime_identity,
)
from src.strategy_profile import (
    StrategyProfile,
    StrategyProfileStore,
)
from src.my_guys import MyGuysPreferences, MyGuysStore
from src.planning_preferences import PlanningPreferencesStore
from src.private_state import PrivateStateAccess
from src.deployment import load_deployment_settings
from src.production_persistence import (
    DurableStateArchive,
    ProductionPersistenceConflict,
    ProductionPersistenceError,
)
from src.auth_identity import (
    extract_authenticated_identity,
    load_authenticated_manager_mappings,
)
from src.portfolio_demo import DEMO_LEAGUE_KEY, build_demo_player_values
from src.keeper_recommendation import (
    build_keeper_recommendations,
)

from src.auction_pool import (
    build_auction_pool,
    normalize_player_name,
)

from src.fantasypros_client import FantasyProsClient

from src.fantasypros_intelligence import (
    build_intelligence_index,
    normalize_fantasypros_intelligence,
)
from src.fantasypros_health import validate_fantasypros_data
from src.fantasypros_bundle import load_fantasypros_bundle
from src.data_freshness import assess_data_freshness
from src.refresh_intelligence import (
    IntelligenceSource,
    build_refresh_on_open_plan,
    build_refresh_plan,
    execute_refresh_plan,
)

from src.projections import (
    build_projection_index,
    normalize_fantasypros_projections,
)
from src.scoring_projection_service import build_league_scoring_projection
from src.expanded_context_ingestion import ingest_structured_context
from src.league_inflation import calculate_live_room_inflation
from src.manager_tendencies import (
    build_manager_tendency_model,
    build_tendency_observations_from_market,
)
from src.opponent_targets import build_opponent_target_profiles
from src.run_hot import build_available_tier_counts, detect_run_hot

from src.auction_values import calculate_auction_values

from src.historical_market import (
    build_historical_market_model,
    calculate_historical_market_values,
)

from src.bidder_threat import (
    build_team_need_profiles,
    calculate_bidder_threats,
    build_threat_index,
)

from src.recommendation import (
    calculate_bid_recommendations,
    build_recommendation_index,
)

from src.live_draft import (
    add_live_sale,
    build_live_team_setups,
    calculate_room_spend_index,
    filter_sold_players,
)

from src.draft_store import DraftStore
from src.draft_recovery import recover_draft_state
from src.optional_feed import load_optional_feed
from src.sleeper_sync import sync_next_sleeper_sale

from src.live_learning import (
    build_live_market_calibration,
    apply_live_market_calibration,
    apply_live_manager_threat_adjustments,
)

from src.nomination_strategy import (
    calculate_nomination_recommendations,
    build_nomination_index,
)

from src.roster_optimizer import (
    build_optimization_candidates,
    optimize_remaining_roster,
    calculate_roster_aware_ceiling,
    compare_buy_vs_pass,
)

from src.draft_simulator import run_draft_simulation

from src.context_store import ContextStore

from src.fantasypros_context import (
    normalize_fantasypros_news,
    normalize_fantasypros_injuries,
)

from src.context_interpreter import (
    interpret_player_context,
)

from src.context_valuation import (
    calculate_context_valuation_adjustment,
)

from src.depth_chart_context import (
    build_depth_chart_documents,
)

from src.depth_chart_history import (
    DepthChartMovementTracker,
)


# =========================================================
# STREAMLIT CONFIG
# =========================================================

st.set_page_config(
    page_title="Fantasy Draft Copilot",
    page_icon="🏈",
    layout="wide",
)

inject_global_styles()
render_sidebar_brand()


# =========================================================
# BUILD / GLOBAL SIDEBAR CONTROLS
# =========================================================

APP_BUILD = "17.0-bid-components"

st.sidebar.caption(
    f"Build: {APP_BUILD}"
)


if (
    "show_add_league_form"
    not in st.session_state
):

    st.session_state[
        "show_add_league_form"
    ] = False


if st.sidebar.button(
    "➕ Add League",
    width="stretch",
    key="global_add_league_button",
):

    st.session_state[
        "show_add_league_form"
    ] = not (
        st.session_state[
            "show_add_league_form"
        ]
    )


# =========================================================
# CONSTANTS
# =========================================================

APP_ROOT = Path(__file__).resolve().parent

DEPLOYMENT_SETTINGS = load_deployment_settings(APP_ROOT)
DATA_ROOT = DEPLOYMENT_SETTINGS.data_root
DEMO_MODE = str(os.getenv("FANTASYFOOTBALL_DEMO_MODE", "")).strip() == "1"
PRODUCTION_PERSISTENCE = DurableStateArchive.from_environment(DATA_ROOT)
try:
    PRODUCTION_PERSISTENCE.restore()
except ProductionPersistenceError as error:
    st.error("Durable application state could not be restored: {0}".format(error))
    st.stop()
def _checkpoint_durable_state() -> None:
    """Mirror the local write to durable storage; never let a sync failure
    crash the app. The local write (SQLite/JSON) that triggered this has
    already succeeded by the time this runs -- a conflict here just means
    another session/rerun wrote more recently, which the next restore()
    will pick up. Losing that sync for one cycle is far better than a hard
    crash on every concurrent session (e.g. multiple portfolio-demo
    visitors, or two tabs open to the same league).
    """

    try:
        PRODUCTION_PERSISTENCE.checkpoint()
    except ProductionPersistenceConflict:
        st.toast(
            "State sync conflicted with another session -- your change is "
            "saved locally; it will resync on the next reload.",
            icon="⚠️",
        )
    except ProductionPersistenceError as error:
        st.toast(
            "State sync failed (change is still saved locally): {0}".format(
                error
            ),
            icon="⚠️",
        )


STATE_CHECKPOINT = (
    _checkpoint_durable_state
    if PRODUCTION_PERSISTENCE.configured
    else None
)

DB_PATH = str(DATA_ROOT / "draft_state.db")
CONTEXT_DB_PATH = str(DATA_ROOT / "player_context.db")

LEAGUE_REGISTRY_PATH = (
    DATA_ROOT
    / "leagues"
)

league_registry = LeagueRegistry(
    root=LEAGUE_REGISTRY_PATH,
    checkpoint_callback=STATE_CHECKPOINT,
)


LEAGUE_SETUP_PATH = (
    DATA_ROOT
    / "league_setup"
)

league_setup_store = LeagueSetupStore(
    root=LEAGUE_SETUP_PATH,
    checkpoint_callback=STATE_CHECKPOINT,
)


STRATEGY_PROFILE_PATH = (
    DATA_ROOT
    / "strategy_profiles"
)
MY_GUYS_PATH = DATA_ROOT / "my_guys"
PLANNING_PREFERENCES_PATH = DATA_ROOT / "planning_preferences"

try:
    AUTHENTICATED_IDENTITY = extract_authenticated_identity(
        dict(st.context.headers)
    )
    AUTHENTICATED_MANAGER_MAPPINGS = load_authenticated_manager_mappings()
except ValueError as error:
    st.error("Authenticated identity configuration is invalid: {0}".format(error))
    st.stop()


# =========================================================
# PERSISTENT CONTEXT STORES
# =========================================================
#
# DraftStore is created after league selection so each league
# can have an isolated auction ledger.
#
context_store = None
depth_chart_tracker = None


# =========================================================
# DATA LOADERS
# =========================================================

def utc_refresh_timestamp():
    return datetime.now(timezone.utc).isoformat()

@st.cache_data(ttl=300)
def load_sleeper_data(
    league_id,
    draft_id,
):

    client = SleeperClient()

    return {
        "league": client.get_league(
            str(
                league_id
            )
        ),
        "users": client.get_league_users(
            str(
                league_id
            )
        ),
        "rosters": client.get_league_rosters(
            str(
                league_id
            )
        ),
        "draft": client.get_draft(
            str(
                draft_id
            )
        ),
        "players": client.get_players(),
        "_fetched_at": utc_refresh_timestamp(),
    }


@st.cache_data(ttl=86400)
def load_sleeper_player_universe():
    """Load global NFL metadata without requiring a Sleeper league."""

    return {
        "players": SleeperClient().get_players(),
        "_fetched_at": utc_refresh_timestamp(),
    }


@st.cache_data
def load_league_workbook(
    workbook_path,
):

    from src.league_data import LeagueDataLoader

    loader = LeagueDataLoader(
        workbook_path
    )

    return loader.load()


def resolve_league_workbook_path(
    league_profile,
    use_legacy_default=False,
):

    configured_path = (
        league_profile
        .metadata
        .get(
            "workbook_path"
        )
    )


    if configured_path:

        path = Path(
            str(
                configured_path
            )
        )

        if not path.is_absolute():

            path = (
                APP_ROOT
                / path
            )

        return path


    if use_legacy_default:

        return (
            APP_ROOT
            / "data"
            / "league.xlsx"
        )


    return None


@st.cache_data(ttl=3600)
def load_fantasypros_data(
    season,
):
    bundle = load_fantasypros_bundle(
        {
            "rankings": lambda: FantasyProsClient().get_rankings(
                season=season, week=0
            ),
            "players": lambda: FantasyProsClient().get_players_with_ecr(),
            "projections": lambda: FantasyProsClient().get_preseason_projections(
                season=season
            ),
        }
    )
    rankings_response = bundle.data.get("rankings", {})
    players_response = bundle.data.get("players", {})
    projection_response = bundle.data.get("projections", {})

    intelligence = (
        normalize_fantasypros_intelligence(
            rankings_response=(
                rankings_response
            ),
            players_response=(
                players_response
            ),
        )
    )

    normalized_projections = normalize_fantasypros_projections(
        response=projection_response,
        scoring_settings={},
    )
    health = None
    if not bundle.errors:
        health = validate_fantasypros_data(
            rankings_response=rankings_response,
            players_response=players_response,
            projection_response=projection_response,
            intelligence=intelligence,
            projections=normalized_projections,
        )

    return {
        "rankings_response": rankings_response,
        "players_response": players_response,
        "projection_response": projection_response,
        "intelligence": intelligence,
        "health": health,
        "_errors": dict(bundle.errors),
        "_fetched_at": utc_refresh_timestamp(),
    }


@st.cache_data(ttl=900)
def load_fantasypros_context_data(
    season,
):

    client = FantasyProsClient()

    news_response = (
        client.get_news(
            limit=100
        )
    )

    injury_response = (
        client.get_injuries(
            season=season
        )
    )

    return {
        "news": news_response,
        "injuries": injury_response,
        "_fetched_at": utc_refresh_timestamp(),
    }


@st.cache_data(ttl=900)
def load_player_context_data(
    fantasypros_id,
    season,
):

    client = FantasyProsClient()

    fantasypros_id = int(
        fantasypros_id
    )

    news_response = (
        client.get_news(
            limit=25,
            fpid=(
                fantasypros_id
            ),
        )
    )

    injury_response = (
        client.get_injuries(
            season=season,
            player_ids=[
                fantasypros_id
            ],
        )
    )

    return {
        "news": news_response,
        "injuries": injury_response,
    }


# =========================================================
# TARGETED PLAYER CONTEXT
# =========================================================

def get_targeted_player_context(
    fp,
    auction_player_name,
    fantasypros_data,
    context_store,
):

    context_lookup_name = (
        auction_player_name
    )

    targeted_news_count = None
    targeted_injury_count = None
    targeted_context_error = None


    if (
        fp
        and
        fp.fantasypros_id
    ):

        try:

            targeted_context_data = (
                load_player_context_data(
                    fp.fantasypros_id,
                    ACTIVE_SEASON,
                )
            )


            targeted_news_response = (
                targeted_context_data[
                    "news"
                ]
            )


            targeted_injury_response = (
                targeted_context_data[
                    "injuries"
                ]
            )


            targeted_news_count = (
                targeted_news_response.get(
                    "count",
                    0,
                )
            )


            targeted_injury_count = (
                targeted_injury_response.get(
                    "count",
                    0,
                )
            )


            targeted_news_documents = (
                normalize_fantasypros_news(
                    response=(
                        targeted_news_response
                    ),
                    intelligence=(
                        fantasypros_data[
                            "intelligence"
                        ]
                    ),
                )
            )


            targeted_injury_documents = (
                normalize_fantasypros_injuries(
                    response=(
                        targeted_injury_response
                    ),
                    intelligence=(
                        fantasypros_data[
                            "intelligence"
                        ]
                    ),
                )
            )


            targeted_documents = (
                targeted_news_documents
                +
                targeted_injury_documents
            )


            if targeted_documents:

                context_store.add_documents(
                    targeted_documents
                )


            context_lookup_name = (
                fp.player_name
            )


        except Exception as error:

            targeted_context_error = str(
                error
            )


    player_context_documents = (
        context_store.get_player_documents(
            player_name=(
                context_lookup_name
            ),
            limit=50,
        )
    )


    player_context_summary = (
        interpret_player_context(
            player_name=(
                context_lookup_name
            ),
            documents=(
                player_context_documents
            ),
        )
    )


    return (
        player_context_summary,
        player_context_documents,
        context_lookup_name,
        targeted_news_count,
        targeted_injury_count,
        targeted_context_error,
    )


# =========================================================
# LOAD SOURCE DATA
# =========================================================

current_league_key = (
    DEMO_LEAGUE_KEY
    if DEMO_MODE and league_registry.exists(DEMO_LEAGUE_KEY)
    else str(SLEEPER_LEAGUE_ID)
)
current_league_profile = None
bootstrap_sleeper_data = None

try:

    if league_registry.exists(
        current_league_key
    ):

        current_league_profile = (
            league_registry.load(
                current_league_key
            )
        )

except Exception:

    current_league_profile = None


if current_league_profile is None:

    try:

        bootstrap_sleeper_data = (
            load_sleeper_data(
                SLEEPER_LEAGUE_ID,
                SLEEPER_DRAFT_ID,
            )
        )

    except Exception as error:

        st.error(
            f"Sleeper failed: {error}"
        )

        st.stop()


# =========================================================
# BOOTSTRAP CURRENT LEAGUE PROFILE
# =========================================================
#
# Build the currently configured league profile from Sleeper
# when it does not exist or cannot be loaded. The registry is
# anchored to this app.py directory so Streamlit's launch
# directory cannot change where profiles are stored.
#
if current_league_profile is None:

    current_league_profile = (
        infer_league_profile_from_sleeper(
            league=(
                bootstrap_sleeper_data[
                    "league"
                ]
            ),
            draft=(
                bootstrap_sleeper_data[
                    "draft"
                ]
            ),
            users=(
                bootstrap_sleeper_data[
                    "users"
                ]
            ),
            rosters=(
                bootstrap_sleeper_data[
                    "rosters"
                ]
            ),
            season=SEASON,
            overrides={
                "league_key": (
                    current_league_key
                ),
                "auction": {
                    "minimum_bid": (
                        MINIMUM_AUCTION_BID
                    ),
                },
                "keepers": {
                    "enabled": True,
                    "max_keepers": 6,
                    "escalation": 11,
                    "midseason_pickup_cost": 10,
                    "future_horizon_years": 3,
                    "lock_hours_before_draft": 48,
                },
                "model": {
                    "current_season_weight": 0.60,
                    "future_value_weight": 0.40,
                },
                "metadata": {
                    "bootstrap_profile": True,
                },
            },
        )
    )

    league_registry.save(
        current_league_profile
    )


# =========================================================
# ADD / CONNECT LEAGUE
# =========================================================
#
# Resolve the configured app owner's Sleeper identity from the
# current league so the Add League form can be prefilled without
# hard-coding a username into the application.
#
default_sleeper_account = ""
configured_user_key = (
    AUTHENTICATED_IDENTITY.user_key
    if AUTHENTICATED_IDENTITY is not None
    else "single-user"
)


legacy_my_identity_for_add = (
    LEGACY_MANAGERS.get(
        LEGACY_MY_MANAGER_ID
    )
)


if (
    legacy_my_identity_for_add
    and
    bootstrap_sleeper_data is not None
    and
    legacy_my_identity_for_add
    .sleeper_roster_id
    is not None
):

    bootstrap_owner_id = None


    for roster in (
        bootstrap_sleeper_data[
            "rosters"
        ]
    ):

        if (
            roster.get(
                "roster_id"
            )
            ==
            legacy_my_identity_for_add
            .sleeper_roster_id
        ):

            bootstrap_owner_id = (
                roster.get(
                    "owner_id"
                )
            )

            break


    if bootstrap_owner_id is not None:

        bootstrap_owner_id = str(
            bootstrap_owner_id
        )


        for user in (
            bootstrap_sleeper_data[
                "users"
            ]
        ):

            if (
                str(
                    user.get(
                        "user_id"
                    )
                )
                ==
                bootstrap_owner_id
            ):

                default_sleeper_account = str(
                    user.get(
                        "username"
                    )
                    or user.get(
                        "display_name"
                    )
                    or bootstrap_owner_id
                )

                break


        if not default_sleeper_account:

            default_sleeper_account = (
                bootstrap_owner_id
            )


for configured_identity in current_league_profile.managers.values():

    if AUTHENTICATED_IDENTITY is not None:
        break

    if (
        legacy_my_identity_for_add
        and legacy_my_identity_for_add.sleeper_roster_id is not None
        and configured_identity.sleeper_roster_id
        == legacy_my_identity_for_add.sleeper_roster_id
    ):

        configured_user_key = str(
            configured_identity.sleeper_user_id
            or "manager-{0}".format(LEGACY_MY_MANAGER_ID)
        )
        break


# =========================================================
# LEAGUE SELECTOR
# =========================================================
#
# Profiles are selected by league_key rather than display
# name so two leagues can safely have the same league name.
#
registered_leagues = (
    league_registry.list_profiles()
)


# Defensive fallback: the configured league should always
# remain selectable even if another profile JSON is malformed.
if not any(
    profile.league_key
    == current_league_profile.league_key

    for profile
    in registered_leagues
):

    registered_leagues.append(
        current_league_profile
    )


league_profiles_by_key = {
    profile.league_key: profile

    for profile
    in registered_leagues
}


league_keys = list(
    league_profiles_by_key.keys()
)


demo_league_key = next(
    (
        profile.league_key
        for profile in registered_leagues
        if bool(profile.metadata.get("portfolio_demo"))
    ),
    None,
)
default_league_key = (
    demo_league_key
    if DEMO_MODE and demo_league_key is not None
    else current_league_profile.league_key
)


default_league_index = (
    league_keys.index(
        default_league_key
    )
    if default_league_key
    in league_keys
    else 0
)


pending_league_key = (
    st.session_state.pop(
        "pending::active_league_key",
        None,
    )
)


if (
    pending_league_key
    and
    pending_league_key
    in league_profiles_by_key
):

    st.session_state[
        "active_league_key"
    ] = (
        pending_league_key
    )


selected_league_key = (
    st.sidebar.selectbox(
        "League",
        options=(
            league_keys
        ),
        index=(
            default_league_index
        ),
        format_func=lambda league_key: (
            f"{league_profiles_by_key[league_key].league_name} "
            f"({league_profiles_by_key[league_key].season})"
        ),
        key="active_league_key",
    )
)


selected_league = (
    league_profiles_by_key[
        selected_league_key
    ]
)


if (
    current_league_profile is not None
    and selected_league_key == current_league_profile.league_key
):
    st.sidebar.caption(
        "This is the app's configured fallback league and can't be "
        "deleted from here."
    )
else:
    delete_league_confirm_key = "confirm_delete_league::{0}".format(
        selected_league_key
    )

    if not st.session_state.get(delete_league_confirm_key, False):

        if st.sidebar.button(
            "🗑️ Delete This League",
            width="stretch",
            help=(
                "Removes this league's profile, budgets/keepers/history, "
                "and any local draft-state data. Cannot be undone."
            ),
        ):
            st.session_state[delete_league_confirm_key] = True
            st.rerun()

    else:

        st.sidebar.warning(
            "This permanently deletes \"{0}\" and all of its saved "
            "setup and draft state.".format(selected_league.league_name)
        )
        delete_confirm_col, delete_cancel_col = st.sidebar.columns(2)
        if delete_confirm_col.button(
            "Confirm Delete",
            type="primary",
            width="stretch",
            key="confirm_delete_league_button",
        ):
            delete_league_data(
                league_key=selected_league_key,
                league_registry=league_registry,
                setup_store=league_setup_store,
                draft_state_directory=DATA_ROOT / "draft_states",
            )
            st.session_state[delete_league_confirm_key] = False
            st.session_state.pop("active_league_key", None)
            st.rerun()
        if delete_cancel_col.button(
            "Cancel",
            width="stretch",
            key="cancel_delete_league_button",
        ):
            st.session_state[delete_league_confirm_key] = False
            st.rerun()


league_summary_parts = [
    selected_league
    .scoring_label
    .replace("_", " ")
    .title()
]


if selected_league.managers:

    league_summary_parts.append(
        f"{len(selected_league.managers)} teams"
    )


league_summary_parts.append(
    str(
        selected_league.season
    )
)


st.sidebar.caption(
    " • ".join(
        league_summary_parts
    )
)

if st.sidebar.button(
    "💡 How This Works",
    width="stretch",
    help="A plain-language walkthrough of how recommendations get made.",
):
    st.session_state["show_how_it_works"] = not st.session_state.get(
        "show_how_it_works", False
    )
    st.rerun()

if st.session_state.get("show_how_it_works"):
    if st.sidebar.button("← Back to app", width="stretch"):
        st.session_state["show_how_it_works"] = False
        st.rerun()
    render_how_it_works_view()
    st.stop()


if st.session_state[
    "show_add_league_form"
]:

    add_league_kwargs = {
        "registry": (
            league_registry
        ),
        "default_season": (
            int(
                selected_league.season
            )
        ),
        "current_profile": (
            selected_league
        ),
        "default_account": (
            default_sleeper_account
        ),
        "selector_state_key": (
            "active_league_key"
        ),
    }


    st.sidebar.caption("**➕ Add a league**")
    render_add_sleeper_league(
        **add_league_kwargs
    )
    render_add_manual_league(
        registry=league_registry,
        default_season=int(selected_league.season),
        setup_store=league_setup_store,
        selector_state_key="active_league_key",
    )
    render_portfolio_demo_loader(
        registry=league_registry,
        setup_store=league_setup_store,
        selector_state_key="active_league_key",
    )


# =========================================================
# APP NAVIGATION
# =========================================================

APP_VIEWS = [
    "🏠 League Setup",
    "🧭 Pre-Draft",
    "🚨 Draft Mode" if selected_league.draft_format != "snake" else SNAKE_DRAFT_VIEW,
    "📚 Draft History",
    MANAGER_INTELLIGENCE_VIEW,
    PLAYER_CONTEXT_VIEW,
    DEPTH_CHARTS_VIEW,
]


ACTIVE_VIEW = st.sidebar.radio(
    "View",
    options=APP_VIEWS,
    index=(1 if DEMO_MODE and selected_league.metadata.get("portfolio_demo") else 2),
    key=(
        private_state_key(
            selected_league.league_key,
            configured_user_key,
            "active_view",
        )
    ),
)

VIEW_REQUIREMENTS = requirements_for_view(
    ACTIVE_VIEW
)

if VIEW_REQUIREMENTS.pre_draft_intelligence:

    context_store = ContextStore(
        db_path=CONTEXT_DB_PATH
    )

if VIEW_REQUIREMENTS.live_draft:

    depth_chart_tracker = (
        DepthChartMovementTracker(
            db_path=CONTEXT_DB_PATH
        )
    )


st.sidebar.divider()


# =========================================================
# ACTIVE LEAGUE RUNTIME
# =========================================================

ACTIVE_SEASON = int(
    selected_league.season
)

is_sleeper_backed_league = selected_league.source_mode == "sleeper"
if is_sleeper_backed_league:
    ACTIVE_LEAGUE_ID = selected_league.sleeper_league_id
    ACTIVE_DRAFT_ID = selected_league.sleeper_draft_id
    if not ACTIVE_LEAGUE_ID or not ACTIVE_DRAFT_ID:
        st.error("The selected Sleeper profile is missing its league or draft ID.")
        st.stop()
    if (
        str(ACTIVE_LEAGUE_ID) == str(SLEEPER_LEAGUE_ID)
        and str(ACTIVE_DRAFT_ID) == str(SLEEPER_DRAFT_ID)
        and bootstrap_sleeper_data is not None
    ):
        sleeper_data = bootstrap_sleeper_data
    else:
        try:
            sleeper_data = load_sleeper_data(ACTIVE_LEAGUE_ID, ACTIVE_DRAFT_ID)
        except Exception as error:
            st.error("Selected Sleeper league failed: {0}".format(error))
            st.stop()
    st.sidebar.caption("Sleeper league: {0}".format(ACTIVE_LEAGUE_ID))
    st.sidebar.caption("Draft: {0}".format(ACTIVE_DRAFT_ID))
else:
    ACTIVE_LEAGUE_ID, ACTIVE_DRAFT_ID = manual_runtime_ids(selected_league)
    try:
        manual_player_data = load_sleeper_player_universe()
    except Exception as error:
        st.error(
            "Sleeper's global NFL player universe is unavailable: {0}".format(error)
        )
        st.stop()
    sleeper_data = {
        "league": {
            "name": selected_league.league_name,
            "league_id": ACTIVE_LEAGUE_ID,
            "scoring_settings": dict(selected_league.scoring.raw),
        },
        "users": [],
        "rosters": [],
        "draft": {
            "draft_id": ACTIVE_DRAFT_ID,
            "status": "manual",
            "season": ACTIVE_SEASON,
        },
        "players": manual_player_data["players"],
        "_fetched_at": manual_player_data["_fetched_at"],
    }
    st.sidebar.caption("Platform: Yahoo / manual")
    st.sidebar.caption("Player universe: Sleeper NFL")


# =========================================================
# PER-LEAGUE DRAFT STORE
# =========================================================
#
# The legacy Bishop league keeps its existing database so no
# saved setup or live-sale history is lost. Every additional
# league receives an isolated SQLite database because
# DraftStore's tables are not partitioned by league.
#
is_legacy_configured_league = (
    str(
        ACTIVE_LEAGUE_ID
    )
    ==
    str(
        SLEEPER_LEAGUE_ID
    )
    and
    str(
        ACTIVE_DRAFT_ID
    )
    ==
    str(
        SLEEPER_DRAFT_ID
    )
)


if is_legacy_configured_league:

    active_draft_db_path = (
        DATA_ROOT
        / "draft_state.db"
    )

else:

    draft_state_directory = (
        DATA_ROOT
        / "draft_states"
    )

    draft_state_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_league_key = "".join(
        character
        if (
            character.isalnum()
            or character
            in {
                "-",
                "_",
            }
        )
        else "_"

        for character
        in selected_league.league_key
    ).strip("_")


    if not safe_league_key:

        safe_league_key = (
            "league"
        )


    active_draft_db_path = draft_state_directory / "{0}_{1}.db".format(
        safe_league_key,
        "sleeper_{0}".format(ACTIVE_DRAFT_ID)
        if is_sleeper_backed_league
        else "manual_{0}".format(ACTIVE_SEASON),
    )


draft_store = DraftStore(
    db_path=str(
        active_draft_db_path
    ),
    league_id=str(
        ACTIVE_LEAGUE_ID
    ),
    draft_id=str(
        ACTIVE_DRAFT_ID
    ),
    season=ACTIVE_SEASON,
    checkpoint_callback=STATE_CHECKPOINT,
)


# =========================================================
# ACTIVE MANAGER RUNTIME
# =========================================================
#
# Manager display names, Sleeper roster IDs, and Sleeper user
# identity now come from the selected LeagueProfile.
#
# Bishop still needs its historical workbook keys for one more
# migration step. We bridge those old keys by Sleeper roster ID
# only; downstream app code no longer reads MANAGERS directly.
#

def build_active_manager_map(
    league_profile,
    legacy_bridge=False,
):

    profile_managers = dict(
        league_profile.managers
    )

    if not legacy_bridge:

        return profile_managers


    legacy_id_by_roster = {
        int(
            identity.sleeper_roster_id
        ): manager_id

        for (
            manager_id,
            identity,
        ) in LEGACY_MANAGERS.items()

        if (
            identity.sleeper_roster_id
            is not None
        )
    }


    active = {}


    for (
        profile_manager_id,
        identity,
    ) in profile_managers.items():

        roster_id = (
            identity.sleeper_roster_id
        )


        runtime_manager_id = (
            legacy_id_by_roster.get(
                int(
                    roster_id
                )
            )
            if roster_id
            is not None
            else None
        )


        if not runtime_manager_id:

            runtime_manager_id = (
                profile_manager_id
            )


        active[
            runtime_manager_id
        ] = identity


    return active


ACTIVE_MANAGERS = (
    build_active_manager_map(
        selected_league,
        legacy_bridge=(
            is_legacy_configured_league
        ),
    )
)


# ---------------------------------------------------------
# Resolve the app owner's permanent Sleeper user ID.
#
# For the existing Bishop migration, the old config tells us
# which roster is ours. From there, the LeagueProfile supplies
# the actual Sleeper user ID. That user ID can then identify
# the same owner in any other registered Sleeper league.
# ---------------------------------------------------------

legacy_my_identity = (
    LEGACY_MANAGERS.get(
        LEGACY_MY_MANAGER_ID
    )
)


APP_SLEEPER_USER_ID = None


if (
    legacy_my_identity
    and
    bootstrap_sleeper_data is not None
    and
    legacy_my_identity.sleeper_roster_id
    is not None
):

    for roster in (
        bootstrap_sleeper_data[
            "rosters"
        ]
    ):

        if (
            roster.get(
                "roster_id"
            )
            ==
            legacy_my_identity.sleeper_roster_id
        ):

            owner_id = (
                roster.get(
                    "owner_id"
                )
            )

            if owner_id is not None:

                APP_SLEEPER_USER_ID = str(
                    owner_id
                )

            break


if (
    APP_SLEEPER_USER_ID
    is None
    and
    legacy_my_identity
    and
    legacy_my_identity.sleeper_roster_id
    is not None
):

    for identity in (
        current_league_profile
        .managers
        .values()
    ):

        if (
            identity.sleeper_roster_id
            ==
            legacy_my_identity.sleeper_roster_id
        ):

            APP_SLEEPER_USER_ID = (
                identity.sleeper_user_id
            )

            break


try:

    runtime_identity = resolve_runtime_identity(
        league_profile=selected_league,
        managers=ACTIVE_MANAGERS,
        sleeper_user_id=APP_SLEEPER_USER_ID,
        fallback_manager_id=(
            LEGACY_MY_MANAGER_ID
            if is_legacy_configured_league
            else selected_league.metadata.get("current_manager_id")
        ),
        authenticated_identity=AUTHENTICATED_IDENTITY,
        authenticated_manager_mappings=AUTHENTICATED_MANAGER_MAPPINGS,
    )

except ValueError as error:

    st.error(
        str(error)
    )

    st.stop()


ACTIVE_MY_MANAGER_ID = runtime_identity.current.manager_id

private_state_access = PrivateStateAccess.from_runtime_identity(runtime_identity)
draft_store.bind_private_scope(private_state_access.scope)


ACTIVE_MY_IDENTITY = (
    ACTIVE_MANAGERS[
        ACTIVE_MY_MANAGER_ID
    ]
)


if is_sleeper_backed_league:
    live_sleeper_draft_type = str(
        (sleeper_data.get("draft") or {}).get("type") or "auction"
    ).lower()
    live_draft_format = (
        "auction" if live_sleeper_draft_type == "auction" else "snake"
    )
    if live_draft_format != selected_league.draft_format:
        # Self-heal profiles saved before draft_format existed (or whose
        # Sleeper draft type changed) so the next page load routes to
        # the right sidebar view without a manual re-sync.
        league_registry.save(replace(selected_league, draft_format=live_draft_format))
else:
    live_draft_format = selected_league.draft_format


ACTIVE_LEAGUE_PROFILE = (
    replace(
        selected_league,
        managers=(
            ACTIVE_MANAGERS
        ),
        draft_format=live_draft_format,
    )
)


strategy_profile_store = None
strategy_profile = None
my_guys_store = None
my_guys_preferences = None
planning_preferences_store = None
planning_preferences = None


if VIEW_REQUIREMENTS.pre_draft_intelligence:

    strategy_profile_store = StrategyProfileStore(
        root=STRATEGY_PROFILE_PATH,
        checkpoint_callback=STATE_CHECKPOINT,
    )

    try:

        strategy_profile = private_state_access.load_strategy(
            strategy_profile_store
        )

    except (OSError, ValueError) as error:

        st.warning(
            "Saved strategy profile unavailable: {0}".format(error)
        )


    if strategy_profile is None:

        strategy_profile = StrategyProfile.from_league_defaults(
            league_profile=ACTIVE_LEAGUE_PROFILE,
            user_key=runtime_identity.current.user_key,
        )

    my_guys_store = MyGuysStore(
        root=MY_GUYS_PATH,
        checkpoint_callback=STATE_CHECKPOINT,
    )
    try:
        my_guys_preferences = private_state_access.load_my_guys(my_guys_store)
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.warning("Saved My Guys unavailable: {0}".format(error))
    if my_guys_preferences is None:
        my_guys_preferences = MyGuysPreferences(
            league_key=runtime_identity.league.league_key,
            user_key=runtime_identity.current.user_key,
        )

    planning_preferences_store = PlanningPreferencesStore(
        root=PLANNING_PREFERENCES_PATH,
        checkpoint_callback=STATE_CHECKPOINT,
    )
    try:
        planning_preferences = private_state_access.load_planning(
            planning_preferences_store
        )
    except (OSError, ValueError) as error:
        st.warning("Saved planning preferences unavailable: {0}".format(error))


st.sidebar.caption(
    f"My team: "
    f"{ACTIVE_MY_IDENTITY.sleeper_team_name}"
)

if AUTHENTICATED_IDENTITY is not None:
    st.sidebar.caption(
        "Authenticated by {0}".format(AUTHENTICATED_IDENTITY.provider)
    )


# Per-league Streamlit state prevents keeper/setup selections
# from leaking between leagues that happen to use the same
# manager IDs.
KEEPER_SELECTIONS_STATE_KEY = (
    runtime_identity.private_key(
        "keeper_selections"
    )
)

# =========================================================
# NORMALIZED LEAGUE SETUP DATA
# =========================================================
#
# The app now normalizes every setup source into LeagueSetupData:
#
# manual overrides > workbook/import > Sleeper facts > defaults
#
# Downstream runtime services consume LeagueSetupData directly.
#

workbook_path = (
    resolve_league_workbook_path(
        selected_league,
        use_legacy_default=(
            is_legacy_configured_league
        ),
    )
)


def clear_active_league_source_caches():
    """Refresh the selected league source plus optional workbook enrichment."""

    if is_sleeper_backed_league:
        load_sleeper_data.clear()
    else:
        load_sleeper_player_universe.clear()
    if workbook_path is not None:
        load_league_workbook.clear()


workbook_loaded = False
workbook_error = None
manual_setup_error = None
manual_setup_loaded = False


# ---------------------------------------------------------
# BASELINE: SLEEPER + GENERAL LEAGUE BUDGET
# ---------------------------------------------------------
#
# Sleeper supplies current roster membership. Roster membership
# is intentionally stored separately from finalized keepers so
# the next Setup UI can ask the user to confirm only what is
# uncertain.
#
league_setup_data = (
    LeagueSetupData.from_sleeper(
        league_profile=(
            ACTIVE_LEAGUE_PROFILE
        ),
        rosters=(
            sleeper_data[
                "rosters"
            ]
        ),
        sleeper_players=(
            sleeper_data[
                "players"
            ]
        ),
        default_budget=int(
            selected_league
            .auction
            .base_budget
        ),
    )
)


# ---------------------------------------------------------
# OPTIONAL WORKBOOK ENRICHMENT
# ---------------------------------------------------------

workbook_result = enrich_setup_from_optional_workbook(
    baseline=league_setup_data,
    league_profile=ACTIVE_LEAGUE_PROFILE,
    workbook_path=workbook_path,
    loader=(
        load_league_workbook
        if workbook_path is not None
        and workbook_path.exists()
        else None
    ),
)
league_setup_data = workbook_result.setup_data
workbook_loaded = workbook_result.loaded
workbook_error = workbook_result.error


# ---------------------------------------------------------
# OPTIONAL PERSISTED MANUAL / IMPORTED OVERRIDES
# ---------------------------------------------------------
#
# Manual/imported overrides are optional and remain higher priority than
# workbook enrichment and Sleeper inference.
#
try:

    manual_setup_data = (
        league_setup_store
        .load_optional(
            selected_league
            .league_key
        )
    )

    if manual_setup_data is not None:

        effective_manual_overrides = permitted_setup_overrides(
            ACTIVE_LEAGUE_PROFILE,
            manual_setup_data,
        )

        league_setup_data = (
            league_setup_data
            .merged_with(
                effective_manual_overrides
            )
        )

        manual_setup_loaded = True


except Exception as error:

    manual_setup_error = str(
        error
    )

    league_setup_data.warnings.append(
        (
            "Saved manual league setup could not "
            f"be loaded: {manual_setup_error}"
        )
    )


league_data = league_setup_data


setup_source_summary = (
    league_setup_data
    .source_summary
)


st.sidebar.caption(
    f"Draft state: "
    f"{active_draft_db_path}"
)


st.sidebar.caption(
    f"Profiles: "
    f"{LEAGUE_REGISTRY_PATH}"
)


st.sidebar.caption(
    f"Setup data: "
    f"{LEAGUE_SETUP_PATH}"
)


st.sidebar.caption(
    f"Managers inferred: "
    f"{len(ACTIVE_MANAGERS)}"
)


if workbook_loaded:

    st.sidebar.caption(
        f"Workbook: "
        f"{workbook_path.name}"
    )

else:

    st.sidebar.caption(
        "Workbook: optional / not active"
    )


st.sidebar.caption(
    f"Sleeper roster players: "
    f"{len(league_setup_data.roster_players)}"
)


st.sidebar.caption(
    f"Team budgets: "
    f"{len(league_setup_data.budgets)}"
)


st.sidebar.caption(
    f"Keeper records: "
    f"{len(league_setup_data.keepers)}"
)


st.sidebar.caption(
    f"Historical sales: "
    f"{len(league_setup_data.historical_sales)}"
)


if manual_setup_loaded:

    st.sidebar.success(
        "Manual setup overrides active"
    )




fantasypros_error = None
fantasypros_data = {
    "rankings_response": {},
    "players_response": {},
    "projection_response": {},
    "intelligence": [],
    "health": None,
}


if (
    VIEW_REQUIREMENTS.pre_draft_intelligence
    and not selected_league.metadata.get("portfolio_demo")
):
    fantasypros_result = load_optional_feed(
        "FantasyPros rankings and projections",
        lambda: load_fantasypros_data(ACTIVE_SEASON),
        fantasypros_data,
        validator=lambda value: bool(
            value.get("intelligence") or value.get("projection_response")
        ),
    )
    fantasypros_data = fantasypros_result.data
    fantasypros_error = fantasypros_result.error
    if fantasypros_result.available and fantasypros_data.get("_errors"):
        fantasypros_error = "; ".join(
            "{0}: {1}".format(name, error)
            for name, error in sorted(fantasypros_data["_errors"].items())
        )


# =========================================================
# UNPACK SLEEPER
# =========================================================

league = sleeper_data[
    "league"
]

sleeper_players = sleeper_data[
    "players"
]


# =========================================================
# FANTASYPROS
# =========================================================

fantasypros_index = (
    build_intelligence_index(
        fantasypros_data[
            "intelligence"
        ]
    )
)

ranking_ensemble = build_repository_ranking_ensemble(
    sleeper_players=sleeper_players,
    third_party_players=fantasypros_data["intelligence"],
)


projection_response = (
    fantasypros_data[
        "projection_response"
    ]
)


scoring_projection_result = None
if projection_response:
    scoring_projection_result = build_league_scoring_projection(
        projection_response=projection_response,
        scoring_settings=league.get("scoring_settings", {}),
        num_teams=max(1, len(ACTIVE_MANAGERS)),
        starting_lineup=ACTIVE_LEAGUE_PROFILE.roster.starting_lineup,
    )
    projections = list(scoring_projection_result.projections)
else:
    projections = []


projection_index = (
    build_projection_index(
        projections
    )
)


# =========================================================
# LEAGUE-WIDE FANTASYPROS CONTEXT
# =========================================================

context_error = None
current_context_documents = []
context_api_data = {}


if (
    VIEW_REQUIREMENTS.live_draft
    and
    fantasypros_data[
    "intelligence"
    ]
):

    context_feed_result = load_optional_feed(
        "FantasyPros news and injuries",
        lambda: load_fantasypros_context_data(ACTIVE_SEASON),
        {},
        validator=lambda value: "news" in value and "injuries" in value,
    )
    if context_feed_result.available:
        try:
            context_api_data = context_feed_result.data
            news_documents = (
                normalize_fantasypros_news(
                    response=(
                        context_api_data[
                            "news"
                        ]
                    ),
                    intelligence=(
                        fantasypros_data[
                            "intelligence"
                        ]
                    ),
                )
            )
            injury_documents = (
                normalize_fantasypros_injuries(
                    response=(
                        context_api_data[
                            "injuries"
                        ]
                    ),
                    intelligence=(
                        fantasypros_data[
                            "intelligence"
                        ]
                    ),
                )
            )
            current_context_documents = (
                news_documents
                +
                injury_documents
            )

        except Exception as error:
            context_error = str(error)
    else:
        context_error = context_feed_result.error


if VIEW_REQUIREMENTS.live_draft:
    structured_context = ingest_structured_context(
        tuple(league_setup_data.metadata.get("context_signals", ()) or ())
    )
    current_context_documents.extend(structured_context.documents)
    for warning in structured_context.warnings:
        st.warning(warning)
    try:
        if current_context_documents:
            context_store.add_documents(current_context_documents)
    except Exception as error:
        context_error = str(error)


# =========================================================
# STATIC SLEEPER DEPTH CHART
# =========================================================

depth_chart_error = None
depth_chart_documents = []


try:

    depth_chart_documents = (
        build_depth_chart_documents(
            sleeper_players=(
                sleeper_players
            ),
            fantasypros_index=(
                fantasypros_index
            ),
        )
        if VIEW_REQUIREMENTS.live_draft
        else []
    )


    if depth_chart_documents:

        context_store.add_documents(
            depth_chart_documents
        )


except Exception as error:

    depth_chart_error = str(
        error
    )


# =========================================================
# DEPTH CHART MOVEMENT DETECTION
# =========================================================

depth_movement_error = None
depth_movement_result = None


try:

    depth_movement_result = (
        depth_chart_tracker.process(
            sleeper_players=(
                sleeper_players
            ),
            fantasypros_index=(
                fantasypros_index
            ),
        )
        if VIEW_REQUIREMENTS.live_draft
        else None
    )


    if (
        depth_movement_result
        and
        depth_movement_result.documents
    ):

        context_store.add_documents(
            depth_movement_result.documents
        )


except Exception as error:

    depth_movement_error = str(
        error
    )


data_freshness = (
    assess_data_freshness(
        "Sleeper",
        sleeper_data.get("_fetched_at"),
        300,
        available=bool(sleeper_players),
    ),
    assess_data_freshness(
        "FantasyPros rankings + projections",
        fantasypros_data.get("_fetched_at"),
        3600,
        error=fantasypros_error,
        available=bool(fantasypros_data.get("intelligence")),
    ),
    assess_data_freshness(
        "FantasyPros news + injuries",
        context_api_data.get("_fetched_at"),
        900,
        error=context_error,
        available=bool(context_api_data),
    ),
    assess_data_freshness(
        "Depth charts",
        sleeper_data.get("_fetched_at"),
        300,
        error=depth_chart_error or depth_movement_error,
        available=bool(depth_chart_documents),
    ),
)

source_by_freshness_name = {
    "Sleeper": IntelligenceSource.SLEEPER,
    "FantasyPros rankings + projections": IntelligenceSource.RANKINGS_PROJECTIONS,
    "FantasyPros news + injuries": IntelligenceSource.NEWS_INJURIES,
    "Depth charts": IntelligenceSource.DEPTH_USAGE_CONTEXT,
}
source_statuses = {
    source_by_freshness_name[item.source]: item.status.value
    for item in data_freshness
}
refresh_on_open_key = runtime_identity.private_key(
    "refresh_on_open_checked_{0}".format(ACTIVE_VIEW)
)
refresh_on_open_plan = build_refresh_on_open_plan(
    source_statuses,
    already_checked=bool(st.session_state.get(refresh_on_open_key, False)),
)
if refresh_on_open_key not in st.session_state:
    st.session_state[refresh_on_open_key] = True
    if not refresh_on_open_plan.empty:
        execute_refresh_plan(
            refresh_on_open_plan,
            {
                "sleeper": clear_active_league_source_caches,
                "fantasypros": load_fantasypros_data.clear,
                "context": load_fantasypros_context_data.clear,
                "targeted_context": load_player_context_data.clear,
            },
        )
        st.rerun()


# =========================================================
# VORP
# =========================================================

replacement_levels = None
player_values = []
player_value_index = {}


if scoring_projection_result is not None:
    replacement_levels = scoring_projection_result.replacement_levels
    player_values = list(scoring_projection_result.player_values)


    player_value_index = {
        normalize_player_name(
            value.player_name
        ): value

        for value
        in player_values
    }

elif selected_league.metadata.get("portfolio_demo"):
    player_values = list(build_demo_player_values(league_setup_data))
    player_value_index = {
        normalize_player_name(value.player_name): value
        for value in player_values
    }


# =========================================================
# HISTORICAL MARKET
# =========================================================

historical_market_model = (
    build_historical_market_model(
        historical_sales=(
            league_data.historical_sales
        ),
        sleeper_players=(
            sleeper_players
        ),
    )
)

manager_tendency_model = build_manager_tendency_model(
    build_tendency_observations_from_market(historical_market_model),
    as_of_season=ACTIVE_SEASON,
)


# =========================================================
# LOAD PERSISTED DRAFT STATE
# =========================================================

persisted_setup_warnings = []

persisted_setup = (
    draft_store.load_team_setups(
        warnings=persisted_setup_warnings
    )
)

league_data.warnings.extend(
    persisted_setup_warnings
)

live_sales = (
    draft_store.load_sales()
)


setup_locked = (
    len(
        live_sales
    )
    > 0
)


# =========================================================
# SESSION DEFAULTS
# =========================================================

if (
    KEEPER_SELECTIONS_STATE_KEY
    not in st.session_state
):

    st.session_state[
        KEEPER_SELECTIONS_STATE_KEY
    ] = {}

    for manager_id in ACTIVE_MANAGERS:

        saved = (
            persisted_setup.get(
                manager_id,
                {},
            )
        )

        st.session_state[
            KEEPER_SELECTIONS_STATE_KEY
        ][
            manager_id
        ] = saved.get(
            "keepers",
            [],
        )


SALE_INPUT_MODE_STATE_KEY = runtime_identity.private_key("sale_input_mode")
SLEEPER_POLL_STATE_KEY = runtime_identity.private_key("sleeper_poll_seconds")
AUTO_SLEEPER_SYNC_STATE_KEY = runtime_identity.private_key("auto_sleeper_sync")


if SALE_INPUT_MODE_STATE_KEY not in st.session_state:

    st.session_state[
        SALE_INPUT_MODE_STATE_KEY
    ] = (
        "Sleeper Live Sync"
        if is_sleeper_backed_league
        else "Manual Sale Entry"
    )


if (
    SLEEPER_POLL_STATE_KEY
    not in st.session_state
):

    st.session_state[
        SLEEPER_POLL_STATE_KEY
    ] = 5


if (
    AUTO_SLEEPER_SYNC_STATE_KEY
    not in st.session_state
):

    st.session_state[
        AUTO_SLEEPER_SYNC_STATE_KEY
    ] = is_sleeper_backed_league


# =========================================================
# HEADER
# =========================================================

render_product_header(
    league_name=league.get("name", selected_league.league_name),
    season=ACTIVE_SEASON,
    view_name=ACTIVE_VIEW,
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header(
        "Draft Controls"
    )


    selected_refresh_sources = st.multiselect(
        "Also refresh selected sources",
        options=list(IntelligenceSource),
        format_func=lambda source: source.value,
        key=runtime_identity.private_key("refresh_intelligence_sources"),
        help="The action always includes stale, failed, and unavailable sources.",
    )
    refresh_plan = build_refresh_plan(
        source_statuses=source_statuses,
        selected_sources=selected_refresh_sources,
    )
    if st.button(
        "Refresh Draft Intelligence",
        width="stretch",
        help="Refresh stale sources plus any sources selected above.",
    ):
        if refresh_plan.empty:
            st.info("All sources are fresh; select a source to force refresh.")
        else:
            execute_refresh_plan(
                refresh_plan,
                {
                    "sleeper": clear_active_league_source_caches,
                    "fantasypros": load_fantasypros_data.clear,
                    "context": load_fantasypros_context_data.clear,
                    "targeted_context": load_player_context_data.clear,
                },
            )
            st.rerun()


    if st.button(
        (
            "Reload Workbook"
            if workbook_path
            else "Workbook Not Configured"
        ),
        width="stretch",
        disabled=(
            workbook_path
            is None
        ),
    ):

        load_league_workbook.clear()

        st.rerun()


    st.divider()


    st.subheader(
        "Persistence"
    )

    st.success(
        "SQLite active"
    )

    st.caption(
        str(
            active_draft_db_path
        )
    )

    st.write(
        f"Stored sales: "
        f"**{draft_store.sale_count()}**"
    )

    st.write(
        (
            "**Pre-draft setup: LOCKED**"
            if setup_locked
            else
            "**Pre-draft setup: EDITABLE**"
        )
    )

    if draft_store.sale_count() > 0:

        reset_sales_confirm_key = runtime_identity.private_key(
            "confirm_reset_sales"
        )

        if not st.session_state.get(reset_sales_confirm_key, False):

            if st.button(
                "Reset Simulated Sales",
                width="stretch",
                help=(
                    "Clears every recorded auction sale for this league "
                    "(simulated picks included) and unlocks pre-draft setup."
                ),
            ):
                st.session_state[reset_sales_confirm_key] = True
                st.rerun()

        else:

            st.warning(
                "This permanently deletes all {0} recorded sale(s) for "
                "this league.".format(draft_store.sale_count())
            )
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button(
                "Confirm Reset",
                type="primary",
                width="stretch",
            ):
                draft_store.reset_sales()
                st.session_state[reset_sales_confirm_key] = False
                st.rerun()
            if cancel_col.button(
                "Cancel",
                width="stretch",
            ):
                st.session_state[reset_sales_confirm_key] = False
                st.rerun()


    st.divider()


    st.subheader(
        "Data"
    )

    with st.expander("Data Freshness", expanded=True):
        status_icons = {
            "FRESH": "🟢",
            "STALE": "🟠",
            "ERROR": "🔴",
            "UNAVAILABLE": "⚪",
        }
        if not VIEW_REQUIREMENTS.pre_draft_intelligence:
            st.caption(
                "This page doesn't load rankings/projections/depth-chart "
                "sources to stay fast -- visit Pre-Draft or Draft Mode to "
                "see their real freshness."
            )
        for freshness in data_freshness:
            refreshed = (
                freshness.last_refresh.strftime("%Y-%m-%d %H:%M:%S UTC")
                if freshness.last_refresh is not None
                else "Never"
            )
            not_loaded_here = (
                freshness.status.value == "UNAVAILABLE"
                and not VIEW_REQUIREMENTS.pre_draft_intelligence
                and freshness.source != "Sleeper"
            )
            st.markdown(
                "{0} **{1}: {2}**".format(
                    status_icons[freshness.status.value],
                    freshness.source,
                    "NOT LOADED HERE" if not_loaded_here else freshness.status.value,
                )
            )
            if not_loaded_here:
                st.caption("Not fetched on this page -- not a data problem.")
            else:
                st.caption(
                    "Last refresh: {0} • Age: {1} • Stale after: {2}{3}".format(
                        refreshed,
                        freshness.age_label,
                        freshness.threshold_label,
                        " • {0}".format(freshness.detail) if freshness.detail else "",
                    )
                )


    active_setup_sources = [
        source_name

        for (
            source_name,
            count,
        ) in setup_source_summary.items()

        if count > 0
    ]


    st.write(
        "League setup sources: "
        f"**{', '.join(active_setup_sources) if active_setup_sources else 'defaults'}**"
    )


    st.write(
        f"Sleeper roster players: "
        f"**{len(league_setup_data.roster_players)}**"
    )


    st.write(
        f"Team budgets: "
        f"**{len(league_setup_data.budgets)}**"
    )


    st.write(
        f"Keeper records: "
        f"**{len(league_setup_data.keepers)}**"
    )


    st.write(
        f"Historical setup sales: "
        f"**{len(league_setup_data.historical_sales)}**"
    )

    st.write(
        f"FantasyPros players: "
        f"**{len(fantasypros_data['intelligence'])}**"
    )

    st.write(
        f"Projections: "
        f"**{len(projections)}**"
    )

    st.write(
        f"Historical mapped: "
        f"**{len(historical_market_model.mapped_sales)}**"
    )

    st.write(
        f"Context documents: "
        f"**{context_store.count() if context_store is not None else 0}**"
    )

    st.write(
        f"Depth chart players: "
        f"**{len(depth_chart_documents)}**"
    )


    try:

        depth_baseline_count = (
            depth_chart_tracker.state_count()
            if depth_chart_tracker is not None
            else 0
        )

    except Exception:

        depth_baseline_count = 0


    st.write(
        f"Depth baseline players: "
        f"**{depth_baseline_count}**"
    )


    current_depth_changes = (
        len(
            depth_movement_result.documents
        )
        if depth_movement_result
        else 0
    )


    st.write(
        f"Depth changes detected: "
        f"**{current_depth_changes}**"
    )


if workbook_error:

    st.info(
        f"Workbook enrichment unavailable: "
        f"{workbook_error}"
    )


if manual_setup_error:

    st.warning(
        f"Saved manual setup unavailable: "
        f"{manual_setup_error}"
    )


if fantasypros_error:

    st.warning(
        f"FantasyPros error: "
        f"{fantasypros_error}"
    )

elif fantasypros_data.get("health") is not None:

    st.sidebar.success(
        "FantasyPros verified: {0}".format(
            fantasypros_data["health"].summary
        )
    )


if context_error:

    st.warning(
        f"Player context update failed: "
        f"{context_error}"
    )


if depth_chart_error:

    st.warning(
        f"Depth chart context failed: "
        f"{depth_chart_error}"
    )


if depth_movement_error:

    st.warning(
        f"Depth chart movement tracking failed: "
        f"{depth_movement_error}"
    )


if VIEW_REQUIREMENTS.player_context:

    render_active_view(
        ACTIVE_VIEW,
        build_view_runtime(
            ACTIVE_DRAFT_ID=str(ACTIVE_DRAFT_ID),
            ACTIVE_LEAGUE_PROFILE=ACTIVE_LEAGUE_PROFILE,
            ACTIVE_MANAGERS=ACTIVE_MANAGERS,
            ACTIVE_MY_MANAGER_ID=ACTIVE_MY_MANAGER_ID,
            selected_league=selected_league,
            runtime_identity=runtime_identity,
            context_store=context_store,
            draft_store=draft_store,
            sleeper_players=sleeper_players,
            fantasypros_data=fantasypros_data,
            fantasypros_index=fantasypros_index,
            projection_index=projection_index,
            get_targeted_player_context=get_targeted_player_context,
            normalize_player_name=normalize_player_name,
        ),
    )

    st.stop()


if VIEW_REQUIREMENTS.snake_draft:

    snake_draft_state = None
    snake_draft_error = None

    if is_sleeper_backed_league:
        snake_picks_result = load_optional_feed(
            "Sleeper draft picks",
            lambda: SleeperClient().get_draft_picks(ACTIVE_DRAFT_ID),
            [],
            validator=lambda value: isinstance(value, list),
        )
        if snake_picks_result.error:
            snake_draft_error = snake_picks_result.error
        snake_draft_state = build_snake_draft_state(
            draft=sleeper_data.get("draft") or {},
            picks=snake_picks_result.data,
            league_profile=ACTIVE_LEAGUE_PROFILE,
            sleeper_players=sleeper_players,
            viewer_manager_id=ACTIVE_MY_MANAGER_ID,
        )
    else:
        snake_draft_error = "Snake draft mode requires a Sleeper-backed league."

    render_active_view(
        ACTIVE_VIEW,
        build_view_runtime(
            ACTIVE_DRAFT_ID=str(ACTIVE_DRAFT_ID),
            ACTIVE_LEAGUE_PROFILE=ACTIVE_LEAGUE_PROFILE,
            ACTIVE_MANAGERS=ACTIVE_MANAGERS,
            ACTIVE_MY_MANAGER_ID=ACTIVE_MY_MANAGER_ID,
            selected_league=selected_league,
            runtime_identity=runtime_identity,
            sleeper_players=sleeper_players,
            player_values=player_values,
            player_value_index=player_value_index,
            snake_draft_state=snake_draft_state,
            snake_draft_error=snake_draft_error,
        ),
    )

    st.stop()


if VIEW_REQUIREMENTS.depth_charts:

    depth_chart_view_error = None
    try:
        depth_chart_view_documents = build_depth_chart_documents(
            sleeper_players=sleeper_players,
            fantasypros_index=fantasypros_index,
        )
    except Exception as error:
        depth_chart_view_documents = []
        depth_chart_view_error = str(error)

    depth_chart_taken_players = {
        sale.player_name for sale in draft_store.load_sales()
    }

    if is_sleeper_backed_league:
        depth_chart_picks_result = load_optional_feed(
            "Sleeper draft picks",
            lambda: SleeperClient().get_draft_picks(ACTIVE_DRAFT_ID),
            [],
            validator=lambda value: isinstance(value, list),
        )
        for pick in depth_chart_picks_result.data:
            player_id = pick.get("player_id")
            if player_id is None:
                continue
            sleeper_player = sleeper_players.get(str(player_id)) or {}
            picked_name = sleeper_player.get("full_name")
            if picked_name:
                depth_chart_taken_players.add(str(picked_name))

    render_active_view(
        ACTIVE_VIEW,
        build_view_runtime(
            selected_league=selected_league,
            runtime_identity=runtime_identity,
            depth_chart_documents=depth_chart_view_documents,
            depth_chart_error=depth_chart_view_error,
            depth_chart_taken_players=sorted(depth_chart_taken_players),
        ),
    )

    st.stop()


if VIEW_REQUIREMENTS.history:

    render_active_view(
        ACTIVE_VIEW,
        build_view_runtime(
            ACTIVE_DRAFT_ID=str(ACTIVE_DRAFT_ID),
            ACTIVE_LEAGUE_PROFILE=ACTIVE_LEAGUE_PROFILE,
            ACTIVE_MANAGERS=ACTIVE_MANAGERS,
            ACTIVE_MY_MANAGER_ID=ACTIVE_MY_MANAGER_ID,
            selected_league=selected_league,
            runtime_identity=runtime_identity,
            private_state_access=private_state_access,
            draft_store=draft_store,
            live_sales=live_sales,
            historical_market_model=historical_market_model,
            manager_tendency_model=manager_tendency_model,
        ),
    )

    st.stop()


# =========================================================
# LEAGUE SETUP VIEW
# =========================================================



# ---------------------------------------------------------
# FINALIZED AUCTION START STATE
# ---------------------------------------------------------
#
# Explicit finalized keeper records are authoritative.
#
# During the Bishop migration, an older SQLite keeper setup
# remains a fallback when no explicit finalized records have
# been saved yet. That preserves the working league while
# removing the need to re-select keepers every app run.
#
team_setups = {}
setup_rows = []


for (
    manager_id,
    identity,
) in ACTIVE_MANAGERS.items():

    explicit_keepers = (
        league_setup_data
        .keepers_for(
            manager_id,
            finalized_only=True,
        )
    )


    manual_keeper_decisions_saved = (
        not is_sleeper_backed_league
        and
        manual_setup_loaded
        and
        manual_setup_data is not None
        and
        bool(
            manual_setup_data
            .metadata
            .get(
                "keepers_configured",
                False,
            )
        )
    )


    if explicit_keepers:

        selected_keepers = [
            keeper.player_name

            for keeper
            in explicit_keepers
        ]

        keeper_source = (
            "Setup data"
        )


    elif manual_keeper_decisions_saved:

        selected_keepers = []

        keeper_source = (
            "Setup data"
        )


    else:

        saved_setup = (
            persisted_setup.get(
                manager_id,
                {},
            )
        )


        saved_names = (
            saved_setup.get(
                "keepers",
                [],
            )
            or []
        )


        valid_keeper_names = {
            keeper.player_name

            for keeper
            in league_setup_data.keepers_for(
                manager_id
            )
        }


        selected_keepers = [
            player_name

            for player_name
            in saved_names

            if player_name
            in valid_keeper_names
        ]


        keeper_source = (
            "Saved legacy setup"
            if selected_keepers
            else "None"
        )


    saved_setup = (
        persisted_setup.get(
            manager_id,
            {},
        )
    )


    try:

        setup = (
            build_team_draft_setup_from_setup_data(
                manager_id=(
                    manager_id
                ),
                league_setup_data=(
                    league_setup_data
                ),
                selected_keeper_names=(
                    selected_keepers
                ),
                league_profile=(
                    ACTIVE_LEAGUE_PROFILE
                ),
            )
        )


        team_setups[
            manager_id
        ] = setup


        if (
            not setup_locked
            and
            (
                explicit_keepers
                or
                manual_keeper_decisions_saved
                or
                manager_id
                in persisted_setup
            )
        ):

            draft_store.save_team_setup(
                manager_id=(
                    manager_id
                ),
                keepers=(
                    selected_keepers
                ),
            )


        budget_record = (
            league_setup_data
            .budgets
            .get(
                manager_id
            )
        )


        budget_source = (
            budget_record.source.source
            if budget_record
            else "default"
        )


        setup_rows.append(
            {
                "Team": (
                    identity.sleeper_team_name
                    or identity.sleeper_username
                    or manager_id
                ),
                "Budget Source": (
                    budget_source
                ),
                "Keeper Source": (
                    keeper_source
                ),
                "Keepers": len(
                    selected_keepers
                ),
                "Keeper $": (
                    setup.keeper_commitments
                ),
                "Entering Cash": (
                    setup.entering_cash
                ),
                "Reserve": (
                    setup.required_reserve
                ),
                "Discretionary": (
                    setup.discretionary_cash
                ),
                "Open Spots": (
                    setup.open_roster_spots
                ),
                "Legal Max": (
                    setup.max_bid
                ),
            }
        )


    except ValueError as error:

        st.error(
            f"{identity.sleeper_team_name}: "
            f"{error}"
        )





# =========================================================
# STARTING AUCTION POOL
# =========================================================

pool_result = (
    build_auction_pool(
        sleeper_players=(
            sleeper_players
        ),
        league_data=(
            league_data
        ),
        team_setups=(
            team_setups
        ),
    )
)


restart_recovery_key = runtime_identity.private_key("restart_recovery_complete")
if (
    VIEW_REQUIREMENTS.live_draft
    and is_sleeper_backed_league
    and not st.session_state.get(restart_recovery_key, False)
):
    try:
        restart_picks = load_optional_feed(
            "Sleeper draft results",
            lambda: SleeperClient().get_draft_picks(ACTIVE_DRAFT_ID),
            [],
            validator=lambda value: isinstance(value, list),
        )
        recovery_result = recover_draft_state(
            draft_store=draft_store,
            draft_picks=restart_picks.data,
            starting_team_setups=team_setups,
            starting_pool_players=pool_result.available_players,
            sleeper_players=sleeper_players,
            managers=ACTIVE_MANAGERS,
        )
        live_sales = list(recovery_result.sales)
        st.session_state[restart_recovery_key] = True
        if restart_picks.error:
            st.warning(
                "Sleeper restart reconciliation is using the persisted local "
                "ledger: {0}".format(restart_picks.error)
            )
        if recovery_result.changes:
            st.info(
                "Recovered and reconciled {0} Sleeper sale(s).".format(
                    len(recovery_result.changes)
                )
            )
        for warning in recovery_result.warnings:
            st.warning(warning)
    except Exception as error:
        st.warning(
            "Draft restart reconciliation was unavailable; using the "
            "persisted local ledger. {0}".format(error)
        )


starting_total_auction_cash = sum(
    setup.auction_cash

    for setup
    in team_setups.values()
)


pre_draft_readiness = build_pre_draft_readiness(
    league_profile=ACTIVE_LEAGUE_PROFILE,
    league_setup_data=league_setup_data,
    team_setups=team_setups,
    persisted_setup=persisted_setup,
    sleeper_player_count=len(sleeper_players),
    projection_count=len(projection_index),
    setup_source_summary=setup_source_summary,
    workbook_loaded=workbook_loaded,
)


# =========================================================
# KEEPER RECOMMENDATIONS
# =========================================================

keeper_recommendations = []
keeper_recommendations_by_manager = {}
keeper_recommendation_warnings = []
keeper_optimization_result = None
keeper_trade_candidate_result = None


if strategy_profile is not None:

    my_starting_setup = team_setups.get(
        ACTIVE_MY_MANAGER_ID
    )

    keeper_batch = build_keeper_recommendations(
        keeper_records=league_setup_data.keepers_for(
            ACTIVE_MY_MANAGER_ID
        ),
        league_profile=ACTIVE_LEAGUE_PROFILE,
        strategy_profile=strategy_profile,
        player_values=player_values,
        fantasypros_index=fantasypros_index,
        sleeper_players=sleeper_players,
        auction_budget=(
            my_starting_setup.pre_keeper_budget
            if my_starting_setup is not None
            else ACTIVE_LEAGUE_PROFILE.auction.base_budget
        ),
    )

    keeper_recommendations = list(
        keeper_batch.recommendations
    )
    keeper_recommendation_warnings = list(
        keeper_batch.warnings
    )

    # Best 4/5/6 keeper-combination search and cross-manager trade
    # candidates were removed to cut Pre-Draft load time -- both required
    # running the full keeper-recommendation engine for every opponent
    # (or an exhaustive combination search) on every rerun.
    keeper_recommendations_by_manager = {
        ACTIVE_MY_MANAGER_ID: list(keeper_recommendations)
    }


if not VIEW_REQUIREMENTS.live_draft:

    inactive_live_context = build_view_runtime(
        ACTIVE_DRAFT_ID=str(ACTIVE_DRAFT_ID),
        ACTIVE_LEAGUE_PROFILE=ACTIVE_LEAGUE_PROFILE,
        ACTIVE_MANAGERS=ACTIVE_MANAGERS,
        ACTIVE_MY_MANAGER_ID=ACTIVE_MY_MANAGER_ID,
        selected_league=selected_league,
        runtime_identity=runtime_identity,
        strategy_profile=strategy_profile,
        strategy_profile_store=strategy_profile_store,
        my_guys_preferences=my_guys_preferences,
        my_guys_store=my_guys_store,
        planning_preferences=planning_preferences,
        planning_preferences_store=planning_preferences_store,
        private_state_access=private_state_access,
        league_data=league_data,
        league_setup_data=league_setup_data,
        league_setup_store=league_setup_store,
        league_registry=league_registry,
        manual_setup_data=(
            manual_setup_data
            if manual_setup_loaded
            else None
        ),
        manual_setup_loaded=manual_setup_loaded,
        persisted_setup=persisted_setup,
        setup_locked=setup_locked,
        setup_rows=setup_rows,
        setup_source_summary=setup_source_summary,
        workbook_loaded=workbook_loaded,
        keeper_recommendations=keeper_recommendations,
        keeper_recommendations_by_manager=keeper_recommendations_by_manager,
        keeper_recommendation_warnings=(
            keeper_recommendation_warnings
        ),
        keeper_optimization_result=keeper_optimization_result,
        keeper_trade_candidate_result=keeper_trade_candidate_result,
        pre_draft_readiness=pre_draft_readiness,
        ranking_ensemble=ranking_ensemble,
        manager_tendency_model=manager_tendency_model,
        draft_store=draft_store,
        sleeper_players=sleeper_players,
        fantasypros_data=fantasypros_data,
        fantasypros_index=fantasypros_index,
        projection_index=projection_index,
        player_value_index=player_value_index,
        player_values=player_values,
        historical_market_model=historical_market_model,
        pool_result=pool_result,
        team_setups=team_setups,
        live_sales=live_sales,
        starting_total_auction_cash=starting_total_auction_cash,
        render_league_setup_editor=render_league_setup_editor,
        run_draft_simulation=run_draft_simulation,
    )

    render_active_view(
        ACTIVE_VIEW,
        inactive_live_context,
    )

    st.stop()


# =========================================================
# LIVE TEAM STATE
# =========================================================

try:

    live_team_setups = (
        build_live_team_setups(
            starting_team_setups=(
                team_setups
            ),
            sales=(
                live_sales
            ),
        )
    )

except ValueError as error:

    st.error(
        "The persisted ledger is incompatible "
        "with the current pre-draft setup."
    )

    st.error(
        str(
            error
        )
    )


    if st.button(
        "Reset Persisted Live Sales"
    ):

        draft_store.reset_sales()

        st.rerun()


    st.stop()


# =========================================================
# AVAILABLE PLAYERS
# =========================================================

available_players = (
    filter_sold_players(
        available_players=(
            pool_result.available_players
        ),
        sales=(
            live_sales
        ),
    )
)


# =========================================================
# LIVE ECONOMY
# =========================================================

live_total_cash = sum(
    setup.auction_cash

    for setup
    in live_team_setups.values()
)


live_open_spots = sum(
    setup.open_roster_spots

    for setup
    in live_team_setups.values()
)


live_reserve = sum(
    setup.required_reserve
    for setup in live_team_setups.values()
)


live_discretionary = sum(
    setup.discretionary_cash
    for setup in live_team_setups.values()
)


room_spend_index = (
    calculate_room_spend_index(
        live_sales
    )
)


# =========================================================
# LIVE LEARNING
# =========================================================

live_calibration = (
    build_live_market_calibration(
        live_sales
    )
)


# =========================================================
# AUCTION VALUES
# =========================================================

auction_values = []


if (
    available_players
    and
    projections
    and
    fantasypros_index
):

    auction_values = (
        calculate_auction_values(
            available_players=(
                available_players
            ),
            team_setups=(
                live_team_setups
            ),
            player_values=(
                player_values
            ),
            projection_index=(
                projection_index
            ),
            fantasypros_index=(
                fantasypros_index
            ),
        )
    )


auction_value_index = {
    normalize_player_name(
        value.player_name
    ): value

    for value
    in auction_values
}


# =========================================================
# HISTORICAL + LIVE MARKET
# =========================================================

market_values = []


if auction_values:

    market_values = (
        calculate_historical_market_values(
            auction_values=(
                auction_values
            ),
            historical_model=(
                historical_market_model
            ),
            current_total_auction_cash=(
                starting_total_auction_cash
            ),
        )
    )


    market_values = (
        apply_live_market_calibration(
            market_values=(
                market_values
            ),
            auction_values=(
                auction_values
            ),
            calibration=(
                live_calibration
            ),
        )
    )


market_value_index = {
    normalize_player_name(
        value.player_name
    ): value

    for value
    in market_values
}

inflation_v2 = calculate_live_room_inflation(
    live_sales=live_sales,
    expected_values=market_value_index,
)


# =========================================================
# TEAM NEEDS
# =========================================================

team_need_profiles = (
    build_team_need_profiles(
        team_setups=(
            live_team_setups
        ),
        sleeper_players=(
            sleeper_players
        ),
    )
)

opponent_target_profiles = build_opponent_target_profiles(
    team_need_profiles=team_need_profiles,
    current_manager_id=ACTIVE_MY_MANAGER_ID,
    manager_tendency_profiles=manager_tendency_model.profiles,
)

run_hot_result = detect_run_hot(
    opponent_profiles=opponent_target_profiles,
    available_tier_counts=build_available_tier_counts(market_values),
)


# =========================================================
# BIDDER THREATS
# =========================================================

threat_summaries = []


if auction_values:

    threat_summaries = (
        calculate_bidder_threats(
            available_players=(
                available_players
            ),
            auction_values=(
                auction_values
            ),
            market_values=(
                market_values
            ),
            team_need_profiles=(
                team_need_profiles
            ),
            historical_model=(
                historical_market_model
            ),
            excluded_manager_id=(
                ACTIVE_MY_MANAGER_ID
            ),
        )
    )


    threat_summaries = (
        apply_live_manager_threat_adjustments(
            threat_summaries=(
                threat_summaries
            ),
            calibration=(
                live_calibration
            ),
        )
    )


threat_index = (
    build_threat_index(
        threat_summaries
    )
)


# =========================================================
# RECOMMENDATIONS
# =========================================================

recommendations = []


if auction_values:

    recommendations = (
        calculate_bid_recommendations(
            available_players=(
                available_players
            ),
            auction_values=(
                auction_values
            ),
            market_values=(
                market_values
            ),
            player_values=(
                player_values
            ),
            threat_summaries=(
                threat_summaries
            ),
            team_need_profiles=(
                team_need_profiles
            ),
            my_manager_id=(
                ACTIVE_MY_MANAGER_ID
            ),
            run_hot_position_pressure=run_hot_result.position_pressure,
        )
    )


recommendation_index = (
    build_recommendation_index(
        recommendations
    )
)


# =========================================================
# NOMINATION STRATEGY
# =========================================================

nomination_recommendations = []


if recommendations:

    nomination_recommendations = (
        calculate_nomination_recommendations(
            recommendations=(
                recommendations
            ),
            threat_summaries=(
                threat_summaries
            ),
            market_values=(
                market_values
            ),
            live_team_setups=(
                live_team_setups
            ),
            live_calibration=(
                live_calibration
            ),
            my_manager_id=(
                ACTIVE_MY_MANAGER_ID
            ),
        )
    )


nomination_index = (
    build_nomination_index(
        nomination_recommendations
    )
)


# =========================================================
# ROSTER OPTIMIZER
# =========================================================

optimization_candidates = []


if auction_values:

    optimization_candidates = (
        build_optimization_candidates(
            available_players=(
                available_players
            ),
            auction_values=(
                auction_values
            ),
            market_values=(
                market_values
            ),
            recommendations=(
                recommendations
            ),
            player_values=(
                player_values
            ),
        )
    )


my_live_setup = (
    live_team_setups.get(
        ACTIVE_MY_MANAGER_ID
    )
)


my_need_profile = (
    team_need_profiles.get(
        ACTIVE_MY_MANAGER_ID
    )
)


optimal_roster_plan = None


if (
    my_live_setup
    and
    my_need_profile
    and
    optimization_candidates
):

    optimal_roster_plan = (
        optimize_remaining_roster(
            my_team_setup=(
                my_live_setup
            ),
            my_need_profile=(
                my_need_profile
            ),
            candidates=(
                optimization_candidates
            ),
        )
    )























# =========================================================
# ACTIVE VIEW RUNTIME CONTEXT
# =========================================================

view_context = AppRuntimeContext(
    ACTIVE_DRAFT_ID=str(
        ACTIVE_DRAFT_ID
    ),
    ACTIVE_LEAGUE_PROFILE=(
        ACTIVE_LEAGUE_PROFILE
    ),
    ACTIVE_MANAGERS=(
        ACTIVE_MANAGERS
    ),
    ACTIVE_MY_MANAGER_ID=(
        ACTIVE_MY_MANAGER_ID
    ),
    selected_league=(
        selected_league
    ),
    runtime_identity=(
        runtime_identity
    ),
    strategy_profile=(
        strategy_profile
    ),
    strategy_profile_store=(
        strategy_profile_store
    ),
    my_guys_preferences=my_guys_preferences,
    my_guys_store=my_guys_store,
    planning_preferences=planning_preferences,
    planning_preferences_store=planning_preferences_store,
    private_state_access=private_state_access,
    league_data=(
        league_data
    ),
    league_setup_data=(
        league_setup_data
    ),
    league_setup_store=(
        league_setup_store
    ),
    league_registry=(
        league_registry
    ),
    manual_setup_data=(
        manual_setup_data
        if manual_setup_loaded
        else None
    ),
    manual_setup_loaded=(
        manual_setup_loaded
    ),
    persisted_setup=(
        persisted_setup
    ),
    setup_locked=(
        setup_locked
    ),
    setup_rows=(
        setup_rows
    ),
    setup_source_summary=(
        setup_source_summary
    ),
    workbook_loaded=(
        workbook_loaded
    ),
    keeper_recommendations=(
        keeper_recommendations
    ),
    keeper_recommendations_by_manager=(
        keeper_recommendations_by_manager
    ),
    keeper_recommendation_warnings=(
        keeper_recommendation_warnings
    ),
    keeper_optimization_result=(
        keeper_optimization_result
    ),
    keeper_trade_candidate_result=(
        keeper_trade_candidate_result
    ),
    pre_draft_readiness=pre_draft_readiness,
    ranking_ensemble=ranking_ensemble,
    manager_tendency_model=manager_tendency_model,
    context_store=(
        context_store
    ),
    draft_store=(
        draft_store
    ),
    sleeper_players=(
        sleeper_players
    ),
    fantasypros_data=(
        fantasypros_data
    ),
    fantasypros_index=(
        fantasypros_index
    ),
    projection_index=(
        projection_index
    ),
    player_value_index=(
        player_value_index
    ),
    player_values=(
        player_values
    ),
    auction_value_index=(
        auction_value_index
    ),
    market_value_index=(
        market_value_index
    ),
    historical_market_model=(
        historical_market_model
    ),
    depth_chart_documents=(
        depth_chart_documents
    ),
    depth_chart_error=(
        depth_chart_error
    ),
    depth_chart_taken_players=[],
    snake_draft_state=None,
    snake_draft_error=None,
    depth_movement_error=(
        depth_movement_error
    ),
    depth_movement_result=(
        depth_movement_result
    ),
    pool_result=(
        pool_result
    ),
    team_setups=(
        team_setups
    ),
    available_players=(
        available_players
    ),
    live_sales=(
        live_sales
    ),
    live_team_setups=(
        live_team_setups
    ),
    team_need_profiles=(
        team_need_profiles
    ),
    opponent_target_profiles=opponent_target_profiles,
    run_hot_result=run_hot_result,
    my_live_setup=(
        my_live_setup
    ),
    my_need_profile=(
        my_need_profile
    ),
    starting_total_auction_cash=(
        starting_total_auction_cash
    ),
    live_total_cash=(
        live_total_cash
    ),
    live_open_spots=(
        live_open_spots
    ),
    live_discretionary=(
        live_discretionary
    ),
    room_spend_index=(
        room_spend_index
    ),
    inflation_v2=inflation_v2,
    live_calibration=(
        live_calibration
    ),
    recommendations=(
        recommendations
    ),
    recommendation_index=(
        recommendation_index
    ),
    nomination_recommendations=(
        nomination_recommendations
    ),
    nomination_index=(
        nomination_index
    ),
    threat_index=(
        threat_index
    ),
    optimization_candidates=(
        optimization_candidates
    ),
    optimal_roster_plan=(
        optimal_roster_plan
    ),
    SleeperClient=(
        SleeperClient
    ),
    add_live_sale=(
        add_live_sale
    ),
    calculate_context_valuation_adjustment=(
        calculate_context_valuation_adjustment
    ),
    calculate_roster_aware_ceiling=(
        calculate_roster_aware_ceiling
    ),
    compare_buy_vs_pass=(
        compare_buy_vs_pass
    ),
    get_targeted_player_context=(
        get_targeted_player_context
    ),
    normalize_player_name=(
        normalize_player_name
    ),
    render_league_setup_editor=(
        render_league_setup_editor
    ),
    run_draft_simulation=(
        run_draft_simulation
    ),
    sync_next_sleeper_sale=(
        sync_next_sleeper_sale
    ),
)


# =========================================================
# ACTIVE VIEW RENDER
# =========================================================

render_active_view(
    ACTIVE_VIEW,
    view_context,
)
