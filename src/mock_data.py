from src.models import (
    DraftState,
    Player,
    TeamState,
)


def build_mock_state() -> DraftState:

    teams = {
        "team_1": TeamState(
            team_id="team_1",
            team_name="My Team",
            starting_budget=200,
            roster_limit=18,
            keeper_count=6,
            keeper_cost=42,
        ),

        "team_2": TeamState(
            team_id="team_2",
            team_name="Team Johnson",
            starting_budget=200,
            roster_limit=18,
            keeper_count=6,
            keeper_cost=63,
        ),

        "team_3": TeamState(
            team_id="team_3",
            team_name="Team Miller",
            starting_budget=200,
            roster_limit=18,
            keeper_count=6,
            keeper_cost=29,
        ),

        "team_4": TeamState(
            team_id="team_4",
            team_name="Team Smith",
            starting_budget=200,
            roster_limit=18,
            keeper_count=6,
            keeper_cost=51,
        ),
    }

    players = [
        Player(
            player_id="p1",
            name="Bijan Robinson",
            position="RB",
            nfl_team="ATL",
        ),
        Player(
            player_id="p2",
            name="Jahmyr Gibbs",
            position="RB",
            nfl_team="DET",
        ),
        Player(
            player_id="p3",
            name="Ja'Marr Chase",
            position="WR",
            nfl_team="CIN",
        ),
        Player(
            player_id="p4",
            name="Justin Jefferson",
            position="WR",
            nfl_team="MIN",
        ),
        Player(
            player_id="p5",
            name="CeeDee Lamb",
            position="WR",
            nfl_team="DAL",
        ),
        Player(
            player_id="p6",
            name="Malik Nabers",
            position="WR",
            nfl_team="NYG",
        ),
        Player(
            player_id="p7",
            name="Brock Bowers",
            position="TE",
            nfl_team="LV",
        ),
        Player(
            player_id="p8",
            name="Trey McBride",
            position="TE",
            nfl_team="ARI",
        ),
        Player(
            player_id="p9",
            name="Josh Allen",
            position="QB",
            nfl_team="BUF",
        ),
        Player(
            player_id="p10",
            name="Lamar Jackson",
            position="QB",
            nfl_team="BAL",
        ),
    ]

    player_dictionary = {
        player.player_id: player
        for player in players
    }

    return DraftState(
        teams=teams,
        available_players=player_dictionary,
    )