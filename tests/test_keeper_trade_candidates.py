import pytest

from src.keeper_recommendation import KeeperDecision, KeeperReasonCode, KeeperRecommendation
from src.keeper_trade_candidates import build_keeper_upgrade_targets


def _recommendation(
    manager_id,
    name,
    score,
    *,
    position="WR",
    surplus=10.0,
    reason_codes=(KeeperReasonCode.POSITIVE_SURPLUS,),
):
    return KeeperRecommendation(
        manager_id=manager_id,
        player_name=name,
        position=position,
        decision=KeeperDecision.KEEP,
        current_value=float(score),
        future_value=float(score),
        age=25,
        age_adjustment=1.0,
        age_adjusted_future_value=float(score),
        cost=10,
        auction_value=10.0 + float(surplus),
        surplus=float(surplus),
        scarcity=0.5,
        roster_fit=0.5,
        strategy_score=float(score),
        reason_codes=reason_codes,
        explanation="test",
    )


def test_opponent_players_are_compared_to_my_best_at_the_same_position():
    recommendations = [
        _recommendation("me", "My RB", 60, position="RB"),
        _recommendation("opponent", "Better RB", 80, position="RB"),
        _recommendation("opponent", "Worse RB", 40, position="RB"),
    ]

    result = build_keeper_upgrade_targets(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={"me": "My Team", "opponent": "Opponent"},
    )

    by_name = {target.player_name: target for target in result.targets}
    assert by_name["Better RB"].is_upgrade is True
    assert by_name["Better RB"].my_player_name == "My RB"
    assert by_name["Better RB"].my_strategy_score == 60
    assert by_name["Better RB"].score_advantage == 20
    assert by_name["Worse RB"].is_upgrade is False
    assert by_name["Worse RB"].score_advantage == -20
    # My own player never appears as a candidate.
    assert "My RB" not in by_name


def test_position_with_no_owned_player_treats_every_opponent_as_an_upgrade():
    recommendations = [
        _recommendation("opponent", "Only TE", 30, position="TE"),
    ]

    result = build_keeper_upgrade_targets(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={"me": "My Team", "opponent": "Opponent"},
    )

    assert len(result.targets) == 1
    target = result.targets[0]
    assert target.is_upgrade is True
    assert target.my_player_name is None
    assert target.my_strategy_score is None
    assert target.score_advantage == 30


def test_upgrades_rank_above_non_upgrades_and_by_advantage():
    recommendations = [
        _recommendation("me", "My WR", 50, position="WR"),
        _recommendation("opp-a", "Slight Upgrade", 55, position="WR"),
        _recommendation("opp-b", "Big Upgrade", 90, position="WR"),
        _recommendation("opp-c", "Downgrade", 20, position="WR"),
    ]

    result = build_keeper_upgrade_targets(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={"me": "Mine", "opp-a": "A", "opp-b": "B", "opp-c": "C"},
    )

    names_in_order = [target.player_name for target in result.targets]
    assert names_in_order == ["Big Upgrade", "Slight Upgrade", "Downgrade"]
    assert [target.rank for target in result.targets] == [1, 2, 3]


def test_limit_is_respected_and_negative_limit_rejected():
    recommendations = [
        _recommendation("opponent", "Player {0}".format(i), 100 - i, position="WR")
        for i in range(15)
    ]

    result = build_keeper_upgrade_targets(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={"me": "Mine", "opponent": "Opponent"},
        limit=5,
    )
    assert len(result.targets) == 5

    with pytest.raises(ValueError, match="cannot be negative"):
        build_keeper_upgrade_targets(
            recommendations=[],
            current_manager_id="me",
            manager_names={},
            limit=-1,
        )


def test_warns_when_current_manager_has_no_keeper_candidates_at_all():
    recommendations = [_recommendation("opponent", "Solo", 50, position="QB")]

    result = build_keeper_upgrade_targets(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={"me": "Mine", "opponent": "Opponent"},
    )

    assert any("no scored keeper candidates" in warning for warning in result.warnings)
