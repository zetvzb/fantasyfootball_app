from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import exp, log
from typing import Dict, List, Optional

from src.evidence_quality import evidence_weight


# =========================================================
# SOURCE WEIGHTS
# =========================================================

SOURCE_WEIGHTS = {
    "injury": 1.00,
    "depth_chart": 0.95,
    "official_news": 0.90,
    "news": 0.80,
    "beat_report": 0.80,
    "usage": 0.85,
    "dynasty": 0.70,
    "social": 0.45,
}


HALF_LIFE_DAYS = {
    "injury": 14,
    "depth_chart": 21,
    "official_news": 14,
    "news": 10,
    "beat_report": 7,
    "usage": 14,
    "dynasty": 60,
    "social": 3,
}


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class ContextDocument:
    document_id: str

    player_name: str
    position: Optional[str]
    nfl_team: Optional[str]

    source_type: str
    source_name: str

    title: str
    content: str

    published_at: Optional[datetime] = None
    url: Optional[str] = None

    confidence: float = 1.0

    # Positive = favorable
    # Negative = unfavorable
    role_signal: float = 0.0
    usage_signal: float = 0.0
    injury_signal: float = 0.0
    dynasty_signal: float = 0.0

    tags: List[str] = field(
        default_factory=list
    )

    metadata: Dict = field(
        default_factory=dict
    )


@dataclass
class PlayerContextSummary:
    player_name: str

    document_count: int

    role_score: float
    usage_score: float
    injury_score: float
    dynasty_score: float

    overall_context_score: float
    confidence: float

    latest_update: Optional[datetime]

    reasons: List[str] = field(
        default_factory=list
    )

    documents: List[
        ContextDocument
    ] = field(
        default_factory=list
    )


# =========================================================
# HELPERS
# =========================================================

def clamp(
    value,
    minimum=-1.0,
    maximum=1.0,
):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def normalize_position(
    value,
):

    if value is None:

        return None


    value = str(
        value
    ).upper()


    if value in {
        "DST",
        "D/ST",
    }:

        return "DEF"


    return value


def ensure_utc(
    value,
):

    if value is None:

        return None


    if value.tzinfo is None:

        return value.replace(
            tzinfo=timezone.utc
        )


    return value.astimezone(
        timezone.utc
    )


def parse_datetime(
    value,
):

    if value is None:

        return None


    if isinstance(
        value,
        datetime,
    ):

        return ensure_utc(
            value
        )


    text = str(
        value
    ).strip()


    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ]


    for date_format in formats:

        try:

            parsed = datetime.strptime(
                text,
                date_format,
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except ValueError:

            continue


    try:

        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )

        return ensure_utc(
            parsed
        )

    except ValueError:

        return None


def recency_weight(
    published_at,
    source_type,
    as_of=None,
):

    if published_at is None:

        return 0.50


    published_at = ensure_utc(
        published_at
    )


    if as_of is None:

        as_of = datetime.now(
            timezone.utc
        )

    else:

        as_of = ensure_utc(
            as_of
        )


    age_seconds = max(
        0,
        (
            as_of
            -
            published_at
        ).total_seconds(),
    )


    age_days = (
        age_seconds
        /
        86400.0
    )


    half_life = (
        HALF_LIFE_DAYS.get(
            source_type,
            14,
        )
    )


    decay_constant = (
        log(
            2.0
        )
        /
        max(
            half_life,
            1,
        )
    )


    return exp(
        -decay_constant
        *
        age_days
    )


def document_weight(
    document,
    as_of=None,
):

    source_weight = (
        SOURCE_WEIGHTS.get(
            document.source_type,
            0.65,
        )
    )


    recency = (
        recency_weight(
            published_at=(
                document.published_at
            ),
            source_type=(
                document.source_type
            ),
            as_of=(
                as_of
            ),
        )
    )


    confidence = clamp(
        document.confidence,
        0.0,
        1.0,
    )


    return (
        source_weight
        *
        recency
        *
        confidence
        *
        evidence_weight(document)
    )


# =========================================================
# AGGREGATE SIGNAL
# =========================================================

def weighted_signal(
    documents,
    attribute,
    as_of=None,
):

    numerator = 0.0
    denominator = 0.0


    for document in documents:

        signal = clamp(
            getattr(
                document,
                attribute,
                0.0,
            )
        )


        if abs(
            signal
        ) < 0.001:

            continue


        weight = (
            document_weight(
                document,
                as_of=(
                    as_of
                ),
            )
        )


        numerator += (
            signal
            *
            weight
        )


        denominator += (
            weight
        )


    if denominator <= 0:

        return 0.0


    return clamp(
        numerator
        /
        denominator
    )


# =========================================================
# EXPLANATIONS
# =========================================================

def build_context_reasons(
    role_score,
    usage_score,
    injury_score,
    dynasty_score,
):

    reasons = []


    if role_score >= 0.35:

        reasons.append(
            "recent context supports an improving role"
        )

    elif role_score <= -0.35:

        reasons.append(
            "recent context suggests role deterioration"
        )


    if usage_score >= 0.35:

        reasons.append(
            "recent usage indicators are favorable"
        )

    elif usage_score <= -0.35:

        reasons.append(
            "recent usage indicators are unfavorable"
        )


    if injury_score >= 0.35:

        reasons.append(
            "health context is improving"
        )

    elif injury_score <= -0.35:

        reasons.append(
            "injury context adds meaningful risk"
        )


    if dynasty_score >= 0.35:

        reasons.append(
            "long-term context is favorable"
        )

    elif dynasty_score <= -0.35:

        reasons.append(
            "long-term context has deteriorated"
        )


    return reasons


# =========================================================
# PLAYER CONTEXT
# =========================================================

def build_player_context_summary(
    player_name,
    documents,
    as_of=None,
):

    relevant_documents = [
        document

        for document
        in documents

        if (
            document.player_name
            ==
            player_name
        )
    ]


    relevant_documents.sort(
        key=lambda document: (
            document.published_at
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )


    role_score = (
        weighted_signal(
            relevant_documents,
            "role_signal",
            as_of=as_of,
        )
    )


    usage_score = (
        weighted_signal(
            relevant_documents,
            "usage_signal",
            as_of=as_of,
        )
    )


    injury_score = (
        weighted_signal(
            relevant_documents,
            "injury_signal",
            as_of=as_of,
        )
    )


    dynasty_score = (
        weighted_signal(
            relevant_documents,
            "dynasty_signal",
            as_of=as_of,
        )
    )


    # -----------------------------------------------------
    # Context score is NOT a dollar adjustment.
    #
    # It is a normalized football-context signal that the
    # deterministic valuation layer can decide how to use.
    # -----------------------------------------------------

    overall_context_score = clamp(
        0.35
        *
        role_score
        +
        0.25
        *
        usage_score
        +
        0.25
        *
        injury_score
        +
        0.15
        *
        dynasty_score
    )


    total_weight = sum(
        document_weight(
            document,
            as_of=as_of,
        )

        for document
        in relevant_documents
    )


    confidence = min(
        1.0,
        total_weight
        /
        3.0,
    )


    latest_update = None


    dated_documents = [
        document.published_at

        for document
        in relevant_documents

        if document.published_at
        is not None
    ]


    if dated_documents:

        latest_update = max(
            dated_documents
        )


    reasons = (
        build_context_reasons(
            role_score=role_score,
            usage_score=usage_score,
            injury_score=injury_score,
            dynasty_score=dynasty_score,
        )
    )


    return PlayerContextSummary(
        player_name=(
            player_name
        ),
        document_count=(
            len(
                relevant_documents
            )
        ),
        role_score=(
            role_score
        ),
        usage_score=(
            usage_score
        ),
        injury_score=(
            injury_score
        ),
        dynasty_score=(
            dynasty_score
        ),
        overall_context_score=(
            overall_context_score
        ),
        confidence=(
            confidence
        ),
        latest_update=(
            latest_update
        ),
        reasons=(
            reasons
        ),
        documents=(
            relevant_documents
        ),
    )


def build_context_summary_index(
    documents,
    as_of=None,
):

    player_names = sorted(
        {
            document.player_name

            for document
            in documents

            if document.player_name
        }
    )


    return {
        player_name: (
            build_player_context_summary(
                player_name=(
                    player_name
                ),
                documents=(
                    documents
                ),
                as_of=(
                    as_of
                ),
            )
        )

        for player_name
        in player_names
    }
