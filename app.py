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


# =========================================================
# STREAMLIT CONFIG
# =========================================================

st.set_page_config(
    page_title="Fantasy Auction Copilot",
    page_icon="🏈",
    layout="wide",
)


# =========================================================
# DATA LOADING
# =========================================================

@st.cache_data(ttl=300)
def load_sleeper_data():
    """
    Load current Sleeper league data.

    Cached for five minutes.
    """

    client = SleeperClient()

    league = client.get_league(
        SLEEPER_LEAGUE_ID
    )

    users = client.get_league_users(
        SLEEPER_LEAGUE_ID
    )

    rosters = client.get_league_rosters(
        SLEEPER_LEAGUE_ID
    )

    draft = client.get_draft(
        SLEEPER_DRAFT_ID
    )

    players = client.get_players()

    return {
        "league": league,
        "users": users,
        "rosters": rosters,
        "draft": draft,
        "players": players,
    }


@st.cache_data
def load_league_workbook():
    """
    Load and normalize the league workbook.
    """

    loader = LeagueDataLoader(
        "data/league.xlsx"
    )

    return loader.load()


@st.cache_data(ttl=3600)
def load_fantasypros_data():
    """
    Load the full FantasyPros rankings universe
    plus player metadata / ECR information.
    """

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
        "`data/league.xlsx` and restart the app."
    )

    st.stop()

except Exception as error:

    st.error(
        f"Could not load league workbook: {error}"
    )

    st.stop()


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
        "intelligence": [],
    }


fantasypros_index = (
    build_intelligence_index(
        fantasypros_data[
            "intelligence"
        ]
    )
)


# =========================================================
# UNPACK SLEEPER DATA
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
        f"Managers loaded: "
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
        f"FantasyPros intelligence: "
        f"**{len(fantasypros_data['intelligence'])}**"
    )

    fp_rank_count = len(
        fantasypros_data[
            "rankings_response"
        ].get(
            "players",
            [],
        )
    )

    st.write(
        f"FP ranking records: "
        f"**{fp_rank_count}**"
    )

    fp_player_count = len(
        fantasypros_data[
            "players_response"
        ].get(
            "players",
            [],
        )
    )

    st.write(
        f"FP player records: "
        f"**{fp_player_count}**"
    )

    st.write(
        f"Workbook warnings: "
        f"**{len(league_data.warnings)}**"
    )

    if fantasypros_error:

        st.error(
            "FantasyPros unavailable."
        )


# =========================================================
# FANTASYPROS STATUS
# =========================================================

if fantasypros_error:

    st.warning(
        f"FantasyPros could not be loaded: "
        f"{fantasypros_error}"
    )


# =========================================================
# LEAGUE SUMMARY
# =========================================================

col1, col2, col3, col4 = st.columns(
    4
)


with col1:

    st.metric(
        "Teams",
        league.get(
            "total_rosters",
            "-"
        ),
    )


with col2:

    st.metric(
        "Draft Type",
        str(
            sleeper_draft.get(
                "type",
                "-"
            )
        ).title(),
    )


with col3:

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


with col4:

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
# MY CURRENT SLEEPER ROSTER
# =========================================================

if my_roster:

    st.markdown(
        "#### Current Sleeper Roster"
    )

    my_player_ids = (
        my_roster.get(
            "players"
        )
        or []
    )

    my_player_rows = []

    for player_id in my_player_ids:

        my_player_rows.append(
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


    my_roster_df = pd.DataFrame(
        my_player_rows
    )


    st.dataframe(
        my_roster_df,
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
        my_league_data.keeper_options
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


    else:

        st.info(
            "No keeper options found."
        )


# =========================================================
# MY COLLEGE PLAYERS
# =========================================================

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


else:

    st.info(
        "No college players found "
        "for your team."
    )


st.divider()


# =========================================================
# LEAGUE ECONOMICS
# =========================================================

st.subheader(
    "💰 2026 League Economics"
)

st.caption(
    "Budgets shown here are each team's "
    "pre-keeper auction budget."
)


economics_rows = []


for (
    manager_id,
    identity,
) in MANAGERS.items():

    workbook_manager = (
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


    if workbook_manager:

        budget = (
            workbook_manager.pre_keeper_budget
        )

        keeper_options = len(
            workbook_manager.keeper_options
        )

        college_picks = len(
            workbook_manager.college_picks
        )


    else:

        budget = None

        keeper_options = 0

        college_picks = 0


    economics_rows.append(
        {
            "Team": (
                identity.sleeper_team_name
            ),

            "Sheet": (
                identity.spreadsheet_tab
            ),

            "Pre-Keeper Budget": (
                budget
            ),

            "Keeper Options": (
                keeper_options
            ),

            "College Rights": (
                college_count
            ),

            "College Picks": (
                college_picks
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


economics_df = pd.DataFrame(
    economics_rows
)


st.dataframe(
    economics_df,
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


manager_options = list(
    MANAGERS.keys()
)


selected_manager_id = (
    st.selectbox(
        "Select a manager",
        options=manager_options,
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


selected_workbook_data = (
    league_data.managers.get(
        selected_manager_id
    )
)


selected_roster = (
    rosters_by_id.get(
        selected_identity.sleeper_roster_id
    )
)


detail1, detail2, detail3, detail4 = (
    st.columns(4)
)


if selected_workbook_data:

    with detail1:

        st.metric(
            "Pre-Keeper Budget",
            (
                f"${selected_workbook_data.pre_keeper_budget}"
            ),
        )


    with detail2:

        st.metric(
            "Keeper Options",
            len(
                selected_workbook_data
                .keeper_options
            ),
        )


    with detail3:

        manager_college_count = len(
            [
                player
                for player
                in league_data.college_players
                if (
                    player.manager_id
                    == selected_manager_id
                )
            ]
        )

        st.metric(
            "College Rights",
            manager_college_count,
        )


    with detail4:

        st.metric(
            "College Picks",
            len(
                selected_workbook_data
                .college_picks
            ),
        )


# =========================================================
# MANAGER DETAIL TABS
# =========================================================

keeper_tab, roster_tab, college_tab = (
    st.tabs(
        [
            "Keeper Options",
            "Sleeper Roster",
            "College Rights",
        ]
    )
)


with keeper_tab:

    if not selected_workbook_data:

        st.warning(
            "No workbook data found "
            "for this manager."
        )


    else:

        rows = []

        for keeper in (
            selected_workbook_data
            .keeper_options
        ):

            rows.append(
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
            )


        if rows:

            keeper_detail_df = (
                pd.DataFrame(
                    rows
                )
            )

            keeper_detail_df = (
                keeper_detail_df.sort_values(
                    by="2026 Cost",
                    ascending=True,
                    na_position="last",
                )
            )

            st.dataframe(
                keeper_detail_df,
                use_container_width=True,
                hide_index=True,
            )


        else:

            st.info(
                "No keeper options found."
            )


with roster_tab:

    if not selected_roster:

        st.warning(
            "No Sleeper roster found."
        )


    else:

        roster_rows = []

        for player_id in (
            selected_roster.get(
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


with college_tab:

    college_rows = []


    for player in (
        league_data.college_players
    ):

        if (
            player.manager_id
            != selected_manager_id
        ):
            continue


        college_rows.append(
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


    if college_rows:

        st.dataframe(
            pd.DataFrame(
                college_rows
            ),
            use_container_width=True,
            hide_index=True,
        )


    else:

        st.info(
            "No college rights found."
        )


st.divider()


# =========================================================
# 2026 DRAFT SETUP
# =========================================================

st.subheader(
    "⚙️ 2026 Draft Setup"
)

st.caption(
    "Select official keepers and planned $0 "
    "college promotions. These selections determine "
    "starting auction cash and roster needs."
)


# =========================================================
# SESSION STATE
# =========================================================

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


# =========================================================
# TEAM SETUPS
# =========================================================

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

        # -------------------------------------------------
        # KEEPER OPTIONS
        # -------------------------------------------------

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
                options=keeper_names,
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


        # -------------------------------------------------
        # COLLEGE CALL-UPS
        # -------------------------------------------------

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
                options=college_names,
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


        # -------------------------------------------------
        # CALCULATE TEAM STATE
        # -------------------------------------------------

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


            c1, c2, c3, c4, c5 = (
                st.columns(5)
            )


            with c1:

                st.metric(
                    "Pre-Keeper $",
                    (
                        f"${setup.pre_keeper_budget}"
                    ),
                )


            with c2:

                st.metric(
                    "Keeper Cost",
                    (
                        f"${setup.keeper_cost}"
                    ),
                )


            with c3:

                st.metric(
                    "Auction Cash",
                    (
                        f"${setup.auction_cash}"
                    ),
                )


            with c4:

                st.metric(
                    "Open Spots",
                    (
                        setup.open_roster_spots
                    ),
                )


            with c5:

                st.metric(
                    "Max Bid",
                    (
                        f"${setup.max_bid}"
                    ),
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

    identity = MANAGERS[
        manager_id
    ]


    setup_rows.append(
        {
            "Team": (
                identity.sleeper_team_name
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
# AUCTION PLAYER POOL
# =========================================================

st.divider()

st.subheader(
    "🏈 2026 Auction Player Pool"
)

st.caption(
    "Sleeper NFL players minus selected keepers "
    "and protected college/taxi rights."
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
# POOL SUMMARY
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

    unmatched_count = (
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
        unmatched_count,
    )


# =========================================================
# AUCTION BOARD + FANTASYPROS
# =========================================================

pool_rows = []


for player in (
    pool_result.available_players
):

    normalized_name = (
        normalize_player_name(
            player.player_name
        )
    )


    fp = (
        fantasypros_index.get(
            normalized_name
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

            # ---------------------------------------------
            # CURRENT SEASON
            # ---------------------------------------------

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

            # ---------------------------------------------
            # DYNASTY
            # ---------------------------------------------

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

            # ---------------------------------------------
            # MARKET
            # ---------------------------------------------

            "ADP": (
                fp.adp
                if fp
                else None
            ),

            # ---------------------------------------------
            # EXPERT UNCERTAINTY
            # ---------------------------------------------

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

            "ECR Avg": (
                fp.ecr_avg
                if fp
                else None
            ),

            "ECR Std": (
                fp.ecr_std
                if fp
                else None
            ),

            # ---------------------------------------------
            # SLEEPER CONTEXT
            # ---------------------------------------------

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
# SORT AUCTION BOARD
# =========================================================

if (
    not pool_df.empty
    and
    "2026 ECR"
    in pool_df.columns
):

    pool_df = (
        pool_df.sort_values(
            by=[
                "2026 ECR",
                "Player",
            ],
            ascending=[
                True,
                True,
            ],
            na_position="last",
        )
    )


# =========================================================
# FANTASYPROS MATCH STATUS
# =========================================================

if not pool_df.empty:

    fp_matches = int(
        pool_df[
            "2026 ECR"
        ].notna().sum()
    )


    fp_unmatched = (
        len(pool_df)
        - fp_matches
    )


    if len(pool_df) > 0:

        fp_match_rate = (
            fp_matches
            / len(pool_df)
            * 100
        )


    else:

        fp_match_rate = 0


    match1, match2, match3 = (
        st.columns(3)
    )


    with match1:

        st.metric(
            "FantasyPros ECR Matches",
            fp_matches,
        )


    with match2:

        st.metric(
            "No FP ECR",
            fp_unmatched,
        )


    with match3:

        st.metric(
            "Match Rate",
            (
                f"{fp_match_rate:.1f}%"
            ),
        )


# =========================================================
# PLAYER SEARCH / FILTERS
# =========================================================

st.markdown(
    "### Player Search"
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

        team_options = sorted(
            pool_df[
                "NFL Team"
            ]
            .dropna()
            .unique()
            .tolist()
        )


    else:

        team_options = []


    selected_nfl_teams = (
        st.multiselect(
            "NFL Team",
            options=(
                team_options
            ),
        )
    )


# =========================================================
# APPLY FILTERS
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
# POSITION COUNTS
# =========================================================

if not filtered_pool_df.empty:

    position_counts = (
        filtered_pool_df[
            "Position"
        ]
        .value_counts()
    )


    positions = [
        "QB",
        "RB",
        "WR",
        "TE",
        "K",
        "DEF",
    ]


    count_columns = (
        st.columns(
            len(positions)
        )
    )


    for (
        column,
        position,
    ) in zip(
        count_columns,
        positions,
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
        "2026 ECR": st.column_config.NumberColumn(
            format="%.0f",
        ),
        "Pos Rank": st.column_config.NumberColumn(
            format="%.0f",
        ),
        "Dynasty ECR": st.column_config.NumberColumn(
            format="%.0f",
        ),
        "Dynasty Pos": st.column_config.NumberColumn(
            format="%.0f",
        ),
        "ADP": st.column_config.NumberColumn(
            format="%.1f",
        ),
        "ECR Min": st.column_config.NumberColumn(
            format="%.0f",
        ),
        "ECR Max": st.column_config.NumberColumn(
            format="%.0f",
        ),
        "ECR Avg": st.column_config.NumberColumn(
            format="%.1f",
        ),
        "ECR Std": st.column_config.NumberColumn(
            format="%.1f",
        ),
    },
)


# =========================================================
# PROTECTED PLAYER REVIEW
# =========================================================

st.markdown(
    "### Protected Players"
)


(
    protected_keeper_tab,
    protected_college_tab,
    matching_tab,
) = st.tabs(
    [
        "Keepers",
        "College Rights",
        "Matching Issues",
    ]
)


with protected_keeper_tab:

    if (
        pool_result.excluded_keepers
    ):

        keeper_protection_df = (
            pd.DataFrame(
                {
                    "Player": (
                        pool_result
                        .excluded_keepers
                    )
                }
            )
        )


        st.dataframe(
            keeper_protection_df,
            use_container_width=True,
            hide_index=True,
        )


    else:

        st.info(
            "No keepers have been "
            "selected yet."
        )


with protected_college_tab:

    if (
        pool_result.excluded_college
    ):

        college_protection_df = (
            pd.DataFrame(
                {
                    "Player": (
                        pool_result
                        .excluded_college
                    )
                }
            )
        )


        st.dataframe(
            college_protection_df,
            use_container_width=True,
            hide_index=True,
        )


    else:

        st.info(
            "No protected college "
            "players found."
        )


with matching_tab:

    if (
        not pool_result
        .unmatched_keepers
        and
        not pool_result
        .unmatched_nfl_college
    ):

        st.success(
            "All protected NFL players "
            "matched successfully to Sleeper."
        )


    else:

        if (
            pool_result
            .unmatched_keepers
        ):

            st.warning(
                "Selected keepers that "
                "could not be matched:"
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
                "NFL college-rights players "
                "that could not be matched:"
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


    history_col1, history_col2 = (
        st.columns(
            [
                1,
                3,
            ]
        )
    )


    with history_col1:

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


    with history_col2:

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
        "No historical auction sales "
        "were loaded."
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
        f"data-quality warnings detected."
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