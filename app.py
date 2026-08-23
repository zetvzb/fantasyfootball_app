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


# =========================================================
# STREAMLIT CONFIG
# =========================================================

st.set_page_config(
    page_title="Fantasy Auction Copilot",
    page_icon="🏈",
    layout="wide",
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
        "rankings_response": (
            rankings_response
        ),
        "players_response": (
            players_response
        ),
        "projection_response": (
            projection_response
        ),
        "intelligence": (
            intelligence
        ),
    }


# =========================================================
# LOAD SLEEPER
# =========================================================

try:

    sleeper_data = (
        load_sleeper_data()
    )

except Exception as error:

    st.error(
        f"Could not load Sleeper data: {error}"
    )

    st.stop()


# =========================================================
# LOAD WORKBOOK
# =========================================================

try:

    league_data = (
        load_league_workbook()
    )

except FileNotFoundError:

    st.error(
        "Could not find data/league.xlsx"
    )

    st.info(
        "Save the Bishop Sycamore workbook as "
        "`data/league.xlsx`."
    )

    st.stop()

except Exception as error:

    st.error(
        f"Could not load league workbook: {error}"
    )

    st.stop()


# =========================================================
# UNPACK SLEEPER
# =========================================================

league = sleeper_data[
    "league"
]

sleeper_users = sleeper_data[
    "users"
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
# LOAD FANTASYPROS
# =========================================================

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
# FANTASYPROS INTELLIGENCE
# =========================================================

fantasypros_index = (
    build_intelligence_index(
        fantasypros_data[
            "intelligence"
        ]
    )
)


# =========================================================
# PROJECTIONS USING LEAGUE SCORING
# =========================================================

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
# REPLACEMENT LEVELS + VORP
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
            player.player_name
        ): player

        for player
        in player_values
    }


# =========================================================
# HISTORICAL LEAGUE MARKET
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
# SLEEPER LOOKUPS
# =========================================================

rosters_by_id = {
    roster["roster_id"]: roster

    for roster
    in sleeper_rosters
}


def get_player_name(
    player_id,
):

    player = sleeper_players.get(
        player_id,
        {},
    )

    return (
        player.get("full_name")
        or player_id
    )


def get_player_position(
    player_id,
):

    player = sleeper_players.get(
        player_id,
        {},
    )

    return (
        player.get("position")
        or "-"
    )


def get_player_team(
    player_id,
):

    player = sleeper_players.get(
        player_id,
        {},
    )

    return (
        player.get("team")
        or "-"
    )


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
        "Refresh Sleeper",
        use_container_width=True,
    ):

        load_sleeper_data.clear()

        st.rerun()


    if st.button(
        "Reload League Workbook",
        use_container_width=True,
    ):

        load_league_workbook.clear()

        st.rerun()


    if st.button(
        "Refresh FantasyPros",
        use_container_width=True,
    ):

        load_fantasypros_data.clear()

        st.rerun()


    st.divider()


    st.subheader(
        "Data Status"
    )

    st.write(
        f"Managers: "
        f"**{len(league_data.managers)}**"
    )

    st.write(
        f"Historical sales: "
        f"**{len(league_data.historical_sales)}**"
    )

    st.write(
        f"Historical mapped: "
        f"**{len(historical_market_model.mapped_sales)}**"
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
        f"VORP players: "
        f"**{len(player_values)}**"
    )


if fantasypros_error:

    st.warning(
        f"FantasyPros could not be loaded: "
        f"{fantasypros_error}"
    )


# =========================================================
# LEAGUE SUMMARY
# =========================================================

summary1, summary2, summary3, summary4 = (
    st.columns(4)
)


with summary1:

    st.metric(
        "Teams",
        league.get(
            "total_rosters",
            "-"
        ),
    )


with summary2:

    st.metric(
        "Draft Type",
        str(
            sleeper_draft.get(
                "type",
                "-"
            )
        ).title(),
    )


with summary3:

    st.metric(
        "Draft Status",
        str(
            sleeper_draft.get(
                "status",
                "-"
            )
        )
        .replace(
            "_",
            " "
        )
        .title(),
    )


with summary4:

    st.metric(
        "Draft Rounds",
        sleeper_draft.get(
            "settings",
            {},
        ).get(
            "rounds",
            "-"
        ),
    )


st.divider()


# =========================================================
# MY TEAM
# =========================================================

my_identity = (
    MANAGERS[
        MY_MANAGER_ID
    ]
)


my_league_data = (
    league_data.managers.get(
        MY_MANAGER_ID
    )
)


my_roster = (
    rosters_by_id.get(
        my_identity.sleeper_roster_id
    )
)


st.subheader(
    f"⭐ My Team — "
    f"{my_identity.sleeper_team_name}"
)


if my_league_data:

    my1, my2, my3, my4 = (
        st.columns(4)
    )


    with my1:

        st.metric(
            "Pre-Keeper Budget",
            f"${my_league_data.pre_keeper_budget}",
        )


    with my2:

        st.metric(
            "Keeper Options",
            len(
                my_league_data.keeper_options
            ),
        )


    with my3:

        my_college_players = [
            player

            for player
            in league_data.college_players

            if (
                player.manager_id
                == MY_MANAGER_ID
            )
        ]

        st.metric(
            "College Rights",
            len(
                my_college_players
            ),
        )


    with my4:

        st.metric(
            "College Picks",
            len(
                my_league_data.college_picks
            ),
        )


# =========================================================
# CURRENT ROSTER
# =========================================================

with st.expander(
    "View Current Sleeper Roster"
):

    roster_rows = []

    if my_roster:

        for player_id in (
            my_roster.get(
                "players"
            )
            or []
        ):

            roster_rows.append(
                {
                    "Player": (
                        get_player_name(
                            player_id
                        )
                    ),
                    "Position": (
                        get_player_position(
                            player_id
                        )
                    ),
                    "NFL Team": (
                        get_player_team(
                            player_id
                        )
                    ),
                }
            )


    if roster_rows:

        st.dataframe(
            pd.DataFrame(
                roster_rows
            ),
            use_container_width=True,
            hide_index=True,
        )


st.divider()


# =========================================================
# DRAFT SETUP
# =========================================================

st.subheader(
    "⚙️ 2026 Draft Setup"
)

st.caption(
    "Set each team's official keepers and planned "
    "$0 college promotions. All downstream values "
    "recalculate from this state."
)


if (
    "keeper_selections"
    not in st.session_state
):

    st.session_state[
        "keeper_selections"
    ] = {
        manager_id: []

        for manager_id
        in MANAGERS
    }


if (
    "college_promotions"
    not in st.session_state
):

    st.session_state[
        "college_promotions"
    ] = {
        manager_id: []

        for manager_id
        in MANAGERS
    }


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
        f"{identity.sleeper_team_name} "
        f"— {identity.spreadsheet_tab}"
    ):

        # =================================================
        # KEEPERS
        # =================================================

        keeper_lookup = {
            keeper.player_name: keeper

            for keeper
            in manager_data.keeper_options

            if (
                keeper.keeper_cost
                is not None
            )
        }


        keeper_names = list(
            keeper_lookup.keys()
        )


        previous_keepers = (
            st.session_state[
                "keeper_selections"
            ].get(
                manager_id,
                [],
            )
        )


        valid_previous_keepers = [
            player_name

            for player_name
            in previous_keepers

            if (
                player_name
                in keeper_names
            )
        ]


        selected_keepers = (
            st.multiselect(
                "Select Keepers",
                options=(
                    keeper_names
                ),
                default=(
                    valid_previous_keepers
                ),
                max_selections=6,
                format_func=lambda player_name: (
                    f"{player_name} "
                    f"({keeper_lookup[player_name].position}) "
                    f"— ${keeper_lookup[player_name].keeper_cost}"
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

        manager_college_players = [
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
            in manager_college_players
        ]


        previous_college = (
            st.session_state[
                "college_promotions"
            ].get(
                manager_id,
                [],
            )
        )


        valid_previous_college = [
            player_name

            for player_name
            in previous_college

            if (
                player_name
                in college_names
            )
        ]


        selected_college = (
            st.multiselect(
                "Planned $0 Draft Call-Ups",
                options=(
                    college_names
                ),
                default=(
                    valid_previous_college
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
        ] = selected_college


        # =================================================
        # TEAM SETUP
        # =================================================

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
                        selected_college
                    ),
                )
            )


            team_setups[
                manager_id
            ] = setup


            s1, s2, s3, s4, s5 = (
                st.columns(5)
            )


            with s1:

                st.metric(
                    "Keeper Cost",
                    f"${setup.keeper_cost}",
                )


            with s2:

                st.metric(
                    "Auction Cash",
                    f"${setup.auction_cash}",
                )


            with s3:

                st.metric(
                    "Keepers",
                    setup.keeper_count,
                )


            with s4:

                st.metric(
                    "Open Spots",
                    setup.open_roster_spots,
                )


            with s5:

                st.metric(
                    "Legal Max",
                    f"${setup.max_bid}",
                )


        except ValueError as error:

            st.error(
                str(error)
            )


# =========================================================
# STARTING DRAFT STATE
# =========================================================

st.markdown(
    "### Draft Room Starting State"
)


setup_rows = []


for (
    manager_id,
    setup,
) in team_setups.items():

    setup_rows.append(
        {
            "Team": (
                MANAGERS[
                    manager_id
                ].sleeper_team_name
            ),

            "Keepers": (
                setup.keeper_count
            ),

            "Keeper $": (
                setup.keeper_cost
            ),

            "College": (
                setup.college_promotion_count
            ),

            "Auction Cash": (
                setup.auction_cash
            ),

            "Open Spots": (
                setup.open_roster_spots
            ),

            "Legal Max": (
                setup.max_bid
            ),

            "My Team": (
                "⭐"
                if manager_id == MY_MANAGER_ID
                else ""
            ),
        }
    )


setup_df = (
    pd.DataFrame(
        setup_rows
    )
)


if not setup_df.empty:

    setup_df = (
        setup_df.sort_values(
            by="Auction Cash",
            ascending=False,
        )
    )


    st.dataframe(
        setup_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Keeper $": (
                st.column_config
                .NumberColumn(
                    format="$%d"
                )
            ),

            "Auction Cash": (
                st.column_config
                .NumberColumn(
                    format="$%d"
                )
            ),

            "Legal Max": (
                st.column_config
                .NumberColumn(
                    format="$%d"
                )
            ),
        },
    )


# =========================================================
# AUCTION ECONOMY
# =========================================================

total_auction_cash = sum(
    setup.auction_cash

    for setup
    in team_setups.values()
)


total_open_spots = sum(
    setup.open_roster_spots

    for setup
    in team_setups.values()
)


reserve_dollars = (
    total_open_spots
    * MINIMUM_AUCTION_BID
)


discretionary_dollars = max(
    0,
    total_auction_cash
    -
    reserve_dollars,
)


st.markdown(
    "### 💵 Auction Economy"
)


e1, e2, e3, e4 = (
    st.columns(4)
)


with e1:

    st.metric(
        "Auction Cash",
        f"${total_auction_cash:,}",
    )


with e2:

    st.metric(
        "Open Spots",
        total_open_spots,
    )


with e3:

    st.metric(
        "$1 Reserve",
        f"${reserve_dollars:,}",
    )


with e4:

    st.metric(
        "Discretionary $",
        f"${discretionary_dollars:,}",
    )


st.caption(
    f"Baseline player valuation uses "
    f"{CURRENT_WEIGHT:.0%} current-season value and "
    f"{FUTURE_WEIGHT:.0%} future/dynasty value."
)


# =========================================================
# AUCTION PLAYER POOL
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


# =========================================================
# BASELINE AUCTION VALUES
# =========================================================

auction_values = []

auction_value_index = {}


if (
    projections
    and
    fantasypros_index
    and
    team_setups
):

    auction_values = (
        calculate_auction_values(
            available_players=(
                pool_result.available_players
            ),
            team_setups=(
                team_setups
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

market_value_index = {}


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
                total_auction_cash
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
# TEAM NEED PROFILES
# =========================================================

team_need_profiles = (
    build_team_need_profiles(
        team_setups=(
            team_setups
        ),
        sleeper_players=(
            sleeper_players
        ),
    )
)


# =========================================================
# BIDDER THREAT MODEL
# =========================================================

threat_summaries = []

threat_index = {}


if (
    auction_values
    and
    market_values
    and
    team_need_profiles
):

    threat_summaries = (
        calculate_bidder_threats(
            available_players=(
                pool_result.available_players
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
# BID RECOMMENDATION MODEL
# =========================================================

recommendations = []

recommendation_index = {}


if (
    auction_values
    and
    market_values
    and
    team_need_profiles
):

    recommendations = (
        calculate_bid_recommendations(
            available_players=(
                pool_result.available_players
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
# DRAFT NIGHT COPILOT
# =========================================================

st.divider()


st.header(
    "🚨 Draft Night Copilot"
)

st.caption(
    "Select the nominated player. "
    "This is the primary live-auction recommendation."
)


recommendation_player_names = sorted(
    [
        recommendation.player_name

        for recommendation
        in recommendations
    ]
)


if recommendation_player_names:

    selected_player_name = (
        st.selectbox(
            "Nominated Player",
            options=(
                recommendation_player_names
            ),
            key="nominated_player",
        )
    )


    selected_key = (
        normalize_player_name(
            selected_player_name
        )
    )


    recommendation = (
        recommendation_index.get(
            selected_key
        )
    )


    threat_summary = (
        threat_index.get(
            selected_key
        )
    )


    selected_fp = (
        fantasypros_index.get(
            selected_key
        )
    )


    selected_projection = (
        projection_index.get(
            selected_key
        )
    )


    selected_player_value = (
        player_value_index.get(
            selected_key
        )
    )


    if recommendation:

        # =================================================
        # MAIN RECOMMENDATION
        # =================================================

        st.markdown(
            f"## {recommendation.player_name} "
            f"— {recommendation.position}"
        )


        main_left, main_center, main_right = (
            st.columns(
                [
                    1.2,
                    2,
                    1.2,
                ]
            )
        )


        with main_left:

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


        with main_center:

            st.markdown(
                "### DO NOT EXCEED"
            )

            st.markdown(
                f"# 💰 ${recommendation.do_not_exceed}"
            )

            st.markdown(
                f"### {recommendation.strategy}"
            )


        with main_right:

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
        # SIGNALS
        # =================================================

        st.markdown(
            "#### Why"
        )


        signal1, signal2, signal3, signal4 = (
            st.columns(4)
        )


        with signal1:

            st.metric(
                "Your Need",
                (
                    f"{recommendation.my_need_score:.0%}"
                ),
            )


        with signal2:

            st.metric(
                "Scarcity",
                (
                    f"{recommendation.scarcity_score:.0%}"
                ),
            )


        with signal3:

            st.metric(
                "Bidder Threat",
                (
                    f"{recommendation.threat_score:.0f}/100"
                ),
            )


        with signal4:

            if (
                selected_player_value
                and
                selected_player_value.vorp
                is not None
            ):

                vorp_display = (
                    f"{selected_player_value.vorp:.1f}"
                )

            else:

                vorp_display = "-"


            st.metric(
                "VORP",
                vorp_display,
            )


        if recommendation.reasons:

            st.write(
                " • ".join(
                    recommendation.reasons
                )
            )


        # =================================================
        # ALTERNATIVE
        # =================================================

        st.markdown(
            "#### Next Option"
        )


        if (
            recommendation.alternative_player
        ):

            alt1, alt2, alt3 = (
                st.columns(3)
            )


            with alt1:

                st.metric(
                    f"Next {recommendation.position}",
                    (
                        recommendation
                        .alternative_player
                    ),
                )


            with alt2:

                if (
                    recommendation
                    .alternative_market_value
                    is not None
                ):

                    alt_market_display = (
                        f"${recommendation.alternative_market_value:.0f}"
                    )

                else:

                    alt_market_display = "-"


                st.metric(
                    "Expected Market",
                    alt_market_display,
                )


            with alt3:

                if (
                    recommendation
                    .alternative_vorp
                    is not None
                ):

                    alt_vorp_display = (
                        f"{recommendation.alternative_vorp:.1f}"
                    )

                else:

                    alt_vorp_display = "-"


                st.metric(
                    "Alternative VORP",
                    alt_vorp_display,
                )


        else:

            st.warning(
                "No meaningful same-position alternative remains."
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


            with intel1:

                st.metric(
                    "Projected Points",
                    (
                        f"{selected_projection.custom_points:.1f}"
                        if (
                            selected_projection
                            and
                            selected_projection.custom_points
                            is not None
                        )
                        else "-"
                    ),
                )


            with intel2:

                st.metric(
                    "2026 ECR",
                    (
                        f"{selected_fp.half_ecr:.0f}"
                        if (
                            selected_fp
                            and
                            selected_fp.half_ecr
                            is not None
                        )
                        else "-"
                    ),
                )


            with intel3:

                st.metric(
                    "Dynasty ECR",
                    (
                        f"{selected_fp.dynasty_ecr:.0f}"
                        if (
                            selected_fp
                            and
                            selected_fp.dynasty_ecr
                            is not None
                        )
                        else "-"
                    ),
                )


            with intel4:

                st.metric(
                    "ADP",
                    (
                        f"{selected_fp.adp:.1f}"
                        if (
                            selected_fp
                            and
                            selected_fp.adp
                            is not None
                        )
                        else "-"
                    ),
                )


        # =================================================
        # COMPETING BIDDERS
        # =================================================

        with st.expander(
            "Who Might Bid Against Me?"
        ):

            if (
                threat_summary
                and
                threat_summary.threats
            ):

                bidder_rows = []


                for threat in (
                    threat_summary.threats
                ):

                    manager_id = (
                        threat.manager_id
                    )


                    if manager_id in MANAGERS:

                        team_name = (
                            MANAGERS[
                                manager_id
                            ].sleeper_team_name
                        )

                    else:

                        team_name = (
                            manager_id
                        )


                    bidder_rows.append(
                        {
                            "Team": (
                                team_name
                            ),

                            "Threat": (
                                threat.threat_score
                            ),

                            "Level": (
                                threat.threat_level
                            ),

                            "Need": (
                                threat.need_score
                                * 100
                            ),

                            "Cash": (
                                threat.auction_cash
                            ),

                            "Max Bid": (
                                threat.max_bid
                            ),

                            "Can Afford": (
                                threat.can_afford_market
                            ),

                            "Why": (
                                "; ".join(
                                    threat.reasons
                                )
                            ),
                        }
                    )


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
                                format="%.0f",
                            )
                        ),

                        "Need": (
                            st.column_config
                            .ProgressColumn(
                                min_value=0,
                                max_value=100,
                                format="%.0f",
                            )
                        ),

                        "Cash": (
                            st.column_config
                            .NumberColumn(
                                format="$%.0f",
                            )
                        ),

                        "Max Bid": (
                            st.column_config
                            .NumberColumn(
                                format="$%.0f",
                            )
                        ),
                    },
                )


            else:

                st.info(
                    "No bidder-threat data available."
                )


else:

    st.warning(
        "No bid recommendations are currently available. "
        "Check FantasyPros data and draft setup."
    )


# =========================================================
# TEAM NEED OVERVIEW
# =========================================================

st.divider()


st.subheader(
    "🧩 Team Needs"
)


team_need_rows = []


for (
    manager_id,
    profile,
) in (
    team_need_profiles.items()
):

    team_name = (
        MANAGERS[
            manager_id
        ].sleeper_team_name

        if manager_id in MANAGERS

        else manager_id
    )


    team_need_rows.append(
        {
            "Team": (
                team_name
            ),

            "QB": (
                profile
                .need_scores
                .get(
                    "QB",
                    0.0,
                )
                * 100
            ),

            "RB": (
                profile
                .need_scores
                .get(
                    "RB",
                    0.0,
                )
                * 100
            ),

            "WR": (
                profile
                .need_scores
                .get(
                    "WR",
                    0.0,
                )
                * 100
            ),

            "TE": (
                profile
                .need_scores
                .get(
                    "TE",
                    0.0,
                )
                * 100
            ),

            "K": (
                profile
                .need_scores
                .get(
                    "K",
                    0.0,
                )
                * 100
            ),

            "DEF": (
                profile
                .need_scores
                .get(
                    "DEF",
                    0.0,
                )
                * 100
            ),

            "Cash": (
                profile.auction_cash
            ),

            "Max Bid": (
                profile.max_bid
            ),

            "Open Spots": (
                profile.open_spots
            ),

            "My Team": (
                "⭐"
                if manager_id == MY_MANAGER_ID
                else ""
            ),
        }
    )


if team_need_rows:

    st.dataframe(
        pd.DataFrame(
            team_need_rows
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "QB": (
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                )
            ),

            "RB": (
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                )
            ),

            "WR": (
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                )
            ),

            "TE": (
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                )
            ),

            "K": (
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                )
            ),

            "DEF": (
                st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                )
            ),

            "Cash": (
                st.column_config.NumberColumn(
                    format="$%.0f",
                )
            ),

            "Max Bid": (
                st.column_config.NumberColumn(
                    format="$%.0f",
                )
            ),
        },
    )


# =========================================================
# BUILD AUCTION BOARD
# =========================================================

pool_rows = []


for player in (
    pool_result.available_players
):

    key = (
        normalize_player_name(
            player.player_name
        )
    )


    fp = (
        fantasypros_index.get(
            key
        )
    )


    projection = (
        projection_index.get(
            key
        )
    )


    value_data = (
        player_value_index.get(
            key
        )
    )


    auction_value = (
        auction_value_index.get(
            key
        )
    )


    market_value = (
        market_value_index.get(
            key
        )
    )


    threat_summary = (
        threat_index.get(
            key
        )
    )


    recommendation = (
        recommendation_index.get(
            key
        )
    )


    # =====================================================
    # TOP COMPETITOR
    # =====================================================

    top_competitor = "-"


    if (
        threat_summary
        and
        threat_summary.top_manager_id
    ):

        manager_id = (
            threat_summary
            .top_manager_id
        )


        if manager_id in MANAGERS:

            top_competitor = (
                MANAGERS[
                    manager_id
                ].sleeper_team_name
            )

        else:

            top_competitor = (
                manager_id
            )


    pool_rows.append(
        {
            "Sleeper ID": (
                player.sleeper_id
            ),

            "Player": (
                player.player_name
            ),

            "Pos": (
                player.position
            ),

            "Team": (
                player.nfl_team
                or "FA"
            ),

            # =============================================
            # PRIMARY RECOMMENDATION
            # =============================================

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

            "My Need": (
                recommendation
                .my_need_score
                * 100

                if recommendation

                else 0.0
            ),

            "Scarcity": (
                recommendation
                .scarcity_score
                * 100

                if recommendation

                else 0.0
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

            # =============================================
            # MARKET
            # =============================================

            "Expected Market $": (
                market_value
                .expected_market_value

                if market_value

                else None
            ),

            "Baseline $": (
                auction_value
                .baseline_value

                if auction_value

                else None
            ),

            "Historical $": (
                market_value
                .historical_expected_price

                if market_value

                else None
            ),

            # =============================================
            # COMPETITION
            # =============================================

            "Top Competitor": (
                top_competitor
            ),

            "Threat Score": (
                threat_summary
                .top_threat_score

                if threat_summary

                else 0.0
            ),

            "High Threats": (
                threat_summary
                .high_threat_count

                if threat_summary

                else 0
            ),

            # =============================================
            # FOOTBALL VALUE
            # =============================================

            "Proj Pts": (
                projection.custom_points

                if projection

                else None
            ),

            "VORP": (
                value_data.vorp

                if value_data

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

            "ADP": (
                fp.adp

                if fp

                else None
            ),

            "Depth": (
                player.depth_chart_position
                or "-"
            ),

            "Age": (
                player.age
            ),
        }
    )


pool_df = (
    pd.DataFrame(
        pool_rows
    )
)


# =========================================================
# AUCTION BOARD
# =========================================================

st.divider()


st.subheader(
    "📋 Full Auction Board"
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

    player_search = (
        st.text_input(
            "Search Player",
            placeholder="Search...",
        )
    )


with filter2:

    selected_positions = (
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

    sort_mode = (
        st.selectbox(
            "Sort By",
            options=[
                "DO NOT EXCEED",
                "Expected Market $",
                "My Need",
                "Scarcity",
                "Threat Score",
                "VORP",
                "2026 ECR",
                "Dynasty ECR",
            ],
        )
    )


filtered_pool_df = (
    pool_df.copy()
)


if selected_positions:

    filtered_pool_df = (
        filtered_pool_df[
            filtered_pool_df[
                "Pos"
            ].isin(
                selected_positions
            )
        ]
    )


if player_search:

    filtered_pool_df = (
        filtered_pool_df[
            filtered_pool_df[
                "Player"
            ]
            .str.contains(
                player_search,
                case=False,
                na=False,
            )
        ]
    )


if not filtered_pool_df.empty:

    if sort_mode in [
        "DO NOT EXCEED",
        "Expected Market $",
        "My Need",
        "Scarcity",
        "Threat Score",
        "VORP",
    ]:

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by=(
                    sort_mode
                ),
                ascending=False,
                na_position="last",
            )
        )


    elif sort_mode in [
        "2026 ECR",
        "Dynasty ECR",
    ]:

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by=(
                    sort_mode
                ),
                ascending=True,
                na_position="last",
            )
        )


st.dataframe(
    filtered_pool_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Sleeper ID": None,

        "DO NOT EXCEED": (
            st.column_config
            .NumberColumn(
                format="$%d",
            )
        ),

        "Expected Market $": (
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

        "Historical $": (
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
                format="%.0f",
            )
        ),

        "Scarcity": (
            st.column_config
            .ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.0f",
            )
        ),

        "Threat Score": (
            st.column_config
            .ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.0f",
            )
        ),

        "Proj Pts": (
            st.column_config
            .NumberColumn(
                format="%.1f",
            )
        ),

        "VORP": (
            st.column_config
            .NumberColumn(
                format="%.1f",
            )
        ),

        "2026 ECR": (
            st.column_config
            .NumberColumn(
                format="%.0f",
            )
        ),

        "Dynasty ECR": (
            st.column_config
            .NumberColumn(
                format="%.0f",
            )
        ),

        "ADP": (
            st.column_config
            .NumberColumn(
                format="%.1f",
            )
        ),
    },
)


# =========================================================
# HISTORICAL LEAGUE INFO
# =========================================================

st.divider()


st.subheader(
    "🧠 Historical League Intelligence"
)


hist1, hist2, hist3, hist4 = (
    st.columns(4)
)


with hist1:

    st.metric(
        "Usable Historical Sales",
        len(
            historical_market_model
            .mapped_sales
        ),
    )


with hist2:

    st.metric(
        "Eligible Seasons",
        len(
            historical_market_model
            .eligible_years
        ),
    )


with hist3:

    st.metric(
        "Excluded Seasons",
        len(
            historical_market_model
            .excluded_years
        ),
    )


with hist4:

    st.metric(
        "Historical Avg Buy",
        (
            f"${historical_market_model.league_average_purchase:.1f}"
        ),
    )


# =========================================================
# MANAGER BEHAVIOR
# =========================================================

with st.expander(
    "Manager Historical Behavior"
):

    manager_rows = []


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

            if manager_id in MANAGERS

            else manager_id
        )


        position_shares = sorted(
            profile
            .position_spend_share
            .items(),
            key=lambda item: (
                item[1]
            ),
            reverse=True,
        )


        if position_shares:

            top_position = (
                position_shares[
                    0
                ][
                    0
                ]
            )

            top_position_share = (
                position_shares[
                    0
                ][
                    1
                ]
            )

        else:

            top_position = "-"

            top_position_share = 0.0


        manager_rows.append(
            {
                "Team": (
                    team_name
                ),

                "Buys": (
                    profile.sales_count
                ),

                "Avg Buy": (
                    profile.average_price
                ),

                "Max Buy": (
                    profile.max_price
                ),

                "Aggressiveness": (
                    profile
                    .aggressiveness_index
                ),

                "Star Chase": (
                    profile
                    .star_chase_index
                ),

                "Top Position": (
                    top_position
                ),

                "Top Pos Spend": (
                    top_position_share
                ),
            }
        )


    if manager_rows:

        st.dataframe(
            pd.DataFrame(
                manager_rows
            ).sort_values(
                by="Aggressiveness",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Avg Buy": (
                    st.column_config
                    .NumberColumn(
                        format="$%.1f"
                    )
                ),

                "Max Buy": (
                    st.column_config
                    .NumberColumn(
                        format="$%.1f"
                    )
                ),

                "Aggressiveness": (
                    st.column_config
                    .NumberColumn(
                        format="%.2f"
                    )
                ),

                "Star Chase": (
                    st.column_config
                    .NumberColumn(
                        format="%.2f"
                    )
                ),

                "Top Pos Spend": (
                    st.column_config
                    .NumberColumn(
                        format="%.0%%"
                    )
                ),
            },
        )


# =========================================================
# PROTECTED PLAYERS
# =========================================================

with st.expander(
    "🔒 Protected Players / Matching"
):

    keeper_tab, college_tab, match_tab = (
        st.tabs(
            [
                "Keepers",
                "College Rights",
                "Matching Issues",
            ]
        )
    )


    with keeper_tab:

        if (
            pool_result
            .excluded_keepers
        ):

            st.dataframe(
                pd.DataFrame(
                    {
                        "Player": (
                            pool_result
                            .excluded_keepers
                        )
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )


    with college_tab:

        if (
            pool_result
            .excluded_college
        ):

            st.dataframe(
                pd.DataFrame(
                    {
                        "Player": (
                            pool_result
                            .excluded_college
                        )
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )


    with match_tab:

        if (
            not pool_result
            .unmatched_keepers
            and
            not pool_result
            .unmatched_nfl_college
        ):

            st.success(
                "All protected NFL players matched."
            )

        else:

            if (
                pool_result
                .unmatched_keepers
            ):

                st.write(
                    "**Unmatched keepers**"
                )

                for player_name in (
                    pool_result
                    .unmatched_keepers
                ):

                    st.write(
                        f"• {player_name}"
                    )


            if (
                pool_result
                .unmatched_nfl_college
            ):

                st.write(
                    "**Unmatched college NFL players**"
                )

                for player_name in (
                    pool_result
                    .unmatched_nfl_college
                ):

                    st.write(
                        f"• {player_name}"
                    )


# =========================================================
# DATA QUALITY
# =========================================================

with st.expander(
    "⚠️ Data Quality"
):

    quality1, quality2, quality3 = (
        st.columns(3)
    )


    with quality1:

        st.metric(
            "Workbook Warnings",
            len(
                league_data.warnings
            ),
        )


    with quality2:

        st.metric(
            "Historical Unmapped",
            historical_market_model
            .unmapped_sales_count,
        )


    with quality3:

        st.metric(
            "Auction Matching Issues",
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


    if league_data.warnings:

        for warning in (
            league_data.warnings
        ):

            st.write(
                f"• {warning}"
            )