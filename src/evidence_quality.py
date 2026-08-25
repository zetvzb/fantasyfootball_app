from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EvidenceClass(str, Enum):
    HARD_EVIDENCE = "hard_evidence"
    STRONG_ANALYTICAL_SIGNAL = "strong_analytical_signal"
    SOFT_SIGNAL = "soft_signal"


EVIDENCE_WEIGHTS = {
    EvidenceClass.HARD_EVIDENCE: 1.0,
    EvidenceClass.STRONG_ANALYTICAL_SIGNAL: 0.75,
    EvidenceClass.SOFT_SIGNAL: 0.40,
}


@dataclass(frozen=True)
class EvidenceAssessment:
    evidence_class: EvidenceClass
    downstream_weight: float
    reason: str


def classify_evidence(document: Any) -> EvidenceAssessment:
    """Classify context deterministically from provenance and verification."""

    explicit = (getattr(document, "metadata", {}) or {}).get("evidence_class")
    if explicit:
        try:
            evidence_class = EvidenceClass(str(explicit))
            return EvidenceAssessment(
                evidence_class,
                EVIDENCE_WEIGHTS[evidence_class],
                "Explicit evidence class supplied by the normalized source.",
            )
        except ValueError:
            pass

    source_type = str(getattr(document, "source_type", "") or "").lower()
    confidence = float(getattr(document, "confidence", 0.0) or 0.0)
    verified = bool((getattr(document, "metadata", {}) or {}).get("verified", False))
    if verified or source_type in ("injury", "depth_chart", "official_news"):
        evidence_class = EvidenceClass.HARD_EVIDENCE
        reason = "Official, verified, injury, or depth-chart fact."
    elif source_type in ("usage", "beat_report", "news") and confidence >= 0.60:
        evidence_class = EvidenceClass.STRONG_ANALYTICAL_SIGNAL
        reason = "Credible usage/news analysis with sufficient confidence."
    else:
        evidence_class = EvidenceClass.SOFT_SIGNAL
        reason = "Unverified, low-confidence, social, or narrative signal."
    return EvidenceAssessment(
        evidence_class,
        EVIDENCE_WEIGHTS[evidence_class],
        reason,
    )


def evidence_weight(document: Any) -> float:
    return classify_evidence(document).downstream_weight
