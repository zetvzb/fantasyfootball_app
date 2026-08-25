from types import SimpleNamespace

from src.live_cockpit import build_live_cockpit_summary


def test_cockpit_contains_every_primary_live_decision_signal():
    summary = build_live_cockpit_summary(
        "Player", 22, 20, 25, 30, "PURSUE", ["scarce tier"],
        [SimpleNamespace(player_name="Fallback")], "HIGH", 82,
    )
    assert summary.decision == "DISCIPLINED BID"
    assert (summary.target_value, summary.soft_cap, summary.hard_cap) == (20, 25, 30)
    assert summary.alternatives == ("Fallback",)
    assert summary.regret_risk == "HIGH"
    assert summary.room_threat == 82


def test_cockpit_passes_above_hard_cap():
    summary = build_live_cockpit_summary("P", 31, 20, 25, 30, "", [], [], "LOW", 0)
    assert summary.decision == "PASS"


def test_draft_view_import_resolves():
    from src.views.draft_mode import render_draft_mode_view
    assert callable(render_draft_mode_view)
