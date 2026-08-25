import pytest

from src.keeper_recommendation import (
    KeeperDecision,
    KeeperReasonCode,
    KeeperRecommendation,
)
from src.keeper_trade_candidates import recommend_keeper_trade_candidates


def _recommendation(
    manager_id,
    name,
    score,
    *,
    surplus=10.0,
    reason_codes=(KeeperReasonCode.POSITIVE_SURPLUS,),
):
    return KeeperRecommendation(
        manager_id=manager_id,
        player_name=name,
        position="WR",
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


def _manager_recommendations(manager_id, count, starting_score=100):
    return [
        _recommendation(
            manager_id,
            "{0} Player {1}".format(manager_id, index),
            starting_score - index,
        )
        for index in range(1, count + 1)
    ]


def test_candidates_exclude_each_opponents_strategy_score_top_six():
    recommendations = (
        _manager_recommendations("opponent-a", 8, 100)
        + _manager_recommendations("opponent-b", 8, 90)
        + _manager_recommendations("me", 10, 110)
    )

    result = recommend_keeper_trade_candidates(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={
            "me": "My Team",
            "opponent-a": "Alpha",
            "opponent-b": "Beta",
        },
    )

    assert result.opponents_evaluated == 2
    assert result.recommendations_evaluated == 16
    assert len(result.candidates) == 4
    assert all(candidate.owner_keeper_rank > 6 for candidate in result.candidates)
    assert all(candidate.owner_manager_id != "me" for candidate in result.candidates)
    assert {candidate.player_name for candidate in result.candidates} == {
        "opponent-a Player 7",
        "opponent-a Player 8",
        "opponent-b Player 7",
        "opponent-b Player 8",
    }


def test_global_ranking_is_limited_to_top_ten_and_deterministic():
    recommendations = []
    names = {"me": "My Team"}
    for index, manager_id in enumerate(("a", "b", "c")):
        names[manager_id] = manager_id.upper()
        recommendations.extend(
            _manager_recommendations(
                manager_id,
                10,
                starting_score=100 - index,
            )
        )

    first = recommend_keeper_trade_candidates(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names=names,
    )
    second = recommend_keeper_trade_candidates(
        recommendations=list(reversed(recommendations)),
        current_manager_id="me",
        manager_names=names,
    )

    assert first == second
    assert len(first.candidates) == 10
    assert [candidate.rank for candidate in first.candidates] == list(range(1, 11))


def test_rationale_explains_owner_rank_value_and_keeper_slot_pressure():
    recommendations = _manager_recommendations("opponent", 6)
    recommendations.append(
        _recommendation(
            "opponent",
            "Young Target",
            80,
            surplus=15,
            reason_codes=(
                KeeperReasonCode.POSITIVE_SURPLUS,
                KeeperReasonCode.FUTURE_UPSIDE,
                KeeperReasonCode.AGE_UPSIDE,
            ),
        )
    )

    result = recommend_keeper_trade_candidates(
        recommendations=recommendations,
        current_manager_id="me",
        manager_names={"me": "Mine", "opponent": "Other Team"},
    )

    rationale = result.candidates[0].rationale
    assert "#7 of 7" in rationale
    assert "outside that team's projected top 6" in rationale
    assert "projected surplus" in rationale
    assert "future-value upside" in rationale
    assert "keeper-slot pressure" in rationale


def test_opponents_with_six_or_fewer_candidates_produce_coverage_warning():
    result = recommend_keeper_trade_candidates(
        recommendations=_manager_recommendations("opponent", 6),
        current_manager_id="me",
        manager_names={
            "me": "Mine",
            "opponent": "Other Team",
            "empty": "No Data Team",
        },
    )

    assert result.candidates == ()
    assert result.opponents_evaluated == 2
    assert any("Other Team has only 6" in warning for warning in result.warnings)
    assert any("No Data Team has only 0" in warning for warning in result.warnings)


def test_invalid_limits_and_duplicate_players_are_rejected():
    recommendation = _recommendation("opponent", "Duplicate", 50)

    with pytest.raises(ValueError, match="cannot be negative"):
        recommend_keeper_trade_candidates(
            recommendations=[],
            current_manager_id="me",
            manager_names={},
            limit=-1,
        )

    with pytest.raises(ValueError, match="unique"):
        recommend_keeper_trade_candidates(
            recommendations=[recommendation, recommendation],
            current_manager_id="me",
            manager_names={"opponent": "Other"},
        )
