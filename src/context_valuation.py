from dataclasses import dataclass, field
from typing import List, Optional

from src.evidence_quality import EvidenceClass

from src.league_config import (
    CURRENT_SEASON_WEIGHT,
    FUTURE_VALUE_WEIGHT,
)

from src.context_interpreter import (
    INJURY_SEVERE,
    INJURY_OUT,
    INJURY_LIMITED,
    ROLE_DOWN,
    ROLE_UP,
    USAGE_DOWN,
    USAGE_UP,
    DYNASTY_DOWN,
    DYNASTY_UP,
)


# =========================================================
# CONFIG
# =========================================================

MAX_POSITIVE_ADJUSTMENT_PCT = 0.06
MAX_NEGATIVE_ADJUSTMENT_PCT = 0.08

MIN_CONTEXT_CONFIDENCE = 0.35
FULL_CONTEXT_CONFIDENCE = 0.85


# =========================================================
# RESULT
# =========================================================

@dataclass
class ContextValuationSignal:
    signal: str
    evidence_class: EvidenceClass
    direction: str
    magnitude: float
    explanation: str
    source_name: str
    source_document_id: str
    source_metadata: dict = field(default_factory=dict)


@dataclass
class ContextValuationAdjustment:

    player_name: str

    base_ceiling: int
    adjusted_ceiling: int

    adjustment_dollars: int
    adjustment_pct: float

    current_signal: float
    future_signal: float
    blended_signal: float

    context_confidence: float
    confidence_strength: float

    applied: bool

    capped_by_context_limit: bool
    capped_by_legal_max: bool

    reasons: List[str] = field(
        default_factory=list
    )

    signal_details: List[ContextValuationSignal] = field(default_factory=list)


def build_valuation_signal_details(context_summary) -> List[ContextValuationSignal]:
    if context_summary is None:
        return []
    details = []
    for event in getattr(context_summary, "active_events", ()):
        event_type = str(event.event_type)
        if event_type.startswith("injury_") or event_type.startswith("depth_"):
            evidence_class = EvidenceClass.HARD_EVIDENCE
        elif float(event.confidence) >= 0.65:
            evidence_class = EvidenceClass.STRONG_ANALYTICAL_SIGNAL
        else:
            evidence_class = EvidenceClass.SOFT_SIGNAL
        impact = float(event.impact)
        details.append(
            ContextValuationSignal(
                signal=event_type,
                evidence_class=evidence_class,
                direction="positive" if impact > 0 else "negative" if impact < 0 else "neutral",
                magnitude=round(abs(impact) * float(event.confidence), 3),
                explanation=str(event.evidence),
                source_name=str(event.source_name),
                source_document_id=str(event.source_document_id),
                source_metadata=dict(getattr(event, "metadata", {}) or {}),
            )
        )
    return details


# =========================================================
# HELPERS
# =========================================================

def clamp(
    value,
    minimum,
    maximum,
):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def has_active_event(
    context_summary,
    event_type,
):

    if context_summary is None:

        return False


    for event in (
        context_summary.active_events
    ):

        if (
            event.event_type
            ==
            event_type
        ):

            return True


    return False


def confidence_strength(
    confidence,
):

    confidence = clamp(
        confidence,
        0.0,
        1.0,
    )


    if (
        confidence
        <
        MIN_CONTEXT_CONFIDENCE
    ):

        return 0.0


    denominator = (
        FULL_CONTEXT_CONFIDENCE
        -
        MIN_CONTEXT_CONFIDENCE
    )


    if denominator <= 0:

        return 1.0


    strength = (
        confidence
        -
        MIN_CONTEXT_CONFIDENCE
    ) / denominator


    return clamp(
        strength,
        0.0,
        1.0,
    )


# =========================================================
# CURRENT / FUTURE SIGNALS
# =========================================================

def calculate_context_signals(
    context_summary,
):

    # -----------------------------------------------------
    # CURRENT SEASON
    #
    # Health matters heavily because unresolved injuries
    # directly affect the upcoming season.
    # -----------------------------------------------------

    current_signal = (
        0.30
        *
        context_summary.role_score

        +
        0.25
        *
        context_summary.usage_score

        +
        0.45
        *
        context_summary.health_score
    )


    # -----------------------------------------------------
    # FUTURE VALUE
    #
    # Dynasty context matters more here while temporary
    # usage/injury effects receive less weight.
    # -----------------------------------------------------

    future_signal = (
        0.25
        *
        context_summary.role_score

        +
        0.10
        *
        context_summary.usage_score

        +
        0.20
        *
        context_summary.health_score

        +
        0.45
        *
        context_summary.dynasty_score
    )


    current_signal = clamp(
        current_signal,
        -1.0,
        1.0,
    )


    future_signal = clamp(
        future_signal,
        -1.0,
        1.0,
    )


    blended_signal = (
        CURRENT_SEASON_WEIGHT
        *
        current_signal

        +
        FUTURE_VALUE_WEIGHT
        *
        future_signal
    )


    return (
        current_signal,
        future_signal,
        clamp(
            blended_signal,
            -1.0,
            1.0,
        ),
    )


# =========================================================
# EVENT SAFEGUARDS
# =========================================================

def apply_material_event_rules(
    adjustment_pct,
    context_summary,
    strength,
):

    # =====================================================
    # SEASON-ENDING / SEVERE INJURY
    #
    # If projections have not caught up yet, this lets
    # current context temporarily protect us.
    # =====================================================

    if has_active_event(
        context_summary,
        INJURY_SEVERE,
    ):

        severe_floor = (
            -MAX_NEGATIVE_ADJUSTMENT_PCT
            *
            strength
        )


        adjustment_pct = min(
            adjustment_pct,
            severe_floor,
        )


    # =====================================================
    # CURRENTLY OUT
    # =====================================================

    elif has_active_event(
        context_summary,
        INJURY_OUT,
    ):

        out_floor = (
            -0.05
            *
            strength
        )


        adjustment_pct = min(
            adjustment_pct,
            out_floor,
        )


    # =====================================================
    # CURRENT LIMITATION
    # =====================================================

    elif has_active_event(
        context_summary,
        INJURY_LIMITED,
    ):

        limited_floor = (
            -0.025
            *
            strength
        )


        adjustment_pct = min(
            adjustment_pct,
            limited_floor,
        )


    # =====================================================
    # ROLE LOSS
    # =====================================================

    if has_active_event(
        context_summary,
        ROLE_DOWN,
    ):

        role_floor = (
            -0.03
            *
            strength
        )


        adjustment_pct = min(
            adjustment_pct,
            role_floor,
        )


    # =====================================================
    # USAGE LOSS
    # =====================================================

    if has_active_event(
        context_summary,
        USAGE_DOWN,
    ):

        usage_floor = (
            -0.02
            *
            strength
        )


        adjustment_pct = min(
            adjustment_pct,
            usage_floor,
        )


    # =====================================================
    # DYNASTY DETERIORATION
    # =====================================================

    if has_active_event(
        context_summary,
        DYNASTY_DOWN,
    ):

        dynasty_floor = (
            -0.025
            *
            strength
        )


        adjustment_pct = min(
            adjustment_pct,
            dynasty_floor,
        )


    # =====================================================
    # POSITIVE ROLE CHANGE
    #
    # Do NOT force positive adjustment if material health
    # risk is unresolved.
    # =====================================================

    material_health_risk = (
        has_active_event(
            context_summary,
            INJURY_SEVERE,
        )
        or
        has_active_event(
            context_summary,
            INJURY_OUT,
        )
    )


    if (
        not material_health_risk
        and
        has_active_event(
            context_summary,
            ROLE_UP,
        )
    ):

        role_bonus = (
            0.02
            *
            strength
        )


        adjustment_pct = max(
            adjustment_pct,
            role_bonus,
        )


    # =====================================================
    # POSITIVE USAGE
    # =====================================================

    if (
        not material_health_risk
        and
        has_active_event(
            context_summary,
            USAGE_UP,
        )
    ):

        usage_bonus = (
            0.0125
            *
            strength
        )


        adjustment_pct = max(
            adjustment_pct,
            usage_bonus,
        )


    # =====================================================
    # STRONG DYNASTY DEVELOPMENT
    # =====================================================

    if (
        not material_health_risk
        and
        has_active_event(
            context_summary,
            DYNASTY_UP,
        )
    ):

        dynasty_bonus = (
            0.015
            *
            strength
        )


        adjustment_pct = max(
            adjustment_pct,
            dynasty_bonus,
        )


    return adjustment_pct


# =========================================================
# EXPLANATIONS
# =========================================================

def build_adjustment_reasons(
    context_summary,
    adjustment_pct,
    strength,
):

    reasons = []


    if strength <= 0:

        reasons.append(
            "Context confidence is too low to change "
            "the deterministic valuation."
        )

        return reasons


    if has_active_event(
        context_summary,
        INJURY_SEVERE,
    ):

        reasons.append(
            "Severe unresolved injury risk triggers "
            "the strongest permitted context discount."
        )


    elif has_active_event(
        context_summary,
        INJURY_OUT,
    ):

        reasons.append(
            "Current unavailable/out status creates "
            "a meaningful short-term discount."
        )


    elif has_active_event(
        context_summary,
        INJURY_LIMITED,
    ):

        reasons.append(
            "Current injury limitation creates a "
            "modest short-term discount."
        )


    if has_active_event(
        context_summary,
        ROLE_UP,
    ):

        reasons.append(
            "Current reporting supports an improved "
            "or clearer offensive role."
        )


    if has_active_event(
        context_summary,
        ROLE_DOWN,
    ):

        reasons.append(
            "Current reporting indicates role loss "
            "or deterioration."
        )


    if has_active_event(
        context_summary,
        USAGE_UP,
    ):

        reasons.append(
            "Recent evidence supports increased usage."
        )


    if has_active_event(
        context_summary,
        USAGE_DOWN,
    ):

        reasons.append(
            "Recent evidence indicates reduced usage."
        )


    if has_active_event(
        context_summary,
        DYNASTY_UP,
    ):

        reasons.append(
            "Long-term context supports future value."
        )


    if has_active_event(
        context_summary,
        DYNASTY_DOWN,
    ):

        reasons.append(
            "Long-term context creates additional "
            "future-value risk."
        )


    if adjustment_pct > 0:

        reasons.append(
            "Positive context is capped at +6%."
        )


    elif adjustment_pct < 0:

        reasons.append(
            "Negative context is capped at -8%."
        )


    return reasons[
        :6
    ]


# =========================================================
# MAIN ADJUSTMENT
# =========================================================

def calculate_context_valuation_adjustment(
    player_name,
    base_ceiling,
    context_summary,
    legal_max=None,
):

    base_ceiling = max(
        1,
        int(
            base_ceiling
        ),
    )


    signal_details = build_valuation_signal_details(context_summary)

    # =====================================================
    # NO CONTEXT
    # =====================================================

    if (
        context_summary is None
        or
        context_summary.document_count
        <= 0
    ):

        return (
            ContextValuationAdjustment(
                player_name=(
                    player_name
                ),
                base_ceiling=(
                    base_ceiling
                ),
                adjusted_ceiling=(
                    min(
                        base_ceiling,
                        int(
                            legal_max
                        ),
                    )
                    if legal_max
                    is not None
                    else base_ceiling
                ),
                adjustment_dollars=0,
                adjustment_pct=0.0,
                current_signal=0.0,
                future_signal=0.0,
                blended_signal=0.0,
                context_confidence=0.0,
                confidence_strength=0.0,
                applied=False,
                capped_by_context_limit=False,
                capped_by_legal_max=False,
                reasons=[
                    "No usable context evidence was available."
                ],
                signal_details=signal_details,
            )
        )


    confidence = clamp(
        context_summary.confidence,
        0.0,
        1.0,
    )


    strength = (
        confidence_strength(
            confidence
        )
    )


    (
        current_signal,
        future_signal,
        blended_signal,
    ) = (
        calculate_context_signals(
            context_summary
        )
    )


    # =====================================================
    # LOW CONFIDENCE = NO VALUATION CHANGE
    # =====================================================

    if strength <= 0:

        adjusted_ceiling = (
            base_ceiling
        )


        capped_by_legal_max = False


        if (
            legal_max is not None
            and
            adjusted_ceiling
            >
            int(
                legal_max
            )
        ):

            adjusted_ceiling = int(
                legal_max
            )

            capped_by_legal_max = True


        return (
            ContextValuationAdjustment(
                player_name=(
                    player_name
                ),
                base_ceiling=(
                    base_ceiling
                ),
                adjusted_ceiling=(
                    adjusted_ceiling
                ),
                adjustment_dollars=(
                    adjusted_ceiling
                    -
                    base_ceiling
                ),
                adjustment_pct=0.0,
                current_signal=(
                    current_signal
                ),
                future_signal=(
                    future_signal
                ),
                blended_signal=(
                    blended_signal
                ),
                context_confidence=(
                    confidence
                ),
                confidence_strength=0.0,
                applied=False,
                capped_by_context_limit=False,
                capped_by_legal_max=(
                    capped_by_legal_max
                ),
                reasons=[
                    (
                        "Context exists, but confidence "
                        "is below the 35% threshold."
                    )
                ],
                signal_details=signal_details,
            )
        )


    # =====================================================
    # RAW PERCENTAGE
    # =====================================================

    if blended_signal >= 0:

        raw_adjustment_pct = (
            blended_signal
            *
            MAX_POSITIVE_ADJUSTMENT_PCT
            *
            strength
        )

    else:

        raw_adjustment_pct = (
            blended_signal
            *
            MAX_NEGATIVE_ADJUSTMENT_PCT
            *
            strength
        )


    # =====================================================
    # MATERIAL EVENT SAFEGUARDS
    # =====================================================

    raw_adjustment_pct = (
        apply_material_event_rules(
            adjustment_pct=(
                raw_adjustment_pct
            ),
            context_summary=(
                context_summary
            ),
            strength=(
                strength
            ),
        )
    )


    # =====================================================
    # HARD CAPS
    # =====================================================

    bounded_adjustment_pct = clamp(
        raw_adjustment_pct,
        -MAX_NEGATIVE_ADJUSTMENT_PCT,
        MAX_POSITIVE_ADJUSTMENT_PCT,
    )


    capped_by_context_limit = (
        abs(
            bounded_adjustment_pct
            -
            raw_adjustment_pct
        )
        >
        0.0001
    )


    # =====================================================
    # APPLY TO CEILING
    # =====================================================

    raw_adjusted_ceiling = int(
        round(
            base_ceiling
            *
            (
                1.0
                +
                bounded_adjustment_pct
            )
        )
    )


    raw_adjusted_ceiling = max(
        1,
        raw_adjusted_ceiling,
    )


    adjusted_ceiling = (
        raw_adjusted_ceiling
    )


    capped_by_legal_max = False


    if (
        legal_max is not None
        and
        adjusted_ceiling
        >
        int(
            legal_max
        )
    ):

        adjusted_ceiling = int(
            legal_max
        )

        capped_by_legal_max = True


    adjustment_dollars = (
        adjusted_ceiling
        -
        base_ceiling
    )


    applied = (
        adjustment_dollars
        !=
        0
    )


    reasons = (
        build_adjustment_reasons(
            context_summary=(
                context_summary
            ),
            adjustment_pct=(
                bounded_adjustment_pct
            ),
            strength=(
                strength
            ),
        )
    )


    return (
        ContextValuationAdjustment(
            player_name=(
                player_name
            ),
            base_ceiling=(
                base_ceiling
            ),
            adjusted_ceiling=(
                adjusted_ceiling
            ),
            adjustment_dollars=(
                adjustment_dollars
            ),
            adjustment_pct=(
                bounded_adjustment_pct
            ),
            current_signal=(
                current_signal
            ),
            future_signal=(
                future_signal
            ),
            blended_signal=(
                blended_signal
            ),
            context_confidence=(
                confidence
            ),
            confidence_strength=(
                strength
            ),
            applied=(
                applied
            ),
            capped_by_context_limit=(
                capped_by_context_limit
            ),
            capped_by_legal_max=(
                capped_by_legal_max
            ),
            reasons=(
                reasons
            ),
            signal_details=signal_details,
        )
    )
