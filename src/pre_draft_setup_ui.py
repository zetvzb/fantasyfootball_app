from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from src.college_domain import apply_college_rules
from src.keeper_domain import (
    EXPLICIT_COST,
    MIDSEASON_PICKUP,
    RETURNING_KEEPER,
    KeeperDomainRules,
    derive_keeper_cost,
)
from src.league_profile import (
    LeagueProfile,
    ManagerIdentity,
)
from src.league_setup_data import (
    CollegeDraftPick,
    CollegeRight,
    HistoricalSale,
    KeeperRecord,
    LeagueSetupData,
    LeagueSetupStore,
    SourceInfo,
    TeamBudget,
)
from src.setup_resource_import import (
    SetupResourceImport,
    parse_setup_resource_rows,
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
                    "Position": player.position or "",
                    "Status": (
                        player.status
                    ),
                    "Eligibility": player.eligibility_status,
                    "Promotion State": player.promotion_status,
                    "Original Owner": label_by_manager.get(
                        player.original_manager_id or player.manager_id,
                        player.original_manager_id or player.manager_id,
                    ),
                    "Trade Provenance": player.trade_provenance or "",
                    "Sleeper Player ID": player.sleeper_player_id or "",
                    "NFL Draft Round": player.nfl_draft_round,
                    "NFL Draft Pick": player.nfl_draft_pick,
                    "Future Year 1": (
                        player.future_values[0]
                        if len(player.future_values) > 0
                        else None
                    ),
                    "Future Year 2": (
                        player.future_values[1]
                        if len(player.future_values) > 1
                        else None
                    ),
                    "Future Year 3": (
                        player.future_values[2]
                        if len(player.future_values) > 2
                        else None
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "Team",
            "Player",
            "School / NFL Team",
            "Position",
            "Status",
            "Eligibility",
            "Promotion State",
            "Original Owner",
            "Trade Provenance",
            "Sleeper Player ID",
            "NFL Draft Round",
            "NFL Draft Pick",
            "Future Year 1",
            "Future Year 2",
            "Future Year 3",
        ],
    )


def _manual_college_pick_dataframe(
    manual_setup: Optional[LeagueSetupData],
    label_by_manager: Dict[str, str],
) -> pd.DataFrame:

    rows = []
    if manual_setup is not None:
        for pick in manual_setup.college_picks:
            rows.append(
                {
                    "Owner": label_by_manager.get(
                        pick.manager_id,
                        pick.manager_id,
                    ),
                    "Original Owner": label_by_manager.get(
                        pick.original_manager_id,
                        pick.original_manager_id,
                    ),
                    "Season": pick.season,
                    "Round": pick.round_number,
                    "Pick": pick.pick_number,
                    "Trade Provenance": pick.trade_provenance or "",
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "Owner",
            "Original Owner",
            "Season",
            "Round",
            "Pick",
            "Trade Provenance",
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
    imported_candidates: Tuple[KeeperRecord, ...],
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
        "Select candidates from the uploaded resource, or add a player by "
        "name. A player is not protected until selected here, and keeper "
        "costs feed directly into auction-budget math."
    )


    manual_keeper_map = (
        _manual_keeper_map(
            manual_setup
        )
    )


    keepers: List[
        KeeperRecord
    ] = []

    candidate_records = []
    if manual_setup is not None:
        candidate_records.extend(
            keeper for keeper in manual_setup.keepers
            if keeper.status == "candidate"
        )
    candidate_records.extend(imported_candidates)
    candidate_by_identity = {
        (candidate.manager_id, candidate.player_name.lower()): candidate
        for candidate in candidate_records
    }
    candidate_records = list(candidate_by_identity.values())


    max_keepers = int(
        league_profile.max_keepers
        or 0
    )
    keeper_rules = KeeperDomainRules.from_league_profile(
        league_profile
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
            candidate_by_name = {
                candidate.player_name: candidate
                for candidate in candidate_records
                if candidate.manager_id == manager_id
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
                |
                set(candidate_by_name.keys())
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
                    "Additional keeper not in the candidate list",
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
                    or candidate_by_name.get(player_name)
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

                saved_cost_basis = (
                    saved_record.cost_basis
                    if saved_record
                    else EXPLICIT_COST
                )
                cost_basis_labels = {
                    EXPLICIT_COST: "Explicit current cost",
                    RETURNING_KEEPER: "Returning keeper",
                    MIDSEASON_PICKUP: "Mid-season pickup",
                }
                cost_basis_options = list(
                    cost_basis_labels.keys()
                )
                if saved_cost_basis not in cost_basis_options:
                    saved_cost_basis = EXPLICIT_COST

                cost_basis = st.selectbox(
                    f"{player_name} cost basis",
                    options=cost_basis_options,
                    index=cost_basis_options.index(saved_cost_basis),
                    format_func=lambda value: cost_basis_labels[value],
                    disabled=disabled,
                    key=(
                        f"keeper_cost_basis::"
                        f"{league_profile.league_key}::"
                        f"{manager_id}::"
                        f"{player_name}"
                    ),
                )

                prior_year_cost = None
                if cost_basis == RETURNING_KEEPER:
                    prior_year_default = 0
                    if (
                        saved_record
                        and saved_record.prior_year_cost is not None
                    ):
                        prior_year_default = int(
                            saved_record.prior_year_cost
                        )
                    prior_year_cost = int(
                        st.number_input(
                            f"{player_name} prior-year cost",
                            min_value=0,
                            max_value=10000,
                            value=prior_year_default,
                            step=1,
                            disabled=disabled,
                            key=(
                                f"keeper_prior_cost::"
                                f"{league_profile.league_key}::"
                                f"{manager_id}::"
                                f"{player_name}"
                            ),
                        )
                    )
                    cost = derive_keeper_cost(
                        cost_basis=cost_basis,
                        explicit_cost=None,
                        prior_year_cost=prior_year_cost,
                        rules=keeper_rules,
                    )
                    st.caption(
                        "Current keeper cost: ${0} (${1} + ${2})".format(
                            cost,
                            prior_year_cost,
                            keeper_rules.annual_escalation,
                        )
                    )
                elif cost_basis == MIDSEASON_PICKUP:
                    cost = derive_keeper_cost(
                        cost_basis=cost_basis,
                        explicit_cost=None,
                        prior_year_cost=None,
                        rules=keeper_rules,
                    )
                    st.caption(
                        "Next-season mid-season pickup cost: ${0}".format(
                            cost
                        )
                    )
                else:
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

                tenure_years = int(
                    st.number_input(
                        f"{player_name} completed keeper seasons",
                        min_value=0,
                        value=(
                            int(saved_record.tenure_years)
                            if saved_record
                            else 0
                        ),
                        step=1,
                        help=(
                            "Recorded for future-value analysis only; "
                            "there is no tenure maximum."
                        ),
                        disabled=disabled,
                        key=(
                            f"keeper_tenure::"
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
                        cost_basis=(
                            cost_basis
                        ),
                        prior_year_cost=(
                            prior_year_cost
                        ),
                        tenure_years=(
                            tenure_years
                        ),
                        future_values=(
                            saved_record.future_values
                            if saved_record
                            else ()
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

    finalized = {
        (keeper.manager_id, keeper.player_name.lower()) for keeper in keepers
    }
    return [
        candidate for candidate in candidate_records
        if (candidate.manager_id, candidate.player_name.lower()) not in finalized
    ] + keepers


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
    imported_players: Tuple[CollegeRight, ...],
    disabled: bool,
) -> Tuple[List[CollegeRight], List[CollegeDraftPick]]:

    st.markdown(
        "### College / Devy Rights"
    )

    if not league_profile.college.enabled:
        st.info(
            "College/devy is disabled for this league. No rights or picks "
            "will be stored."
        )
        return [], []

    st.caption(
        "Enter off-platform college or devy rights here. "
        "Leave this blank when the league does not use them "
        "or when no information is available."
    )


    display_setup = LeagueSetupData(
        league_key=league_profile.league_key,
        college_players=(
            list(manual_setup.college_players) if manual_setup is not None else []
        ) + list(imported_players),
        college_picks=(
            list(manual_setup.college_picks) if manual_setup is not None else []
        ),
    )
    college_df = (
        _manual_college_dataframe(
            display_setup,
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
                "Position": st.column_config.SelectboxColumn(
                    "Position",
                    options=["QB", "RB", "WR", "TE"],
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
                "Eligibility": st.column_config.SelectboxColumn(
                    "Eligibility",
                    options=["eligible", "ineligible", "unknown"],
                    default="unknown",
                    required=True,
                ),
                "Promotion State": st.column_config.SelectboxColumn(
                    "Promotion State",
                    options=["taxi", "promoted"],
                    default="taxi",
                    required=True,
                ),
                "Original Owner": st.column_config.SelectboxColumn(
                    "Original Owner",
                    options=team_options,
                    required=True,
                ),
                "Trade Provenance": st.column_config.TextColumn(
                    "Trade Provenance"
                ),
                "Sleeper Player ID": st.column_config.TextColumn(
                    "Sleeper Player ID"
                ),
                "NFL Draft Round": st.column_config.NumberColumn(
                    "NFL Draft Round",
                    min_value=1,
                    max_value=7,
                    step=1,
                ),
                "NFL Draft Pick": st.column_config.NumberColumn(
                    "NFL Draft Pick",
                    min_value=1,
                    step=1,
                ),
                "Future Year 1": st.column_config.NumberColumn(
                    "Future Year 1",
                    min_value=0.0,
                    max_value=100.0,
                ),
                "Future Year 2": st.column_config.NumberColumn(
                    "Future Year 2",
                    min_value=0.0,
                    max_value=100.0,
                ),
                "Future Year 3": st.column_config.NumberColumn(
                    "Future Year 3",
                    min_value=0.0,
                    max_value=100.0,
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

        future_values = []
        for column_name in (
            "Future Year 1",
            "Future Year 2",
            "Future Year 3",
        ):
            value = row.get(column_name)
            future_values.append(
                None
                if value is None or pd.isna(value)
                else float(value)
            )
        while future_values and future_values[-1] is None:
            future_values.pop()


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
                position=(
                    _normalize_optional_text(row.get("Position"))
                ),
                status=(
                    status
                ),
                eligibility_status=(
                    _normalize_optional_text(
                        row.get("Eligibility")
                    )
                    or "unknown"
                ),
                promotion_status=(
                    _normalize_optional_text(
                        row.get("Promotion State")
                    )
                    or "taxi"
                ),
                original_manager_id=(
                    manager_by_label.get(
                        _normalize_optional_text(
                            row.get("Original Owner")
                        )
                        or team_label
                    )
                    or manager_id
                ),
                trade_provenance=(
                    _normalize_optional_text(
                        row.get("Trade Provenance")
                    )
                ),
                sleeper_player_id=(
                    _normalize_optional_text(
                        row.get("Sleeper Player ID")
                    )
                ),
                nfl_draft_round=_to_int_or_none(
                    row.get("NFL Draft Round")
                ),
                nfl_draft_pick=_to_int_or_none(
                    row.get("NFL Draft Pick")
                ),
                future_values=tuple(future_values),
                source=(
                    next(
                        (
                            player.source for player in imported_players
                            if player.player_name.lower() == player_name.lower()
                            and player.manager_id == manager_id
                        ),
                        MANUAL_SOURCE,
                    )
                ),
            )
        )


    active_counts: Dict[str, int] = {}
    for record in records:
        if record.promotion_status == "promoted":
            continue
        active_counts[record.manager_id] = (
            active_counts.get(record.manager_id, 0) + 1
        )
    for manager_id, count in active_counts.items():
        if count > league_profile.college.max_college_players:
            st.error(
                "{0} has {1} active college rights; maximum is {2}.".format(
                    label_by_manager.get(manager_id, manager_id),
                    count,
                    league_profile.college.max_college_players,
                )
            )

    st.markdown("#### College Draft Pick Ownership")
    st.caption(
        "Record current and original ownership. The app does not run the "
        "college draft."
    )
    edited_pick_df = st.data_editor(
        _manual_college_pick_dataframe(manual_setup, label_by_manager),
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        disabled=disabled,
        column_config={
            "Owner": st.column_config.SelectboxColumn(
                "Owner",
                options=team_options,
                required=True,
            ),
            "Original Owner": st.column_config.SelectboxColumn(
                "Original Owner",
                options=team_options,
                required=True,
            ),
            "Season": st.column_config.NumberColumn(
                "Season",
                min_value=1,
                step=1,
                required=True,
            ),
            "Round": st.column_config.NumberColumn(
                "Round",
                min_value=1,
                max_value=(
                    league_profile.college.draft_rounds
                    if league_profile.college.draft_rounds > 0
                    else None
                ),
                step=1,
                required=True,
            ),
            "Pick": st.column_config.NumberColumn(
                "Pick",
                min_value=1,
                step=1,
            ),
            "Trade Provenance": st.column_config.TextColumn(
                "Trade Provenance"
            ),
        },
        key="college_pick_editor::{0}".format(league_profile.league_key),
    )

    picks: List[CollegeDraftPick] = []
    for row in edited_pick_df.to_dict(orient="records"):
        owner_label = _normalize_optional_text(row.get("Owner"))
        original_label = _normalize_optional_text(row.get("Original Owner"))
        season = row.get("Season")
        round_number = row.get("Round")
        if not owner_label or not original_label:
            continue
        if pd.isna(season) or pd.isna(round_number):
            continue
        owner_id = manager_by_label.get(owner_label)
        original_owner_id = manager_by_label.get(original_label)
        if owner_id is None or original_owner_id is None:
            continue
        pick_number = row.get("Pick")
        picks.append(
            CollegeDraftPick(
                manager_id=owner_id,
                original_manager_id=original_owner_id,
                season=int(season),
                round_number=int(round_number),
                pick_number=(
                    None if pd.isna(pick_number) else int(pick_number)
                ),
                trade_provenance=_normalize_optional_text(
                    row.get("Trade Provenance")
                ),
                source=MANUAL_SOURCE,
            )
        )

    return records, picks


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
    imported_sales: Tuple[HistoricalSale, ...],
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


    display_setup = LeagueSetupData(
        league_key=league_profile.league_key,
        historical_sales=(
            list(manual_setup.historical_sales) if manual_setup is not None else []
        ) + list(imported_sales),
    )
    history_df = (
        _manual_history_dataframe(
            display_setup,
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
                    next(
                        (
                            sale.source for sale in imported_sales
                            if sale.player_name.lower() == player_name.lower()
                            and int(sale.year) == int(year)
                        ),
                        MANUAL_SOURCE,
                    )
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
    manual_protected_entry = league_profile.source_mode != "sleeper"
    resource_import = SetupResourceImport()


    with st.expander(
        "🛠️ League Setup Data",
        expanded=(
            not workbook_loaded
            and
            manual_setup is None
        ),
    ):

        st.caption(
            (
                "Enter Yahoo/manual budgets and protected players here. "
                "Sleeper supplies only the global NFL player universe."
                if manual_protected_entry
                else "Sleeper and optional workbook/import data provide "
                "rosters and protected players. Manual setup is limited to "
                "budget and history overrides."
            )
        )


        if setup_locked:

            st.warning(
                "The auction has live sales, so setup editing "
                "is locked. Reset live sales before changing "
                "budgets or protected-player data."
            )

        if manual_protected_entry and not setup_locked:
            st.markdown("### Optional League Resource")
            st.caption(
                "Upload CSV or XLSX instead of typing player lists. Supported "
                "columns: Type (keeper/devy/history), Team, Player, Position, "
                "Value, Keeper Cost, Year, and Price. Team may be omitted for "
                "your own keeper candidates."
            )
            uploaded_resource = st.file_uploader(
                "Keeper, devy, valuation, or draft-history resource",
                type=["csv", "xlsx", "xls"],
                key="setup_resource::{0}".format(league_profile.league_key),
            )
            if uploaded_resource is not None:
                try:
                    if uploaded_resource.name.lower().endswith(".csv"):
                        resource_frame = pd.read_csv(uploaded_resource)
                    else:
                        resource_frame = pd.read_excel(uploaded_resource)
                    aliases = {}
                    for manager_id, identity in managers.items():
                        aliases[manager_id.lower()] = manager_id
                        aliases[label_by_manager[manager_id].lower()] = manager_id
                        for value in (
                            identity.sleeper_team_name,
                            identity.sleeper_username,
                        ) + tuple(identity.historical_aliases):
                            if value:
                                aliases[str(value).strip().lower()] = manager_id
                    resource_import = parse_setup_resource_rows(
                        resource_frame.to_dict(orient="records"),
                        manager_aliases=aliases,
                        default_manager_id=str(
                            league_profile.metadata.get("current_manager_id") or ""
                        ),
                        current_season=int(league_profile.season),
                    )
                except Exception as error:
                    st.error("Resource could not be read: {0}".format(error))
                else:
                    st.success(
                        "Loaded {0} keeper values, {1} devy players, and {2} "
                        "historical sales.".format(
                            len(resource_import.keeper_candidates),
                            len(resource_import.college_players),
                            len(resource_import.historical_sales),
                        )
                    )
                    for warning in resource_import.warnings:
                        st.warning(warning)


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
            if manual_protected_entry:
                keepers = _keeper_editor(
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
                    imported_candidates=resource_import.keeper_candidates,
                    disabled=(
                        setup_locked
                    ),
                )
            else:
                keepers = []
                st.info(
                    "Keeper selections are source-driven for this Sleeper "
                    "league. Update Sleeper/the configured workbook, then use "
                    "Refresh Draft Intelligence or Reload Workbook."
                )
                finalized = [
                    keeper for keeper in effective_setup.keepers
                    if keeper.status == "finalized"
                ]
                if finalized:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Team": label_by_manager.get(
                                        keeper.manager_id, keeper.manager_id
                                    ),
                                    "Player": keeper.player_name,
                                    "Position": keeper.position,
                                    "Cost": keeper.cost,
                                    "Source": keeper.source.source,
                                }
                                for keeper in finalized
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )


        with college_tab:
            if manual_protected_entry:
                college_players, college_picks = _college_editor(
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
                    imported_players=resource_import.college_players,
                    disabled=(
                        setup_locked
                    ),
                )
            else:
                college_players, college_picks = [], []
                st.info(
                    "College/devy ownership is source-driven for this Sleeper "
                    "league. Update the configured source and refresh it."
                )
                if effective_setup.college_players:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Team": label_by_manager.get(
                                        player.manager_id, player.manager_id
                                    ),
                                    "Player": player.player_name,
                                    "Status": player.status,
                                    "Source": player.source.source,
                                }
                                for player in effective_setup.college_players
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
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
                    imported_sales=resource_import.historical_sales,
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
            len(college_players) + len(college_picks),
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
                    "keepers_configured": manual_protected_entry,
                    "college_configured": manual_protected_entry,
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
                        college_picks=(
                            college_picks
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


                try:
                    manual_data = apply_college_rules(
                        league_profile=league_profile,
                        setup_data=manual_data,
                    )
                    setup_store.save(
                        manual_data
                    )
                except ValueError as error:
                    st.error(
                        "College/devy setup is invalid: {0}".format(error)
                    )
                else:
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
