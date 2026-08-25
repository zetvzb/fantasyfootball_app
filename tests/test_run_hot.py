from types import SimpleNamespace

from src.run_hot import build_available_tier_counts, detect_run_hot


def test_cash_rich_overlap_on_scarce_tier_creates_pressure_warning():
    profiles = (
        SimpleNamespace(manager_id="a", cash_strength=0.9, likely_positions=("WR",), likely_tiers=("elite",)),
        SimpleNamespace(manager_id="b", cash_strength=0.8, likely_positions=("WR",), likely_tiers=("elite",)),
        SimpleNamespace(manager_id="c", cash_strength=0.2, likely_positions=("WR",), likely_tiers=("elite",)),
    )
    result = detect_run_hot(
        opponent_profiles=profiles,
        available_tier_counts={("WR", "elite"): 1},
    )

    assert len(result.warnings) == 1
    assert result.position_pressure["WR"] == 1.0
    assert result.warnings[0].competing_managers == ("a", "b")


def test_abundant_tier_does_not_run_hot_and_market_values_are_tiered():
    counts = build_available_tier_counts(
        (
            SimpleNamespace(position="RB", expected_market_value=50),
            SimpleNamespace(position="RB", expected_market_value=20),
            SimpleNamespace(position="RB", expected_market_value=5),
        )
    )
    assert counts == {("RB", "elite"): 1, ("RB", "starter"): 1, ("RB", "depth"): 1}
