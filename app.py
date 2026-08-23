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

    sleeper_data = load_sleeper_data()

except Exception as error:

    st.error(
        f"Could not load Sleeper data: {error}"
    )

    st.stop()


# =========================================================
# LOAD WORKBOOK
# =========================================================

try:

    league_data = load_league_workbook()

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
# PROJECTIONS USING EXACT LEAGUE SCORING
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

        for player in player_values
    }


# =========================================================
# SLEEPER LOOKUPS
# =========================================================

users_by_id = {
    user["user_id"]: user
    for user in sleeper_users
}


rosters_by_id = {
    roster["roster_id"]: roster
    for roster in sleeper_rosters
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
        "League"
    )

    st.write(
        f"**Season:** {SEASON}"
    )

    st.write(
        f"**League ID:** "
        f"{SLEEPER_LEAGUE_ID}"
    )

    st.write(
        f"**Draft ID:** "
        f"{SLEEPER_DRAFT_ID}"
    )


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
        f"College players: "
        f"**{len(league_data.college_players)}**"
    )

    st.write(
        f"FP intelligence: "
        f"**{len(fantasypros_data['intelligence'])}**"
    )

    st.write(
        f"FP projections: "
        f"**{len(projections)}**"
    )

    st.write(
        f"VORP players: "
        f"**{len(player_values)}**"
    )

    st.write(
        f"Workbook warnings: "
        f"**{len(league_data.warnings)}**"
    )


# =========================================================
# DATA ERRORS
# =========================================================

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

my_identity = MANAGERS[
    MY_MANAGER_ID
]

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
            (
                f"${my_league_data.pre_keeper_budget}"
            ),
        )


    with my2:

        st.metric(
            "Keeper Options",
            len(
                my_league_data
                .keeper_options
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
                my_league_data
                .college_picks
            ),
        )


# =========================================================
# MY CURRENT SLEEPER ROSTER
# =========================================================

if my_roster:

    st.markdown(
        "#### Current Sleeper Roster"
    )

    roster_rows = []


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


    st.dataframe(
        pd.DataFrame(
            roster_rows
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# MY KEEPER OPTIONS
# =========================================================

if my_league_data:

    st.markdown(
        "#### 2026 Keeper Options"
    )

    keeper_rows = []


    for keeper in (
        my_league_data
        .keeper_options
    ):

        keeper_rows.append(
            {
                "Player": (
                    keeper.player_name
                ),
                "Position": (
                    keeper.position
                ),
                "2026 Keeper Cost": (
                    keeper.keeper_cost
                ),
            }
        )


    keeper_df = pd.DataFrame(
        keeper_rows
    )


    if not keeper_df.empty:

        keeper_df = (
            keeper_df.sort_values(
                by="2026 Keeper Cost",
                ascending=True,
                na_position="last",
            )
        )

        st.dataframe(
            keeper_df,
            use_container_width=True,
            hide_index=True,
        )


st.markdown(
    "#### College / Taxi Rights"
)


my_college_rows = []


for player in (
    league_data.college_players
):

    if (
        player.manager_id
        != MY_MANAGER_ID
    ):
        continue


    my_college_rows.append(
        {
            "Player": (
                player.player_name
            ),
            "School / Team": (
                player.school_or_team
            ),
            "Status": (
                "NFL"
                if (
                    player.status
                    == "in_nfl"
                )
                else "College"
            ),
        }
    )


if my_college_rows:

    st.dataframe(
        pd.DataFrame(
            my_college_rows
        ),
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# =========================================================
# LEAGUE ECONOMICS
# =========================================================

st.subheader(
    "💰 2026 League Economics"
)


economics_rows = []


for (
    manager_id,
    identity,
) in MANAGERS.items():

    manager_data = (
        league_data.managers.get(
            manager_id
        )
    )


    sleeper_roster = (
        rosters_by_id.get(
            identity.sleeper_roster_id
        )
    )


    current_roster_count = 0


    if sleeper_roster:

        current_roster_count = len(
            sleeper_roster.get(
                "players"
            )
            or []
        )


    college_count = len(
        [
            player
            for player
            in league_data.college_players
            if (
                player.manager_id
                == manager_id
            )
        ]
    )


    economics_rows.append(
        {
            "Team": (
                identity.sleeper_team_name
            ),
            "Manager Sheet": (
                identity.spreadsheet_tab
            ),
            "Pre-Keeper Budget": (
                manager_data.pre_keeper_budget
                if manager_data
                else None
            ),
            "Keeper Options": (
                len(
                    manager_data
                    .keeper_options
                )
                if manager_data
                else 0
            ),
            "College Rights": (
                college_count
            ),
            "College Picks": (
                len(
                    manager_data
                    .college_picks
                )
                if manager_data
                else 0
            ),
            "Sleeper Players": (
                current_roster_count
            ),
            "My Team": (
                "⭐"
                if (
                    manager_id
                    == MY_MANAGER_ID
                )
                else ""
            ),
        }
    )


st.dataframe(
    pd.DataFrame(
        economics_rows
    ),
    use_container_width=True,
    hide_index=True,
)


st.divider()


# =========================================================
# MANAGER DETAIL
# =========================================================

st.subheader(
    "👥 Manager Detail"
)


selected_manager_id = (
    st.selectbox(
        "Select a manager",
        options=list(
            MANAGERS.keys()
        ),
        format_func=lambda manager_id: (
            MANAGERS[
                manager_id
            ].sleeper_team_name
        ),
    )
)


selected_identity = MANAGERS[
    selected_manager_id
]


selected_manager_data = (
    league_data.managers.get(
        selected_manager_id
    )
)


selected_roster = (
    rosters_by_id.get(
        selected_identity
        .sleeper_roster_id
    )
)


if selected_manager_data:

    d1, d2, d3, d4 = (
        st.columns(4)
    )


    with d1:

        st.metric(
            "Pre-Keeper Budget",
            f"${selected_manager_data.pre_keeper_budget}",
        )


    with d2:

        st.metric(
            "Keeper Options",
            len(
                selected_manager_data
                .keeper_options
            ),
        )


    selected_college = [
        player
        for player
        in league_data.college_players
        if (
            player.manager_id
            == selected_manager_id
        )
    ]


    with d3:

        st.metric(
            "College Rights",
            len(
                selected_college
            ),
        )


    with d4:

        st.metric(
            "College Picks",
            len(
                selected_manager_data
                .college_picks
            ),
        )


manager_keeper_tab, manager_roster_tab, manager_college_tab = (
    st.tabs(
        [
            "Keeper Options",
            "Sleeper Roster",
            "College Rights",
        ]
    )
)


with manager_keeper_tab:

    if selected_manager_data:

        rows = [
            {
                "Player": (
                    keeper.player_name
                ),
                "Position": (
                    keeper.position
                ),
                "2026 Cost": (
                    keeper.keeper_cost
                ),
            }

            for keeper
            in selected_manager_data
            .keeper_options
        ]


        if rows:

            df = pd.DataFrame(
                rows
            ).sort_values(
                by="2026 Cost",
                ascending=True,
                na_position="last",
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )


with manager_roster_tab:

    rows = []


    if selected_roster:

        for player_id in (
            selected_roster.get(
                "players"
            )
            or []
        ):

            rows.append(
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


    if rows:

        st.dataframe(
            pd.DataFrame(
                rows
            ),
            use_container_width=True,
            hide_index=True,
        )


with manager_college_tab:

    rows = [
        {
            "Player": (
                player.player_name
            ),
            "School / Team": (
                player.school_or_team
            ),
            "Status": (
                "NFL"
                if (
                    player.status
                    == "in_nfl"
                )
                else "College"
            ),
        }

        for player
        in league_data.college_players

        if (
            player.manager_id
            == selected_manager_id
        )
    ]


    if rows:

        st.dataframe(
            pd.DataFrame(
                rows
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
    "Select official keepers and planned "
    "$0 college call-ups."
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
        # KEEPER OPTIONS
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
                    f"— "
                    f"${keeper_lookup[player_name].keeper_cost}"
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
        # COLLEGE CALL-UPS
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
        # TEAM STATE
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
                    "Pre-Keeper $",
                    f"${setup.pre_keeper_budget}",
                )


            with s2:

                st.metric(
                    "Keeper Cost",
                    f"${setup.keeper_cost}",
                )


            with s3:

                st.metric(
                    "Auction Cash",
                    f"${setup.auction_cash}",
                )


            with s4:

                st.metric(
                    "Open Spots",
                    setup.open_roster_spots,
                )


            with s5:

                st.metric(
                    "Max Bid",
                    f"${setup.max_bid}",
                )


        except ValueError as error:

            st.error(
                str(error)
            )


# =========================================================
# DRAFT ROOM STARTING STATE
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
            "College Call-Ups": (
                setup.college_promotion_count
            ),
            "Auction Cash": (
                setup.auction_cash
            ),
            "Open Spots": (
                setup.open_roster_spots
            ),
            "Max Bid": (
                setup.max_bid
            ),
            "My Team": (
                "⭐"
                if (
                    manager_id
                    == MY_MANAGER_ID
                )
                else ""
            ),
        }
    )


setup_df = pd.DataFrame(
    setup_rows
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
    )


# =========================================================
# AUCTION ECONOMY
# =========================================================

st.markdown(
    "### 💵 Auction Economy"
)


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
    - reserve_dollars,
)


econ1, econ2, econ3, econ4 = (
    st.columns(4)
)


with econ1:

    st.metric(
        "Auction Cash",
        f"${total_auction_cash:,}"
    )


with econ2:

    st.metric(
        "Open Roster Spots",
        total_open_spots,
    )


with econ3:

    st.metric(
        "$1 Reserve",
        f"${reserve_dollars:,}",
    )


with econ4:

    st.metric(
        "Discretionary $",
        f"${discretionary_dollars:,}",
    )


st.caption(
    f"Baseline auction model: "
    f"{CURRENT_WEIGHT:.0%} current-season value + "
    f"{FUTURE_WEIGHT:.0%} dynasty/future value."
)


# =========================================================
# REPLACEMENT LEVELS
# =========================================================

if replacement_levels:

    st.markdown(
        "### 📊 Replacement Levels"
    )


    rep1, rep2, rep3, rep4 = (
        st.columns(4)
    )


    with rep1:

        st.metric(
            "QB Replacement",
            round(
                replacement_levels
                .points_by_position[
                    "QB"
                ],
                1,
            ),
        )


    with rep2:

        st.metric(
            "RB Replacement",
            round(
                replacement_levels
                .points_by_position[
                    "RB"
                ],
                1,
            ),
        )


    with rep3:

        st.metric(
            "WR Replacement",
            round(
                replacement_levels
                .points_by_position[
                    "WR"
                ],
                1,
            ),
        )


    with rep4:

        st.metric(
            "TE Replacement",
            round(
                replacement_levels
                .points_by_position[
                    "TE"
                ],
                1,
            ),
        )


    flex_description = ", ".join(
        [
            f"{position}: {count}"

            for (
                position,
                count,
            ) in (
                replacement_levels
                .flex_allocations
                .items()
            )
        ]
    )


    st.caption(
        f"Projected FLEX allocation: "
        f"{flex_description}"
    )


# =========================================================
# AUCTION PLAYER POOL
# =========================================================

st.divider()


st.subheader(
    "🏈 2026 Auction Player Pool"
)


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
# CALCULATE BASELINE AUCTION VALUES
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
                pool_result
                .available_players
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
# PLAYER POOL SUMMARY
# =========================================================

pool1, pool2, pool3, pool4 = (
    st.columns(4)
)


with pool1:

    st.metric(
        "Available Players",
        len(
            pool_result
            .available_players
        ),
    )


with pool2:

    st.metric(
        "Selected Keepers",
        len(
            pool_result
            .excluded_keepers
        ),
    )


with pool3:

    st.metric(
        "Protected College",
        len(
            pool_result
            .excluded_college
        ),
    )


with pool4:

    matching_issues = (
        len(
            pool_result
            .unmatched_keepers
        )
        +
        len(
            pool_result
            .unmatched_nfl_college
        )
    )

    st.metric(
        "Matching Issues",
        matching_issues,
    )


# =========================================================
# BUILD AUCTION BOARD
# =========================================================

pool_rows = []


for player in (
    pool_result.available_players
):

    key = normalize_player_name(
        player.player_name
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


    pool_rows.append(
        {
            "Sleeper ID": (
                player.sleeper_id
            ),

            "Player": (
                player.player_name
            ),

            "Position": (
                player.position
            ),

            "NFL Team": (
                player.nfl_team
                or "FA"
            ),

            # =============================================
            # FIRST AUCTION VALUE
            # =============================================

            "Baseline $": (
                auction_value
                .baseline_value

                if auction_value

                else None
            ),

            "Expected Drafted": (
                auction_value
                .expected_to_be_drafted

                if auction_value

                else False
            ),

            # =============================================
            # PROJECTIONS / VORP
            # =============================================

            "Proj Pts": (
                projection.custom_points

                if projection

                else None
            ),

            "Replacement": (
                value_data
                .replacement_points

                if value_data

                else None
            ),

            "VORP": (
                value_data.vorp

                if value_data

                else None
            ),

            # =============================================
            # CURRENT ECR
            # =============================================

            "2026 ECR": (
                fp.half_ecr

                if fp

                else None
            ),

            "Pos Rank": (
                fp.half_position_rank

                if fp

                else None
            ),

            # =============================================
            # DYNASTY
            # =============================================

            "Dynasty ECR": (
                fp.dynasty_ecr

                if fp

                else None
            ),

            "Dynasty Pos": (
                fp.dynasty_position_rank

                if fp

                else None
            ),

            # =============================================
            # MARKET SIGNALS
            # =============================================

            "ADP": (
                fp.adp

                if fp

                else None
            ),

            # =============================================
            # EXPERT UNCERTAINTY
            # =============================================

            "ECR Min": (
                fp.ecr_min

                if fp

                else None
            ),

            "ECR Max": (
                fp.ecr_max

                if fp

                else None
            ),

            "ECR Std": (
                fp.ecr_std

                if fp

                else None
            ),

            # =============================================
            # PLAYER CONTEXT
            # =============================================

            "Depth": (
                player
                .depth_chart_position
                or "-"
            ),

            "Depth Order": (
                player.depth_chart_order
            ),

            "Age": (
                player.age
            ),

            "Experience": (
                player.years_exp
            ),

            "Status": (
                player.status
                or "-"
            ),
        }
    )


pool_df = pd.DataFrame(
    pool_rows
)


# =========================================================
# AUCTION BOARD FILTERS
# =========================================================

st.markdown(
    "### 🔎 Auction Board"
)


filter1, filter2, filter3, filter4 = (
    st.columns(
        [
            2,
            1,
            1,
            1,
        ]
    )
)


with filter1:

    player_search = (
        st.text_input(
            "Search player",
            placeholder=(
                "e.g. Jahmyr Gibbs"
            ),
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

    if not pool_df.empty:

        nfl_team_options = sorted(
            pool_df[
                "NFL Team"
            ]
            .dropna()
            .unique()
            .tolist()
        )

    else:

        nfl_team_options = []


    selected_nfl_teams = (
        st.multiselect(
            "NFL Team",
            options=(
                nfl_team_options
            ),
        )
    )


with filter4:

    sort_mode = (
        st.selectbox(
            "Sort By",
            options=[
                "Baseline $",
                "VORP",
                "2026 ECR",
                "Dynasty ECR",
                "Projected Points",
            ],
        )
    )


# =========================================================
# FILTER PLAYER BOARD
# =========================================================

filtered_pool_df = (
    pool_df.copy()
)


if selected_positions:

    filtered_pool_df = (
        filtered_pool_df[
            filtered_pool_df[
                "Position"
            ].isin(
                selected_positions
            )
        ]
    )


if selected_nfl_teams:

    filtered_pool_df = (
        filtered_pool_df[
            filtered_pool_df[
                "NFL Team"
            ].isin(
                selected_nfl_teams
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


# =========================================================
# SORT PLAYER BOARD
# =========================================================

if not filtered_pool_df.empty:

    if sort_mode == "Baseline $":

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by=[
                    "Baseline $",
                    "VORP",
                ],
                ascending=[
                    False,
                    False,
                ],
                na_position="last",
            )
        )


    elif sort_mode == "VORP":

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by="VORP",
                ascending=False,
                na_position="last",
            )
        )


    elif sort_mode == "2026 ECR":

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by="2026 ECR",
                ascending=True,
                na_position="last",
            )
        )


    elif sort_mode == "Dynasty ECR":

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by="Dynasty ECR",
                ascending=True,
                na_position="last",
            )
        )


    elif sort_mode == "Projected Points":

        filtered_pool_df = (
            filtered_pool_df.sort_values(
                by="Proj Pts",
                ascending=False,
                na_position="last",
            )
        )


# =========================================================
# POSITION COUNTS
# =========================================================

if not filtered_pool_df.empty:

    position_counts = (
        filtered_pool_df[
            "Position"
        ]
        .value_counts()
    )


    position_columns = (
        st.columns(6)
    )


    for (
        column,
        position,
    ) in zip(
        position_columns,
        [
            "QB",
            "RB",
            "WR",
            "TE",
            "K",
            "DEF",
        ],
    ):

        with column:

            st.metric(
                position,
                int(
                    position_counts.get(
                        position,
                        0,
                    )
                ),
            )


# =========================================================
# DISPLAY AUCTION BOARD
# =========================================================

st.dataframe(
    filtered_pool_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Sleeper ID": None,

        "Baseline $": (
            st.column_config
            .NumberColumn(
                format="$%.1f",
            )
        ),

        "Proj Pts": (
            st.column_config
            .NumberColumn(
                format="%.1f",
            )
        ),

        "Replacement": (
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

        "Pos Rank": (
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

        "Dynasty Pos": (
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

        "ECR Min": (
            st.column_config
            .NumberColumn(
                format="%.0f",
            )
        ),

        "ECR Max": (
            st.column_config
            .NumberColumn(
                format="%.0f",
            )
        ),

        "ECR Std": (
            st.column_config
            .NumberColumn(
                format="%.1f",
            )
        ),
    },
)


st.caption(
    "Baseline $ is the first deterministic model, "
    "not yet the final DO NOT EXCEED price. "
    "Opponent demand, historical league pricing, "
    "your roster need, and live auction behavior "
    "will be layered on next."
)


# =========================================================
# PROTECTED PLAYERS
# =========================================================

st.markdown(
    "### 🔒 Protected Players"
)


keeper_protection_tab, college_protection_tab, match_tab = (
    st.tabs(
        [
            "Keepers",
            "College Rights",
            "Matching Issues",
        ]
    )
)


with keeper_protection_tab:

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
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No keepers selected yet."
        )


with college_protection_tab:

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
            use_container_width=True,
            hide_index=True,
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
            "All protected NFL players "
            "matched successfully."
        )


    else:

        if (
            pool_result
            .unmatched_keepers
        ):

            st.warning(
                "Unmatched keepers:"
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

            st.warning(
                "Unmatched NFL college-rights players:"
            )

            for player_name in (
                pool_result
                .unmatched_nfl_college
            ):

                st.write(
                    f"• {player_name}"
                )


# =========================================================
# HISTORICAL AUCTION DATA
# =========================================================

st.divider()


st.subheader(
    "📚 Historical Auction Data"
)


history_rows = []


for sale in (
    league_data.historical_sales
):

    manager_name = None


    if (
        sale.manager_id
        and
        sale.manager_id
        in MANAGERS
    ):

        manager_name = (
            MANAGERS[
                sale.manager_id
            ].sleeper_team_name
        )


    history_rows.append(
        {
            "Year": (
                sale.year
            ),
            "Player": (
                sale.player_name
            ),
            "Price": (
                sale.price
            ),
            "Manager": (
                manager_name
                or sale.manager_raw
                or "-"
            ),
        }
    )


if history_rows:

    history_df = (
        pd.DataFrame(
            history_rows
        )
    )


    history1, history2 = (
        st.columns(
            [
                1,
                3,
            ]
        )
    )


    with history1:

        available_years = sorted(
            history_df[
                "Year"
            ].unique()
        )


        selected_years = (
            st.multiselect(
                "Years",
                options=(
                    available_years
                ),
                default=(
                    available_years
                ),
            )
        )


    filtered_history = (
        history_df[
            history_df[
                "Year"
            ].isin(
                selected_years
            )
        ]
    )


    with history2:

        st.write(
            f"**{len(filtered_history):,} "
            f"historical auction sales loaded**"
        )


    st.dataframe(
        filtered_history,
        use_container_width=True,
        hide_index=True,
    )


else:

    st.warning(
        "No historical auction sales loaded."
    )


# =========================================================
# DATA QUALITY
# =========================================================

st.divider()


st.subheader(
    "⚠️ Data Quality"
)


if not league_data.warnings:

    st.success(
        "No workbook warnings detected."
    )


else:

    st.warning(
        f"{len(league_data.warnings)} "
        f"workbook warnings detected."
    )


    with st.expander(
        "Show warnings"
    ):

        for warning in (
            league_data.warnings
        ):

            st.write(
                f"• {warning}"
            )