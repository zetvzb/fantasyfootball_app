import pytest

from src.live_evidence import LIVE_EVIDENCE_SECTIONS, evidence_section


def test_deep_live_evidence_sections_default_to_collapsed():
    assert {section.key for section in LIVE_EVIDENCE_SECTIONS} == {
        "scenario", "context", "signals"
    }
    assert all(not section.expanded for section in LIVE_EVIDENCE_SECTIONS)
    assert "Raw Evidence" in evidence_section("context").label


def test_unknown_evidence_section_is_rejected():
    with pytest.raises(KeyError):
        evidence_section("missing")


def test_bid_copilot_import_resolves_after_evidence_restructure():
    from src.views.draft_components.bid_copilot import render_bid_copilot
    assert callable(render_bid_copilot)
