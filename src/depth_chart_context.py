from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.auction_pool import normalize_player_name
from src.player_context import ContextDocument


SUPPORTED_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
}


# =========================================================
# HELPERS
# =========================================================

def numeric_int(
    value,
):

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


def sleeper_player_name(
    player,
):

    full_name = (
        player.get(
            "full_name"
        )
    )


    if full_name:

        return str(
            full_name
        ).strip()


    first_name = str(
        player.get(
            "first_name"
        )
        or
        ""
    ).strip()


    last_name = str(
        player.get(
            "last_name"
        )
        or
        ""
    ).strip()


    return (
        first_name
        +
        " "
        +
        last_name
    ).strip()


def normalize_position(
    value,
):

    if value is None:

        return None


    value = str(
        value
    ).upper().strip()


    if value in {
        "DST",
        "D/ST",
    }:

        return "DEF"


    return value


def is_active_player(
    player,
):

    active = (
        player.get(
            "active"
        )
    )


    status = str(
        player.get(
            "status"
        )
        or
        ""
    ).lower()


    team = (
        player.get(
            "team"
        )
    )


    if not team:

        return False


    if active is False:

        return False


    if status in {
        "inactive",
        "retired",
    }:

        return False


    return True


def canonical_player_name(
    sleeper_name,
    fantasypros_index=None,
):

    if not fantasypros_index:

        return sleeper_name


    key = (
        normalize_player_name(
            sleeper_name
        )
    )


    fp = (
        fantasypros_index.get(
            key
        )
    )


    if (
        fp
        and
        fp.player_name
    ):

        return fp.player_name


    return sleeper_name


# =========================================================
# DEPTH ROLE
# =========================================================

def calculate_depth_signals(
    position,
    order,
    teammate_orders,
):

    role_signal = 0.0
    usage_signal = 0.0
    confidence = 0.85
    role_label = "DEPTH"

    committee_risk = False


    # =====================================================
    # QB
    # =====================================================

    if position == "QB":

        if order == 1:

            role_signal = 0.80
            usage_signal = 0.60
            role_label = "QB1"

        elif order == 2:

            role_signal = -0.45
            usage_signal = -0.55
            role_label = "QB2"

        elif order is not None:

            role_signal = -0.70
            usage_signal = -0.75
            role_label = (
                f"QB{order}"
            )


    # =====================================================
    # RB
    # =====================================================

    elif position == "RB":

        has_rb2 = (
            2
            in teammate_orders
        )


        if order == 1:

            role_signal = 0.60

            usage_signal = (
                0.25
                if has_rb2
                else 0.45
            )

            role_label = "RB1"

            committee_risk = (
                has_rb2
            )


        elif order == 2:

            role_signal = 0.15
            usage_signal = 0.05
            role_label = "RB2"

            committee_risk = True


        elif order == 3:

            role_signal = -0.25
            usage_signal = -0.30
            role_label = "RB3"


        elif order is not None:

            role_signal = -0.55
            usage_signal = -0.60
            role_label = (
                f"RB{order}"
            )


    # =====================================================
    # WR
    #
    # WR3 is not treated like QB3/RB3 because NFL teams
    # regularly start three receivers.
    # =====================================================

    elif position == "WR":

        if order == 1:

            role_signal = 0.65
            usage_signal = 0.40
            role_label = "WR1"


        elif order == 2:

            role_signal = 0.50
            usage_signal = 0.30
            role_label = "WR2"


        elif order == 3:

            role_signal = 0.25
            usage_signal = 0.12
            role_label = "WR3"


        elif order == 4:

            role_signal = -0.15
            usage_signal = -0.20
            role_label = "WR4"


        elif order is not None:

            role_signal = -0.45
            usage_signal = -0.50
            role_label = (
                f"WR{order}"
            )


    # =====================================================
    # TE
    # =====================================================

    elif position == "TE":

        if order == 1:

            role_signal = 0.65
            usage_signal = 0.35
            role_label = "TE1"


        elif order == 2:

            role_signal = 0.00
            usage_signal = -0.10
            role_label = "TE2"


        elif order is not None:

            role_signal = -0.45
            usage_signal = -0.50
            role_label = (
                f"TE{order}"
            )


    # =====================================================
    # K
    # =====================================================

    elif position == "K":

        if order == 1:

            role_signal = 0.75
            usage_signal = 0.30
            role_label = "K1"


        elif order is not None:

            role_signal = -0.65
            usage_signal = -0.65
            role_label = (
                f"K{order}"
            )


    return {
        "role_signal": (
            role_signal
        ),
        "usage_signal": (
            usage_signal
        ),
        "confidence": (
            confidence
        ),
        "role_label": (
            role_label
        ),
        "committee_risk": (
            committee_risk
        ),
    }


# =========================================================
# BUILD DEPTH CHART DOCUMENTS
# =========================================================

def build_depth_chart_documents(
    sleeper_players,
    fantasypros_index=None,
):

    now = datetime.now(
        timezone.utc
    )


    snapshot_date = (
        now.strftime(
            "%Y-%m-%d"
        )
    )


    groups = defaultdict(
        list
    )


    # =====================================================
    # GROUP ACTIVE PLAYERS BY TEAM + POSITION
    # =====================================================

    for (
        sleeper_id,
        player,
    ) in sleeper_players.items():

        if not isinstance(
            player,
            dict,
        ):

            continue


        if not is_active_player(
            player
        ):

            continue


        position = (
            normalize_position(
                player.get(
                    "position"
                )
            )
        )


        if (
            position
            not in SUPPORTED_POSITIONS
        ):

            continue


        team = str(
            player.get(
                "team"
            )
            or
            ""
        ).upper()


        if not team:

            continue


        player_name = (
            sleeper_player_name(
                player
            )
        )


        if not player_name:

            continue


        order = (
            numeric_int(
                player.get(
                    "depth_chart_order"
                )
            )
        )


        if order is None:

            continue


        groups[
            (
                team,
                position,
            )
        ].append(
            {
                "sleeper_id": (
                    str(
                        sleeper_id
                    )
                ),
                "player_name": (
                    player_name
                ),
                "order": (
                    order
                ),
                "depth_chart_position": (
                    player.get(
                        "depth_chart_position"
                    )
                ),
                "search_rank": (
                    player.get(
                        "search_rank"
                    )
                ),
                "injury_status": (
                    player.get(
                        "injury_status"
                    )
                ),
            }
        )


    documents = []


    # =====================================================
    # CREATE ONE SNAPSHOT DOCUMENT PER PLAYER
    # =====================================================

    for (
        team,
        position,
    ), players in groups.items():

        players = sorted(
            players,
            key=lambda value: (
                value[
                    "order"
                ],
                (
                    numeric_int(
                        value.get(
                            "search_rank"
                        )
                    )
                    or
                    999999
                ),
            ),
        )


        teammate_orders = {
            player[
                "order"
            ]

            for player
            in players
        }


        for player in players:

            sleeper_name = (
                player[
                    "player_name"
                ]
            )


            player_name = (
                canonical_player_name(
                    sleeper_name=(
                        sleeper_name
                    ),
                    fantasypros_index=(
                        fantasypros_index
                    ),
                )
            )


            order = (
                player[
                    "order"
                ]
            )


            signals = (
                calculate_depth_signals(
                    position=(
                        position
                    ),
                    order=(
                        order
                    ),
                    teammate_orders=(
                        teammate_orders
                    ),
                )
            )


            nearby_players = []


            for teammate in players:

                if (
                    teammate[
                        "sleeper_id"
                    ]
                    ==
                    player[
                        "sleeper_id"
                    ]
                ):

                    continue


                nearby_players.append(
                    (
                        f"{teammate['player_name']} "
                        f"({position}"
                        f"{teammate['order']})"
                    )
                )


            nearby_text = (
                ", ".join(
                    nearby_players[
                        :5
                    ]
                )
                if nearby_players
                else
                "none"
            )


            role_label = (
                signals[
                    "role_label"
                ]
            )


            committee_text = (
                " Committee competition is present."
                if (
                    signals[
                        "committee_risk"
                    ]
                )
                else
                ""
            )


            injury_status = (
                player.get(
                    "injury_status"
                )
            )


            injury_text = ""


            if injury_status:

                injury_text = (
                    f" Sleeper injury status: "
                    f"{injury_status}."
                )


            content = (
                f"Current Sleeper depth chart snapshot "
                f"lists {player_name} as {role_label} "
                f"for {team}. "
                f"Depth chart order is {order}. "
                f"Other {position}s on the team: "
                f"{nearby_text}."
                f"{committee_text}"
                f"{injury_text}"
            )


            document_id = (
                "sleeper-depth-"
                +
                player[
                    "sleeper_id"
                ]
                +
                "-"
                +
                snapshot_date
            )


            tags = [
                "depth_chart",
                position.lower(),
                team.lower(),
                role_label.lower(),
            ]


            if (
                signals[
                    "committee_risk"
                ]
            ):

                tags.append(
                    "committee"
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
                        team
                    ),
                    source_type=(
                        "depth_chart"
                    ),
                    source_name=(
                        "Sleeper"
                    ),
                    title=(
                        f"{player_name}: "
                        f"{team} {role_label}"
                    ),
                    content=(
                        content
                    ),
                    published_at=(
                        now
                    ),
                    confidence=(
                        signals[
                            "confidence"
                        ]
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
                    injury_signal=0.0,
                    dynasty_signal=0.0,
                    tags=(
                        tags
                    ),
                    metadata={
                        "sleeper_id": (
                            player[
                                "sleeper_id"
                            ]
                        ),
                        "team": (
                            team
                        ),
                        "position": (
                            position
                        ),
                        "depth_chart_order": (
                            order
                        ),
                        "depth_chart_position": (
                            player.get(
                                "depth_chart_position"
                            )
                        ),
                        "role_label": (
                            role_label
                        ),
                        "committee_risk": (
                            signals[
                                "committee_risk"
                            ]
                        ),
                        "nearby_players": (
                            nearby_players
                        ),
                        "snapshot_date": (
                            snapshot_date
                        ),
                    },
                )
            )


    return documents