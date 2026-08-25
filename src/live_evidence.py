from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class EvidenceSection:
    key: str
    label: str
    expanded: bool = False


LIVE_EVIDENCE_SECTIONS: Tuple[EvidenceSection, ...] = (
    EvidenceSection("scenario", "🔮 Scenario Analysis & Pass Plan"),
    EvidenceSection("context", "🧠 Player Context & Raw Evidence"),
    EvidenceSection("signals", "📊 Rankings, Projections & Player Signals"),
)


def evidence_section(key: str) -> EvidenceSection:
    for section in LIVE_EVIDENCE_SECTIONS:
        if section.key == key:
            return section
    raise KeyError("Unknown live evidence section: {0}".format(key))
