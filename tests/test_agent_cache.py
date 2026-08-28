from types import SimpleNamespace

from src.agent_cache import auction_advice_fingerprint, nomination_advice_fingerprint
from src.live_cockpit import build_live_cockpit_summary


def _nomination(action="DRAIN CASH", score=90.0):
    return SimpleNamespace(
        player_name="Alpha",
        position="WR",
        nomination_score=score,
        action=action,
        reason="The room needs receivers.",
        expected_market_value=30.0,
        do_not_exceed=22,
        target_manager_id="manager-2",
    )


def _auction_inputs(current_bid=10):
    alternative = SimpleNamespace(
        player_name="Beta",
        expected_price_low=12,
        expected_price_high=17,
        availability_probability=0.75,
    )
    summary = build_live_cockpit_summary(
        "Alpha", current_bid, 15, 20, 24, "PURSUE", ["fills WR need"],
        [alternative], "MEDIUM", 35.0,
    )
    state = SimpleNamespace(
        recommendation=SimpleNamespace(
            legal_max_bid=28,
            strategy="PURSUE",
            reasons=["fills WR need"],
        ),
        pass_alternatives=[alternative],
    )
    team = SimpleNamespace(
        live_cash=100,
        open_roster_spots=5,
        discretionary_cash=96,
    )
    return summary, state, team


def test_nomination_fingerprint_changes_for_mode_candidates_and_context():
    base = nomination_advice_fingerprint([_nomination()])

    assert base == nomination_advice_fingerprint([_nomination()])
    assert base != nomination_advice_fingerprint([_nomination(action="HIDE NEED")])
    assert base != nomination_advice_fingerprint([_nomination(score=91.0)])
    assert base != nomination_advice_fingerprint([_nomination()], "RBs are cheap.")


def test_auction_fingerprint_covers_bid_source_roster_and_context_modes():
    summary, state, team = _auction_inputs()
    base = auction_advice_fingerprint(summary, state, team, "manual")

    assert base == auction_advice_fingerprint(summary, state, team, "manual")
    assert base != auction_advice_fingerprint(*_auction_inputs(11), "manual")
    assert base != auction_advice_fingerprint(summary, state, team, "sleeper")
    assert base != auction_advice_fingerprint(
        summary,
        state,
        SimpleNamespace(live_cash=90, open_roster_spots=5, discretionary_cash=86),
        "manual",
    )
    assert base != auction_advice_fingerprint(
        summary, state, team, "manual", "Manager 2 is chasing WRs."
    )
