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

from src.league_data import (
    LeagueDataLoader,
)

from src.sleeper_client import (
    SleeperClient,
)

from src.draft_setup import (
    build_team_draft_setup,
)

from src.auction_pool import (
    build_auction_pool,
    normalize_player_name,
)

from src.fantasypros_client import (
    FantasyProsClient,
)

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

from src.auction_values import (
    CURRENT_WEIGHT,
    FUTURE_WEIGHT,
    calculate_auction_values,
)

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

from src.draft_store import (
    DraftStore,
)

from src.sleeper_sync import (
    sync_next_sleeper_sale,
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


# =========================================================
# PERSISTENT DRAFT STORE
# =========================================================

draft_store = DraftStore(
    db_path=DB_PATH,
    league_id=SLEEPER_LEAGUE_ID,
    draft_id=SLEEPER_DRAFT_ID,
    season=SEASON,
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
            rankings_response=rankings_response,
            players_response=players_response,
        )
    )

    return {
        "rankings_response": rankings_response,
        "players_response": players_response,
        "projection_response": projection_response,
        "intelligence": intelligence,
    }


# =========================================================
# LOAD SOURCE DATA
# =========================================================

try:

    sleeper_data = load_sleeper_data()

except Exception as error:

    st.error(
        f"Sleeper failed: {error}"
    )

    st.stop()


try:

    league_data = load_league_workbook()

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

sleeper_rosters = sleeper_data[
    "rosters"
]

sleeper_draft = sleeper_data[
    "draft"
]

sleeper_players = sleeper_data[
    "players"
]


# =========================================================
# FANTASYPROS INTELLIGENCE
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
            response=projection_response,
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
# REPLACEMENT + VORP
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
            projections=projections,
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
# LOAD PERSISTED STATE
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
# SESSION STATE DEFAULTS
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
        "SQLite persistence active"
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
        f"FantasyPros rankings: "
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


if fantasypros_error:

    st.warning(
        f"FantasyPros error: "
        f"{fantasypros_error}"
    )


# =========================================================
# PRE-DRAFT SETUP
# =========================================================

st.subheader(
    "⚙️ Pre-Draft Setup"
)


if setup_locked:

    st.info(
        "Keeper and college settings are locked "
        "because the live auction has started. "
        "Reset the live sales to edit them."
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
                options=keeper_names,
                default=current_keepers,
                max_selections=6,
                disabled=setup_locked,
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
                options=college_names,
                default=current_promotions,
                disabled=setup_locked,
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


        # =================================================
        # SAVE PREDRAFT SETUP
        # =================================================

        draft_store.save_team_setup(
            manager_id=manager_id,
            keepers=selected_keepers,
            college_promotions=(
                selected_promotions
            ),
        )


        # =================================================
        # BUILD TEAM SETUP
        # =================================================

        try:

            setup = (
                build_team_draft_setup(
                    manager_id=manager_id,
                    manager_data=manager_data,
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
# INITIAL AUCTION POOL
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
            sales=live_sales,
        )
    )

except ValueError as error:

    st.error(
        "The persisted live ledger is incompatible "
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
# REMOVE SOLD PLAYERS
# =========================================================

available_players = (
    filter_sold_players(
        available_players=(
            pool_result.available_players
        ),
        sales=live_sales,
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
# LIVE BASELINE AUCTION VALUES
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
# HISTORICAL MARKET CALIBRATION
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


market_value_index = {
    normalize_player_name(
        value.player_name
    ): value

    for value
    in market_values
}


# =========================================================
# LIVE TEAM NEEDS
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
# LIVE BIDDER THREATS
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


threat_index = (
    build_threat_index(
        threat_summaries
    )
)


# =========================================================
# LIVE RECOMMENDATIONS
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
            "The room has paid above modeled market "
            "so far. Those overpayments remove money "
            "from the remaining auction."
        )


    elif room_spend_index <= 0.92:

        st.info(
            "Players have sold below modeled market "
            "so far. Extra cash remains available "
            "for later bidding."
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
# SALE INPUT MODE
# =========================================================

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
        key="sale_input_mode",
    )
)


# =========================================================
# SLEEPER SYNC FUNCTION
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
            managers=MANAGERS,
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


# =========================================================
# SLEEPER LIVE SYNC
# =========================================================

if (
    sale_input_mode
    ==
    "Sleeper Live Sync"
):

    st.info(
        "Sleeper is currently the live sale feed. "
        "Completed auction sales will be written "
        "into the same SQLite ledger used by manual entry."
    )


    sync_control1, sync_control2 = (
        st.columns(2)
    )


    with sync_control1:

        auto_sync = (
            st.toggle(
                "Auto-sync Sleeper",
                key="auto_sleeper_sync",
            )
        )


    with sync_control2:

        poll_seconds = (
            st.number_input(
                "Polling interval (seconds)",
                min_value=1,
                max_value=300,
                step=1,
                key=(
                    "sleeper_poll_seconds"
                ),
                help=(
                    "Enter any whole-number interval "
                    "from 1 to 300 seconds."
                ),
            )
        )


    poll_seconds = int(
        poll_seconds
    )


    if auto_sync:

        st.caption(
            f"Checking Sleeper every "
            f"{poll_seconds} second"
            f"{'' if poll_seconds == 1 else 's'}."
        )

    else:

        st.caption(
            "Automatic polling is disabled. "
            "Use Sync Sleeper Now whenever you want."
        )


    # =====================================================
    # AUTO POLLING VIA STREAMLIT FRAGMENT
    # =====================================================

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
            run_every=fragment_interval
        )
        def sleeper_live_feed():

            button_clicked = (
                st.button(
                    "🔄 Sync Sleeper Now",
                    use_container_width=True,
                    key="sync_sleeper_now",
                )
            )


            should_sync = (
                auto_sync
                or
                button_clicked
            )


            if not should_sync:

                return


            try:

                result = (
                    perform_sleeper_sync()
                )


                if (
                    result.status
                    == "imported"
                ):

                    manager_name = (
                        MANAGERS[
                            result
                            .imported_manager_id
                        ].sleeper_team_name

                        if (
                            result
                            .imported_manager_id
                            in MANAGERS
                        )

                        else (
                            result
                            .imported_manager_id
                        )
                    )


                    st.success(
                        f"✅ Imported "
                        f"{result.imported_player} "
                        f"→ {manager_name} "
                        f"for "
                        f"${result.imported_price}"
                    )


                    # Full rerun is intentional.
                    #
                    # We import only one unseen sale
                    # per sync cycle so the full model
                    # can recalculate before importing
                    # the next auction sale.
                    st.rerun()


                elif (
                    result.status
                    == "conflict"
                ):

                    st.error(
                        "⚠️ Sleeper Sync Conflict"
                    )

                    st.error(
                        result.message
                    )


                else:

                    st.success(
                        "✅ Sleeper synchronized"
                    )


                if result.warnings:

                    with st.expander(
                        "Sleeper Sync Warnings"
                    ):

                        for warning in (
                            result.warnings
                        ):

                            st.write(
                                f"• {warning}"
                            )


            except Exception as error:

                st.error(
                    f"Sleeper sync failed: "
                    f"{error}"
                )


        sleeper_live_feed()


    # =====================================================
    # FALLBACK IF FRAGMENTS NOT AVAILABLE
    # =====================================================

    else:

        st.warning(
            "Your Streamlit version does not support "
            "automatic fragment polling."
        )


        if st.button(
            "🔄 Sync Sleeper Now",
            use_container_width=True,
            key="fallback_sync_sleeper",
        ):

            try:

                result = (
                    perform_sleeper_sync()
                )


                if (
                    result.status
                    == "imported"
                ):

                    st.success(
                        result.message
                    )

                    st.rerun()


                elif (
                    result.status
                    == "conflict"
                ):

                    st.error(
                        result.message
                    )


                else:

                    st.success(
                        result.message
                    )


            except Exception as error:

                st.error(
                    f"Sleeper sync failed: "
                    f"{error}"
                )


# =========================================================
# NOMINATED PLAYER
# =========================================================

st.divider()


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
            key="nominated_player",
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


    market_value = (
        market_value_index.get(
            nominated_key
        )
    )


    if recommendation:

        # =================================================
        # MAIN COPILOT DISPLAY
        # =================================================

        st.markdown(
            f"# {recommendation.player_name}"
        )


        st.caption(
            recommendation.position
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
                (
                    f"${recommendation.expected_market_value:.0f}"
                ),
            )


            st.metric(
                "Baseline Value",
                (
                    f"${recommendation.baseline_value:.0f}"
                ),
            )


        with center:

            st.markdown(
                "## DO NOT EXCEED"
            )


            st.markdown(
                f"# 💰 ${recommendation.do_not_exceed}"
            )


            st.markdown(
                f"### {recommendation.strategy}"
            )


        with right:

            st.metric(
                "Your Legal Max",
                (
                    f"${recommendation.legal_max_bid}"
                ),
            )


            st.metric(
                "Value Edge",
                (
                    f"${recommendation.value_edge:+.0f}"
                ),
            )


        # =================================================
        # CURRENT LIVE BID
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
            recommendation.do_not_exceed
        ):

            st.success(
                f"${recommendation.do_not_exceed - current_bid} "
                f"of bidding room remains."
            )


        elif (
            current_bid
            ==
            recommendation.do_not_exceed
        ):

            st.warning(
                "THIS IS YOUR CEILING. "
                "Do not bid again."
            )


        else:

            st.error(
                f"STOP — current bid is "
                f"${current_bid - recommendation.do_not_exceed} "
                f"above your modeled ceiling."
            )


        # =================================================
        # RECOMMENDATION SIGNALS
        # =================================================

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
                recommendation
                .alternative_player,
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
        # PLAYER INTELLIGENCE
        # =================================================

        with st.expander(
            "Player Intelligence"
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
        # BIDDER THREAT DETAILS
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


                    bidder_rows.append(
                        {
                            "Team": team_name,

                            "Threat": (
                                threat
                                .threat_score
                            ),

                            "Need": (
                                threat
                                .need_score
                                * 100
                            ),

                            "Cash": (
                                threat
                                .auction_cash
                            ),

                            "Legal Max": (
                                threat
                                .max_bid
                            ),

                            "Can Afford": (
                                threat
                                .can_afford_market
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
                    column_config={
                        "Threat": (
                            st.column_config
                            .ProgressColumn(
                                min_value=0,
                                max_value=100,
                            )
                        ),

                        "Need": (
                            st.column_config
                            .ProgressColumn(
                                min_value=0,
                                max_value=100,
                            )
                        ),

                        "Cash": (
                            st.column_config
                            .NumberColumn(
                                format="$%.0f",
                            )
                        ),

                        "Legal Max": (
                            st.column_config
                            .NumberColumn(
                                format="$%.0f",
                            )
                        ),
                    },
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


            st.info(
                "Manual mode is active. "
                "The sale will be written to the "
                "same SQLite ledger used by Sleeper sync."
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
                                price=int(
                                    sale_price
                                ),
                                modeled_market_value=(
                                    recommendation
                                    .expected_market_value
                                ),
                                do_not_exceed=(
                                    recommendation
                                    .do_not_exceed
                                ),
                            )
                        )


                        new_sale = (
                            updated_sales[
                                -1
                            ]
                        )


                        draft_store.add_sale(
                            new_sale
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
        "No auction recommendations are "
        "currently available."
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


    team_rows.append(
        {
            "Team": (
                MANAGERS[
                    manager_id
                ].sleeper_team_name
            ),

            "Cash": (
                setup.auction_cash
            ),

            "Open Spots": (
                setup.open_roster_spots
            ),

            "Legal Max": (
                setup.max_bid
            ),

            "Bought": (
                setup.purchased_count
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
                == MY_MANAGER_ID
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
        column_config={
            "Cash": (
                st.column_config
                .NumberColumn(
                    format="$%.0f",
                )
            ),

            "Legal Max": (
                st.column_config
                .NumberColumn(
                    format="$%.0f",
                )
            ),

            "QB Need": (
                st.column_config
                .ProgressColumn(
                    min_value=0,
                    max_value=100,
                )
            ),

            "RB Need": (
                st.column_config
                .ProgressColumn(
                    min_value=0,
                    max_value=100,
                )
            ),

            "WR Need": (
                st.column_config
                .ProgressColumn(
                    min_value=0,
                    max_value=100,
                )
            ),

            "TE Need": (
                st.column_config
                .ProgressColumn(
                    min_value=0,
                    max_value=100,
                )
            ),

            "K Need": (
                st.column_config
                .ProgressColumn(
                    min_value=0,
                    max_value=100,
                )
            ),

            "DEF Need": (
                st.column_config
                .ProgressColumn(
                    min_value=0,
                    max_value=100,
                )
            ),
        },
    )


# =========================================================
# SALE LEDGER
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


    ledger_rows.append(
        {
            "#": (
                sale.sale_number
            ),

            "Player": (
                sale.player_name
            ),

            "Pos": (
                sale.position
            ),

            "Winner": (
                team_name
            ),

            "Price": (
                sale.price
            ),

            "Market at Sale": (
                sale
                .modeled_market_value
            ),

            "vs Market": (
                delta
            ),

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
        column_config={
            "Price": (
                st.column_config
                .NumberColumn(
                    format="$%.0f",
                )
            ),

            "Market at Sale": (
                st.column_config
                .NumberColumn(
                    format="$%.1f",
                )
            ),

            "vs Market": (
                st.column_config
                .NumberColumn(
                    format="$%+.1f",
                )
            ),

            "My Ceiling": (
                st.column_config
                .NumberColumn(
                    format="$%.0f",
                )
            ),
        },
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


    fp = (
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
            "Player": (
                player.player_name
            ),

            "Pos": (
                player.position
            ),

            "NFL": (
                player.nfl_team
                or "FA"
            ),

            "DO NOT EXCEED": (
                recommendation
                .do_not_exceed
                if recommendation
                else None
            ),

            "Strategy": (
                recommendation
                .strategy
                if recommendation
                else "-"
            ),

            "Market $": (
                market
                .expected_market_value
                if market
                else None
            ),

            "Baseline $": (
                baseline
                .baseline_value
                if baseline
                else None
            ),

            "My Need": (
                recommendation
                .my_need_score
                * 100
                if recommendation
                else 0
            ),

            "Scarcity": (
                recommendation
                .scarcity_score
                * 100
                if recommendation
                else 0
            ),

            "Next Option": (
                recommendation
                .alternative_player
                if (
                    recommendation
                    and
                    recommendation
                    .alternative_player
                )
                else "-"
            ),

            "Threat": (
                threat
                .top_threat_score
                if threat
                else 0
            ),

            "Top Competitor": (
                top_competitor
            ),

            "VORP": (
                vorp.vorp
                if vorp
                else None
            ),

            "2026 ECR": (
                fp.half_ecr
                if fp
                else None
            ),

            "Dynasty ECR": (
                fp.dynasty_ecr
                if fp
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
            "Search Player",
            placeholder="Player...",
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
                "DO NOT EXCEED",
                "Market $",
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


if positions:

    filtered_board = (
        filtered_board[
            filtered_board[
                "Pos"
            ].isin(
                positions
            )
        ]
    )


if search:

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
    column_config={
        "DO NOT EXCEED": (
            st.column_config
            .NumberColumn(
                format="$%.0f",
            )
        ),

        "Market $": (
            st.column_config
            .NumberColumn(
                format="$%.1f",
            )
        ),

        "Baseline $": (
            st.column_config
            .NumberColumn(
                format="$%.1f",
            )
        ),

        "My Need": (
            st.column_config
            .ProgressColumn(
                min_value=0,
                max_value=100,
            )
        ),

        "Scarcity": (
            st.column_config
            .ProgressColumn(
                min_value=0,
                max_value=100,
            )
        ),

        "Threat": (
            st.column_config
            .ProgressColumn(
                min_value=0,
                max_value=100,
            )
        ),

        "VORP": (
            st.column_config
            .NumberColumn(
                format="%.1f",
            )
        ),
    },
)


# =========================================================
# DATA QUALITY
# =========================================================

with st.expander(
    "⚠️ Data Quality"
):

    q1, q2, q3, q4 = (
        st.columns(4)
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


    if league_data.warnings:

        for warning in (
            league_data.warnings
        ):

            st.write(
                f"• {warning}"
            )