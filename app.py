import pandas as pd
import streamlit as st

from src.config import (
    SEASON,
    SLEEPER_DRAFT_ID,
    SLEEPER_LEAGUE_ID,
    SLEEPER_USER_ID,
)
from src.sleeper_client import SleeperClient


st.set_page_config(
    page_title="Fantasy Auction Copilot",
    page_icon="🏈",
    layout="wide",
)


# ---------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------

@st.cache_data(ttl=300)
def load_sleeper_data():
    """
    Load the current Sleeper league state.

    Cached for 5 minutes so normal Streamlit interactions
    don't repeatedly hit Sleeper.
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


data = load_sleeper_data()

league = data["league"]
users = data["users"]
rosters = data["rosters"]
draft = data["draft"]
players = data["players"]


# ---------------------------------------------------------
# BUILD LOOKUPS
# ---------------------------------------------------------

users_by_id = {
    user["user_id"]: user
    for user in users
}


def get_team_name(user):
    metadata = user.get("metadata") or {}

    return (
        metadata.get("team_name")
        or user.get("display_name")
        or user.get("username")
        or "Unknown Team"
    )


def get_player_name(player_id):
    player = players.get(
        player_id,
        {}
    )

    return (
        player.get("full_name")
        or player_id
    )


def get_player_position(player_id):
    player = players.get(
        player_id,
        {}
    )

    return (
        player.get("position")
        or "-"
    )


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🏈 Fantasy Auction Copilot")

st.caption(
    f"{league.get('name')} • {SEASON}"
)


# ---------------------------------------------------------
# REFRESH
# ---------------------------------------------------------

with st.sidebar:

    st.header("Draft Controls")

    if st.button(
        "Refresh Sleeper",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.write(
        f"**League ID:** {SLEEPER_LEAGUE_ID}"
    )

    st.write(
        f"**Draft ID:** {SLEEPER_DRAFT_ID}"
    )
    
# ---------------------------------------------------------
# LEAGUE DATA UPLOAD
# ---------------------------------------------------------

st.sidebar.divider()

st.sidebar.subheader("League Data")

uploaded_file = st.sidebar.file_uploader(
    "Upload league Excel file",
    type=["xlsx"],
)

if uploaded_file is not None:

    excel_file = pd.ExcelFile(uploaded_file)

    st.subheader("📊 League Data Workbook")

    st.success(
        f"Loaded workbook with {len(excel_file.sheet_names)} sheets."
    )

    selected_sheet = st.selectbox(
        "Inspect Sheet",
        options=excel_file.sheet_names,
    )

    sheet_df = pd.read_excel(
        uploaded_file,
        sheet_name=selected_sheet,
    )

    st.write(
        f"**Rows:** {len(sheet_df):,} "
        f"• **Columns:** {len(sheet_df.columns)}"
    )

    st.write("**Columns:**")

    st.write(
        list(sheet_df.columns)
    )

    st.dataframe(
        sheet_df.head(50),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

# ---------------------------------------------------------
# LEAGUE SUMMARY
# ---------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Teams",
        league.get("total_rosters"),
    )

with col2:
    st.metric(
        "Draft Type",
        str(
            draft.get(
                "type",
                "-"
            )
        ).title(),
    )

with col3:
    st.metric(
        "Draft Status",
        str(
            draft.get(
                "status",
                "-"
            )
        ).replace(
            "_",
            " "
        ).title(),
    )

with col4:
    st.metric(
        "Draft Rounds",
        draft.get(
            "settings",
            {}
        ).get(
            "rounds",
            "-"
        ),
    )


st.divider()


# ---------------------------------------------------------
# BUILD TEAM TABLE
# ---------------------------------------------------------

team_rows = []

my_roster = None


for roster in rosters:

    owner_id = roster.get(
        "owner_id"
    )

    user = users_by_id.get(
        owner_id,
        {}
    )

    team_name = get_team_name(
        user
    )

    player_ids = (
        roster.get("players")
        or []
    )

    is_my_team = (
        owner_id == SLEEPER_USER_ID
    )

    if is_my_team:
        my_roster = roster

    team_rows.append(
        {
            "Roster ID": roster.get(
                "roster_id"
            ),
            "Team": team_name,
            "Manager": (
                user.get("display_name")
                or user.get("username")
                or owner_id
            ),
            "Players": len(
                player_ids
            ),
            "My Team": (
                "⭐" if is_my_team else ""
            ),
        }
    )


team_df = pd.DataFrame(
    team_rows
)


# ---------------------------------------------------------
# YOUR TEAM
# ---------------------------------------------------------

if my_roster:

    my_user = users_by_id.get(
        SLEEPER_USER_ID,
        {}
    )

    st.subheader(
        f"⭐ My Team — {get_team_name(my_user)}"
    )

    my_player_ids = (
        my_roster.get(
            "players"
        )
        or []
    )

    my_player_rows = []

    for player_id in my_player_ids:

        player = players.get(
            player_id,
            {}
        )

        my_player_rows.append(
            {
                "Player": get_player_name(
                    player_id
                ),
                "Position": (
                    player.get(
                        "position"
                    )
                    or "-"
                ),
                "NFL Team": (
                    player.get(
                        "team"
                    )
                    or "-"
                ),
                "Status": (
                    player.get(
                        "status"
                    )
                    or "-"
                ),
            }
        )

    my_player_df = pd.DataFrame(
        my_player_rows
    )

    st.dataframe(
        my_player_df,
        use_container_width=True,
        hide_index=True,
    )


st.divider()


# ---------------------------------------------------------
# DRAFT ROOM
# ---------------------------------------------------------

st.subheader("Draft Room")

st.dataframe(
    team_df,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# ALL CURRENT ROSTERS
# ---------------------------------------------------------

st.subheader("Current Sleeper Rosters")

st.caption(
    "These are offseason Sleeper rosters. "
    "They are NOT yet being treated as official keepers."
)


for roster in rosters:

    owner_id = roster.get(
        "owner_id"
    )

    user = users_by_id.get(
        owner_id,
        {}
    )

    team_name = get_team_name(
        user
    )

    player_ids = (
        roster.get(
            "players"
        )
        or []
    )

    label = (
        f"{team_name} — "
        f"{len(player_ids)} players"
    )

    with st.expander(label):

        roster_rows = []

        for player_id in player_ids:

            player = players.get(
                player_id,
                {}
            )

            roster_rows.append(
                {
                    "Player": get_player_name(
                        player_id
                    ),
                    "Position": (
                        player.get(
                            "position"
                        )
                        or "-"
                    ),
                    "NFL Team": (
                        player.get(
                            "team"
                        )
                        or "-"
                    ),
                }
            )

        roster_df = pd.DataFrame(
            roster_rows
        )

        st.dataframe(
            roster_df,
            use_container_width=True,
            hide_index=True,
        )