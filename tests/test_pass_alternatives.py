from types import SimpleNamespace

from src.pass_alternatives import find_pass_alternatives


def test_comparable_same_position_alternatives_include_expected_price_ranges():
    candidates = (
        SimpleNamespace(player_name="Target", position="WR", vorp=50, expected_market_value=40),
        SimpleNamespace(player_name="Fallback A", position="WR", vorp=45, expected_market_value=30),
        SimpleNamespace(player_name="Wrong Pos", position="RB", vorp=48, expected_market_value=20),
        SimpleNamespace(player_name="Too Weak", position="WR", vorp=5, expected_market_value=3),
    )
    alternatives = find_pass_alternatives(
        player_name="Target",
        position="WR",
        player_vorp=50,
        candidates=candidates,
        auction_stage=0.25,
        threat_score=20,
        remaining_cash=100,
    )

    assert [item.player_name for item in alternatives] == ["Fallback A"]
    assert alternatives[0].expected_price_low == 26
    assert alternatives[0].expected_price_high == 34
    assert "$26-$34" in alternatives[0].rationale
    assert alternatives[0].availability_label == "HIGH"


def test_late_hot_room_reduces_alternative_availability_probability():
    candidate = SimpleNamespace(
        player_name="Fallback", position="WR", vorp=45, expected_market_value=30
    )
    early = find_pass_alternatives(
        player_name="Target", position="WR", player_vorp=50,
        candidates=(candidate,), auction_stage=0.1, threat_score=10, remaining_cash=100,
    )[0]
    late = find_pass_alternatives(
        player_name="Target", position="WR", player_vorp=50,
        candidates=(candidate,), auction_stage=0.9, threat_score=90, remaining_cash=20,
    )[0]
    assert late.availability_probability < early.availability_probability
