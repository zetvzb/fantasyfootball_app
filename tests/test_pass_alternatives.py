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
    )

    assert [item.player_name for item in alternatives] == ["Fallback A"]
    assert alternatives[0].expected_price_low == 26
    assert alternatives[0].expected_price_high == 34
    assert "$26-$34" in alternatives[0].rationale
