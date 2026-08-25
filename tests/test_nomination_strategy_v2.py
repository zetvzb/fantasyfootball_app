from src.nomination_strategy import nomination_strategy_mode


def test_nomination_v2_supports_all_five_explicit_modes():
    assert nomination_strategy_mode(0.2, 1.0, 0.5, 0.8, 0.6, "m1") == "DRAIN CASH"
    assert nomination_strategy_mode(0.8, 0.9, 0.5, 0.2, 0.2, None) == "ACQUIRE TARGET"
    assert nomination_strategy_mode(0.2, 1.0, 0.4, 0.3, 0.5, None) == "CREATE CHAOS"
    assert nomination_strategy_mode(0.8, 1.05, 0.5, 0.2, 0.2, None) == "HIDE NEED"
    assert nomination_strategy_mode(0.2, 1.0, 0.8, 0.4, 0.8, "m1") == "ATTACK MANAGER"


def test_attack_manager_requires_a_specific_target():
    assert nomination_strategy_mode(0.2, 1.0, 0.9, 0.3, 0.9, None) == "CREATE CHAOS"
