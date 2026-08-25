from types import SimpleNamespace

from src.context_valuation import (
    calculate_context_valuation_adjustment,
)
from src.evidence_quality import EvidenceClass


def test_context_adjustment_exposes_signal_evidence_direction_and_source():
    event = SimpleNamespace(
        event_type="injury_out",
        impact=-0.8,
        confidence=0.9,
        evidence="Official injury designation",
        source_name="Team",
        source_document_id="doc-1",
        metadata={"url": "https://example.test/injury"},
    )
    summary = SimpleNamespace(
        document_count=1,
        confidence=0.9,
        role_score=0.0,
        usage_score=0.0,
        health_score=-0.8,
        dynasty_score=-0.2,
        active_events=[event],
    )

    adjustment = calculate_context_valuation_adjustment(
        player_name="Player",
        base_ceiling=50,
        context_summary=summary,
        legal_max=100,
    )

    signal = adjustment.signal_details[0]
    assert signal.evidence_class is EvidenceClass.HARD_EVIDENCE
    assert signal.direction == "negative"
    assert signal.magnitude == 0.72
    assert signal.explanation == "Official injury designation"
    assert signal.source_name == "Team"
    assert signal.source_metadata["url"].endswith("injury")
