from types import SimpleNamespace

from src.pass_regret import calculate_pass_regret_risk


def test_high_regret_combines_scarcity_need_competition_and_tier_drop():
    result = calculate_pass_regret_risk(
        scarcity=1,
        roster_need=1,
        competitor_pressure=100,
        player_vorp=50,
        alternatives=(SimpleNamespace(vorp=20, availability_probability=0.2),),
    )
    assert result.level == "HIGH"
    assert result.score >= 67
    assert len(result.reasons) >= 4


def test_low_regret_when_good_available_alternative_exists():
    result = calculate_pass_regret_risk(
        scarcity=0.1,
        roster_need=0.1,
        competitor_pressure=10,
        player_vorp=50,
        alternatives=(SimpleNamespace(vorp=49, availability_probability=0.95),),
    )
    assert result.level == "LOW"
    assert result.reasons == ("Comparable paths remain available.",)
