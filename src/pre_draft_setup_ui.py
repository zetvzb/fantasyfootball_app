from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from src.league_profile import (
    LeagueProfile,
    ManagerIdentity,
)
from src.league_setup_data import (
    CollegeRight,
    HistoricalSale,
    KeeperRecord,
    LeagueSetupData,
    LeagueSetupStore,
    SourceInfo,
    TeamBudget,
)


MANUAL_SOURCE = SourceInfo(
    source="manual",
    confidence=1.0,
    inferred=False,
    detail="Entered in Pre-Draft Setup",
)


def _team_label(
    manager_id: str,
    identity: ManagerIdentity,
) -> str:

    name = (
        identity.sleeper_team_name
        or identity.sleeper_username
        or manager_id
    )

    return (
        f"{name} [{manager_id}]"
    )


def _manager_label_maps(
    managers: Dict[
        str,
        ManagerIdentity,
    ],
) -> Tuple[
    Dict[str, str],
    Dict[str, str],
]:

    label_by_manager = {
        manager_id: _team_label(
            manager_id,
            identity,
        )

        for (
            manager_id,
            identity,
        ) in managers.items()
    }

    manager_by_label = {
        label: manager_id

        for (
            manager_id,
            label,
        ) in label_by_manager.items()
    }

    return (
        label_by_manager,
        manager_by_label,
    )


def _manual_budget_metadata(
    manual_setup: Optional[
        LeagueSetupData
    ],
) -> dict:

    if manual_setup is None:
        return {}

    return dict(
        manual_setup.metadata
        or {}
    )


def _manual_keeper_map(
    manual_setup: Optional[
        LeagueSetupData
    ],
) -> Dict[str, List[KeeperRecord]]:

    result: Dict[
        str,
        List[KeeperRecord],
    ] = {}

    if manual_setup is None:
        return result

    for keeper in (
        manual_setup.keepers
    ):

        if (
            keeper.source.source
            != "manual"
        ):
            continue

        if keeper.status != "finalized":
            continue

        result.setdefault(
            keeper.manager_id,
            [],
        ).append(
            keeper
        )

    return result


def _manual_college_dataframe(
    manual_setup: Optional[
        LeagueSetupData
    ],
    label_by_manager: Dict[
        str,
        str,
    ],
) -> pd.DataFrame:

    rows = []

    if manual_setup is not None:

        for player in (
            manual_setup
            .college_players
        ):

            if (
                player.source.source
                != "manual"
            ):
                continue

            rows.append(
                {
                    "Team": (
                        label_by_manager.get(
                            player.manager_id,
                            player.manager_id,
                        )
                    ),
                    "Player": (
                        player.player_name
                    ),
                    "School / NFL Team": (
                        player.school_or_team
                        or ""
                    ),
                    "Status": (
                        player.status
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "Team",
            "Player",
            "School / NFL Team",
            "Status",
        ],
    )


def _manual_history_dataframe(
    manual_setup: Optional[
        LeagueSetupData
    ],
    label_by_manager: Dict[
        str,
        str,
    ],
    season: int,
) -> pd.DataFrame:

    rows = []

    if manual_setup is not None:

        for sale in (
            manual_setup
            .historical_sales
        ):

            if (
                sale.source.source
                != "manual"
            ):
                continue

            team_value = ""

            if sale.manager_id:

                team_value = (
                    label_by_manager.get(
                        sale.manager_id,
                        sale.manager_raw
                        or sale.manager_id,
                    )
                )

            elif sale.manager_raw:

                team_value = (
                    sale.manager_raw
                )

            rows.append(
                {
                    "Year": (
                        int(
                            sale.year
                        )
                    ),
                    "Player": (
                        sale.player_name
                    ),
                    "Position": (
                        sale.position
                        or ""
                    ),
                    "Team": (
                        team_value
                    ),
                    "Price": (
                        int(
                            sale.price
                        )
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "Year",
            "Player",
            "Position",
            "Team",
            "Price",
        ],
    )


def _normalize_optional_text(
    value,
) -> Optional[str]:

    if value is None:
        return None

    text = str(
        value
    ).strip()

    return (
        text
        if text
        else None
    )


def _to_int_or_none(
    value,
) -> Optional[int]:

    if value is None:
        return None

    if (
        isinstance(
            value,
            float,
        )
        and
        pd.isna(
            value
        )
    ):
        return None

    try:

        return int(
            float(
                value
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


def _budget_editor(
    *,
    league_profile: LeagueProfile,
    managers: Dict[
        str,
        ManagerIdentity,
    ],
    effective_setup: LeagueSetupData,
    manual_setup: Optional[
        LeagueSetupData
    ],
    label_by_manager: Dict[
        str,
        str,
    ],
    disabled: bool,
) -> Tuple[
    Dict[str, TeamBudget],
    dict,
]:

    st.markdown(
        "### Auction Budgets"
    )

    st.caption(
        "Use one league-wide budget when every team starts "
        "from the same number. Switch to team-specific budgets "
        "when keeper economics or league rules create different "
        "starting amounts."
    )


    metadata = (
        _manual_budget_metadata(
            manual_setup
        )
    )


    saved_mode = (
        metadata.get(
            "budget_mode"
        )
    )


    if saved_mode is None:

        effective_amounts = {
            int(
                budget.amount
            )

            for budget
            in effective_setup
            .budgets
            .values()
        }

        saved_mode = (
            "Team-specific budgets"
            if len(
                effective_amounts
            )
            > 1
            else
            "Same budget for every team"
        )


    if saved_mode not in {
        "Same budget for every team",
        "Team-specific budgets",
    }:

        saved_mode = (
            "Same budget for every team"
        )


    budget_mode = st.radio(
        "Budget setup",
        options=[
            "Same budget for every team",
            "Team-specific budgets",
        ],
        index=(
            0
            if saved_mode
            == "Same budget for every team"
            else 1
        ),
        horizontal=True,
        disabled=disabled,
        key=(
            f"budget_mode::"
            f"{league_profile.league_key}"
        ),
    )


    saved_kind = (
        metadata.get(
            "budget_kind"
        )
    )


    if saved_kind is None:

        saved_kind = (
            "pre_keeper"
            if any(
                budget.budget_kind
                == "pre_keeper"

                for budget
                in effective_setup
                .budgets
                .values()
            )
            else
            "auction_cash"
        )


    budget_kind_label = st.radio(
        "What does this budget represent?",
        options=[
            "Auction cash available after keeper costs",
            "Salary cap before keeper costs",
        ],
        index=(
            0
            if saved_kind
            == "auction_cash"
            else 1
        ),
        horizontal=True,
        disabled=disabled,
        key=(
            f"budget_kind::"
            f"{league_profile.league_key}"
        ),
    )


    budget_kind = (
        "auction_cash"
        if budget_kind_label
        == "Auction cash available after keeper costs"
        else "pre_keeper"
    )


    budgets: Dict[
        str,
        TeamBudget,
    ] = {}


    if (
        budget_mode
        ==
        "Same budget for every team"
    ):

        saved_general_budget = (
            metadata.get(
                "general_budget"
            )
        )


        if saved_general_budget is None:

            amounts = [
                budget.amount

                for budget
                in effective_setup
                .budgets
                .values()
            ]

            if amounts:

                saved_general_budget = int(
                    round(
                        sum(
                            amounts
                        )
                        /
                        len(
                            amounts
                        )
                    )
                )

            else:

                saved_general_budget = int(
                    league_profile
                    .auction
                    .base_budget
                )


        general_budget = int(
            st.number_input(
                "General auction budget",
                min_value=1,
                max_value=10000,
                value=int(
                    saved_general_budget
                ),
                step=1,
                disabled=disabled,
                key=(
                    f"general_budget::"
                    f"{league_profile.league_key}"
                ),
            )
        )


        for manager_id in managers:

            budgets[
                manager_id
            ] = TeamBudget(
                manager_id=(
                    manager_id
                ),
                amount=(
                    general_budget
                ),
                budget_kind=(
                    budget_kind
                ),
                source=(
                    MANUAL_SOURCE
                ),
            )


    else:

        budget_rows = []


        for (
            manager_id,
            identity,
        ) in managers.items():

            existing = (
                effective_setup
                .budgets
                .get(
                    manager_id
                )
            )

            amount = (
                existing.amount
                if existing
                else league_profile
                .auction
                .base_budget
            )

            budget_rows.append(
                {
                    "Team": (
                        label_by_manager[
                            manager_id
                        ]
                    ),
                    "Budget": int(
                        amount
                    ),
                    "Traded Dollars": int(
                        existing.traded_dollars
                        if existing
                        else 0
                    ),
                }
            )


        budget_df = pd.DataFrame(
            budget_rows
        )


        edited_budget_df = (
            st.data_editor(
                budget_df,
                width="stretch",
                hide_index=True,
                disabled=(
                    ["Team"]
                    if not disabled
                    else True
                ),
                column_config={
                    "Team": (
                        st.column_config
                        .TextColumn(
                            "Team",
                        )
                    ),
                    "Budget": (
                        st.column_config
                        .NumberColumn(
                            "Budget",
                            min_value=1,
                            step=1,
                            format="$%d",
                        )
                    ),
                    "Traded Dollars": (
                        st.column_config
                        .NumberColumn(
                            "Traded Dollars",
                            help=(
                                "Net auction dollars received (+) "
                                "or traded away (-). Budget remains "
                                "the authoritative team total."
                            ),
                            step=1,
                            format="$%d",
                        )
                    ),
                },
                key=(
                    f"team_budgets::"
                    f"{league_profile.league_key}"
                ),
            )
        )


        for row in (
            edited_budget_df
            .to_dict(
                orient="records"
            )
        ):

            label = str(
                row.get(
                    "Team",
                    "",
                )
            )

            manager_id = (
                next(
                    (
                        manager_id

                        for (
                            manager_id,
                            manager_label,
                        )
                        in label_by_manager.items()

                        if manager_label
                        == label
                    ),
                    None,
                )
            )


            if manager_id is None:
                continue


            amount = (
                _to_int_or_none(
                    row.get(
                        "Budget"
                    )
                )
            )


            if (
                amount is None
                or amount <= 0
            ):
                continue


            budgets[
                manager_id
            ] = TeamBudget(
                manager_id=(
                    manager_id
                ),
                amount=int(
                    amount
                ),
                budget_kind=(
                    budget_kind
                ),
                traded_dollars=int(
                    _to_int_or_none(
                        row.get(
                            "Traded Dollars"
                        )
                    )
                    or 0
                ),
                source=(
                    MANUAL_SOURCE
                ),
            )


    budget_metadata = {
        "budget_mode": (
            budget_mode
        ),
        "budget_kind": (
            budget_kind
        ),
    }


    if (
        budget_mode
        ==
        "Same budget for every team"
    ):

        budget_metadata[
            "general_budget"
        ] = int(
            next(
                iter(
                    budgets.values()
                )
            ).amount
        )


    return (
        budgets,
        budget_metadata,
    )


def _keeper_editor(
    *,
    league_profile: LeagueProfile,
    managers: Dict[
        str,
        ManagerIdentity,
    ],
    effective_setup: LeagueSetupData,
    manual_setup: Optional[
        LeagueSetupData
    ],
    persisted_setup: dict,
    disabled: bool,
) -> List[KeeperRecord]:

    st.markdown(
        "### Finalized Keepers"
    )

    if not league_profile.keepers.enabled:

        st.info(
            "This LeagueProfile does not currently "
            "have keeper rules enabled."
        )

        return []


    st.caption(
        "Sleeper roster membership is used to make selection "
        "easy, but a player is not treated as protected until "
        "you confirm them here. Keeper costs feed directly into "
        "auction-budget math."
    )


    manual_keeper_map = (
        _manual_keeper_map(
            manual_setup
        )
    )


    keepers: List[
        KeeperRecord
    ] = []


    max_keepers = int(
        league_profile.max_keepers
        or 0
    )


    for (
        manager_id,
        identity,
    ) in managers.items():

        team_name = (
            identity.sleeper_team_name
            or identity.sleeper_username
            or manager_id
        )


        with st.expander(
            team_name,
            expanded=False,
        ):

            roster_records = (
                effective_setup
                .roster_for(
                    manager_id
                )
            )


            roster_by_name = {
                player.player_name: player

                for player
                in roster_records
            }


            manual_keeper_decisions_saved = (
                manual_setup is not None
                and
                bool(
                    manual_setup
                    .metadata
                    .get(
                        "keepers_configured",
                        False,
                    )
                )
            )


            saved_keepers = (
                manual_keeper_map.get(
                    manager_id,
                    [],
                )
            )


            if manual_keeper_decisions_saved:

                saved_names = [
                    keeper.player_name

                    for keeper
                    in saved_keepers
                ]

            else:

                legacy_names = list(
                    (
                        persisted_setup.get(
                            manager_id,
                            {},
                        )
                        .get(
                            "keepers",
                            [],
                        )
                    )
                    or []
                )


                effective_by_name = {
                    keeper.player_name: keeper

                    for keeper
                    in effective_setup
                    .keepers_for(
                        manager_id
                    )
                }


                saved_names = [
                    name

                    for name
                    in legacy_names
                ]


                saved_keepers = [
                    effective_by_name[
                        name
                    ]

                    for name
                    in saved_names

                    if name
                    in effective_by_name
                ]


            extra_saved_names = [
                name

                for name
                in saved_names

                if name
                not in roster_by_name
            ]


            options = sorted(
                set(
                    roster_by_name.keys()
                )
                |
                set(
                    extra_saved_names
                )
            )


            selected_names = (
                st.multiselect(
                    "Protected players",
                    options=options,
                    default=[
                        name

                        for name
                        in saved_names

                        if name
                        in options
                    ],
                    max_selections=(
                        max_keepers
                        if max_keepers > 0
                        else None
                    ),
                    disabled=disabled,
                    key=(
                        f"setup_keepers::"
                        f"{league_profile.league_key}::"
                        f"{manager_id}"
                    ),
                )
            )


            additional_text = (
                st.text_input(
                    "Additional keeper not on Sleeper roster",
                    value="",
                    placeholder=(
                        "Optional player name"
                    ),
                    disabled=disabled,
                    key=(
                        f"extra_keeper::"
                        f"{league_profile.league_key}::"
                        f"{manager_id}"
                    ),
                )
                .strip()
            )


            if (
                additional_text
                and
                additional_text
                not in selected_names
            ):

                if (
                    max_keepers <= 0
                    or
                    len(
                        selected_names
                    )
                    < max_keepers
                ):

                    selected_names.append(
                        additional_text
                    )

                else:

                    st.warning(
                        f"Maximum keepers for this "
                        f"league: {max_keepers}."
                    )


            saved_by_name = {
                keeper.player_name: keeper

                for keeper
                in saved_keepers
            }


            for player_name in (
                selected_names
            ):

                roster_record = (
                    roster_by_name.get(
                        player_name
                    )
                )

                saved_record = (
                    saved_by_name.get(
                        player_name
                    )
                )


                default_cost = 0

                if (
                    saved_record
                    and
                    saved_record.cost
                    is not None
                ):

                    default_cost = int(
                        saved_record.cost
                    )


                cost = int(
                    st.number_input(
                        f"{player_name} keeper cost",
                        min_value=0,
                        max_value=10000,
                        value=default_cost,
                        step=1,
                        disabled=disabled,
                        key=(
                            f"keeper_cost::"
                            f"{league_profile.league_key}::"
                            f"{manager_id}::"
                            f"{player_name}"
                        ),
                    )
                )


                position = None
                sleeper_player_id = None

                if roster_record:

                    position = (
                        roster_record.position
                    )

                    sleeper_player_id = (
                        roster_record
                        .sleeper_player_id
                    )

                elif saved_record:

                    position = (
                        saved_record.position
                    )

                    sleeper_player_id = (
                        saved_record
                        .sleeper_player_id
                    )


                keepers.append(
                    KeeperRecord(
                        manager_id=(
                            manager_id
                        ),
                        player_name=(
                            player_name
                        ),
                        position=(
                            position
                        ),
                        cost=(
                            cost
                        ),
                        status="finalized",
                        sleeper_player_id=(
                            sleeper_player_id
                        ),
                        source=(
                            MANUAL_SOURCE
                        ),
                    )
                )


    return keepers


def _college_editor(
    *,
    league_profile: LeagueProfile,
    managers: Dict[
        str,
        ManagerIdentity,
    ],
    manual_setup: Optional[
        LeagueSetupData
    ],
    label_by_manager: Dict[
        str,
        str,
    ],
    manager_by_label: Dict[
        str,
        str,
    ],
    disabled: bool,
) -> List[CollegeRight]:

    st.markdown(
        "### College / Devy Rights"
    )

    st.caption(
        "Enter off-platform college or devy rights here. "
        "Leave this blank when the league does not use them "
        "or when no information is available."
    )


    college_df = (
        _manual_college_dataframe(
            manual_setup,
            label_by_manager,
        )
    )


    team_options = list(
        label_by_manager.values()
    )


    edited_df = (
        st.data_editor(
            college_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            disabled=disabled,
            column_config={
                "Team": (
                    st.column_config
                    .SelectboxColumn(
                        "Team",
                        options=(
                            team_options
                        ),
                        required=True,
                    )
                ),
                "Player": (
                    st.column_config
                    .TextColumn(
                        "Player",
                        required=True,
                    )
                ),
                "School / NFL Team": (
                    st.column_config
                    .TextColumn(
                        "School / NFL Team",
                    )
                ),
                "Status": (
                    st.column_config
                    .SelectboxColumn(
                        "Status",
                        options=[
                            "in_college",
                            "in_nfl",
                            "unknown",
                        ],
                        default="unknown",
                        required=True,
                    )
                ),
            },
            key=(
                f"college_editor::"
                f"{league_profile.league_key}"
            ),
        )
    )


    records: List[
        CollegeRight
    ] = []


    for row in (
        edited_df
        .to_dict(
            orient="records"
        )
    ):

        team_label = (
            _normalize_optional_text(
                row.get(
                    "Team"
                )
            )
        )

        player_name = (
            _normalize_optional_text(
                row.get(
                    "Player"
                )
            )
        )


        if (
            not team_label
            or
            not player_name
        ):
            continue


        manager_id = (
            manager_by_label.get(
                team_label
            )
        )


        if manager_id is None:
            continue


        status = (
            _normalize_optional_text(
                row.get(
                    "Status"
                )
            )
            or "unknown"
        )


        records.append(
            CollegeRight(
                manager_id=(
                    manager_id
                ),
                player_name=(
                    player_name
                ),
                school_or_team=(
                    _normalize_optional_text(
                        row.get(
                            "School / NFL Team"
                        )
                    )
                ),
                status=(
                    status
                ),
                source=(
                    MANUAL_SOURCE
                ),
            )
        )


    return records


def _history_editor(
    *,
    league_profile: LeagueProfile,
    manual_setup: Optional[
        LeagueSetupData
    ],
    label_by_manager: Dict[
        str,
        str,
    ],
    manager_by_label: Dict[
        str,
        str,
    ],
    disabled: bool,
) -> List[HistoricalSale]:

    st.markdown(
        "### Historical Auction Sales"
    )

    st.caption(
        "Historical data is optional. Add whatever past "
        "auction sales you have; leave the table empty when "
        "the league has no usable history."
    )


    history_df = (
        _manual_history_dataframe(
            manual_setup,
            label_by_manager,
            league_profile.season,
        )
    )


    edited_df = (
        st.data_editor(
            history_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            disabled=disabled,
            column_config={
                "Year": (
                    st.column_config
                    .NumberColumn(
                        "Year",
                        min_value=2000,
                        max_value=(
                            int(
                                league_profile
                                .season
                            )
                        ),
                        step=1,
                        required=True,
                    )
                ),
                "Player": (
                    st.column_config
                    .TextColumn(
                        "Player",
                        required=True,
                    )
                ),
                "Position": (
                    st.column_config
                    .SelectboxColumn(
                        "Position",
                        options=[
                            "",
                            "QB",
                            "RB",
                            "WR",
                            "TE",
                            "K",
                            "DEF",
                        ],
                    )
                ),
                "Team": (
                    st.column_config
                    .TextColumn(
                        "Team / Manager",
                        help=(
                            "Optional. Active team labels are "
                            "recognized automatically; older "
                            "manager names may be typed freely."
                        ),
                    )
                ),
                "Price": (
                    st.column_config
                    .NumberColumn(
                        "Price",
                        min_value=0,
                        step=1,
                        format="$%d",
                        required=True,
                    )
                ),
            },
            key=(
                f"history_editor::"
                f"{league_profile.league_key}"
            ),
        )
    )


    records: List[
        HistoricalSale
    ] = []


    for row in (
        edited_df
        .to_dict(
            orient="records"
        )
    ):

        year = (
            _to_int_or_none(
                row.get(
                    "Year"
                )
            )
        )

        player_name = (
            _normalize_optional_text(
                row.get(
                    "Player"
                )
            )
        )

        price = (
            _to_int_or_none(
                row.get(
                    "Price"
                )
            )
        )


        if (
            year is None
            or
            not player_name
            or
            price is None
        ):
            continue


        team_label = (
            _normalize_optional_text(
                row.get(
                    "Team"
                )
            )
        )


        manager_id = None
        manager_raw = None

        if team_label:

            manager_id = (
                manager_by_label.get(
                    team_label
                )
            )

            if manager_id is None:

                manager_raw = (
                    team_label
                )


        records.append(
            HistoricalSale(
                year=int(
                    year
                ),
                player_name=(
                    player_name
                ),
                price=int(
                    price
                ),
                manager_id=(
                    manager_id
                ),
                manager_raw=(
                    manager_raw
                ),
                position=(
                    _normalize_optional_text(
                        row.get(
                            "Position"
                        )
                    )
                ),
                source=(
                    MANUAL_SOURCE
                ),
            )
        )


    return records


def render_league_setup_editor(
    *,
    league_profile: LeagueProfile,
    managers: Dict[
        str,
        ManagerIdentity,
    ],
    effective_setup: LeagueSetupData,
    manual_setup: Optional[
        LeagueSetupData
    ],
    persisted_setup: dict,
    setup_store: LeagueSetupStore,
    setup_locked: bool,
    workbook_loaded: bool,
) -> None:
    """
    Render persistent pre-draft setup inputs.

    Saved records contain only manual overrides. On the next
    Streamlit run, app.py merges them over workbook, Sleeper,
    and league defaults using LeagueSetupData precedence.
    """

    label_by_manager, manager_by_label = (
        _manager_label_maps(
            managers
        )
    )


    with st.expander(
        "🛠️ League Setup Data",
        expanded=(
            not workbook_loaded
            and
            manual_setup is None
        ),
    ):

        st.caption(
            "Sleeper provides league structure and current "
            "rosters. Add only the information you actually "
            "know. Missing college or historical data is valid."
        )


        if setup_locked:

            st.warning(
                "The auction has live sales, so setup editing "
                "is locked. Reset live sales before changing "
                "budgets or protected-player data."
            )


        (
            budget_tab,
            keeper_tab,
            college_tab,
            history_tab,
        ) = st.tabs(
            [
                "💵 Budgets",
                "🔒 Keepers",
                "🎓 College / Devy",
                "📚 History",
            ]
        )


        with budget_tab:

            (
                budgets,
                budget_metadata,
            ) = _budget_editor(
                league_profile=(
                    league_profile
                ),
                managers=(
                    managers
                ),
                effective_setup=(
                    effective_setup
                ),
                manual_setup=(
                    manual_setup
                ),
                label_by_manager=(
                    label_by_manager
                ),
                disabled=(
                    setup_locked
                ),
            )


        with keeper_tab:

            keepers = (
                _keeper_editor(
                    league_profile=(
                        league_profile
                    ),
                    managers=(
                        managers
                    ),
                    effective_setup=(
                        effective_setup
                    ),
                    manual_setup=(
                        manual_setup
                    ),
                    persisted_setup=(
                        persisted_setup
                    ),
                    disabled=(
                        setup_locked
                    ),
                )
            )


        with college_tab:

            college_players = (
                _college_editor(
                    league_profile=(
                        league_profile
                    ),
                    managers=(
                        managers
                    ),
                    manual_setup=(
                        manual_setup
                    ),
                    label_by_manager=(
                        label_by_manager
                    ),
                    manager_by_label=(
                        manager_by_label
                    ),
                    disabled=(
                        setup_locked
                    ),
                )
            )


        with history_tab:

            historical_sales = (
                _history_editor(
                    league_profile=(
                        league_profile
                    ),
                    manual_setup=(
                        manual_setup
                    ),
                    label_by_manager=(
                        label_by_manager
                    ),
                    manager_by_label=(
                        manager_by_label
                    ),
                    disabled=(
                        setup_locked
                    ),
                )
            )


        st.divider()


        s1, s2, s3, s4 = (
            st.columns(4)
        )


        s1.metric(
            "Budget Overrides",
            len(
                budgets
            ),
        )

        s2.metric(
            "Finalized Keepers",
            len(
                keepers
            ),
        )

        s3.metric(
            "College / Devy",
            len(
                college_players
            ),
        )

        s4.metric(
            "Historical Sales",
            len(
                historical_sales
            ),
        )


        save_col, clear_col = (
            st.columns(
                [
                    3,
                    1,
                ]
            )
        )


        with save_col:

            if st.button(
                "💾 Save League Setup",
                type="primary",
                width="stretch",
                disabled=(
                    setup_locked
                ),
                key=(
                    f"save_setup::"
                    f"{league_profile.league_key}"
                ),
            ):

                metadata = {
                    **budget_metadata,
                    "saved_from_ui": True,
                    "keepers_configured": True,
                    "college_configured": True,
                    "history_configured": True,
                }


                manual_data = (
                    LeagueSetupData(
                        league_key=(
                            league_profile
                            .league_key
                        ),
                        budgets=(
                            budgets
                        ),
                        keepers=(
                            keepers
                        ),
                        college_players=(
                            college_players
                        ),
                        historical_sales=(
                            historical_sales
                        ),
                        warnings=[],
                        metadata=(
                            metadata
                        ),
                    )
                )


                setup_store.save(
                    manual_data
                )

                st.success(
                    "League setup saved."
                )

                st.rerun()


        with clear_col:

            if st.button(
                "Clear Manual",
                width="stretch",
                disabled=(
                    setup_locked
                    or
                    manual_setup is None
                ),
                key=(
                    f"clear_setup::"
                    f"{league_profile.league_key}"
                ),
            ):

                setup_store.delete(
                    league_profile
                    .league_key
                )

                st.rerun()
