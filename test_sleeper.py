from src.sleeper_client import SleeperClient


USERNAME = "zeke11111"
SEASON = 2026


client = SleeperClient()


# ---------------------------------------------------------
# USER
# ---------------------------------------------------------

user = client.get_user(
    USERNAME
)

user_id = user["user_id"]

print()
print("=" * 70)
print("SLEEPER USER")
print("=" * 70)

print(
    f"{user['display_name']} "
    f"({user_id})"
)


# ---------------------------------------------------------
# LEAGUES
# ---------------------------------------------------------

leagues = client.get_user_leagues(
    user_id=user_id,
    season=SEASON,
)


for league in leagues:

    league_id = league["league_id"]

    print()
    print("=" * 70)
    print(league["name"])
    print("=" * 70)

    print(
        f"League ID: {league_id}"
    )

    print(
        f"Teams: {league.get('total_rosters')}"
    )

    print(
        f"Status: {league.get('status')}"
    )


    # -----------------------------------------------------
    # MANAGERS / ROSTERS
    # -----------------------------------------------------

    roster_summaries = (
        client.build_roster_summary(
            league_id
        )
    )

    print()
    print("ROSTERS")
    print("-" * 70)

    for roster in roster_summaries:

        print()
        print(
            f"Roster {roster['roster_id']}: "
            f"{roster['team_name']}"
        )

        print(
            f"Manager: "
            f"{roster['manager_name']}"
        )

        print(
            f"Players: "
            f"{len(roster['player_names'])}"
        )

        for player_name in (
            roster["player_names"]
        ):

            print(
                f"    - {player_name}"
            )


    # -----------------------------------------------------
    # DRAFTS
    # -----------------------------------------------------

    drafts = client.get_league_drafts(
        league_id
    )

    print()
    print("DRAFTS")
    print("-" * 70)

    if not drafts:

        print(
            "No drafts found."
        )

    for draft in drafts:

        print(
            f"Draft ID: "
            f"{draft.get('draft_id')}"
        )

        print(
            f"Type: "
            f"{draft.get('type')}"
        )

        print(
            f"Status: "
            f"{draft.get('status')}"
        )

        print(
            f"Season: "
            f"{draft.get('season')}"
        )

        print(
            f"Rounds: "
            f"{draft.get('settings', {}).get('rounds')}"
        )

        print("-" * 30)