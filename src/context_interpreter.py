from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import exp, log
from typing import Dict, List, Optional

from src.player_context import ContextDocument


# =========================================================
# EVENT TYPES
# =========================================================

TEAM_CHANGE = "TEAM_CHANGE"

ROLE_UP = "ROLE_UP"
ROLE_DOWN = "ROLE_DOWN"

USAGE_UP = "USAGE_UP"
USAGE_DOWN = "USAGE_DOWN"

INJURY_SEVERE = "INJURY_SEVERE"
INJURY_OUT = "INJURY_OUT"
INJURY_LIMITED = "INJURY_LIMITED"
INJURY_RECOVERING = "INJURY_RECOVERING"
INJURY_RESOLVED = "INJURY_RESOLVED"

OFFENSE_ADAPTATION = "OFFENSE_ADAPTATION"
RAPPORT_UP = "RAPPORT_UP"

AVAILABILITY_DOWN = "AVAILABILITY_DOWN"
AVAILABILITY_RESOLVED = "AVAILABILITY_RESOLVED"

DYNASTY_UP = "DYNASTY_UP"
DYNASTY_DOWN = "DYNASTY_DOWN"

PRODUCTION_UP = "PRODUCTION_UP"

LEGACY_SIGNAL = "LEGACY_SIGNAL"


# =========================================================
# RECENCY HALF-LIVES
# =========================================================

BASE_HALF_LIFE_DAYS = {
    TEAM_CHANGE: 120,

    ROLE_UP: 60,
    ROLE_DOWN: 60,

    USAGE_UP: 30,
    USAGE_DOWN: 30,

    INJURY_SEVERE: 180,
    INJURY_OUT: 14,
    INJURY_LIMITED: 10,
    INJURY_RECOVERING: 21,
    INJURY_RESOLVED: 30,

    OFFENSE_ADAPTATION: 45,
    RAPPORT_UP: 45,

    AVAILABILITY_DOWN: 14,
    AVAILABILITY_RESOLVED: 21,

    DYNASTY_UP: 180,
    DYNASTY_DOWN: 180,

    PRODUCTION_UP: 30,

    LEGACY_SIGNAL: 21,
}


# =========================================================
# DATA OBJECTS
# =========================================================

@dataclass
class ContextEvent:

    event_id: str

    player_name: str

    event_type: str
    dimension: str

    impact: float
    confidence: float

    occurred_at: Optional[datetime]

    source_document_id: str
    source_name: str

    title: str
    evidence: str

    state_key: Optional[str] = None

    metadata: Dict = field(
        default_factory=dict
    )


@dataclass
class InterpretedPlayerContext:

    player_name: str

    document_count: int
    event_count: int

    role_score: float
    usage_score: float
    health_score: float
    dynasty_score: float

    overall_context_score: float

    confidence: float

    latest_update: Optional[datetime]

    reasons: List[str] = field(
        default_factory=list
    )

    active_events: List[
        ContextEvent
    ] = field(
        default_factory=list
    )

    all_events: List[
        ContextEvent
    ] = field(
        default_factory=list
    )


# =========================================================
# BASIC HELPERS
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


def normalize_text(
    value,
):

    if value is None:

        return ""


    return (
        str(
            value
        )
        .lower()
        .replace(
            "’",
            "'",
        )
        .replace(
            "–",
            "-",
        )
    )


def contains_any(
    text,
    phrases,
):

    return any(
        phrase in text

        for phrase
        in phrases
    )


def document_text(
    document,
):

    return (
        normalize_text(
            document.title
        )
        +
        " "
        +
        normalize_text(
            document.content
        )
    )


# =========================================================
# BODY PART DETECTION
# =========================================================

BODY_PARTS = [
    "achilles",
    "ankle",
    "back",
    "calf",
    "concussion",
    "elbow",
    "foot",
    "groin",
    "hamstring",
    "hand",
    "head",
    "hip",
    "knee",
    "neck",
    "quad",
    "quadriceps",
    "rib",
    "shoulder",
    "toe",
    "wrist",
]


def detect_body_part(
    text,
):

    for body_part in BODY_PARTS:

        if body_part in text:

            return body_part


    return "general"


# =========================================================
# OFFSEASON-AWARE RECENCY
# =========================================================

def is_offseason(
    as_of,
):

    if as_of is None:

        as_of = datetime.now(
            timezone.utc
        )


    as_of = ensure_utc(
        as_of
    )


    # Fantasy offseason / preseason context should
    # persist much longer than weekly practice reports.
    return as_of.month in {
        2,
        3,
        4,
        5,
        6,
        7,
        8,
    }


def adjusted_half_life(
    event_type,
    as_of=None,
):

    base = (
        BASE_HALF_LIFE_DAYS.get(
            event_type,
            30,
        )
    )


    if not is_offseason(
        as_of
    ):

        return base


    if event_type in {
        TEAM_CHANGE,
        ROLE_UP,
        ROLE_DOWN,
        OFFENSE_ADAPTATION,
        RAPPORT_UP,
    }:

        return (
            base
            *
            1.8
        )


    if event_type in {
        DYNASTY_UP,
        DYNASTY_DOWN,
    }:

        return (
            base
            *
            2.0
        )


    if event_type in {
        INJURY_SEVERE,
        INJURY_OUT,
        INJURY_LIMITED,
        INJURY_RECOVERING,
        INJURY_RESOLVED,
    }:

        return (
            base
            *
            1.35
        )


    return (
        base
        *
        1.25
    )


def event_recency_weight(
    event,
    as_of=None,
):

    if event.occurred_at is None:

        return 0.50


    if as_of is None:

        as_of = datetime.now(
            timezone.utc
        )


    as_of = ensure_utc(
        as_of
    )


    occurred_at = ensure_utc(
        event.occurred_at
    )


    age_days = max(
        0.0,
        (
            as_of
            -
            occurred_at
        ).total_seconds()
        /
        86400.0,
    )


    half_life = max(
        1.0,
        adjusted_half_life(
            event.event_type,
            as_of=as_of,
        ),
    )


    decay = (
        log(
            2.0
        )
        /
        half_life
    )


    return exp(
        -decay
        *
        age_days
    )


def event_weight(
    event,
    as_of=None,
):

    return (
        clamp(
            event.confidence,
            0.0,
            1.0,
        )
        *
        event_recency_weight(
            event,
            as_of=as_of,
        )
    )


# =========================================================
# EVENT CREATOR
# =========================================================

def make_event(
    document,
    event_type,
    dimension,
    impact,
    confidence,
    evidence,
    state_key=None,
    metadata=None,
):

    event_id = (
        document.document_id
        +
        ":"
        +
        event_type
        +
        ":"
        +
        str(
            state_key
            or dimension
        )
    )


    return ContextEvent(
        event_id=event_id,
        player_name=(
            document.player_name
        ),
        event_type=(
            event_type
        ),
        dimension=(
            dimension
        ),
        impact=clamp(
            impact
        ),
        confidence=clamp(
            confidence,
            0.0,
            1.0,
        ),
        occurred_at=(
            document.published_at
        ),
        source_document_id=(
            document.document_id
        ),
        source_name=(
            document.source_name
        ),
        title=(
            document.title
        ),
        evidence=(
            evidence
        ),
        state_key=(
            state_key
        ),
        metadata=(
            metadata
            or {}
        ),
    )


# =========================================================
# EVENT EXTRACTION
# =========================================================

def extract_context_events(
    document,
):

    events = []

    text = document_text(
        document
    )


    body_part = detect_body_part(
        text
    )


    injury_state_key = (
        "injury:"
        +
        body_part
    )


    # =====================================================
    # SEVERE INJURY
    # =====================================================

    severe_injury_phrases = [
        "season-ending",
        "season ending",
        "torn acl",
        "torn achilles",
        "ruptured achilles",
        "placed on injured reserve",
        "placed on ir",
        "out for the season",
    ]


    if contains_any(
        text,
        severe_injury_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=INJURY_SEVERE,
                dimension="health",
                impact=-1.00,
                confidence=0.98,
                evidence=(
                    "Severe or long-term injury reported."
                ),
                state_key=(
                    injury_state_key
                ),
                metadata={
                    "body_part": body_part,
                },
            )
        )


    # =====================================================
    # OUT / UNAVAILABLE
    # =====================================================

    out_phrases = [
        "ruled out",
        "will miss",
        "expected to miss",
        "not expected to play",
        "won't play",
        "will not play",
    ]


    if contains_any(
        text,
        out_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=INJURY_OUT,
                dimension="health",
                impact=-0.80,
                confidence=0.90,
                evidence=(
                    "Player reported unavailable "
                    "or expected to miss time."
                ),
                state_key=(
                    injury_state_key
                ),
                metadata={
                    "body_part": body_part,
                },
            )
        )


    # =====================================================
    # LIMITED / QUESTIONABLE
    # =====================================================

    limited_phrases = [
        "limited practice",
        "limited participant",
        "questionable",
        "day-to-day",
        "day to day",
        "did not practice",
        "didn't practice",
        "not practicing",
    ]


    if contains_any(
        text,
        limited_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=INJURY_LIMITED,
                dimension="health",
                impact=-0.40,
                confidence=0.80,
                evidence=(
                    "Player has a current practice "
                    "or availability limitation."
                ),
                state_key=(
                    injury_state_key
                ),
                metadata={
                    "body_part": body_part,
                },
            )
        )


    # =====================================================
    # RECOVERING
    # =====================================================

    recovering_phrases = [
        "returned to practice",
        "returns to practice",
        "practicing on",
        "practiced on",
        "resumed practicing",
        "activated from injured reserve",
        "activated from ir",
    ]


    if contains_any(
        text,
        recovering_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=INJURY_RECOVERING,
                dimension="health",
                impact=0.35,
                confidence=0.82,
                evidence=(
                    "Player has returned to practice "
                    "or resumed football activity."
                ),
                state_key=(
                    injury_state_key
                ),
                metadata={
                    "body_part": body_part,
                },
            )
        )


    # =====================================================
    # RESOLVED / HEALTHY
    # =====================================================

    resolved_phrases = [
        "not expected to be limited",
        "not expected to be limited by",
        "won't be limited",
        "will not be limited",
        "without limitation",
        "without limitations",
        "full participant",
        "full practice",
        "cleared to play",
        "off injury report",
        "removed from injury report",
        "expected to play",
        "good to go",
    ]


    if contains_any(
        text,
        resolved_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=INJURY_RESOLVED,
                dimension="health",
                impact=0.60,
                confidence=0.92,
                evidence=(
                    "Latest report indicates the "
                    "injury should not materially limit "
                    "the player."
                ),
                state_key=(
                    injury_state_key
                ),
                metadata={
                    "body_part": body_part,
                },
            )
        )


    # =====================================================
    # ROLE UP
    # =====================================================

    role_up_phrases = [
        "clear no. 1 option",
        "clear no 1 option",
        "clear no.1 option",
        "clear number one option",
        "clear wr1",
        "wr1 role",
        "top receiving option",
        "top option",
        "primary receiver",
        "lead receiver",
        "lead back",
        "featured back",
        "feature back",
        "named starter",
        "starting role",
        "will start",
        "first-team reps",
        "first team reps",
        "earned the starting job",
        "locked-in starter",
        "locked in starter",
    ]


    if contains_any(
        text,
        role_up_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=ROLE_UP,
                dimension="role",
                impact=0.75,
                confidence=0.88,
                evidence=(
                    "Recent reporting supports a "
                    "clear or expanded role."
                ),
                state_key="role:primary",
            )
        )


    # =====================================================
    # ROLE DOWN
    # =====================================================

    role_down_phrases = [
        "benched",
        "demoted",
        "backup role",
        "lost the starting job",
        "lost starting job",
        "third-string",
        "third string",
        "buried on the depth chart",
        "reduced role",
        "waived",
        "released",
    ]


    if contains_any(
        text,
        role_down_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=ROLE_DOWN,
                dimension="role",
                impact=-0.80,
                confidence=0.90,
                evidence=(
                    "Recent reporting indicates "
                    "role deterioration."
                ),
                state_key="role:primary",
            )
        )


    # =====================================================
    # USAGE UP
    # =====================================================

    usage_up_phrases = [
        "expanded role",
        "increased role",
        "increased workload",
        "larger workload",
        "more touches",
        "more carries",
        "more targets",
        "target volume",
        "target share increased",
        "career-high targets",
        "career high targets",
    ]


    if contains_any(
        text,
        usage_up_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=USAGE_UP,
                dimension="usage",
                impact=0.60,
                confidence=0.80,
                evidence=(
                    "Recent reporting supports "
                    "increased opportunity or workload."
                ),
                state_key="usage:current",
            )
        )


    # =====================================================
    # USAGE DOWN
    # =====================================================

    usage_down_phrases = [
        "reduced workload",
        "limited role",
        "fewer touches",
        "fewer carries",
        "fewer targets",
        "snap count declined",
        "declining snap share",
    ]


    if contains_any(
        text,
        usage_down_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=USAGE_DOWN,
                dimension="usage",
                impact=-0.60,
                confidence=0.80,
                evidence=(
                    "Recent reporting indicates "
                    "reduced usage or workload."
                ),
                state_key="usage:current",
            )
        )


    # =====================================================
    # TEAM CHANGE
    # =====================================================

    team_change_phrases = [
        "traded to",
        "signs with",
        "signed with",
        "acquired by",
        "claimed by",
        "joins the",
    ]


    if contains_any(
        text,
        team_change_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=TEAM_CHANGE,
                dimension="dynasty",
                impact=0.08,
                confidence=0.95,
                evidence=(
                    "Player changed teams, creating "
                    "a new offensive environment."
                ),
                state_key="team:current",
            )
        )


    # =====================================================
    # NEW OFFENSE / ADAPTATION
    # =====================================================

    adaptation_phrases = [
        "learning the offense",
        "learning patriots offense",
        "learning new offense",
        "learning the new offense",
        "adjusting to a new offense",
        "adjusting to the offense",
        "adjusted to a new offense",
        "new offense and system",
    ]


    if contains_any(
        text,
        adaptation_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=OFFENSE_ADAPTATION,
                dimension="role",
                impact=-0.08,
                confidence=0.72,
                evidence=(
                    "Player is still adapting to "
                    "a new offensive system."
                ),
                state_key="adaptation:offense",
            )
        )


    # =====================================================
    # RAPPORT
    # =====================================================

    rapport_phrases = [
        "building rapport",
        "build a rapport",
        "developing chemistry",
        "building chemistry",
        "develop chemistry",
    ]


    if contains_any(
        text,
        rapport_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=RAPPORT_UP,
                dimension="usage",
                impact=0.15,
                confidence=0.65,
                evidence=(
                    "Reports indicate developing "
                    "chemistry with the offense."
                ),
                state_key="rapport:quarterback",
            )
        )


    # =====================================================
    # AVAILABILITY / SUSPENSION
    # =====================================================

    availability_down_phrases = [
        "suspended",
        "suspension",
        "will miss games",
        "personal leave",
    ]


    if contains_any(
        text,
        availability_down_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=AVAILABILITY_DOWN,
                dimension="health",
                impact=-0.80,
                confidence=0.90,
                evidence=(
                    "Non-injury availability risk "
                    "is currently present."
                ),
                state_key="availability:current",
            )
        )


    availability_resolved_phrases = [
        "suspension lifted",
        "reinstated",
        "returns from suspension",
        "returned from suspension",
    ]


    if contains_any(
        text,
        availability_resolved_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=AVAILABILITY_RESOLVED,
                dimension="health",
                impact=0.40,
                confidence=0.90,
                evidence=(
                    "Previous availability restriction "
                    "has been resolved."
                ),
                state_key="availability:current",
            )
        )


    # =====================================================
    # DYNASTY POSITIVE
    # =====================================================

    dynasty_up_phrases = [
        "contract extension",
        "signed an extension",
        "long-term extension",
        "franchise cornerstone",
    ]


    if contains_any(
        text,
        dynasty_up_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=DYNASTY_UP,
                dimension="dynasty",
                impact=0.30,
                confidence=0.75,
                evidence=(
                    "Long-term organizational commitment "
                    "supports dynasty stability."
                ),
                state_key="dynasty:contract",
            )
        )


    # =====================================================
    # DYNASTY NEGATIVE
    # =====================================================

    dynasty_down_phrases = [
        "considering retirement",
        "expected to retire",
        "likely to retire",
        "retirement possible",
        "retirement rumors",
    ]


    if contains_any(
        text,
        dynasty_down_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=DYNASTY_DOWN,
                dimension="dynasty",
                impact=-0.60,
                confidence=0.75,
                evidence=(
                    "Long-term availability or career "
                    "duration is uncertain."
                ),
                state_key="dynasty:career",
            )
        )


    # =====================================================
    # PRODUCTION SIGNAL
    # =====================================================

    production_phrases = [
        "eclipses 1,000 yards",
        "eclipsed 1,000 yards",
        "career-high receiving",
        "career high receiving",
        "career-high rushing",
        "career high rushing",
    ]


    if contains_any(
        text,
        production_phrases,
    ):

        events.append(
            make_event(
                document=document,
                event_type=PRODUCTION_UP,
                dimension="usage",
                impact=0.20,
                confidence=0.75,
                evidence=(
                    "Recent production supports "
                    "meaningful offensive involvement."
                ),
                state_key=None,
            )
        )


    # =====================================================
    # FALLBACK TO EXISTING RULE-BASED SIGNALS
    #
    # Only use these when the new interpreter did not
    # already produce an event for that dimension.
    # =====================================================

    event_dimensions = {
        event.dimension

        for event
        in events
    }


    fallback_signals = [
        (
            "role",
            document.role_signal,
        ),
        (
            "usage",
            document.usage_signal,
        ),
        (
            "health",
            document.injury_signal,
        ),
        (
            "dynasty",
            document.dynasty_signal,
        ),
    ]


    for (
        dimension,
        signal,
    ) in fallback_signals:

        if (
            dimension
            in event_dimensions
        ):

            continue


        if abs(
            signal
        ) < 0.10:

            continue


        events.append(
            make_event(
                document=document,
                event_type=LEGACY_SIGNAL,
                dimension=dimension,
                impact=(
                    signal
                ),
                confidence=0.45,
                evidence=(
                    "Fallback signal from the "
                    "original context rules."
                ),
                state_key=None,
            )
        )


    return events


# =========================================================
# STATE RESOLUTION
# =========================================================

def event_timestamp(
    event,
):

    if event.occurred_at is None:

        return datetime.min.replace(
            tzinfo=timezone.utc
        )


    return ensure_utc(
        event.occurred_at
    )


def resolve_event_states(
    events,
):

    stateful = {}

    stateless = []


    sorted_events = sorted(
        events,
        key=event_timestamp,
    )


    for event in sorted_events:

        if event.state_key:

            # Newer information replaces older information
            # about the same football state.
            stateful[
                event.state_key
            ] = event

        else:

            stateless.append(
                event
            )


    resolved = (
        list(
            stateful.values()
        )
        +
        stateless
    )


    return sorted(
        resolved,
        key=event_timestamp,
        reverse=True,
    )


# =========================================================
# DIMENSION SCORING
# =========================================================

def aggregate_dimension(
    events,
    dimension,
    as_of=None,
):

    relevant = [
        event

        for event
        in events

        if event.dimension
        ==
        dimension
    ]


    if not relevant:

        return 0.0


    numerator = 0.0
    denominator = 0.0


    for event in relevant:

        weight = (
            event_weight(
                event,
                as_of=as_of,
            )
        )


        numerator += (
            event.impact
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
# CONFIDENCE
# =========================================================

def calculate_context_confidence(
    events,
    as_of=None,
):

    if not events:

        return 0.0


    strengths = [
        event_weight(
            event,
            as_of=as_of,
        )

        for event
        in events
    ]


    total_strength = sum(
        strengths
    )


    dimensions = {
        event.dimension

        for event
        in events
    }


    # Saturating evidence curve.
    evidence_confidence = (
        1.0
        -
        exp(
            -total_strength
            /
            1.6
        )
    )


    # Reward evidence covering multiple dimensions,
    # but don't require all four.
    diversity_multiplier = min(
        1.0,
        0.76
        +
        0.07
        *
        len(
            dimensions
        ),
    )


    confidence = (
        evidence_confidence
        *
        diversity_multiplier
    )


    return clamp(
        confidence,
        0.0,
        0.97,
    )


# =========================================================
# REASONS
# =========================================================

def latest_event_of_type(
    events,
    event_types,
):

    matching = [
        event

        for event
        in events

        if event.event_type
        in event_types
    ]


    if not matching:

        return None


    return max(
        matching,
        key=event_timestamp,
    )


def build_interpretation_reasons(
    active_events,
    role_score,
    usage_score,
    health_score,
    dynasty_score,
):

    reasons = []


    team_change = (
        latest_event_of_type(
            active_events,
            {
                TEAM_CHANGE,
            },
        )
    )


    if team_change:

        reasons.append(
            "Recent team change creates a new "
            "offensive environment."
        )


    role_up_event = (
        latest_event_of_type(
            active_events,
            {
                ROLE_UP,
            },
        )
    )


    role_down_event = (
        latest_event_of_type(
            active_events,
            {
                ROLE_DOWN,
            },
        )
    )


    if (
        role_score
        >= 0.30
        and
        role_up_event
    ):

        reasons.append(
            "Current reporting supports a clear "
            "or expanded offensive role."
        )


    elif (
        role_score
        <= -0.30
        and
        role_down_event
    ):

        reasons.append(
            "Current reporting indicates meaningful "
            "role deterioration."
        )


    if usage_score >= 0.30:

        reasons.append(
            "Current usage evidence is favorable."
        )


    elif usage_score <= -0.30:

        reasons.append(
            "Current usage evidence is unfavorable."
        )


    health_resolved = (
        latest_event_of_type(
            active_events,
            {
                INJURY_RESOLVED,
            },
        )
    )


    health_negative = (
        latest_event_of_type(
            active_events,
            {
                INJURY_SEVERE,
                INJURY_OUT,
                INJURY_LIMITED,
            },
        )
    )


    if health_resolved:

        reasons.append(
            "Latest health reporting indicates the "
            "injury is not expected to materially "
            "limit him."
        )


    elif (
        health_score
        <= -0.30
        and
        health_negative
    ):

        reasons.append(
            "Current injury information adds "
            "meaningful short-term risk."
        )


    adaptation_event = (
        latest_event_of_type(
            active_events,
            {
                OFFENSE_ADAPTATION,
            },
        )
    )


    if adaptation_event:

        reasons.append(
            "He is still adapting to a new offensive "
            "system, adding mild short-term uncertainty."
        )


    rapport_event = (
        latest_event_of_type(
            active_events,
            {
                RAPPORT_UP,
            },
        )
    )


    if rapport_event:

        reasons.append(
            "Reports indicate developing chemistry "
            "within the new offense."
        )


    if dynasty_score >= 0.30:

        reasons.append(
            "Long-term context is favorable."
        )


    elif dynasty_score <= -0.30:

        reasons.append(
            "Long-term context contains meaningful risk."
        )


    # Prevent noisy giant lists.
    return reasons[
        :6
    ]


# =========================================================
# MAIN INTERPRETER
# =========================================================

def interpret_player_context(
    player_name,
    documents,
    as_of=None,
):

    if as_of is None:

        as_of = datetime.now(
            timezone.utc
        )


    relevant_documents = [
        document

        for document
        in documents

        if document.player_name
        ==
        player_name
    ]


    all_events = []


    for document in relevant_documents:

        all_events.extend(
            extract_context_events(
                document
            )
        )


    active_events = (
        resolve_event_states(
            all_events
        )
    )


    role_score = (
        aggregate_dimension(
            active_events,
            "role",
            as_of=as_of,
        )
    )


    usage_score = (
        aggregate_dimension(
            active_events,
            "usage",
            as_of=as_of,
        )
    )


    health_score = (
        aggregate_dimension(
            active_events,
            "health",
            as_of=as_of,
        )
    )


    dynasty_score = (
        aggregate_dimension(
            active_events,
            "dynasty",
            as_of=as_of,
        )
    )


    # Context remains a football signal.
    # It is NOT directly a dollar adjustment.
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
        health_score
        +
        0.15
        *
        dynasty_score
    )


    confidence = (
        calculate_context_confidence(
            active_events,
            as_of=as_of,
        )
    )


    dated_documents = [
        document.published_at

        for document
        in relevant_documents

        if document.published_at
        is not None
    ]


    latest_update = (
        max(
            dated_documents
        )
        if dated_documents
        else None
    )


    reasons = (
        build_interpretation_reasons(
            active_events=(
                active_events
            ),
            role_score=(
                role_score
            ),
            usage_score=(
                usage_score
            ),
            health_score=(
                health_score
            ),
            dynasty_score=(
                dynasty_score
            ),
        )
    )


    return (
        InterpretedPlayerContext(
            player_name=(
                player_name
            ),
            document_count=(
                len(
                    relevant_documents
                )
            ),
            event_count=(
                len(
                    active_events
                )
            ),
            role_score=(
                role_score
            ),
            usage_score=(
                usage_score
            ),
            health_score=(
                health_score
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
            active_events=(
                active_events
            ),
            all_events=(
                all_events
            ),
        )
    )