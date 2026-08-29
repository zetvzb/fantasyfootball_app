from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

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
    HistoricalSale,
    KeeperRecord,
    LeagueSetupData,
    LeagueSetupStore,
    SourceInfo,
    TeamBudget,
)
from src.league_setup_import import parse_league_setup_workbook
from src.sleeper_player_search import (
    searchable_sleeper_players,
    sleeper_player_option_label,
)
from src.setup_resource_import import (
    IMPORT_SOURCE,
    SetupResourceImport,
    build_manager_aliases,
    parse_setup_resource_rows,
)


MANUAL_SOURCE = SourceInfo(
    source="manual",
    confidence=1.0,
    inferred=False,
    detail="Entered in Pre-Draft Setup",
)


def _render_import_warnings(warnings: Tuple[str, ...]) -> None:
    """Row-level import warnings as individual toasts get lost in scroll
    once there are more than a few; switch to a reviewable table."""

    if not warnings:
        return
    if len(warnings) <= 3:
        for warning in warnings:
            st.warning(warning)
        return
    with st.expander("⚠️ {0} import warnings".format(len(warnings))):
        st.dataframe(
            pd.DataFrame({"Warning": list(warnings)}),
            width="stretch",
            hide_index=True,
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
    Dict[str, str],
]:

    renamed_teams: Dict[str, str] = {}

    if league_profile.source_mode != "sleeper":

        st.markdown(
            "### Team Names"
        )
        st.caption(
            "Manual league team names are yours to edit -- nothing "
            "here is auto-filled from an external source."
        )

        name_rows = [
            {
                "Manager": manager_id,
                "Team": label_by_manager[manager_id],
            }
            for manager_id in managers
        ]

        edited_name_df = st.data_editor(
            pd.DataFrame(name_rows),
            width="stretch",
            hide_index=True,
            disabled=(
                ["Manager"]
                if not disabled
                else True
            ),
            column_config={
                "Manager": (
                    st.column_config.TextColumn(
                        "Manager ID",
                        help="Internal identifier; not editable here.",
                    )
                ),
                "Team": (
                    st.column_config.TextColumn(
                        "Team Name",
                    )
                ),
            },
            key=(
                f"team_names::"
                f"{league_profile.league_key}"
            ),
        )

        for row in edited_name_df.to_dict(orient="records"):
            manager_id = str(row.get("Manager", ""))
            if manager_id not in managers:
                continue
            new_name = str(row.get("Team", "")).strip()
            if new_name and new_name != label_by_manager[manager_id]:
                renamed_teams[manager_id] = new_name

        if renamed_teams:
            label_by_manager = {
                **label_by_manager,
                **renamed_teams,
            }


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
        renamed_teams,
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
    sleeper_players: Optional[Dict[str, Any]] = None,
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
        "Select candidates from the uploaded resource, or search Sleeper's "
        "full player pool below. A player is not protected until selected "
        "here, and keeper costs feed directly into auction-budget math."
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

    sleeper_pool_options = (
        searchable_sleeper_players(sleeper_players)
        if sleeper_players
        else ()
    )
    sleeper_pool_by_label = {
        sleeper_player_option_label(name, player): (name, player_id, player)
        for name, player_id, player in sleeper_pool_options
    }


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


            pool_pick_by_name: Dict[str, Tuple[str, dict]] = {}
            multiselect_key = (
                f"setup_keepers::"
                f"{league_profile.league_key}::"
                f"{manager_id}"
            )
            pending_key = (
                f"pending_keeper_adds::"
                f"{league_profile.league_key}::"
                f"{manager_id}"
            )
            # Names added via the add-row this editing session, kept until
            # "Save League Setup" is actually clicked. Unlike a one-shot
            # pending value, this has to survive every rerun -- otherwise
            # the next render recomputes `options` without the new name
            # (nothing was ever persisted to manual_setup), the multiselect's
            # stored selection is no longer a subset of `options`, and
            # Streamlit silently drops it from the selection.
            locally_added_key = (
                f"locally_added_keepers::"
                f"{league_profile.league_key}::"
                f"{manager_id}"
            )
            locally_added = dict(
                st.session_state.get(locally_added_key, {})
            )

            # Apply any add-row submission from the previous run now,
            # before the multiselect below is instantiated -- Streamlit
            # forbids writing to a widget's own session_state key once
            # that widget has rendered in the current script pass.
            pending_add = st.session_state.pop(pending_key, None)
            if pending_add:
                pending_name, pending_id, pending_player, pending_cost = (
                    pending_add
                )
                locally_added[pending_name] = (
                    pending_id,
                    pending_player,
                )
                st.session_state[locally_added_key] = locally_added

                current_selection = list(
                    st.session_state.get(multiselect_key, [])
                )
                if pending_name not in current_selection:
                    current_selection.append(pending_name)
                st.session_state[multiselect_key] = current_selection
                st.session_state[
                    f"keeper_cost::"
                    f"{league_profile.league_key}::"
                    f"{manager_id}::"
                    f"{pending_name}"
                ] = int(pending_cost)

                # Reset the add-row now too -- also before its widgets
                # are instantiated below -- so it's ready for the next
                # player instead of still showing the last pick.
                st.session_state[
                    f"extra_keeper::"
                    f"{league_profile.league_key}::"
                    f"{manager_id}"
                ] = ""
                st.session_state[
                    f"extra_keeper_cost::"
                    f"{league_profile.league_key}::"
                    f"{manager_id}"
                ] = 0

            pool_pick_by_name.update(locally_added)
            extra_saved_names = extra_saved_names + [
                name
                for name in locally_added
                if name not in extra_saved_names
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
                    key=multiselect_key,
                )
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

                position = None
                sleeper_player_id = None

                if player_name in pool_pick_by_name:

                    pool_id, pool_player = pool_pick_by_name[player_name]

                    position = str(
                        pool_player.get("position") or ""
                    ).upper() or None

                    sleeper_player_id = pool_id

                elif roster_record:

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

            st.divider()

            add_col, cost_col, button_col = st.columns([3, 1, 1])
            additional_label = add_col.selectbox(
                "Add a keeper: search Sleeper's player pool",
                options=[""] + list(sleeper_pool_by_label),
                format_func=lambda label: (
                    label or "Search Sleeper's player pool..."
                ),
                disabled=disabled,
                key=(
                    f"extra_keeper::"
                    f"{league_profile.league_key}::"
                    f"{manager_id}"
                ),
            )
            new_keeper_cost = cost_col.number_input(
                "Cost",
                min_value=0,
                max_value=10000,
                value=0,
                step=1,
                disabled=disabled,
                key=(
                    f"extra_keeper_cost::"
                    f"{league_profile.league_key}::"
                    f"{manager_id}"
                ),
            )
            button_col.markdown("&nbsp;")
            add_clicked = button_col.button(
                "➕ Add",
                disabled=disabled or not additional_label,
                key=(
                    f"extra_keeper_add::"
                    f"{league_profile.league_key}::"
                    f"{manager_id}"
                ),
            )

            if add_clicked and additional_label:

                if (
                    max_keepers > 0
                    and len(selected_names) >= max_keepers
                ):

                    st.warning(
                        f"Maximum keepers for this "
                        f"league: {max_keepers}."
                    )

                else:

                    additional_name, additional_id, additional_player = (
                        sleeper_pool_by_label[additional_label]
                    )

                    # Stash for the next run to apply before the
                    # multiselect and add-row widgets are instantiated
                    # (see the pending_add handling near the top of this
                    # manager's block). st.rerun() is safe to call here
                    # specifically because every other widget for this
                    # manager -- the multiselect and every player's cost
                    # row -- has already been instantiated earlier in
                    # this same run. Calling it any earlier (e.g. right
                    # after this button, before the per-player loop had
                    # run) would skip re-registering those widgets for
                    # this run, and Streamlit garbage-collects any widget
                    # state not re-registered in the most recently
                    # completed run -- silently wiping already-entered
                    # keeper costs on every subsequent add.
                    st.session_state[pending_key] = (
                        additional_name,
                        additional_id,
                        additional_player,
                        int(new_keeper_cost),
                    )

                    st.rerun()

    finalized = {
        (keeper.manager_id, keeper.player_name.lower()) for keeper in keepers
    }
    return [
        candidate for candidate in candidate_records
        if (candidate.manager_id, candidate.player_name.lower()) not in finalized
    ] + keepers



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
    sleeper_players: Optional[Dict[str, Any]] = None,
    league_registry: Optional[Any] = None,
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
                "columns: Type (keeper/history), Team, Player, Position, "
                "Value, Keeper Cost, Year, and Price. Team may be omitted for "
                "your own keeper candidates."
            )
            uploaded_resource = st.file_uploader(
                "Keeper, valuation, draft-history, or team-budget "
                "resource (e.g. an updated season roster/budget workbook)",
                type=["csv", "xlsx", "xls"],
                key="setup_resource::{0}".format(league_profile.league_key),
            )
            detected_team_budgets: Dict[str, TeamBudget] = {}
            if uploaded_resource is not None:
                try:
                    if uploaded_resource.name.lower().endswith(".csv"):
                        resource_frame = pd.read_csv(uploaded_resource)
                        raw_sheets = {
                            uploaded_resource.name: pd.read_csv(
                                uploaded_resource, header=None
                            )
                        }
                    else:
                        resource_frame = pd.read_excel(uploaded_resource)
                        raw_sheets = pd.read_excel(
                            uploaded_resource, sheet_name=None, header=None
                        )
                    aliases = build_manager_aliases(managers)
                    resource_import = parse_setup_resource_rows(
                        resource_frame.to_dict(orient="records"),
                        manager_aliases=aliases,
                        default_manager_id=str(
                            league_profile.metadata.get("current_manager_id") or ""
                        ),
                        current_season=int(league_profile.season),
                    )
                    workbook_import = parse_league_setup_workbook(
                        raw_sheets, current_season=int(league_profile.season)
                    )
                    for raw_team_name, detected_budget in (
                        workbook_import.team_budgets.items()
                    ):
                        manager_id = aliases.get(raw_team_name.strip().lower())
                        if manager_id is None:
                            continue
                        detected_team_budgets[manager_id] = TeamBudget(
                            manager_id=manager_id,
                            amount=detected_budget.amount,
                            budget_kind=detected_budget.budget_kind,
                            source=IMPORT_SOURCE,
                        )
                except Exception as error:
                    st.error("Resource could not be read: {0}".format(error))
                else:
                    st.success(
                        "Loaded {0} keeper values, {1} historical sales, "
                        "and {2} team budget(s).".format(
                            len(resource_import.keeper_candidates),
                            len(resource_import.historical_sales),
                            len(detected_team_budgets),
                        )
                    )
                    _render_import_warnings(
                        tuple(resource_import.warnings) + tuple(workbook_import.warnings)
                    )
                    if detected_team_budgets and st.button(
                        "Apply {0} detected budget(s)".format(
                            len(detected_team_budgets)
                        ),
                        key="apply_setup_budgets::{0}".format(
                            league_profile.league_key
                        ),
                    ):
                        merged_budgets = dict(
                            manual_setup.budgets if manual_setup is not None else {}
                        )
                        merged_budgets.update(detected_team_budgets)
                        setup_store.save(
                            LeagueSetupData(
                                league_key=league_profile.league_key,
                                budgets=merged_budgets,
                                keepers=(
                                    list(manual_setup.keepers)
                                    if manual_setup is not None
                                    else []
                                ),
                                historical_sales=(
                                    list(manual_setup.historical_sales)
                                    if manual_setup is not None
                                    else []
                                ),
                                warnings=[],
                                metadata=(
                                    dict(manual_setup.metadata)
                                    if manual_setup is not None
                                    else {}
                                ),
                            )
                        )
                        st.success("Applied detected budgets.")
                        st.rerun()


        (
            budget_tab,
            keeper_tab,
            history_tab,
        ) = st.tabs(
            [
                "💵 Budgets",
                "🔒 Keepers",
                "📚 History",
            ]
        )


        with budget_tab:

            (
                budgets,
                budget_metadata,
                renamed_teams,
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
                    sleeper_players=(
                        sleeper_players
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


        s1, s2, s3 = (
            st.columns(3)
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

                if renamed_teams and league_registry is not None:
                    updated_managers = dict(league_profile.managers)
                    for manager_id, new_name in renamed_teams.items():
                        existing_identity = updated_managers.get(manager_id)
                        if existing_identity is None:
                            continue
                        updated_managers[manager_id] = replace(
                            existing_identity,
                            sleeper_team_name=new_name,
                        )
                    league_registry.save(
                        replace(
                            league_profile,
                            managers=updated_managers,
                        )
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
