import pandas as pd
import streamlit as st

from src.config import (
    SEASON,
    SLEEPER_DRAFT_ID,
    SLEEPER_LEAGUE_ID,
    SLEEPER_USER_ID,
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

    Cached for 5 minutes so normal Streamlit
    interactions don't repeatedly hit Sleeper.
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
    Load and normalize our league Excel workbook.
    """

    loader = LeagueDataLoader(
        "data/league.xlsx"
    )

    return loader.load()


# =========================================================
# LOAD DATA
# =========================================================

try:

    sleeper_data = load_sleeper_data()

except Exception as error:

    st.error(
        f"Could not load Sleeper data: {error}"
    )

    st.stop()


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


league = sleeper_data["league"]

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


def get_sleeper_team_name(user):
    """
    Resolve the displayed Sleeper team name.
    """

    if not user:
        return "Unknown Team"

    metadata = (
        user.get("metadata")
        or {}
    )

    return (
        metadata.get("team_name")
        or user.get("display_name")
        or user.get("username")
        or "Unknown Team"
    )


def get_player_name(player_id):
    """
    Convert a Sleeper player ID to readable name.
    """

    player = sleeper_players.get(
        player_id,
        {}
    )

    return (
        player.get("full_name")
        or player_id
    )


def get_player_position(player_id):
    player = sleeper_players.get(
        player_id,
        {}
    )

    return (
        player.get("position")
        or "-"
    )


def get_player_team(player_id):
    player = sleeper_players.get(
        player_id,
        {}
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
        f"Workbook warnings: "
        f"**{len(league_data.warnings)}**"
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
            {}
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

my_roster = rosters_by_id.get(
    my_identity.sleeper_roster_id
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
                if player.status
                == "in_nfl"
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
    "pre-keeper auction budget from the workbook."
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
                if manager_id
                == MY_MANAGER_ID
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
# MANAGER DETAIL VIEW
# =========================================================

st.subheader(
    "👥 Manager Detail"
)


manager_options = list(
    MANAGERS.keys()
)


selected_manager_id = st.selectbox(
    "Select a manager",
    options=manager_options,
    format_func=lambda manager_id: (
        MANAGERS[
            manager_id
        ].sleeper_team_name
    ),
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
                in league_data
                .college_players
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
# MANAGER TABS
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
                    if player.status
                    == "in_nfl"
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
# HISTORICAL AUCTION DATA
# =========================================================

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
        and sale.manager_id
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

    history_df = pd.DataFrame(
        history_rows
    )

    history_col1, history_col2 = (
        st.columns(
            [1, 3]
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
                options=available_years,
                default=available_years,
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


st.divider()


# =========================================================
# DATA QUALITY / WARNINGS
# =========================================================

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