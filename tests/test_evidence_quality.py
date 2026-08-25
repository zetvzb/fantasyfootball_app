from datetime import datetime, timezone

from src.evidence_quality import EvidenceClass, classify_evidence
from src.player_context import ContextDocument, document_weight


def _document(source_type, confidence=0.9, metadata=None):
    return ContextDocument(
        document_id=source_type,
        player_name="Player",
        position="WR",
        nfl_team="CHI",
        source_type=source_type,
        source_name="source",
        title="Signal",
        content="Evidence",
        published_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        confidence=confidence,
        role_signal=1.0,
        metadata=metadata or {},
    )


def test_hard_strong_and_soft_evidence_classes_are_deterministic():
    assert classify_evidence(_document("injury")).evidence_class is EvidenceClass.HARD_EVIDENCE
    assert classify_evidence(_document("usage")).evidence_class is EvidenceClass.STRONG_ANALYTICAL_SIGNAL
    assert classify_evidence(_document("social")).evidence_class is EvidenceClass.SOFT_SIGNAL


def test_evidence_quality_weights_downstream_impact():
    as_of = datetime(2026, 8, 25, tzinfo=timezone.utc)
    hard = document_weight(_document("official_news"), as_of=as_of)
    soft = document_weight(_document("social"), as_of=as_of)

    assert hard > soft
    assert classify_evidence(_document("social")).downstream_weight == 0.4


def test_explicit_normalized_evidence_class_overrides_source_inference():
    assessment = classify_evidence(
        _document("social", metadata={"evidence_class": "hard_evidence"})
    )

    assert assessment.evidence_class is EvidenceClass.HARD_EVIDENCE
    assert assessment.downstream_weight == 1.0
