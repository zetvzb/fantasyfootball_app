from src.scoring_projection_service import build_league_scoring_projection


def _response():
    players = []
    for position in ("QB", "RB", "WR", "TE"):
        for index in range(4):
            players.append(
                {
                    "fpid": "{0}{1}".format(position, index),
                    "name": "{0} Player {1}".format(position, index),
                    "position_id": position,
                    "stats": {
                        "pass_yds": 1000 - index * 100 if position == "QB" else 0,
                        "rush_yds": 800 - index * 100 if position == "RB" else 0,
                        "rec_rec": 80 - index * 10 if position in ("WR", "TE") else 0,
                        "rec_yds": 900 - index * 100 if position in ("WR", "TE") else 0,
                    },
                }
            )
    return {"players": players}


def test_raw_stats_flow_through_league_scoring_replacement_and_vorp():
    result = build_league_scoring_projection(
        projection_response=_response(),
        scoring_settings={"pass_yd": 0.04, "rush_yd": 0.1, "rec": 0.5, "rec_yd": 0.1},
        num_teams=1,
    )

    wr = next(value for value in result.player_values if value.player_name == "WR Player 0")
    assert wr.projected_points == 130.0
    assert wr.replacement_points < wr.projected_points
    assert wr.vorp == wr.projected_points - wr.replacement_points
    assert result.exact_projection_count == 16


def test_league_reception_scoring_changes_points_without_using_fallback():
    standard = build_league_scoring_projection(
        projection_response=_response(),
        scoring_settings={"rec": 0.0, "rec_yd": 0.1},
        num_teams=1,
    )
    ppr = build_league_scoring_projection(
        projection_response=_response(),
        scoring_settings={"rec": 1.0, "rec_yd": 0.1},
        num_teams=1,
    )

    standard_wr = next(value for value in standard.player_values if value.player_name == "WR Player 0")
    ppr_wr = next(value for value in ppr.player_values if value.player_name == "WR Player 0")
    assert ppr_wr.projected_points - standard_wr.projected_points == 80.0


def test_superflex_lineup_increases_qb_replacement_demand():
    one_qb = build_league_scoring_projection(
        projection_response=_response(),
        scoring_settings={"pass_yd": 1.0},
        num_teams=1,
        starting_lineup=("QB", "RB", "WR", "TE"),
    )
    superflex = build_league_scoring_projection(
        projection_response=_response(),
        scoring_settings={"pass_yd": 1.0},
        num_teams=1,
        starting_lineup=("QB", "RB", "WR", "TE", "SUPER_FLEX"),
    )

    assert one_qb.replacement_levels.starter_demand["QB"] == 1
    assert superflex.replacement_levels.starter_demand["QB"] == 2
    assert (
        superflex.replacement_levels.points_by_position["QB"]
        <= one_qb.replacement_levels.points_by_position["QB"]
    )
