import pandas as pd
import streamlit as st

from src.config import (
    SEASON,
    SLEEPER_DRAFT_ID,
    SLEEPER_LEAGUE_ID,
)

from src.league_config import (
    MANAGERS,
    MY_MANAGER_ID,
    MINIMUM_AUCTION_BID,
)

from src.league_data import LeagueDataLoader
from src.sleeper_client import SleeperClient
from src.draft_setup import build_team_draft_setup

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


# =========================================================
# STREAMLIT CONFIG
# =========================================================

st.set_page_config(
    page_title="Fantasy Auction Copilot",
    page_icon="🏈",
    layout="wide",
)


# =========================================================
# CONSTANTS
# =========================================================

DB_PATH = "data/draft_state.db"
CONTEXT_DB_PATH = "data/player_context.db"


# =========================================================
# PERSISTENT STORES
# =========================================================

draft_store = DraftStore(
    db_path=DB_PATH,
    league_id=SLEEPER_LEAGUE_ID,
    draft_id=SLEEPER_DRAFT_ID,
    season=SEASON,
)


context_store = ContextStore(
    db_path=CONTEXT_DB_PATH
)


# =========================================================
# DATA LOADERS
# =========================================================

@st.cache_data(ttl=300)
def load_sleeper_data():

    client = SleeperClient()

    return {
        "league": client.get_league(
            SLEEPER_LEAGUE_ID
        ),
        "users": client.get_league_users(
            SLEEPER_LEAGUE_ID
        ),
        "rosters": client.get_league_rosters(
            SLEEPER_LEAGUE_ID
        ),
        "draft": client.get_draft(
            SLEEPER_DRAFT_ID
        ),
        "players": client.get_players(),
    }


@st.cache_data
def load_league_workbook():

    loader = LeagueDataLoader(
        "data/league.xlsx"
    )

    return loader.load()


@st.cache_data(ttl=3600)
def load_fantasypros_data():

    client = FantasyProsClient()

    rankings_response = (
        client.get_rankings(
            season=SEASON,
            week=0,
        )
    )

    players_response = (
        client.get_players_with_ecr()
    )

    projection_response = (
        client.get_preseason_projections(
            season=SEASON
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


# =========================================================
# LEAGUE-WIDE CONTEXT REFRESH
# =========================================================

@st.cache_data(ttl=900)
def load_fantasypros_context_data():

    client = FantasyProsClient()

    news_response = (
        client.get_news(
            limit=100
        )
    )

    injury_response = (
        client.get_injuries(
            season=SEASON
        )
    )

    return {
        "news": news_response,
        "injuries": injury_response,
    }


# =========================================================
# TARGETED PLAYER CONTEXT
# =========================================================

@st.cache_data(ttl=900)
def load_player_context_data(
    fantasypros_id,
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
            season=SEASON,
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
# LOAD SOURCE DATA
# =========================================================

try:

    sleeper_data = (
        load_sleeper_data()
    )

except Exception as error:

    st.error(
        f"Sleeper failed: {error}"
    )

    st.stop()


try:

    league_data = (
        load_league_workbook()
    )

except Exception as error:

    st.error(
        f"Workbook failed: {error}"
    )

    st.stop()


fantasypros_error = None


try:

    fantasypros_data = (
        load_fantasypros_data()
    )

except Exception as error:

    fantasypros_error = str(
        error
    )

    fantasypros_data = {
        "rankings_response": {},
        "players_response": {},
        "projection_response": {},
        "intelligence": [],
    }


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
# LEAGUE-WIDE PLAYER CONTEXT INGESTION
# =========================================================

context_error = None
current_context_documents = []


if fantasypros_data[
    "intelligence"
]:

    try:

        context_api_data = (
            load_fantasypros_context_data()
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
    "keeper_selections"
    not in st.session_state
):

    st.session_state[
        "keeper_selections"
    ] = {}

    for manager_id in MANAGERS:

        saved = (
            persisted_setup.get(
                manager_id,
                {},
            )
        )

        st.session_state[
            "keeper_selections"
        ][
            manager_id
        ] = saved.get(
            "keepers",
            [],
        )


if (
    "college_promotions"
    not in st.session_state
):

    st.session_state[
        "college_promotions"
    ] = {}

    for manager_id in MANAGERS:

        saved = (
            persisted_setup.get(
                manager_id,
                {},
            )
        )

        st.session_state[
            "college_promotions"
        ][
            manager_id
        ] = saved.get(
            "college_promotions",
            [],
        )


if (
    "sale_input_mode"
    not in st.session_state
):

    st.session_state[
        "sale_input_mode"
    ] = (
        "Sleeper Live Sync"
    )


if (
    "sleeper_poll_seconds"
    not in st.session_state
):

    st.session_state[
        "sleeper_poll_seconds"
    ] = 5


if (
    "auto_sleeper_sync"
    not in st.session_state
):

    st.session_state[
        "auto_sleeper_sync"
    ] = True


# =========================================================
# HEADER
# =========================================================

st.title(
    "🏈 Fantasy Auction Copilot"
)

st.caption(
    f"{league.get('name')} • {SEASON}"
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
        use_container_width=True,
    ):

        load_sleeper_data.clear()

        st.rerun()


    if st.button(
        "Refresh FantasyPros",
        use_container_width=True,
    ):

        load_fantasypros_data.clear()
        load_player_context_data.clear()

        st.rerun()


    if st.button(
        "Refresh News + Injuries",
        use_container_width=True,
    ):

        load_fantasypros_context_data.clear()
        load_player_context_data.clear()

        st.rerun()


    if st.button(
        "Reload Workbook",
        use_container_width=True,
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
        DB_PATH
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
        f"**{context_store.count()}**"
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


# =========================================================
# PRE-DRAFT SETUP
# =========================================================

st.subheader(
    "⚙️ Pre-Draft Setup"
)


if setup_locked:

    st.info(
        "Keeper and college selections are locked "
        "because the auction has started. "
        "Reset live sales before changing them."
    )

else:

    st.caption(
        "Keeper and college selections are "
        "automatically persisted to SQLite."
    )


team_setups = {}


for (
    manager_id,
    identity,
) in MANAGERS.items():

    manager_data = (
        league_data.managers.get(
            manager_id
        )
    )


    if manager_data is None:

        continue


    with st.expander(
        identity.sleeper_team_name
    ):

        # =================================================
        # KEEPERS
        # =================================================

        keeper_lookup = {
            keeper.player_name: keeper

            for keeper
            in manager_data.keeper_options

            if keeper.keeper_cost
            is not None
        }


        keeper_names = list(
            keeper_lookup.keys()
        )


        current_keepers = [
            player_name

            for player_name
            in (
                st.session_state[
                    "keeper_selections"
                ].get(
                    manager_id,
                    [],
                )
            )

            if player_name
            in keeper_names
        ]


        selected_keepers = (
            st.multiselect(
                "Keepers",
                options=(
                    keeper_names
                ),
                default=(
                    current_keepers
                ),
                max_selections=6,
                disabled=(
                    setup_locked
                ),
                format_func=lambda name: (
                    f"{name} "
                    f"({keeper_lookup[name].position}) "
                    f"— ${keeper_lookup[name].keeper_cost}"
                ),
                key=(
                    f"keepers_{manager_id}"
                ),
            )
        )


        st.session_state[
            "keeper_selections"
        ][
            manager_id
        ] = selected_keepers


        # =================================================
        # COLLEGE PROMOTIONS
        # =================================================

        nfl_college_players = [
            player

            for player
            in league_data.college_players

            if (
                player.manager_id
                == manager_id
                and
                player.status
                == "in_nfl"
            )
        ]


        college_names = [
            player.player_name

            for player
            in nfl_college_players
        ]


        current_promotions = [
            player_name

            for player_name
            in (
                st.session_state[
                    "college_promotions"
                ].get(
                    manager_id,
                    [],
                )
            )

            if player_name
            in college_names
        ]


        selected_promotions = (
            st.multiselect(
                "$0 College Promotions",
                options=(
                    college_names
                ),
                default=(
                    current_promotions
                ),
                disabled=(
                    setup_locked
                ),
                key=(
                    f"college_{manager_id}"
                ),
            )
        )


        st.session_state[
            "college_promotions"
        ][
            manager_id
        ] = selected_promotions


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


        try:

            setup = (
                build_team_draft_setup(
                    manager_id=(
                        manager_id
                    ),
                    manager_data=(
                        manager_data
                    ),
                    selected_keeper_names=(
                        selected_keepers
                    ),
                    college_promotions=(
                        selected_promotions
                    ),
                )
            )


            team_setups[
                manager_id
            ] = setup


            s1, s2, s3, s4 = (
                st.columns(4)
            )


            s1.metric(
                "Keeper $",
                f"${setup.keeper_cost}",
            )

            s2.metric(
                "Auction Cash",
                f"${setup.auction_cash}",
            )

            s3.metric(
                "Open Spots",
                setup.open_roster_spots,
            )

            s4.metric(
                "Legal Max",
                f"${setup.max_bid}",
            )


        except ValueError as error:

            st.error(
                str(
                    error
                )
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


live_reserve = (
    live_open_spots
    *
    MINIMUM_AUCTION_BID
)


live_discretionary = max(
    0,
    live_total_cash
    -
    live_reserve,
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
                MY_MANAGER_ID
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
                MY_MANAGER_ID
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
                MY_MANAGER_ID
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
        MY_MANAGER_ID
    )
)


my_need_profile = (
    team_need_profiles.get(
        MY_MANAGER_ID
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
# LIVE AUCTION HEADER
# =========================================================

st.divider()


st.header(
    "🚨 LIVE AUCTION"
)


m1, m2, m3, m4, m5 = (
    st.columns(5)
)


m1.metric(
    "Players Sold",
    len(
        live_sales
    ),
)


m2.metric(
    "Remaining Cash",
    f"${live_total_cash:,}",
)


m3.metric(
    "Open Spots",
    live_open_spots,
)


m4.metric(
    "Discretionary $",
    f"${live_discretionary:,}",
)


m5.metric(
    "Room vs Model",
    (
        f"{room_spend_index:.2f}x"
        if room_spend_index
        is not None
        else "-"
    ),
)


if room_spend_index is not None:

    if room_spend_index >= 1.08:

        st.warning(
            "The room has paid above modeled market. "
            "Those overpayments have removed cash "
            "from the remaining auction."
        )


    elif room_spend_index <= 0.92:

        st.info(
            "Players have sold below modeled market. "
            "Extra cash remains in the room and may "
            "produce later inflation."
        )


# =========================================================
# LIVE LEARNING PANEL
# =========================================================

with st.expander(
    "🧠 2026 Live Learning",
    expanded=(
        len(
            live_sales
        )
        >= 2
    ),
):

    overall = (
        live_calibration.overall
    )


    l1, l2, l3 = (
        st.columns(3)
    )


    l1.metric(
        "Learned Sales",
        overall.sample_size,
    )


    l2.metric(
        "Actual / Model",
        (
            f"{overall.raw_ratio:.2f}x"
            if overall.sample_size
            else "-"
        ),
    )


    l3.metric(
        "Shrunk Room Signal",
        (
            f"{overall.multiplier:.3f}x"
            if overall.sample_size
            else "1.000x"
        ),
    )


    st.caption(
        "Early samples are deliberately shrunk. "
        "Position and tier adjustments redistribute "
        "remaining auction dollars rather than "
        "creating new money."
    )


    # =====================================================
    # POSITION MARKET
    # =====================================================

    st.markdown(
        "#### Position Market"
    )


    position_rows = []


    for position in [
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    ]:

        signal = (
            live_calibration
            .position_signals
            .get(
                position
            )
        )


        if signal:

            position_rows.append(
                {
                    "Position": position,
                    "Sales": signal.sample_size,
                    "Actual $": signal.actual_spend,
                    "Model $": signal.modeled_spend,
                    "Raw vs Model": signal.raw_ratio,
                    "Learned Signal": signal.multiplier,
                }
            )


    if position_rows:

        st.dataframe(
            pd.DataFrame(
                position_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No position-level learning yet."
        )


    # =====================================================
    # TIER MARKET
    # =====================================================

    st.markdown(
        "#### Price Tier Market"
    )


    tier_rows = []


    for tier in [
        "ELITE",
        "PREMIUM",
        "CORE",
        "VALUE",
    ]:

        signal = (
            live_calibration
            .tier_signals
            .get(
                tier
            )
        )


        if signal:

            tier_rows.append(
                {
                    "Tier": tier,
                    "Sales": signal.sample_size,
                    "Actual $": signal.actual_spend,
                    "Model $": signal.modeled_spend,
                    "Raw vs Model": signal.raw_ratio,
                    "Learned Signal": signal.multiplier,
                }
            )


    if tier_rows:

        st.dataframe(
            pd.DataFrame(
                tier_rows
            ),
            use_container_width=True,
            hide_index=True,
        )


    # =====================================================
    # MANAGER BEHAVIOR
    # =====================================================

    st.markdown(
        "#### Manager Behavior"
    )


    manager_learning_rows = []


    for (
        manager_id,
        profile,
    ) in (
        live_calibration
        .manager_profiles
        .items()
    ):

        team_name = (
            MANAGERS[
                manager_id
            ].sleeper_team_name

            if manager_id
            in MANAGERS

            else manager_id
        )


        hot_positions = [
            (
                f"{position} "
                f"{multiplier:.2f}x"
            )

            for (
                position,
                multiplier,
            ) in (
                profile
                .position_multipliers
                .items()
            )

            if (
                profile
                .position_counts
                .get(
                    position,
                    0,
                )
                >= 2
                and
                multiplier
                >= 1.05
            )
        ]


        manager_learning_rows.append(
            {
                "Team": team_name,
                "Buys": profile.purchases,
                "Spent": profile.actual_spend,
                "Model $": profile.modeled_spend,
                "Raw vs Model": profile.raw_ratio,
                "Learned Aggression": profile.multiplier,
                "Hot Positions": (
                    ", ".join(
                        hot_positions
                    )
                    if hot_positions
                    else "-"
                ),
            }
        )


    if manager_learning_rows:

        st.dataframe(
            pd.DataFrame(
                manager_learning_rows
            ).sort_values(
                by="Learned Aggression",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# UNDO / RESET
# =========================================================

control1, control2, control3 = (
    st.columns(
        [
            1,
            1,
            3,
        ]
    )
)


with control1:

    if st.button(
        "↩️ Undo Last Sale",
        disabled=(
            len(
                live_sales
            )
            == 0
        ),
        use_container_width=True,
    ):

        draft_store.undo_last_sale()

        st.rerun()


with control2:

    if st.button(
        "🗑️ Reset Live Sales",
        disabled=(
            len(
                live_sales
            )
            == 0
        ),
        use_container_width=True,
    ):

        draft_store.reset_sales()

        st.rerun()


# =========================================================
# OPTIMAL REMAINING ROSTER
# =========================================================

st.divider()


st.header(
    "🧩 Optimal Remaining Roster"
)


st.caption(
    "Whole-roster planning based on your remaining "
    "cash, starter gaps, FLEX needs, expected prices, "
    "and $1 endgame requirements."
)


if (
    optimal_roster_plan
    and
    optimal_roster_plan.feasible
):

    r1, r2, r3, r4, r5 = (
        st.columns(5)
    )


    r1.metric(
        "Your Cash",
        f"${optimal_roster_plan.starting_cash}",
    )


    r2.metric(
        "Open Spots",
        optimal_roster_plan.starting_open_spots,
    )


    r3.metric(
        "Planned Spend",
        f"${optimal_roster_plan.planned_spend}",
    )


    r4.metric(
        "Cash Left",
        f"${optimal_roster_plan.cash_after_plan}",
    )


    r5.metric(
        "Plan Utility",
        f"{optimal_roster_plan.total_utility:.1f}",
    )


    roster_rows = []


    for entry in (
        optimal_roster_plan.entries
    ):

        roster_rows.append(
            {
                "Slot": entry.slot,
                "Player": entry.player_name,
                "Pos": entry.position,
                "Plan $": entry.planned_cost,
                "Market $": entry.expected_market_value,
                "Player Ceiling": entry.do_not_exceed,
                "Baseline": entry.baseline_value,
                "VORP": entry.vorp,
                "Fallback": entry.is_filler,
            }
        )


    st.dataframe(
        pd.DataFrame(
            roster_rows
        ),
        use_container_width=True,
        hide_index=True,
    )


else:

    st.warning(
        "No feasible complete roster plan was found."
    )


# =========================================================
# NOMINATION COPILOT
# =========================================================

st.divider()


st.header(
    "🎯 WHO SHOULD I NOMINATE?"
)


st.caption(
    "Find players who can drain opponent budgets, "
    "attack positional desperation, or create a "
    "buy window for one of your own targets."
)


if nomination_recommendations:

    top_nomination = (
        nomination_recommendations[
            0
        ]
    )


    top1, top2, top3 = (
        st.columns(
            [
                2,
                1,
                1,
            ]
        )
    )


    with top1:

        st.markdown(
            f"## {top_nomination.player_name}"
        )

        st.markdown(
            f"### {top_nomination.action}"
        )


    with top2:

        st.metric(
            "Nomination Score",
            f"{top_nomination.nomination_score:.0f}/100",
        )


    with top3:

        st.metric(
            "Expected Market",
            f"${top_nomination.expected_market_value:.0f}",
        )


    nomination_rows = []


    for nomination in (
        nomination_recommendations[
            :20
        ]
    ):

        if (
            nomination.top_opponent_id
            and
            nomination.top_opponent_id
            in MANAGERS
        ):

            opponent_name = (
                MANAGERS[
                    nomination
                    .top_opponent_id
                ].sleeper_team_name
            )

        else:

            opponent_name = (
                nomination
                .top_opponent_id
                or "-"
            )


        nomination_rows.append(
            {
                "Player": nomination.player_name,
                "Pos": nomination.position,
                "Score": nomination.nomination_score,
                "Action": nomination.action,
                "Market $": nomination.expected_market_value,
                "Player Ceiling": nomination.do_not_exceed,
                "My Interest": (
                    nomination.my_interest_score
                    *
                    100
                ),
                "Opponent Need": (
                    nomination.opponent_need_score
                    *
                    100
                ),
                "Cash Drain": (
                    nomination.cash_drain_score
                    *
                    100
                ),
                "Competition": (
                    nomination.competition_score
                    *
                    100
                ),
                "Top Opponent": opponent_name,
                "Live Heat": nomination.live_market_heat,
            }
        )


    st.dataframe(
        pd.DataFrame(
            nomination_rows
        ),
        use_container_width=True,
        hide_index=True,
    )


    (
        drain_tab,
        target_tab,
        window_tab,
    ) = (
        st.tabs(
            [
                "🔥 Drain the Room",
                "🎯 My Targets",
                "🪟 Buy Windows",
            ]
        )
    )


    with drain_tab:

        drain_candidates = [
            nomination

            for nomination
            in nomination_recommendations

            if (
                nomination
                .my_interest_score
                <= 0.45
            )
        ]


        if drain_candidates:

            for candidate in (
                drain_candidates[
                    :8
                ]
            ):

                st.markdown(
                    f"**{candidate.player_name} "
                    f"({candidate.position})** — "
                    f"{candidate.action} — "
                    f"{candidate.nomination_score:.0f}/100"
                )


                if candidate.reasons:

                    st.caption(
                        " • ".join(
                            candidate.reasons
                        )
                    )

        else:

            st.info(
                "No strong cash-drain nominations "
                "are currently available."
            )


    with target_tab:

        my_targets = sorted(
            [
                nomination

                for nomination
                in nomination_recommendations

                if (
                    nomination
                    .my_interest_score
                    >= 0.65
                )
            ],
            key=lambda value: (
                value.my_interest_score
            ),
            reverse=True,
        )


        if my_targets:

            for candidate in (
                my_targets[
                    :10
                ]
            ):

                st.markdown(
                    f"**{candidate.player_name} "
                    f"({candidate.position})**"
                )

                st.caption(
                    f"My interest "
                    f"{candidate.my_interest_score:.0%} • "
                    f"Market "
                    f"${candidate.expected_market_value:.0f} • "
                    f"Ceiling "
                    f"${candidate.do_not_exceed}"
                )

        else:

            st.info(
                "No high-priority personal targets "
                "are currently identified."
            )


    with window_tab:

        buy_windows = [
            nomination

            for nomination
            in nomination_recommendations

            if (
                nomination.action
                ==
                "BUY WINDOW"
            )
        ]


        if buy_windows:

            for candidate in buy_windows:

                st.success(
                    f"{candidate.player_name} — "
                    f"market heat "
                    f"{candidate.live_market_heat:.3f}x — "
                    f"expected "
                    f"${candidate.expected_market_value:.0f}"
                )

        else:

            st.info(
                "No clear buy windows right now."
            )


# =========================================================
# SALE INPUT MODE
# =========================================================

st.divider()


st.markdown(
    "## 📡 Sale Input"
)


sale_input_mode = (
    st.radio(
        "How should completed auction sales enter the app?",
        options=[
            "Sleeper Live Sync",
            "Manual Sale Entry",
        ],
        horizontal=True,
        key=(
            "sale_input_mode"
        ),
    )
)


# =========================================================
# SLEEPER SYNC
# =========================================================

def perform_sleeper_sync():

    client = SleeperClient()

    draft_picks = (
        client.get_draft_picks(
            SLEEPER_DRAFT_ID
        )
    )

    latest_local_sales = (
        draft_store.load_sales()
    )

    return (
        sync_next_sleeper_sale(
            draft_picks=(
                draft_picks
            ),
            starting_team_setups=(
                team_setups
            ),
            starting_pool_players=(
                pool_result.available_players
            ),
            sleeper_players=(
                sleeper_players
            ),
            managers=(
                MANAGERS
            ),
            existing_sales=(
                latest_local_sales
            ),
            recommendation_index=(
                recommendation_index
            ),
            draft_store=(
                draft_store
            ),
        )
    )


if (
    sale_input_mode
    ==
    "Sleeper Live Sync"
):

    st.info(
        "Sleeper is currently the live sale feed. "
        "Completed sales write into the same SQLite "
        "ledger used by manual entry."
    )


    sync1, sync2 = (
        st.columns(2)
    )


    with sync1:

        auto_sync = (
            st.toggle(
                "Auto-sync Sleeper",
                key=(
                    "auto_sleeper_sync"
                ),
            )
        )


    with sync2:

        poll_seconds = (
            st.number_input(
                "Polling interval",
                min_value=1,
                max_value=300,
                step=1,
                key=(
                    "sleeper_poll_seconds"
                ),
            )
        )


    poll_seconds = int(
        poll_seconds
    )


    if hasattr(
        st,
        "fragment",
    ):

        fragment_interval = (
            f"{poll_seconds}s"
            if auto_sync
            else None
        )


        @st.fragment(
            run_every=(
                fragment_interval
            )
        )
        def sleeper_live_feed():

            manual_sync = (
                st.button(
                    "🔄 Sync Sleeper Now",
                    use_container_width=True,
                    key="sync_sleeper_now",
                )
            )


            if not (
                auto_sync
                or
                manual_sync
            ):

                return


            try:

                result = (
                    perform_sleeper_sync()
                )


                if (
                    result.status
                    ==
                    "imported"
                ):

                    st.success(
                        result.message
                    )

                    st.rerun()


                elif (
                    result.status
                    ==
                    "conflict"
                ):

                    st.error(
                        result.message
                    )


            except Exception as error:

                st.error(
                    f"Sleeper sync failed: "
                    f"{error}"
                )


        sleeper_live_feed()


    else:

        if st.button(
            "🔄 Sync Sleeper Now",
            use_container_width=True,
        ):

            try:

                result = (
                    perform_sleeper_sync()
                )

                st.success(
                    result.message
                )

                if (
                    result.status
                    ==
                    "imported"
                ):

                    st.rerun()

            except Exception as error:

                st.error(
                    f"Sleeper sync failed: "
                    f"{error}"
                )


# =========================================================
# LIVE BID COPILOT
# =========================================================

st.divider()


st.header(
    "💰 Live Bid Copilot"
)


recommendation_names = sorted(
    [
        recommendation.player_name

        for recommendation
        in recommendations
    ]
)


if (
    "nominated_player"
    in st.session_state
    and
    st.session_state[
        "nominated_player"
    ]
    not in recommendation_names
):

    del st.session_state[
        "nominated_player"
    ]


if recommendation_names:

    nominated_player = (
        st.selectbox(
            "Nominated Player",
            options=(
                recommendation_names
            ),
            key=(
                "nominated_player"
            ),
        )
    )


    nominated_key = (
        normalize_player_name(
            nominated_player
        )
    )


    recommendation = (
        recommendation_index.get(
            nominated_key
        )
    )


    nomination_info = (
        nomination_index.get(
            nominated_key
        )
    )


    threat_summary = (
        threat_index.get(
            nominated_key
        )
    )


    fp = (
        fantasypros_index.get(
            nominated_key
        )
    )


    projection = (
        projection_index.get(
            nominated_key
        )
    )


    vorp_value = (
        player_value_index.get(
            nominated_key
        )
    )


    selected_market = (
        market_value_index.get(
            nominated_key
        )
    )


    if recommendation:

        # =================================================
        # ROSTER-AWARE CEILING
        # =================================================

        player_level_ceiling = int(
            recommendation.do_not_exceed
        )


        roster_ceiling = (
            player_level_ceiling
        )


        roster_ceiling_available = False


        if (
            my_live_setup
            and
            my_need_profile
            and
            optimization_candidates
        ):

            (
                calculated_roster_ceiling,
                _,
            ) = (
                calculate_roster_aware_ceiling(
                    player_name=(
                        recommendation.player_name
                    ),
                    my_team_setup=(
                        my_live_setup
                    ),
                    my_need_profile=(
                        my_need_profile
                    ),
                    candidates=(
                        optimization_candidates
                    ),
                    existing_do_not_exceed=(
                        player_level_ceiling
                    ),
                )
            )


            if (
                calculated_roster_ceiling
                >
                0
            ):

                roster_ceiling = int(
                    calculated_roster_ceiling
                )

                roster_ceiling_available = True


        final_do_not_exceed = min(
            player_level_ceiling,
            roster_ceiling,
        )


        # =================================================
        # MAIN PLAYER DISPLAY
        # =================================================

        st.markdown(
            f"# {recommendation.player_name}"
        )


        if nomination_info:

            st.caption(
                f"{recommendation.position} • "
                f"Nomination: "
                f"{nomination_info.action}"
            )


        left, center, right = (
            st.columns(
                [
                    1.2,
                    2,
                    1.2,
                ]
            )
        )


        with left:

            st.metric(
                "Expected Market",
                f"${recommendation.expected_market_value:.0f}",
            )

            st.metric(
                "Player Ceiling",
                f"${player_level_ceiling}",
            )


        with center:

            st.markdown(
                "## DO NOT EXCEED"
            )

            st.markdown(
                f"# 💰 ${final_do_not_exceed}"
            )

            st.markdown(
                f"### {recommendation.strategy}"
            )


        with right:

            st.metric(
                "Roster-Aware Ceiling",
                f"${roster_ceiling}",
            )

            st.metric(
                "Legal Max",
                f"${recommendation.legal_max_bid}",
            )


        if (
            roster_ceiling_available
            and
            roster_ceiling
            <
            player_level_ceiling
        ):

            st.warning(
                f"Roster construction lowers the ceiling "
                f"from ${player_level_ceiling} "
                f"to ${roster_ceiling}."
            )


        # =================================================
        # LIVE MARKET DETAIL
        # =================================================

        if selected_market:

            with st.expander(
                "2026 Live Price Adjustment"
            ):

                lp1, lp2, lp3, lp4 = (
                    st.columns(4)
                )


                lp1.metric(
                    "Before Live Learning",
                    (
                        f"${selected_market.pre_live_market_value:.1f}"
                    ),
                )


                lp2.metric(
                    "Live Multiplier",
                    (
                        f"{selected_market.live_multiplier:.3f}x"
                    ),
                )


                lp3.metric(
                    "Position Signal",
                    (
                        f"{selected_market.position_multiplier:.3f}x"
                    ),
                )


                lp4.metric(
                    "Tier",
                    selected_market.price_tier,
                )


        # =================================================
        # CURRENT BID
        # =================================================

        current_bid = (
            st.number_input(
                "Current Bid",
                min_value=1,
                value=1,
                step=1,
                key=(
                    f"current_bid_"
                    f"{nominated_key}"
                ),
            )
        )


        if (
            current_bid
            <
            final_do_not_exceed
        ):

            st.success(
                f"${final_do_not_exceed - current_bid} "
                f"of bidding room remains."
            )


        elif (
            current_bid
            ==
            final_do_not_exceed
        ):

            st.warning(
                "THIS IS YOUR CEILING. "
                "Do not bid again."
            )


        else:

            st.error(
                f"STOP — ${current_bid} is above "
                f"your ${final_do_not_exceed} ceiling."
            )


        # =================================================
        # BUY VS PASS
        # =================================================

        st.markdown(
            "## 🔮 What If I Win Him?"
        )


        scenario_max_price = max(
            1,
            int(
                recommendation.legal_max_bid
            ),
        )


        scenario_default_price = min(
            scenario_max_price,
            max(
                1,
                int(
                    round(
                        recommendation
                        .expected_market_value
                    )
                ),
            ),
        )


        hypothetical_price = (
            st.number_input(
                "Hypothetical Winning Price",
                min_value=1,
                max_value=(
                    scenario_max_price
                ),
                value=(
                    scenario_default_price
                ),
                step=1,
                key=(
                    f"scenario_price_"
                    f"{nominated_key}"
                ),
            )
        )


        scenario = None


        if (
            my_live_setup
            and
            my_need_profile
            and
            optimization_candidates
        ):

            scenario = (
                compare_buy_vs_pass(
                    player_name=(
                        recommendation.player_name
                    ),
                    proposed_price=(
                        int(
                            hypothetical_price
                        )
                    ),
                    my_team_setup=(
                        my_live_setup
                    ),
                    my_need_profile=(
                        my_need_profile
                    ),
                    candidates=(
                        optimization_candidates
                    ),
                    existing_do_not_exceed=(
                        player_level_ceiling
                    ),
                )
            )


        if scenario:

            sc1, sc2, sc3, sc4 = (
                st.columns(4)
            )


            sc1.metric(
                "Winning Price",
                f"${hypothetical_price}",
            )

            sc2.metric(
                "Roster Ceiling",
                f"${scenario.recommended_ceiling}",
            )

            sc3.metric(
                "Buy vs Pass Utility",
                f"{scenario.utility_delta:+.1f}",
            )

            sc4.metric(
                "Cash After Buy",
                (
                    f"${scenario.buy_plan.cash_after_plan}"
                    if scenario.buy_plan.feasible
                    else "-"
                ),
            )


            if not scenario.buy_plan.feasible:

                st.error(
                    "❌ Buying at this price prevents "
                    "a legal complete roster."
                )


            elif (
                hypothetical_price
                >
                scenario.recommended_ceiling
            ):

                st.error(
                    f"❌ PASS AT ${hypothetical_price}"
                )


            elif (
                scenario.utility_delta
                >= 0.25
            ):

                st.success(
                    f"✅ BUY AT ${hypothetical_price}"
                )


            elif (
                scenario.utility_delta
                >= -0.25
            ):

                st.info(
                    "⚖️ CLOSE CALL"
                )


            else:

                st.warning(
                    f"⚠️ PASS IS BETTER AT "
                    f"${hypothetical_price}"
                )


            buy_column, pass_column = (
                st.columns(2)
            )


            with buy_column:

                st.markdown(
                    "### ✅ BUY PLAN"
                )


                if scenario.buy_plan.feasible:

                    buy_rows = [
                        {
                            "Slot": entry.slot,
                            "Player": entry.player_name,
                            "Pos": entry.position,
                            "Plan $": entry.planned_cost,
                            "Market $": entry.expected_market_value,
                            "VORP": entry.vorp,
                        }

                        for entry
                        in scenario.buy_plan.entries
                    ]


                    st.dataframe(
                        pd.DataFrame(
                            buy_rows
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )


            with pass_column:

                st.markdown(
                    "### ⏭️ PASS PLAN"
                )


                if scenario.pass_plan.feasible:

                    pass_rows = [
                        {
                            "Slot": entry.slot,
                            "Player": entry.player_name,
                            "Pos": entry.position,
                            "Plan $": entry.planned_cost,
                            "Market $": entry.expected_market_value,
                            "VORP": entry.vorp,
                        }

                        for entry
                        in scenario.pass_plan.entries
                    ]


                    st.dataframe(
                        pd.DataFrame(
                            pass_rows
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )


            # =================================================
            # OPPORTUNITY COST
            # =================================================

            if (
                scenario.buy_plan.feasible
                and
                scenario.pass_plan.feasible
            ):

                buy_names = {
                    normalize_player_name(
                        entry.player_name
                    )

                    for entry
                    in scenario.buy_plan.entries

                    if not entry.is_filler
                }


                pass_only_entries = [
                    entry

                    for entry
                    in scenario.pass_plan.entries

                    if (
                        not entry.is_filler
                        and
                        normalize_player_name(
                            entry.player_name
                        )
                        not in buy_names
                    )
                ]


                if pass_only_entries:

                    st.markdown(
                        "### 💸 What Buying Him Costs You"
                    )


                    lost_players = sorted(
                        pass_only_entries,
                        key=lambda entry: (
                            entry.utility
                        ),
                        reverse=True,
                    )


                    for entry in (
                        lost_players[
                            :5
                        ]
                    ):

                        st.write(
                            f"• **{entry.player_name}** "
                            f"({entry.position}) — "
                            f"planned at "
                            f"${entry.planned_cost}"
                        )


        # =================================================
        # PLAYER CONTEXT
        # =================================================

        st.markdown(
            "## 🧠 Player Context"
        )


        player_context_summary = None

        context_lookup_name = (
            recommendation.player_name
        )


        targeted_news_count = None
        targeted_injury_count = None
        targeted_context_error = None


        # =================================================
        # TARGETED FANTASYPROS LOOKUP
        #
        # This fixes the old problem where we only had the
        # latest 100 league-wide news stories.
        # =================================================

        if (
            fp
            and
            fp.fantasypros_id
        ):

            try:

                targeted_context_data = (
                    load_player_context_data(
                        fp.fantasypros_id
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
                        "count"
                    )
                )


                targeted_injury_count = (
                    targeted_injury_response.get(
                        "count"
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


                # =================================================
                # IMPORTANT:
                # Context is stored under FantasyPros canonical
                # player name, not necessarily Sleeper spelling.
                # =================================================

                context_lookup_name = (
                    fp.player_name
                )


            except Exception as error:

                targeted_context_error = str(
                    error
                )


        # =================================================
        # READ STORED CONTEXT
        # =================================================

        player_context_summary = (
            context_store.get_player_summary(
                context_lookup_name
            )
        )


        # =================================================
        # CONTEXT DEBUG INFO
        # =================================================

        with st.expander(
            "Context Retrieval Status"
        ):

            cdebug1, cdebug2, cdebug3, cdebug4 = (
                st.columns(4)
            )


            cdebug1.metric(
                "FantasyPros ID",
                (
                    str(
                        fp.fantasypros_id
                    )
                    if (
                        fp
                        and
                        fp.fantasypros_id
                    )
                    else "-"
                ),
            )


            cdebug2.metric(
                "Targeted News",
                (
                    targeted_news_count
                    if targeted_news_count
                    is not None
                    else "-"
                ),
            )


            cdebug3.metric(
                "Targeted Injuries",
                (
                    targeted_injury_count
                    if targeted_injury_count
                    is not None
                    else "-"
                ),
            )


            cdebug4.metric(
                "Stored Docs",
                (
                    player_context_summary
                    .document_count
                    if player_context_summary
                    else 0
                ),
            )


            st.caption(
                f"Auction name: "
                f"{recommendation.player_name}"
            )


            st.caption(
                f"Context lookup name: "
                f"{context_lookup_name}"
            )


            if targeted_context_error:

                st.error(
                    f"Targeted player context failed: "
                    f"{targeted_context_error}"
                )


        # =================================================
        # DISPLAY CONTEXT
        # =================================================

        if (
            player_context_summary
            and
            player_context_summary.document_count
            > 0
        ):

            ctx1, ctx2, ctx3, ctx4 = (
                st.columns(4)
            )


            ctx1.metric(
                "Role",
                (
                    f"{player_context_summary.role_score:+.2f}"
                ),
            )


            ctx2.metric(
                "Usage",
                (
                    f"{player_context_summary.usage_score:+.2f}"
                ),
            )


            ctx3.metric(
                "Health",
                (
                    f"{player_context_summary.injury_score:+.2f}"
                ),
            )


            ctx4.metric(
                "Dynasty",
                (
                    f"{player_context_summary.dynasty_score:+.2f}"
                ),
            )


            ctx5, ctx6, ctx7 = (
                st.columns(3)
            )


            ctx5.metric(
                "Overall Context",
                (
                    f"{player_context_summary.overall_context_score:+.2f}"
                ),
            )


            ctx6.metric(
                "Confidence",
                (
                    f"{player_context_summary.confidence:.0%}"
                ),
            )


            ctx7.metric(
                "Evidence",
                player_context_summary.document_count,
            )


            st.caption(
                "Context is advisory right now. "
                "It does not directly alter the deterministic "
                "DO NOT EXCEED."
            )


            if (
                player_context_summary.reasons
            ):

                st.markdown(
                    "### Context Summary"
                )


                for reason in (
                    player_context_summary.reasons
                ):

                    st.write(
                        f"• {reason}"
                    )


            # =================================================
            # RECENT EVIDENCE
            # =================================================

            with st.expander(
                "Recent Context Evidence",
                expanded=True,
            ):

                for document in (
                    player_context_summary.documents[
                        :10
                    ]
                ):

                    date_text = "-"


                    if document.published_at:

                        date_text = (
                            document
                            .published_at
                            .strftime(
                                "%Y-%m-%d %H:%M"
                            )
                        )


                    st.markdown(
                        f"**{document.title}**"
                    )


                    st.caption(
                        f"{document.source_name} • "
                        f"{document.source_type} • "
                        f"{date_text}"
                    )


                    if document.content:

                        content = (
                            document.content
                        )


                        if len(
                            content
                        ) > 700:

                            content = (
                                content[
                                    :700
                                ]
                                +
                                "..."
                            )


                        st.write(
                            content
                        )


                    signal_parts = []


                    if abs(
                        document.role_signal
                    ) >= 0.05:

                        signal_parts.append(
                            f"Role "
                            f"{document.role_signal:+.2f}"
                        )


                    if abs(
                        document.usage_signal
                    ) >= 0.05:

                        signal_parts.append(
                            f"Usage "
                            f"{document.usage_signal:+.2f}"
                        )


                    if abs(
                        document.injury_signal
                    ) >= 0.05:

                        signal_parts.append(
                            f"Health "
                            f"{document.injury_signal:+.2f}"
                        )


                    if abs(
                        document.dynasty_signal
                    ) >= 0.05:

                        signal_parts.append(
                            f"Dynasty "
                            f"{document.dynasty_signal:+.2f}"
                        )


                    if signal_parts:

                        st.caption(
                            " • ".join(
                                signal_parts
                            )
                        )


                    if document.url:

                        st.markdown(
                            f"[Open source]({document.url})"
                        )


                    st.divider()


        else:

            if targeted_context_error:

                st.warning(
                    "Player context could not be retrieved "
                    "from FantasyPros for this player."
                )

            elif (
                fp is None
                or
                not fp.fantasypros_id
            ):

                st.warning(
                    "No FantasyPros player ID was matched "
                    "for this player, so targeted context "
                    "retrieval cannot run yet."
                )

            else:

                st.info(
                    "FantasyPros currently has no stored "
                    "news or injury evidence for this player. "
                    "That can be completely normal for a "
                    "healthy player without a recent news item."
                )


        # =================================================
        # PLAYER SIGNALS
        # =================================================

        st.markdown(
            "### Player Signals"
        )


        signal1, signal2, signal3, signal4 = (
            st.columns(4)
        )


        signal1.metric(
            "Your Need",
            (
                f"{recommendation.my_need_score:.0%}"
            ),
        )


        signal2.metric(
            "Scarcity",
            (
                f"{recommendation.scarcity_score:.0%}"
            ),
        )


        signal3.metric(
            "Bidder Threat",
            (
                f"{recommendation.threat_score:.0f}/100"
            ),
        )


        signal4.metric(
            "VORP",
            (
                f"{vorp_value.vorp:.1f}"
                if vorp_value
                else "-"
            ),
        )


        if recommendation.reasons:

            st.write(
                " • ".join(
                    recommendation.reasons
                )
            )


        # =================================================
        # NEXT OPTION
        # =================================================

        st.markdown(
            "### Next Option"
        )


        if (
            recommendation
            .alternative_player
        ):

            alt1, alt2, alt3 = (
                st.columns(3)
            )


            alt1.metric(
                f"Next {recommendation.position}",
                recommendation.alternative_player,
            )


            alt2.metric(
                "Expected Market",
                (
                    f"${recommendation.alternative_market_value:.0f}"
                    if (
                        recommendation
                        .alternative_market_value
                        is not None
                    )
                    else "-"
                ),
            )


            alt3.metric(
                "VORP",
                (
                    f"{recommendation.alternative_vorp:.1f}"
                    if (
                        recommendation
                        .alternative_vorp
                        is not None
                    )
                    else "-"
                ),
            )


        else:

            st.warning(
                "No meaningful same-position "
                "alternative remains."
            )


        # =================================================
        # FANTASYPROS INTELLIGENCE
        # =================================================

        with st.expander(
            "FantasyPros Intelligence"
        ):

            intel1, intel2, intel3, intel4 = (
                st.columns(4)
            )


            intel1.metric(
                "Projected Points",
                (
                    f"{projection.custom_points:.1f}"
                    if (
                        projection
                        and
                        projection.custom_points
                        is not None
                    )
                    else "-"
                ),
            )


            intel2.metric(
                "2026 ECR",
                (
                    f"{fp.half_ecr:.0f}"
                    if (
                        fp
                        and
                        fp.half_ecr
                        is not None
                    )
                    else "-"
                ),
            )


            intel3.metric(
                "Dynasty ECR",
                (
                    f"{fp.dynasty_ecr:.0f}"
                    if (
                        fp
                        and
                        fp.dynasty_ecr
                        is not None
                    )
                    else "-"
                ),
            )


            intel4.metric(
                "ADP",
                (
                    f"{fp.adp:.1f}"
                    if (
                        fp
                        and
                        fp.adp
                        is not None
                    )
                    else "-"
                ),
            )


        # =================================================
        # BIDDER THREATS
        # =================================================

        with st.expander(
            "Who Might Bid Against Me?"
        ):

            bidder_rows = []


            if threat_summary:

                for threat in (
                    threat_summary.threats
                ):

                    manager_id = (
                        threat.manager_id
                    )


                    team_name = (
                        MANAGERS[
                            manager_id
                        ].sleeper_team_name

                        if manager_id
                        in MANAGERS

                        else manager_id
                    )


                    live_manager = (
                        live_calibration
                        .manager_profiles
                        .get(
                            manager_id
                        )
                    )


                    bidder_rows.append(
                        {
                            "Team": team_name,
                            "Threat": threat.threat_score,
                            "Need": (
                                threat.need_score
                                *
                                100
                            ),
                            "Cash": threat.auction_cash,
                            "Legal Max": threat.max_bid,
                            "Can Afford": (
                                threat.can_afford_market
                            ),
                            "2026 Buys": (
                                live_manager.purchases
                                if live_manager
                                else 0
                            ),
                            "2026 Aggression": (
                                live_manager.multiplier
                                if live_manager
                                else 1.0
                            ),
                            "Why": (
                                "; ".join(
                                    threat.reasons
                                )
                            ),
                        }
                    )


            if bidder_rows:

                st.dataframe(
                    pd.DataFrame(
                        bidder_rows
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


        # =================================================
        # MANUAL SALE ENTRY
        # =================================================

        if (
            sale_input_mode
            ==
            "Manual Sale Entry"
        ):

            st.markdown(
                "## 🧾 Record Completed Sale"
            )


            with st.form(
                key=(
                    f"record_sale_"
                    f"{nominated_key}"
                )
            ):

                winner_id = (
                    st.selectbox(
                        "Winning Team",
                        options=list(
                            live_team_setups.keys()
                        ),
                        format_func=(
                            lambda manager_id: (
                                MANAGERS[
                                    manager_id
                                ].sleeper_team_name
                            )
                        ),
                    )
                )


                winner_state = (
                    live_team_setups[
                        winner_id
                    ]
                )


                st.caption(
                    f"Cash: "
                    f"${winner_state.auction_cash} • "
                    f"Open spots: "
                    f"{winner_state.open_roster_spots} • "
                    f"Legal max: "
                    f"${winner_state.max_bid}"
                )


                sale_price = (
                    st.number_input(
                        "Sale Price",
                        min_value=1,
                        value=1,
                        step=1,
                    )
                )


                submit_sale = (
                    st.form_submit_button(
                        "✅ RECORD SALE",
                        use_container_width=True,
                    )
                )


                if submit_sale:

                    try:

                        updated_sales = (
                            add_live_sale(
                                starting_team_setups=(
                                    team_setups
                                ),
                                existing_sales=(
                                    live_sales
                                ),
                                player_name=(
                                    recommendation
                                    .player_name
                                ),
                                position=(
                                    recommendation
                                    .position
                                ),
                                manager_id=(
                                    winner_id
                                ),
                                price=(
                                    int(
                                        sale_price
                                    )
                                ),
                                modeled_market_value=(
                                    recommendation
                                    .expected_market_value
                                ),
                                do_not_exceed=(
                                    final_do_not_exceed
                                ),
                            )
                        )


                        draft_store.add_sale(
                            updated_sales[
                                -1
                            ]
                        )


                        st.rerun()


                    except ValueError as error:

                        st.error(
                            str(
                                error
                            )
                        )


else:

    st.warning(
        "No auction recommendations are available."
    )


# =========================================================
# LIVE TEAM STATE
# =========================================================

st.divider()


st.subheader(
    "💰 Live Team State"
)


team_rows = []


for (
    manager_id,
    setup,
) in live_team_setups.items():

    need = (
        team_need_profiles.get(
            manager_id
        )
    )


    live_manager = (
        live_calibration
        .manager_profiles
        .get(
            manager_id
        )
    )


    team_rows.append(
        {
            "Team": (
                MANAGERS[
                    manager_id
                ].sleeper_team_name
            ),
            "Cash": setup.auction_cash,
            "Open Spots": (
                setup.open_roster_spots
            ),
            "Legal Max": setup.max_bid,
            "Bought": setup.purchased_count,
            "2026 Aggression": (
                live_manager.multiplier
                if live_manager
                else 1.0
            ),
            "QB Need": (
                need.need_scores.get(
                    "QB",
                    0.0,
                ) * 100
                if need
                else 0
            ),
            "RB Need": (
                need.need_scores.get(
                    "RB",
                    0.0,
                ) * 100
                if need
                else 0
            ),
            "WR Need": (
                need.need_scores.get(
                    "WR",
                    0.0,
                ) * 100
                if need
                else 0
            ),
            "TE Need": (
                need.need_scores.get(
                    "TE",
                    0.0,
                ) * 100
                if need
                else 0
            ),
            "K Need": (
                need.need_scores.get(
                    "K",
                    0.0,
                ) * 100
                if need
                else 0
            ),
            "DEF Need": (
                need.need_scores.get(
                    "DEF",
                    0.0,
                ) * 100
                if need
                else 0
            ),
            "My Team": (
                "⭐"
                if manager_id
                ==
                MY_MANAGER_ID
                else ""
            ),
        }
    )


if team_rows:

    st.dataframe(
        pd.DataFrame(
            team_rows
        ).sort_values(
            by="Cash",
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# AUCTION LEDGER
# =========================================================

st.subheader(
    "📜 Persistent Auction Ledger"
)


ledger_rows = []


for sale in live_sales:

    team_name = (
        MANAGERS[
            sale.manager_id
        ].sleeper_team_name

        if sale.manager_id
        in MANAGERS

        else sale.manager_id
    )


    delta = None


    if (
        sale.modeled_market_value
        is not None
    ):

        delta = (
            sale.price
            -
            sale.modeled_market_value
        )


    ratio = None


    if (
        sale.modeled_market_value
        is not None
        and
        sale.modeled_market_value
        > 0
    ):

        ratio = (
            sale.price
            /
            sale.modeled_market_value
        )


    ledger_rows.append(
        {
            "#": sale.sale_number,
            "Player": sale.player_name,
            "Pos": sale.position,
            "Winner": team_name,
            "Price": sale.price,
            "Market at Sale": (
                sale.modeled_market_value
            ),
            "vs Market": delta,
            "Actual / Model": ratio,
            "My Ceiling": (
                sale.do_not_exceed
            ),
        }
    )


if ledger_rows:

    st.dataframe(
        pd.DataFrame(
            ledger_rows
        ),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No auction sales recorded yet."
    )


# =========================================================
# LIVE AUCTION BOARD
# =========================================================

st.divider()


st.subheader(
    "📋 Live Auction Board"
)


st.caption(
    "Select a player in Live Bid Copilot for the "
    "authoritative roster-aware DO NOT EXCEED."
)


board_rows = []


for player in available_players:

    key = (
        normalize_player_name(
            player.player_name
        )
    )


    recommendation = (
        recommendation_index.get(
            key
        )
    )


    nomination = (
        nomination_index.get(
            key
        )
    )


    market = (
        market_value_index.get(
            key
        )
    )


    baseline = (
        auction_value_index.get(
            key
        )
    )


    threat = (
        threat_index.get(
            key
        )
    )


    fp_board = (
        fantasypros_index.get(
            key
        )
    )


    vorp = (
        player_value_index.get(
            key
        )
    )


    top_competitor = "-"


    if (
        threat
        and
        threat.top_manager_id
    ):

        manager_id = (
            threat.top_manager_id
        )


        top_competitor = (
            MANAGERS[
                manager_id
            ].sleeper_team_name

            if manager_id
            in MANAGERS

            else manager_id
        )


    board_rows.append(
        {
            "Player": player.player_name,
            "Pos": player.position,
            "NFL": player.nfl_team or "FA",
            "Player Ceiling": (
                recommendation.do_not_exceed
                if recommendation
                else None
            ),
            "Strategy": (
                recommendation.strategy
                if recommendation
                else "-"
            ),
            "Nominate Score": (
                nomination.nomination_score
                if nomination
                else None
            ),
            "Nomination Action": (
                nomination.action
                if nomination
                else "-"
            ),
            "Market $": (
                market.expected_market_value
                if market
                else None
            ),
            "Live Multiplier": (
                market.live_multiplier
                if market
                else 1.0
            ),
            "Baseline $": (
                baseline.baseline_value
                if baseline
                else None
            ),
            "My Need": (
                recommendation.my_need_score
                *
                100
                if recommendation
                else 0
            ),
            "Scarcity": (
                recommendation.scarcity_score
                *
                100
                if recommendation
                else 0
            ),
            "Next Option": (
                recommendation.alternative_player
                if (
                    recommendation
                    and
                    recommendation.alternative_player
                )
                else "-"
            ),
            "Threat": (
                threat.top_threat_score
                if threat
                else 0
            ),
            "Top Competitor": top_competitor,
            "VORP": (
                vorp.vorp
                if vorp
                else None
            ),
            "2026 ECR": (
                fp_board.half_ecr
                if fp_board
                else None
            ),
            "Dynasty ECR": (
                fp_board.dynasty_ecr
                if fp_board
                else None
            ),
        }
    )


board_df = (
    pd.DataFrame(
        board_rows
    )
)


filter1, filter2, filter3 = (
    st.columns(
        [
            2,
            1,
            1,
        ]
    )
)


with filter1:

    search = (
        st.text_input(
            "Search Player"
        )
    )


with filter2:

    positions = (
        st.multiselect(
            "Position",
            options=[
                "QB",
                "RB",
                "WR",
                "TE",
                "K",
                "DEF",
            ],
            default=[
                "QB",
                "RB",
                "WR",
                "TE",
                "K",
                "DEF",
            ],
        )
    )


with filter3:

    sort_by = (
        st.selectbox(
            "Sort",
            options=[
                "Player Ceiling",
                "Nominate Score",
                "Market $",
                "Live Multiplier",
                "My Need",
                "Scarcity",
                "Threat",
                "VORP",
                "2026 ECR",
                "Dynasty ECR",
            ],
        )
    )


filtered_board = (
    board_df.copy()
)


if (
    not filtered_board.empty
    and
    positions
):

    filtered_board = (
        filtered_board[
            filtered_board[
                "Pos"
            ].isin(
                positions
            )
        ]
    )


if (
    not filtered_board.empty
    and
    search
):

    filtered_board = (
        filtered_board[
            filtered_board[
                "Player"
            ]
            .str.contains(
                search,
                case=False,
                na=False,
            )
        ]
    )


if not filtered_board.empty:

    ascending = (
        sort_by
        in {
            "2026 ECR",
            "Dynasty ECR",
        }
    )


    filtered_board = (
        filtered_board.sort_values(
            by=sort_by,
            ascending=ascending,
            na_position="last",
        )
    )


st.dataframe(
    filtered_board,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# HISTORICAL INTELLIGENCE
# =========================================================

with st.expander(
    "📚 Historical Bishop Sycamore Market"
):

    h1, h2, h3, h4 = (
        st.columns(4)
    )


    h1.metric(
        "Mapped Sales",
        len(
            historical_market_model
            .mapped_sales
        ),
    )


    h2.metric(
        "Eligible Seasons",
        len(
            historical_market_model
            .eligible_years
        ),
    )


    h3.metric(
        "Unmapped Sales",
        historical_market_model
        .unmapped_sales_count,
    )


    h4.metric(
        "Historical Avg Buy",
        (
            f"${historical_market_model.league_average_purchase:.1f}"
        ),
    )


    historical_manager_rows = []


    for (
        manager_id,
        profile,
    ) in (
        historical_market_model
        .manager_profiles
        .items()
    ):

        team_name = (
            MANAGERS[
                manager_id
            ].sleeper_team_name

            if manager_id
            in MANAGERS

            else manager_id
        )


        historical_manager_rows.append(
            {
                "Team": team_name,
                "Buys": profile.sales_count,
                "Avg Buy": profile.average_price,
                "Max Buy": profile.max_price,
                "Aggressiveness": (
                    profile.aggressiveness_index
                ),
                "Star Chase": (
                    profile.star_chase_index
                ),
            }
        )


    if historical_manager_rows:

        st.dataframe(
            pd.DataFrame(
                historical_manager_rows
            ).sort_values(
                by="Aggressiveness",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# DRAFT SIMULATION
# =========================================================

st.divider()


st.header(
    "🧪 Draft Simulation / Test Mode"
)


sim1, sim2, sim3, sim4 = (
    st.columns(4)
)


with sim1:

    simulation_sale_count = (
        st.number_input(
            "Fake Sales",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            key=(
                "simulation_sale_count"
            ),
        )
    )


with sim2:

    simulation_seed = (
        st.number_input(
            "Simulation Seed",
            min_value=1,
            max_value=999999,
            value=42,
            step=1,
            key=(
                "simulation_seed"
            ),
        )
    )


with sim3:

    simulation_checkpoint = (
        st.number_input(
            "Full Checkpoint Every",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
            key=(
                "simulation_checkpoint"
            ),
        )
    )


with sim4:

    simulation_from_current = (
        st.checkbox(
            "Start from current ledger",
            value=False,
        )
    )


st.info(
    "Simulation sales are in-memory only. "
    "draft_state.db is not modified."
)


run_simulation = (
    st.button(
        "🧪 RUN DRAFT SIMULATION",
        type="primary",
        use_container_width=True,
    )
)


if run_simulation:

    initial_simulation_sales = (
        live_sales
        if simulation_from_current
        else []
    )


    simulation_progress = (
        st.progress(
            0.0
        )
    )


    simulation_status = (
        st.empty()
    )


    simulation_detail = (
        st.empty()
    )


    def update_simulation_progress(
        completed,
        total,
        message,
    ):

        progress_value = (
            completed
            /
            total
            if total
            else 0.0
        )


        simulation_progress.progress(
            min(
                1.0,
                max(
                    0.0,
                    progress_value,
                ),
            )
        )


        simulation_status.markdown(
            f"**Simulation progress: "
            f"{completed} / {total} sales**"
        )


        simulation_detail.caption(
            message
        )


    try:

        simulation_result = (
            run_draft_simulation(
                number_of_sales=(
                    int(
                        simulation_sale_count
                    )
                ),
                seed=(
                    int(
                        simulation_seed
                    )
                ),
                starting_team_setups=(
                    team_setups
                ),
                starting_pool_players=(
                    pool_result.available_players
                ),
                sleeper_players=(
                    sleeper_players
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
                historical_market_model=(
                    historical_market_model
                ),
                starting_total_auction_cash=(
                    starting_total_auction_cash
                ),
                my_manager_id=(
                    MY_MANAGER_ID
                ),
                initial_sales=(
                    initial_simulation_sales
                ),
                checkpoint_every=(
                    int(
                        simulation_checkpoint
                    )
                ),
                progress_callback=(
                    update_simulation_progress
                ),
            )
        )


        simulation_progress.progress(
            1.0
        )


        simulation_status.success(
            f"Simulation complete — "
            f"{simulation_result.completed_sales} "
            f"sales processed."
        )


        st.session_state[
            "draft_simulation_result"
        ] = simulation_result


    except Exception as error:

        simulation_status.error(
            "Simulation stopped."
        )

        st.error(
            f"Simulation failed: {error}"
        )


simulation_result = (
    st.session_state.get(
        "draft_simulation_result"
    )
)


if simulation_result:

    st.markdown(
        "## Test Results"
    )


    t1, t2, t3, t4, t5 = (
        st.columns(5)
    )


    t1.metric(
        "Requested",
        simulation_result.requested_sales,
    )

    t2.metric(
        "Completed",
        simulation_result.completed_sales,
    )

    t3.metric(
        "Violations",
        len(
            simulation_result.violations
        ),
    )

    t4.metric(
        "Room vs Model",
        (
            f"{simulation_result.final_room_spend_index:.2f}x"
            if (
                simulation_result
                .final_room_spend_index
                is not None
            )
            else "-"
        ),
    )

    t5.metric(
        "Optimizer",
        (
            "FEASIBLE"
            if simulation_result
            .final_optimizer_feasible
            else "FAILED"
        ),
    )


    if not simulation_result.violations:

        st.success(
            "✅ TEST PASSED"
        )

    else:

        st.error(
            f"❌ "
            f"{len(simulation_result.violations)} "
            f"violation(s) detected."
        )


    if simulation_result.stopped_reason:

        st.warning(
            simulation_result.stopped_reason
        )


    simulation_rows = []


    for step in (
        simulation_result.steps
    ):

        manager_name = (
            MANAGERS[
                step.manager_id
            ].sleeper_team_name

            if step.manager_id
            in MANAGERS

            else step.manager_id
        )


        simulation_rows.append(
            {
                "#": step.sale_number,
                "Player": step.player_name,
                "Pos": step.position,
                "Winner": manager_name,
                "Price": step.price,
                "Model $": step.expected_market_value,
                "Player Ceiling": step.player_ceiling,
                "Roster Ceiling": (
                    step.roster_aware_ceiling
                ),
                "Winner Max Before": (
                    step.winner_pre_sale_max_bid
                ),
                "Remaining Cash": (
                    step.remaining_cash
                ),
                "Open Spots": (
                    step.remaining_open_spots
                ),
                "Room vs Model": (
                    step.room_spend_index
                ),
                "Live Signal": (
                    step.live_room_multiplier
                ),
                "Optimizer": (
                    "OK"
                    if step.optimizer_feasible
                    else "FAILED"
                ),
                "Next Nomination": (
                    step.top_nomination
                    or "-"
                ),
                "Violations": (
                    "; ".join(
                        step.violations
                    )
                ),
            }
        )


    if simulation_rows:

        st.dataframe(
            pd.DataFrame(
                simulation_rows
            ),
            use_container_width=True,
            hide_index=True,
        )


    # =====================================================
    # FINAL SIMULATED TEAM STATE
    # =====================================================

    st.markdown(
        "### Final Simulated Team State"
    )


    final_team_rows = []


    for (
        manager_id,
        setup,
    ) in (
        simulation_result
        .final_team_setups
        .items()
    ):

        team_name = (
            MANAGERS[
                manager_id
            ].sleeper_team_name

            if manager_id
            in MANAGERS

            else manager_id
        )


        final_team_rows.append(
            {
                "Team": team_name,
                "Cash": setup.auction_cash,
                "Open Spots": (
                    setup.open_roster_spots
                ),
                "Legal Max": setup.max_bid,
                "Auction Buys": (
                    setup.purchased_count
                ),
                "My Team": (
                    "⭐"
                    if manager_id
                    ==
                    MY_MANAGER_ID
                    else ""
                ),
            }
        )


    if final_team_rows:

        st.dataframe(
            pd.DataFrame(
                final_team_rows
            ).sort_values(
                by="Cash",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )


    # =====================================================
    # POSITION LEARNING
    # =====================================================

    st.markdown(
        "### Learned Position Market"
    )


    position_signal_rows = []


    for position in [
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    ]:

        multiplier = (
            simulation_result
            .final_position_signals
            .get(
                position
            )
        )


        if multiplier is not None:

            position_signal_rows.append(
                {
                    "Position": position,
                    "Learned Multiplier": (
                        multiplier
                    ),
                }
            )


    if position_signal_rows:

        st.dataframe(
            pd.DataFrame(
                position_signal_rows
            ),
            use_container_width=True,
            hide_index=True,
        )


    # =====================================================
    # MANAGER LEARNING
    # =====================================================

    st.markdown(
        "### Learned Manager Behavior"
    )


    manager_signal_rows = []


    for (
        manager_id,
        multiplier,
    ) in (
        simulation_result
        .final_manager_signals
        .items()
    ):

        team_name = (
            MANAGERS[
                manager_id
            ].sleeper_team_name

            if manager_id
            in MANAGERS

            else manager_id
        )


        manager_signal_rows.append(
            {
                "Team": team_name,
                "2026 Aggression": multiplier,
            }
        )


    if manager_signal_rows:

        st.dataframe(
            pd.DataFrame(
                manager_signal_rows
            ).sort_values(
                by="2026 Aggression",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )


    if simulation_result.violations:

        with st.expander(
            "❌ Simulation Violations",
            expanded=True,
        ):

            for violation in (
                simulation_result
                .violations
            ):

                st.error(
                    violation
                )


    if st.button(
        "Clear Simulation Results"
    ):

        del st.session_state[
            "draft_simulation_result"
        ]

        st.rerun()


# =========================================================
# DATA QUALITY
# =========================================================

with st.expander(
    "⚠️ Data Quality"
):

    q1, q2, q3, q4, q5 = (
        st.columns(5)
    )


    q1.metric(
        "Workbook Warnings",
        len(
            league_data.warnings
        ),
    )


    q2.metric(
        "Historical Unmapped",
        historical_market_model
        .unmapped_sales_count,
    )


    q3.metric(
        "Protected Match Issues",
        (
            len(
                pool_result
                .unmatched_keepers
            )
            +
            len(
                pool_result
                .unmatched_nfl_college
            )
        ),
    )


    q4.metric(
        "Persisted Sales",
        draft_store.sale_count(),
    )


    q5.metric(
        "Context Docs",
        context_store.count(),
    )


    if league_data.warnings:

        for warning in (
            league_data.warnings
        ):

            st.write(
                f"• {warning}"
            )