from typing import Dict, List

from src.player_context import (
    ContextDocument,
    clamp,
    normalize_position,
    parse_datetime,
)


# =========================================================
# HELPERS
# =========================================================

def text_value(
    value,
):

    if value is None:

        return ""


    return str(
        value
    ).strip()


def combined_text(
    item,
):

    fields = [
        item.get(
            "title"
        ),
        item.get(
            "description"
        ),
        item.get(
            "comment"
        ),
        item.get(
            "analysis"
        ),
        item.get(
            "impact"
        ),
        item.get(
            "impact_analysis"
        ),
        item.get(
            "content"
        ),
    ]


    return " ".join(
        [
            text_value(
                value
            )

            for value
            in fields

            if value
        ]
    )


def build_player_lookup(
    intelligence,
):

    lookup = {}


    for player in intelligence:

        if not player.fantasypros_id:

            continue


        lookup[
            str(
                player.fantasypros_id
            )
        ] = player


    return lookup


# =========================================================
# RULE-BASED NEWS SIGNALS
# =========================================================

def infer_news_signals(
    text,
):

    value = text.lower()


    role_signal = 0.0
    usage_signal = 0.0
    injury_signal = 0.0
    dynasty_signal = 0.0


    # =====================================================
    # ROLE UP
    # =====================================================

    role_up_terms = [
        "named starter",
        "will start",
        "starting role",
        "promoted to starter",
        "first-team reps",
        "first team reps",
        "lead back",
        "featured back",
        "feature back",
        "earned starting",
    ]


    role_down_terms = [
        "benched",
        "demoted",
        "backup role",
        "lost the starting job",
        "lost starting job",
        "third string",
        "third-string",
        "waived",
        "released",
    ]


    if any(
        term in value

        for term
        in role_up_terms
    ):

        role_signal += 0.65


    if any(
        term in value

        for term
        in role_down_terms
    ):

        role_signal -= 0.70


    # =====================================================
    # USAGE
    # =====================================================

    usage_up_terms = [
        "expanded role",
        "increased role",
        "more touches",
        "more carries",
        "more targets",
        "increased workload",
        "larger workload",
    ]


    usage_down_terms = [
        "limited role",
        "reduced role",
        "reduced workload",
        "fewer touches",
        "fewer targets",
        "snap count declined",
    ]


    if any(
        term in value

        for term
        in usage_up_terms
    ):

        usage_signal += 0.55


    if any(
        term in value

        for term
        in usage_down_terms
    ):

        usage_signal -= 0.55


    # =====================================================
    # INJURY / HEALTH
    # =====================================================

    severe_injury_terms = [
        "season-ending",
        "season ending",
        "torn acl",
        "torn achilles",
        "placed on injured reserve",
        "placed on ir",
    ]


    injury_negative_terms = [
        "will miss",
        "ruled out",
        "doubtful",
        "did not practice",
        "not practicing",
    ]


    injury_positive_terms = [
        "cleared to play",
        "full practice",
        "returned to practice",
        "activated from injured reserve",
        "activated from ir",
        "expected to play",
    ]


    if any(
        term in value

        for term
        in severe_injury_terms
    ):

        injury_signal -= 1.00


    elif any(
        term in value

        for term
        in injury_negative_terms
    ):

        injury_signal -= 0.65


    if any(
        term in value

        for term
        in injury_positive_terms
    ):

        injury_signal += 0.55


    return {
        "role_signal": clamp(
            role_signal
        ),
        "usage_signal": clamp(
            usage_signal
        ),
        "injury_signal": clamp(
            injury_signal
        ),
        "dynasty_signal": clamp(
            dynasty_signal
        ),
    }


# =========================================================
# INJURY STATUS SIGNAL
# =========================================================

def injury_status_signal(
    injury,
):

    status = text_value(
        injury.get(
            "status"
        )
    ).lower()


    status_short = text_value(
        injury.get(
            "status_short"
        )
    ).lower()


    base_signal = 0.0


    if (
        "injured reserve"
        in status
        or
        status_short
        in {
            "ir",
            "pup",
        }
    ):

        base_signal = -0.95


    elif (
        "out"
        in status
        or
        status_short
        ==
        "o"
    ):

        base_signal = -0.85


    elif (
        "doubtful"
        in status
    ):

        base_signal = -0.70


    elif (
        "questionable"
        in status
        or
        status_short
        ==
        "q"
    ):

        base_signal = -0.40


    elif (
        "probable"
        in status
    ):

        base_signal = -0.10


    probability = (
        injury.get(
            "probability_of_playing"
        )
    )


    try:

        probability = float(
            probability
        )

    except (
        TypeError,
        ValueError,
    ):

        probability = None


    if probability is not None:

        probability_signal = (
            (
                probability
                -
                0.50
            )
            *
            1.6
        )


        base_signal = (
            0.70
            *
            base_signal
            +
            0.30
            *
            probability_signal
        )


    return clamp(
        base_signal
    )


# =========================================================
# NEWS
# =========================================================

def normalize_fantasypros_news(
    response,
    intelligence,
) -> List[ContextDocument]:

    documents = []


    player_lookup = (
        build_player_lookup(
            intelligence
        )
    )


    for item in (
        response.get(
            "items",
            []
        )
    ):

        player_id = item.get(
            "player_id"
        )


        player = (
            player_lookup.get(
                str(
                    player_id
                )
            )
        )


        if player is None:

            continue


        content = combined_text(
            item
        )


        signals = (
            infer_news_signals(
                content
            )
        )


        categories = item.get(
            "categories",
            []
        )


        if not isinstance(
            categories,
            list,
        ):

            categories = [
                str(
                    categories
                )
            ]


        published_at = (
            parse_datetime(
                item.get(
                    "updated"
                )
                or
                item.get(
                    "created"
                )
            )
        )


        documents.append(
            ContextDocument(
                document_id=(
                    "fantasypros-news-"
                    +
                    str(
                        item.get(
                            "id"
                        )
                    )
                ),
                player_name=(
                    player.player_name
                ),
                position=(
                    normalize_position(
                        player.position
                    )
                ),
                nfl_team=(
                    player.nfl_team
                ),
                source_type=(
                    "news"
                ),
                source_name=(
                    "FantasyPros"
                ),
                title=(
                    text_value(
                        item.get(
                            "title"
                        )
                    )
                ),
                content=(
                    content
                ),
                published_at=(
                    published_at
                ),
                url=(
                    item.get(
                        "link"
                    )
                ),
                confidence=(
                    0.85
                ),
                role_signal=(
                    signals[
                        "role_signal"
                    ]
                ),
                usage_signal=(
                    signals[
                        "usage_signal"
                    ]
                ),
                injury_signal=(
                    signals[
                        "injury_signal"
                    ]
                ),
                dynasty_signal=(
                    signals[
                        "dynasty_signal"
                    ]
                ),
                tags=[
                    str(
                        category
                    ).lower()

                    for category
                    in categories
                ],
                metadata={
                    "fantasypros_id": (
                        str(
                            player_id
                        )
                    ),
                    "author": (
                        item.get(
                            "author"
                        )
                    ),
                },
            )
        )


    return documents


# =========================================================
# INJURIES
# =========================================================

def normalize_fantasypros_injuries(
    response,
    intelligence,
) -> List[ContextDocument]:

    documents = []


    player_lookup = (
        build_player_lookup(
            intelligence
        )
    )


    for injury in (
        response.get(
            "injuries",
            []
        )
    ):

        player_id = (
            injury.get(
                "player_id"
            )
        )


        player = (
            player_lookup.get(
                str(
                    player_id
                )
            )
        )


        player_name = (
            player.player_name
            if player
            else text_value(
                injury.get(
                    "name"
                )
            )
        )


        if not player_name:

            continue


        position = (
            normalize_position(
                player.position
            )
            if player
            else normalize_position(
                injury.get(
                    "position_id"
                )
            )
        )


        nfl_team = (
            player.nfl_team
            if player
            else injury.get(
                "team_id"
            )
        )


        injury_type = text_value(
            injury.get(
                "injury_type"
            )
            or
            injury.get(
                "practice_report_injury_type"
            )
        )


        status = text_value(
            injury.get(
                "status"
            )
        )


        comment = text_value(
            injury.get(
                "comment"
            )
        )


        content = (
            f"Status: {status}. "
            f"Injury: {injury_type}. "
            f"{comment}"
        ).strip()


        update_date = (
            injury.get(
                "injury_update_date"
            )
        )


        document_id = (
            "fantasypros-injury-"
            +
            str(
                player_id
            )
            +
            "-"
            +
            str(
                update_date
                or
                "current"
            )
        )


        documents.append(
            ContextDocument(
                document_id=(
                    document_id
                ),
                player_name=(
                    player_name
                ),
                position=(
                    position
                ),
                nfl_team=(
                    nfl_team
                ),
                source_type=(
                    "injury"
                ),
                source_name=(
                    "FantasyPros"
                ),
                title=(
                    (
                        f"{player_name}: "
                        f"{status}"
                    )
                ),
                content=(
                    content
                ),
                published_at=(
                    parse_datetime(
                        update_date
                    )
                ),
                confidence=(
                    0.95
                ),
                injury_signal=(
                    injury_status_signal(
                        injury
                    )
                ),
                tags=[
                    "injury",
                    status.lower(),
                ],
                metadata={
                    "fantasypros_id": (
                        str(
                            player_id
                        )
                    ),
                    "injury_type": (
                        injury_type
                    ),
                    "status": (
                        status
                    ),
                    "status_short": (
                        injury.get(
                            "status_short"
                        )
                    ),
                    "probability_of_playing": (
                        injury.get(
                            "probability_of_playing"
                        )
                    ),
                    "practice_1": (
                        injury.get(
                            "practice_1"
                        )
                    ),
                    "practice_2": (
                        injury.get(
                            "practice_2"
                        )
                    ),
                    "practice_3": (
                        injury.get(
                            "practice_3"
                        )
                    ),
                },
            )
        )


    return documents