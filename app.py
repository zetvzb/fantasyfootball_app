from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import (
    SEASON,
    SLEEPER_DRAFT_ID,
    SLEEPER_LEAGUE_ID,
)

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
    build_view_runtime,
    requirements_for_view,
)
from src.league_registry import LeagueRegistry
from src.league_management_ui import (
    render_add_sleeper_league,
)
from src.league_profile import (
    infer_league_profile_from_sleeper,
)
from src.sleeper_client import SleeperClient
from src.draft_setup import build_team_draft_setup_from_setup_data
from src.workbook_enrichment import enrich_setup_from_optional_workbook
from src.college_domain import apply_college_rules
from src.runtime_identity import (
    private_state_key,
    resolve_runtime_identity,
)
from src.strategy_profile import (
    StrategyProfile,
    StrategyProfileStore,
)
from src.keeper_recommendation import (
    build_keeper_recommendations,
)
from src.keeper_optimizer import (
    KeeperOptimizationInput,
    optimize_keeper_combinations,
)
from src.keeper_trade_candidates import (
    recommend_keeper_trade_candidates,
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

from src.projections import (
    build_projection_index,
    normalize_fantasypros_projections,
)

from src.valuation import (
    calculate_player_values,
    calculate_replacement_levels,
)

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
    page_title="Fantasy Auction Copilot",
    page_icon="🏈",
    layout="wide",
)


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

DB_PATH = "data/draft_state.db"
CONTEXT_DB_PATH = "data/player_context.db"

LEAGUE_REGISTRY_PATH = (
    APP_ROOT
    / "data"
    / "leagues"
)

league_registry = LeagueRegistry(
    root=LEAGUE_REGISTRY_PATH
)


LEAGUE_SETUP_PATH = (
    APP_ROOT
    / "data"
    / "league_setup"
)

league_setup_store = LeagueSetupStore(
    root=LEAGUE_SETUP_PATH
)


STRATEGY_PROFILE_PATH = (
    APP_ROOT
    / "data"
    / "strategy_profiles"
)


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

    client = FantasyProsClient()

    rankings_response = (
        client.get_rankings(
            season=season,
            week=0,
        )
    )

    players_response = (
        client.get_players_with_ecr()
    )

    projection_response = (
        client.get_preseason_projections(
            season=season
        )
    )

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

    return {
        "rankings_response": rankings_response,
        "players_response": players_response,
        "projection_response": projection_response,
        "intelligence": intelligence,
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

current_league_key = str(
    SLEEPER_LEAGUE_ID
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
                "college": {
                    "enabled": True,
                    "max_college_players": 6,
                    "pre_draft_promotion_cost": 1,
                    "during_draft_promotion_cost": 0,
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
configured_user_key = "single-user"


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


default_league_key = (
    current_league_profile.league_key
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


    render_add_sleeper_league(
        **add_league_kwargs
    )


# =========================================================
# APP NAVIGATION
# =========================================================

APP_VIEWS = [
    "🏠 League Setup",
    "🧭 Pre-Draft",
    "🚨 Draft Mode",
    "📚 Draft History",
]


ACTIVE_VIEW = st.sidebar.radio(
    "View",
    options=APP_VIEWS,
    index=2,
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

if VIEW_REQUIREMENTS.live_draft:

    context_store = ContextStore(
        db_path=CONTEXT_DB_PATH
    )

    depth_chart_tracker = (
        DepthChartMovementTracker(
            db_path=CONTEXT_DB_PATH
        )
    )


st.sidebar.divider()


# =========================================================
# ACTIVE LEAGUE RUNTIME
# =========================================================

if (
    selected_league.source_mode
    != "sleeper"
):

    st.error(
        "The selected league is not a Sleeper-backed "
        "profile yet. Manual league runtime support will "
        "be added in the setup workflow."
    )

    st.stop()


ACTIVE_LEAGUE_ID = (
    selected_league.sleeper_league_id
)

ACTIVE_DRAFT_ID = (
    selected_league.sleeper_draft_id
)

ACTIVE_SEASON = int(
    selected_league.season
)


if not ACTIVE_LEAGUE_ID:

    st.error(
        "The selected league profile does not contain "
        "a Sleeper league ID."
    )

    st.stop()


if not ACTIVE_DRAFT_ID:

    st.error(
        "The selected league profile does not contain "
        "a Sleeper draft ID."
    )

    st.stop()


# Reuse the already-loaded configured league when possible.
if (
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
):

    if bootstrap_sleeper_data is not None:

        sleeper_data = bootstrap_sleeper_data

    else:

        try:

            sleeper_data = load_sleeper_data(
                ACTIVE_LEAGUE_ID,
                ACTIVE_DRAFT_ID,
            )

        except Exception as error:

            st.error(
                f"Selected Sleeper league failed: {error}"
            )

            st.stop()

else:

    try:

        sleeper_data = (
            load_sleeper_data(
                ACTIVE_LEAGUE_ID,
                ACTIVE_DRAFT_ID,
            )
        )

    except Exception as error:

        st.error(
            f"Selected Sleeper league failed: "
            f"{error}"
        )

        st.stop()


st.sidebar.caption(
    f"Sleeper league: "
    f"{ACTIVE_LEAGUE_ID}"
)


st.sidebar.caption(
    f"Draft: "
    f"{ACTIVE_DRAFT_ID}"
)


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
        APP_ROOT
        / "data"
        / "draft_state.db"
    )

else:

    draft_state_directory = (
        APP_ROOT
        / "data"
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


    active_draft_db_path = (
        draft_state_directory
        / (
            f"{safe_league_key}_"
            f"{ACTIVE_DRAFT_ID}.db"
        )
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
            else None
        ),
    )

except ValueError as error:

    st.error(
        str(error)
    )

    st.stop()


ACTIVE_MY_MANAGER_ID = runtime_identity.current.manager_id


ACTIVE_MY_IDENTITY = (
    ACTIVE_MANAGERS[
        ACTIVE_MY_MANAGER_ID
    ]
)


ACTIVE_LEAGUE_PROFILE = (
    replace(
        selected_league,
        managers=(
            ACTIVE_MANAGERS
        ),
    )
)


strategy_profile_store = None
strategy_profile = None


if VIEW_REQUIREMENTS.pre_draft_intelligence:

    strategy_profile_store = StrategyProfileStore(
        root=STRATEGY_PROFILE_PATH
    )

    try:

        strategy_profile = strategy_profile_store.load(
            league_key=runtime_identity.league.league_key,
            user_key=runtime_identity.current.user_key,
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


st.sidebar.caption(
    f"My team: "
    f"{ACTIVE_MY_IDENTITY.sleeper_team_name}"
)


# Per-league Streamlit state prevents keeper/setup selections
# from leaking between leagues that happen to use the same
# manager IDs.
KEEPER_SELECTIONS_STATE_KEY = (
    runtime_identity.private_key(
        "keeper_selections"
    )
)

COLLEGE_PROMOTIONS_STATE_KEY = (
    runtime_identity.private_key(
        "college_promotions"
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

        league_setup_data = (
            league_setup_data
            .merged_with(
                manual_setup_data
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


try:

    league_setup_data = apply_college_rules(
        league_profile=ACTIVE_LEAGUE_PROFILE,
        setup_data=league_setup_data,
    )

except ValueError as error:

    st.error(
        "College/devy setup is invalid: {0}".format(error)
    )

    st.stop()


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
    f"College records: "
    f"{len(league_setup_data.college_players)}"
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
}


if VIEW_REQUIREMENTS.pre_draft_intelligence:

    try:

        fantasypros_data = (
            load_fantasypros_data(
                ACTIVE_SEASON
            )
        )

    except Exception as error:

        fantasypros_error = str(
            error
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


projection_response = (
    fantasypros_data[
        "projection_response"
    ]
)


if projection_response:

    projections = (
        normalize_fantasypros_projections(
            response=(
                projection_response
            ),
            scoring_settings=(
                league.get(
                    "scoring_settings",
                    {},
                )
            ),
        )
    )

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


if (
    VIEW_REQUIREMENTS.live_draft
    and
    fantasypros_data[
    "intelligence"
    ]
):

    try:

        context_api_data = (
            load_fantasypros_context_data(
                ACTIVE_SEASON
            )
        )


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


        if current_context_documents:

            context_store.add_documents(
                current_context_documents
            )


    except Exception as error:

        context_error = str(
            error
        )


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


# =========================================================
# VORP
# =========================================================

replacement_levels = None
player_values = []
player_value_index = {}


if projections:

    replacement_levels = (
        calculate_replacement_levels(
            projections
        )
    )


    player_values = (
        calculate_player_values(
            projections=(
                projections
            ),
            replacement_levels=(
                replacement_levels
            ),
        )
    )


    player_value_index = {
        normalize_player_name(
            value.player_name
        ): value

        for value
        in player_values
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


# =========================================================
# LOAD PERSISTED DRAFT STATE
# =========================================================

persisted_setup = (
    draft_store.load_team_setups()
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


if (
    COLLEGE_PROMOTIONS_STATE_KEY
    not in st.session_state
):

    st.session_state[
        COLLEGE_PROMOTIONS_STATE_KEY
    ] = {}

    for manager_id in ACTIVE_MANAGERS:

        saved = (
            persisted_setup.get(
                manager_id,
                {},
            )
        )

        st.session_state[
            COLLEGE_PROMOTIONS_STATE_KEY
        ][
            manager_id
        ] = saved.get(
            "college_promotions",
            [],
        )


SALE_INPUT_MODE_STATE_KEY = runtime_identity.private_key("sale_input_mode")
SLEEPER_POLL_STATE_KEY = runtime_identity.private_key("sleeper_poll_seconds")
AUTO_SLEEPER_SYNC_STATE_KEY = runtime_identity.private_key("auto_sleeper_sync")


if (
    SALE_INPUT_MODE_STATE_KEY
    not in st.session_state
):

    st.session_state[
        SALE_INPUT_MODE_STATE_KEY
    ] = "Sleeper Live Sync"


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
    ] = True


# =========================================================
# HEADER
# =========================================================

st.title(
    "🏈 Fantasy Auction Copilot"
)

st.caption(
    f"{league.get('name')} • "
    f"{ACTIVE_SEASON} • "
    f"{ACTIVE_VIEW}"
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header(
        "Draft Controls"
    )


    if st.button(
        "Refresh Sleeper Data",
        width="stretch",
    ):

        load_sleeper_data.clear()

        st.rerun()


    if st.button(
        "Refresh FantasyPros",
        width="stretch",
    ):

        load_fantasypros_data.clear()
        load_fantasypros_context_data.clear()
        load_player_context_data.clear()

        st.rerun()


    if st.button(
        "Refresh News + Injuries",
        width="stretch",
    ):

        load_fantasypros_context_data.clear()
        load_player_context_data.clear()

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


    st.divider()


    st.subheader(
        "Data"
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
        f"College records: "
        f"**{len(league_setup_data.college_players)}**"
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
            draft_store=draft_store,
            live_sales=live_sales,
            historical_market_model=historical_market_model,
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


    selected_promotions = list(
        saved_setup.get(
            "college_promotions",
            [],
        )
        or []
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
                college_promotions=(
                    selected_promotions
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
                college_promotions=(
                    selected_promotions
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


        college_rights = (
            league_setup_data
            .college_for(
                manager_id
            )
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
                "Traded $": (
                    setup.traded_dollars
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
                "College / Devy": len(
                    college_rights
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


starting_total_auction_cash = sum(
    setup.auction_cash

    for setup
    in team_setups.values()
)


# =========================================================
# KEEPER RECOMMENDATIONS
# =========================================================

keeper_recommendations = []
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

    keeper_optimization_result = optimize_keeper_combinations(
        KeeperOptimizationInput(
            manager_id=ACTIVE_MY_MANAGER_ID,
            recommendations=tuple(keeper_recommendations),
            strategy_profile=strategy_profile,
            pre_keeper_budget=(
                my_starting_setup.pre_keeper_budget
                if my_starting_setup is not None
                else ACTIVE_LEAGUE_PROFILE.auction.base_budget
            ),
            roster_size=(
                my_starting_setup.roster_size
                if my_starting_setup is not None
                else ACTIVE_LEAGUE_PROFILE.roster.roster_size
            ),
            minimum_bid=(
                my_starting_setup.minimum_auction_bid
                if my_starting_setup is not None
                else ACTIVE_LEAGUE_PROFILE.auction.minimum_bid
            ),
            max_keepers=ACTIVE_LEAGUE_PROFILE.keepers.max_keepers,
            starting_lineup=tuple(
                ACTIVE_LEAGUE_PROFILE.roster.starting_lineup
            ),
            college_promotion_count=(
                my_starting_setup.college_promotion_count
                if my_starting_setup is not None
                else 0
            ),
            college_promotion_cost=(
                my_starting_setup.college_promotion_cost
                if my_starting_setup is not None
                else ACTIVE_LEAGUE_PROFILE.college.during_draft_promotion_cost
            ),
        )
    )

    opponent_recommendations = []
    opponent_recommendation_warnings = []
    manager_names = {}
    for manager_id, identity in ACTIVE_MANAGERS.items():
        manager_names[manager_id] = (
            identity.sleeper_team_name
            or identity.sleeper_username
            or manager_id
        )
        if manager_id == ACTIVE_MY_MANAGER_ID:
            continue

        opponent_setup = team_setups.get(manager_id)
        opponent_batch = build_keeper_recommendations(
            keeper_records=league_setup_data.keepers_for(manager_id),
            league_profile=ACTIVE_LEAGUE_PROFILE,
            strategy_profile=strategy_profile,
            player_values=player_values,
            fantasypros_index=fantasypros_index,
            sleeper_players=sleeper_players,
            auction_budget=(
                opponent_setup.pre_keeper_budget
                if opponent_setup is not None
                else ACTIVE_LEAGUE_PROFILE.auction.base_budget
            ),
        )
        opponent_recommendations.extend(opponent_batch.recommendations)
        opponent_recommendation_warnings.extend(
            "{0}: {1}".format(manager_names[manager_id], warning)
            for warning in opponent_batch.warnings
        )

    keeper_trade_candidate_result = recommend_keeper_trade_candidates(
        recommendations=opponent_recommendations,
        current_manager_id=ACTIVE_MY_MANAGER_ID,
        manager_names=manager_names,
    )
    if opponent_recommendation_warnings:
        keeper_trade_candidate_result = replace(
            keeper_trade_candidate_result,
            warnings=(
                tuple(opponent_recommendation_warnings)
                + keeper_trade_candidate_result.warnings
            ),
        )


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
        league_data=league_data,
        league_setup_data=league_setup_data,
        league_setup_store=league_setup_store,
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
        keeper_recommendation_warnings=(
            keeper_recommendation_warnings
        ),
        keeper_optimization_result=keeper_optimization_result,
        keeper_trade_candidate_result=keeper_trade_candidate_result,
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
    league_data=(
        league_data
    ),
    league_setup_data=(
        league_setup_data
    ),
    league_setup_store=(
        league_setup_store
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
    keeper_recommendation_warnings=(
        keeper_recommendation_warnings
    ),
    keeper_optimization_result=(
        keeper_optimization_result
    ),
    keeper_trade_candidate_result=(
        keeper_trade_candidate_result
    ),
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
