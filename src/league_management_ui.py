from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from src.league_profile import (
    LeagueProfile,
    infer_league_profile_from_sleeper,
)
from src.league_registry import LeagueRegistry
from src.league_setup_data import LeagueSetupData, LeagueSetupStore, TeamBudget
from src.league_setup_import import (
    FIELD_LABELS,
    LeagueSetupWorkbookImport,
    parse_league_setup_workbook,
)
from src.manual_league import build_manual_league_profile
from src.portfolio_demo import install_portfolio_demo
from src.setup_resource_import import (
    IMPORT_SOURCE,
    build_manager_aliases,
    parse_setup_resource_rows,
)
from src.sleeper_client import SleeperClient


_SCALAR_WIDGET_KEYS = {
    "league_name": "name",
    "season": "season",
    "roster_size": "roster_size",
    "auction_budget": "budget",
    "minimum_bid": "minimum_bid",
    "max_keepers": "max_keepers",
    "keeper_escalation": "keeper_escalation",
}


def _read_uploaded_sheets(uploaded_files) -> Dict[str, pd.DataFrame]:
    """Load every uploaded CSV/XLSX as raw (headerless) grids, keyed by
    sheet name (XLSX) or file name stem (CSV), so parse_league_setup_workbook
    can decide per-table what shape each one is."""

    sheets: Dict[str, pd.DataFrame] = {}
    for uploaded in uploaded_files:
        name = uploaded.name.lower()
        if name.endswith(".csv"):
            sheets[Path(uploaded.name).stem] = pd.read_csv(uploaded, header=None)
        else:
            workbook = pd.read_excel(uploaded, sheet_name=None, header=None)
            for sheet_name, frame in workbook.items():
                sheets["{0}: {1}".format(uploaded.name, sheet_name)] = frame
    return sheets


def _upload_signature(uploaded_files) -> Tuple[Tuple[str, int], ...]:
    return tuple((f.name, f.size) for f in uploaded_files)


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


# =========================================================
# CACHED SLEEPER DISCOVERY
# =========================================================

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def discover_sleeper_leagues(
    account: str,
    season: int,
) -> dict:

    client = SleeperClient()

    user = client.get_user(
        account.strip()
    )

    user_id = user.get(
        "user_id"
    )

    if not user_id:

        raise ValueError(
            "Sleeper could not resolve that "
            "username or user ID."
        )


    leagues = (
        client.get_user_leagues(
            str(
                user_id
            ),
            int(
                season
            ),
        )
    )


    return {
        "user": user,
        "leagues": (
            leagues
            or []
        ),
    }


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_sleeper_league_for_setup(
    league_id: str,
) -> dict:

    client = SleeperClient()

    league = client.get_league(
        str(
            league_id
        )
    )

    users = client.get_league_users(
        str(
            league_id
        )
    )

    rosters = client.get_league_rosters(
        str(
            league_id
        )
    )

    drafts = client.get_league_drafts(
        str(
            league_id
        )
    )


    return {
        "league": league,
        "users": (
            users
            or []
        ),
        "rosters": (
            rosters
            or []
        ),
        "drafts": (
            drafts
            or []
        ),
    }


# =========================================================
# LABEL HELPERS
# =========================================================

def _league_label(
    league: dict,
) -> str:

    name = (
        league.get(
            "name"
        )
        or "Sleeper League"
    )

    league_id = (
        league.get(
            "league_id"
        )
        or ""
    )

    status = (
        league.get(
            "status"
        )
        or ""
    )


    pieces = [
        str(
            name
        )
    ]


    if status:

        pieces.append(
            str(
                status
            )
        )


    if league_id:

        pieces.append(
            str(
                league_id
            )
        )


    return " • ".join(
        pieces
    )


def _draft_label(
    draft: dict,
) -> str:

    season = (
        draft.get(
            "season"
        )
        or ""
    )

    draft_type = (
        draft.get(
            "type"
        )
        or ""
    )

    status = (
        draft.get(
            "status"
        )
        or ""
    )

    draft_id = (
        draft.get(
            "draft_id"
        )
        or ""
    )


    pieces = [
        str(
            value
        )

        for value
        in [
            season,
            draft_type,
            status,
        ]

        if value
    ]


    if draft_id:

        pieces.append(
            str(
                draft_id
            )
        )


    return " • ".join(
        pieces
    )


def _sort_drafts(
    drafts: List[dict],
) -> List[dict]:

    status_order = {
        "drafting": 0,
        "pre_draft": 1,
        "complete": 2,
    }


    return sorted(
        drafts,
        key=lambda draft: (
            status_order.get(
                str(
                    draft.get(
                        "status"
                    )
                    or ""
                ),
                9,
            ),
            str(
                draft.get(
                    "draft_id"
                )
                or ""
            ),
        ),
    )


def _scoring_display(
    profile: LeagueProfile,
) -> str:

    return (
        profile
        .scoring_label
        .replace(
            "_",
            " ",
        )
        .title()
    )


def _default_account_from_profile(
    profile: Optional[
        LeagueProfile
    ],
) -> str:

    if profile is None:

        return ""


    metadata_user = (
        profile
        .metadata
        .get(
            "my_sleeper_user_id"
        )
    )


    if metadata_user:

        return str(
            metadata_user
        )


    for identity in (
        profile.managers.values()
    ):

        if identity.sleeper_username:

            # A profile alone cannot prove which manager is
            # the app owner, so do not guess a username.
            break


    return ""


# =========================================================
# ADD LEAGUE UI
# =========================================================

def render_portfolio_demo_loader(
    *,
    registry: LeagueRegistry,
    setup_store: LeagueSetupStore,
    selector_state_key: str = "active_league_key",
) -> None:
    """Install the synthetic portfolio league without external integrations."""

    with st.sidebar.expander("🎬 Portfolio Demo", expanded=False):
        st.caption(
            "Install a synthetic eight-team auction league with unequal "
            "budgets, keeper candidates, and historical sales."
        )
        if st.button(
            "Load Portfolio Demo",
            width="stretch",
            key="portfolio_demo::load",
        ):
            try:
                profile = install_portfolio_demo(registry, setup_store)
            except (OSError, ValueError) as error:
                st.error("Portfolio demo could not be installed: {0}".format(error))
            else:
                st.session_state["pending::{0}".format(selector_state_key)] = (
                    profile.league_key
                )
                st.success("Loaded {0}.".format(profile.league_name))
                st.rerun()


def _apply_detected_league_defaults(
    prefix: str,
    detected: LeagueSetupWorkbookImport,
) -> None:
    """Seed the manual-league form's widget session_state from a parsed
    spreadsheet, before those widgets are instantiated. This must run,
    then trigger a rerun, prior to calling the corresponding st.* widget --
    Streamlit only honors a programmatic session_state value set before a
    keyed widget's first call in that run."""

    def _set(field_name: str, value) -> None:
        st.session_state["{0}::{1}".format(prefix, _SCALAR_WIDGET_KEYS[field_name])] = value

    if detected.league_name is not None:
        _set("league_name", str(detected.league_name.value))
    if detected.season is not None:
        _set("season", int(detected.season.value))
    if detected.scoring_format is not None:
        st.session_state["{0}::scoring".format(prefix)] = (
            "PPR" if detected.scoring_format.value == "ppr" else "Half PPR"
        )
    if detected.team_names:
        st.session_state["{0}::teams".format(prefix)] = "\n".join(detected.team_names)
    if detected.current_team_guess is not None:
        st.session_state["{0}::current_team".format(prefix)] = detected.current_team_guess
    if detected.roster_size is not None:
        _set("roster_size", int(detected.roster_size.value))
    if detected.auction_budget is not None:
        _set("auction_budget", int(detected.auction_budget.value))
    if detected.minimum_bid is not None:
        _set("minimum_bid", int(detected.minimum_bid.value))
    if detected.max_keepers is not None:
        _set("max_keepers", int(detected.max_keepers.value))
    if detected.keeper_escalation is not None:
        _set("keeper_escalation", int(detected.keeper_escalation.value))


def _seed_setup_from_workbook_import(
    profile: LeagueProfile,
    detected: LeagueSetupWorkbookImport,
    setup_store: LeagueSetupStore,
) -> Optional[str]:
    """After a manual league is created, fold in whatever the same
    spreadsheet also carried beyond the league-creation fields: per-team
    budgets and any keeper/history rows. Returns a short summary of
    what was saved, or None if the spreadsheet had nothing further to add.
    """

    aliases = build_manager_aliases(profile.managers)

    budgets: Dict[str, TeamBudget] = {}
    for raw_team_name, detected_budget in detected.team_budgets.items():
        manager_id = aliases.get(raw_team_name.strip().lower())
        if manager_id is None:
            continue
        budgets[manager_id] = TeamBudget(
            manager_id=manager_id,
            amount=detected_budget.amount,
            budget_kind=detected_budget.budget_kind,
            source=IMPORT_SOURCE,
        )

    resource_import = parse_setup_resource_rows(
        detected.leftover_rows,
        manager_aliases=aliases,
        default_manager_id=str(profile.metadata.get("current_manager_id") or ""),
        current_season=int(profile.season),
    )

    if not (
        budgets
        or resource_import.keeper_candidates
        or resource_import.historical_sales
    ):
        return None

    setup_store.save(
        LeagueSetupData(
            league_key=profile.league_key,
            budgets=budgets,
            keepers=list(resource_import.keeper_candidates),
            historical_sales=list(resource_import.historical_sales),
            warnings=list(resource_import.warnings),
            metadata={"import_seeded": True},
        )
    )

    parts = []
    for count, noun in (
        (len(budgets), "team budget"),
        (len(resource_import.keeper_candidates), "keeper candidate"),
        (len(resource_import.historical_sales), "historical sale"),
    ):
        if count:
            parts.append("{0} {1}{2}".format(count, noun, "" if count == 1 else "s"))
    return "Also saved " + ", ".join(parts) + " from your spreadsheet."


def render_add_manual_league(
    *,
    registry: LeagueRegistry,
    default_season: int,
    setup_store: LeagueSetupStore,
    selector_state_key: str = "active_league_key",
) -> None:
    """Create and persist a Yahoo/off-platform auction league."""

    prefix = "add_manual_league"
    applied_key = "{0}::applied_signature".format(prefix)
    staged_key = "{0}::staged_import".format(prefix)

    with st.sidebar.expander("➕ Add Yahoo / Manual League", expanded=True):
        st.caption(
            "No Yahoo or Sleeper league connection is required. Sleeper's "
            "global NFL player database is used only as the player universe."
        )

        st.markdown("###### Optional: import from a spreadsheet")
        st.caption(
            "Drop a CSV/XLSX and the fields below are filled in wherever "
            "they can be detected: a Setting/Value table for league rules, "
            "a Team table (Team/Budget/Current columns), a per-manager tab "
            "with a Draft Budget/Salary label, or Type=keeper/history "
            "player rows. Anything not found stays below for you to enter."
        )
        uploaded_files = st.file_uploader(
            "League spreadsheet(s)",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="{0}::workbook".format(prefix),
        )

        staged_import: Optional[LeagueSetupWorkbookImport] = None
        if uploaded_files:
            signature = _upload_signature(uploaded_files)
            try:
                sheets = _read_uploaded_sheets(uploaded_files)
                detected = parse_league_setup_workbook(
                    sheets, current_season=int(default_season)
                )
            except Exception as error:
                st.error("Spreadsheet could not be read: {0}".format(error))
                detected = None

            if detected is not None:
                if st.session_state.get(applied_key) != signature:
                    _apply_detected_league_defaults(prefix, detected)
                    st.session_state[applied_key] = signature
                    st.session_state[staged_key] = detected
                    st.rerun()

                staged_import = st.session_state.get(staged_key)
                detected_labels = []
                missing_labels = []
                for field_name, label in FIELD_LABELS.items():
                    value = getattr(detected, field_name)
                    (detected_labels if value is not None else missing_labels).append(label)
                if detected.team_names:
                    detected_labels.append("Teams ({0})".format(len(detected.team_names)))
                else:
                    missing_labels.append("Teams")
                if detected_labels:
                    st.success("Detected from spreadsheet: " + ", ".join(detected_labels))
                if missing_labels:
                    st.info(
                        "Not found in the spreadsheet -- please fill in below: "
                        + ", ".join(missing_labels)
                    )
                if detected.team_budgets:
                    st.caption(
                        "Found budgets for {0} team(s); saved automatically once "
                        "the league is created.".format(len(detected.team_budgets))
                    )
                _render_import_warnings(detected.warnings)
        elif applied_key in st.session_state:
            # Upload was cleared -- forget the staged import.
            st.session_state.pop(applied_key, None)
            st.session_state.pop(staged_key, None)

        st.divider()

        league_name = st.text_input(
            "League name",
            placeholder="Yahoo Dynasty League",
            key="{0}::name".format(prefix),
        )
        season = int(
            st.number_input(
                "Season",
                min_value=2020,
                max_value=2100,
                value=int(default_season),
                step=1,
                key="{0}::season".format(prefix),
            )
        )
        scoring_label = st.radio(
            "Reception scoring",
            options=["Half PPR", "PPR"],
            horizontal=True,
            key="{0}::scoring".format(prefix),
        )
        team_text = st.text_area(
            "Teams (one per line)",
            placeholder="My Team\nOpponent 1\nOpponent 2",
            help="These labels can be Yahoo team or manager names.",
            key="{0}::teams".format(prefix),
        )
        team_names = [
            line.strip() for line in team_text.splitlines() if line.strip()
        ]
        current_team = st.selectbox(
            "Which team is yours?",
            options=team_names or ["Enter teams above"],
            disabled=not team_names,
            key="{0}::current_team".format(prefix),
        )
        rule_1, rule_2 = st.columns(2)
        roster_size = int(
            rule_1.number_input(
                "Roster size", min_value=1, max_value=100, value=18, step=1,
                key="{0}::roster_size".format(prefix),
            )
        )
        general_budget = int(
            rule_2.number_input(
                "Default budget", min_value=1, max_value=10000, value=200,
                step=1, key="{0}::budget".format(prefix),
                help="Team-specific budgets are entered after creation.",
            )
        )
        rule_3, rule_4 = st.columns(2)
        minimum_bid = int(
            rule_3.number_input(
                "Minimum bid", min_value=1, max_value=1000, value=1, step=1,
                key="{0}::minimum_bid".format(prefix),
            )
        )
        max_keepers = int(
            rule_4.number_input(
                "Maximum keepers", min_value=0, max_value=100, value=0,
                step=1, key="{0}::max_keepers".format(prefix),
            )
        )
        keeper_escalation = int(
            st.number_input(
                "Keeper value increase", min_value=0, max_value=1000,
                value=0, step=1,
                key="{0}::keeper_escalation".format(prefix),
            )
        )

        if st.button(
            "Save Yahoo / Manual League",
            type="primary",
            width="stretch",
            disabled=not league_name.strip() or len(team_names) < 2,
            key="{0}::save".format(prefix),
        ):
            try:
                profile = build_manual_league_profile(
                    league_name=league_name,
                    season=season,
                    team_names=team_names,
                    current_team_name=current_team,
                    scoring_format=(
                        "ppr" if scoring_label == "PPR" else "half_ppr"
                    ),
                    roster_size=roster_size,
                    auction_budget=general_budget,
                    minimum_bid=minimum_bid,
                    max_keepers=max_keepers,
                    keeper_escalation=keeper_escalation,
                )
                if registry.exists(profile.league_key):
                    raise ValueError(
                        "A manual league with this name and season already exists."
                    )
                registry.save(profile)
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.session_state["pending::{0}".format(selector_state_key)] = (
                    profile.league_key
                )
                summary = "Saved {0}.".format(profile.league_name)
                if staged_import is not None:
                    seeded_summary = _seed_setup_from_workbook_import(
                        profile, staged_import, setup_store
                    )
                    if seeded_summary:
                        summary += " " + seeded_summary
                st.session_state.pop(applied_key, None)
                st.session_state.pop(staged_key, None)
                st.success(summary)
                st.rerun()

def render_add_sleeper_league(
    *,
    registry: LeagueRegistry,
    default_season: int,
    current_profile: Optional[
        LeagueProfile
    ] = None,
    default_account: Optional[
        str
    ] = None,
    selector_state_key: str = (
        "active_league_key"
    ),
) -> None:
    """
    Add another Sleeper auction league without editing code.

    The resulting LeagueProfile contains league/draft IDs,
    managers, scoring, roster shape, general budget rules,
    keeper rules, and model weighting. The Step 10
    setup editor then collects any team-specific budgets,
    finalized keepers, or historical sales.
    """

    prefix = "add_sleeper_league"

    if default_account is None:

        default_account = (
            _default_account_from_profile(
                current_profile
            )
        )


    with st.sidebar.expander(
        "➕ Add Sleeper League",
        expanded=False,
    ):

        st.caption(
            "Find a league from a Sleeper account, "
            "choose its draft (auction or snake), and "
            "save it as another LeagueProfile."
        )


        account = st.text_input(
            "Sleeper username or user ID",
            value=(
                default_account
                or ""
            ),
            key=(
                f"{prefix}::account"
            ),
        )


        season = int(
            st.number_input(
                "Season",
                min_value=2020,
                max_value=2100,
                value=int(
                    default_season
                ),
                step=1,
                key=(
                    f"{prefix}::season"
                ),
            )
        )


        find_pressed = st.button(
            "Find My Sleeper Leagues",
            width="stretch",
            key=(
                f"{prefix}::find"
            ),
        )


        if find_pressed:

            if not account.strip():

                st.error(
                    "Enter a Sleeper username "
                    "or user ID."
                )

            else:

                st.session_state[
                    f"{prefix}::lookup"
                ] = {
                    "account": (
                        account.strip()
                    ),
                    "season": (
                        season
                    ),
                }


        lookup = (
            st.session_state.get(
                f"{prefix}::lookup"
            )
        )


        if not lookup:

            return


        try:

            discovered = (
                discover_sleeper_leagues(
                    account=(
                        lookup[
                            "account"
                        ]
                    ),
                    season=int(
                        lookup[
                            "season"
                        ]
                    ),
                )
            )

        except Exception as error:

            st.error(
                f"Sleeper league lookup failed: "
                f"{error}"
            )

            return


        user = (
            discovered[
                "user"
            ]
        )

        leagues = list(
            discovered[
                "leagues"
            ]
        )


        if not leagues:

            st.info(
                "No NFL leagues were found "
                "for that Sleeper account "
                f"in {lookup['season']}."
            )

            return


        st.success(
            f"Found {len(leagues)} league"
            f"{'' if len(leagues) == 1 else 's'} "
            f"for "
            f"{user.get('display_name') or user.get('username') or user.get('user_id')}."
        )


        leagues_by_id = {
            str(
                league.get(
                    "league_id"
                )
            ): league

            for league
            in leagues

            if league.get(
                "league_id"
            )
            is not None
        }


        league_ids = list(
            leagues_by_id.keys()
        )


        selected_league_id = (
            st.selectbox(
                "League to add",
                options=(
                    league_ids
                ),
                format_func=lambda league_id: (
                    _league_label(
                        leagues_by_id[
                            league_id
                        ]
                    )
                ),
                key=(
                    f"{prefix}::league"
                ),
            )
        )


        try:

            bundle = (
                load_sleeper_league_for_setup(
                    selected_league_id
                )
            )

        except Exception as error:

            st.error(
                f"Could not load that league: "
                f"{error}"
            )

            return


        drafts = (
            _sort_drafts(
                bundle[
                    "drafts"
                ]
            )
        )


        if not drafts:

            st.warning(
                "This league does not currently "
                "have a draft available."
            )

            return


        drafts_by_id = {
            str(
                draft.get(
                    "draft_id"
                )
            ): draft

            for draft
            in drafts

            if draft.get(
                "draft_id"
            )
            is not None
        }


        draft_ids = list(
            drafts_by_id.keys()
        )


        selected_draft_id = (
            st.selectbox(
                "Draft",
                options=(
                    draft_ids
                ),
                format_func=lambda draft_id: (
                    _draft_label(
                        drafts_by_id[
                            draft_id
                        ]
                    )
                ),
                key=(
                    f"{prefix}::draft"
                ),
            )
        )


        selected_draft = (
            drafts_by_id[
                selected_draft_id
            ]
        )


        inferred = (
            infer_league_profile_from_sleeper(
                league=(
                    bundle[
                        "league"
                    ]
                ),
                draft=(
                    selected_draft
                ),
                users=(
                    bundle[
                        "users"
                    ]
                ),
                rosters=(
                    bundle[
                        "rosters"
                    ]
                ),
                season=int(
                    lookup[
                        "season"
                    ]
                ),
                my_sleeper_user_id=str(
                    user[
                        "user_id"
                    ]
                ),
            )
        )


        st.divider()

        st.markdown(
            "#### Detected"
        )


        d1, d2 = st.columns(2)


        d1.metric(
            "Scoring",
            _scoring_display(
                inferred
            ),
        )

        d2.metric(
            "Teams",
            len(
                inferred.managers
            ),
        )


        d3, d4 = st.columns(2)


        d3.metric(
            "Roster Size",
            inferred.roster_size,
        )

        d4.metric(
            "Draft Status",
            str(
                selected_draft.get(
                    "status"
                )
                or "-"
            ),
        )


        league_name = st.text_input(
            "League name",
            value=(
                inferred.league_name
            ),
            key=(
                f"{prefix}::name::"
                f"{selected_league_id}"
            ),
        )


        if inferred.draft_format == "snake":

            general_budget = int(inferred.auction.base_budget)
            minimum_bid = int(inferred.minimum_auction_bid)

        else:

            general_budget = int(
                st.number_input(
                    "General auction budget",
                    min_value=1,
                    max_value=10000,
                    value=max(
                        1,
                        int(
                            inferred
                            .auction
                            .base_budget
                        ),
                    ),
                    step=1,
                    help=(
                        "This becomes the default for "
                        "every team. Team-specific "
                        "budgets can be entered in "
                        "Pre-Draft Setup."
                    ),
                    key=(
                        f"{prefix}::budget::"
                        f"{selected_league_id}"
                    ),
                )
            )


            minimum_bid = int(
                st.number_input(
                    "Minimum auction bid",
                    min_value=1,
                    max_value=1000,
                    value=max(
                        1,
                        int(
                            inferred
                            .minimum_auction_bid
                        ),
                    ),
                    step=1,
                    key=(
                        f"{prefix}::min_bid::"
                        f"{selected_league_id}"
                    ),
                )
            )


        st.markdown(
            "#### Keeper Rules"
        )


        keeper_enabled = st.toggle(
            "Keeper league",
            value=(
                inferred
                .keepers
                .enabled
            ),
            key=(
                f"{prefix}::keeper_enabled::"
                f"{selected_league_id}"
            ),
        )


        max_keepers = 0
        keeper_escalation = 11
        keeper_midseason_pickup_cost = 10
        keeper_future_horizon_years = 3


        if keeper_enabled:

            k1, k2 = st.columns(2)


            max_keepers = int(
                k1.number_input(
                    "Maximum keepers",
                    min_value=1,
                    max_value=max(
                        1,
                        inferred.roster_size,
                    ),
                    value=max(
                        1,
                        int(
                            inferred
                            .max_keepers
                            or 1
                        ),
                    ),
                    step=1,
                    key=(
                        f"{prefix}::max_keepers::"
                        f"{selected_league_id}"
                    ),
                )
            )


            escalation_value = int(
                k2.number_input(
                    "Annual keeper escalation",
                    min_value=0,
                    max_value=10000,
                    value=max(
                        0,
                        int(
                            inferred
                            .keepers
                            .escalation
                            or 0
                        ),
                    ),
                    step=1,
                    help=(
                        "Use 0 if this league "
                        "does not increase keeper "
                        "prices each year."
                    ),
                    key=(
                        f"{prefix}::keeper_escalation::"
                        f"{selected_league_id}"
                    ),
                )
            )


            keeper_escalation = escalation_value

            k3, k4 = st.columns(2)

            keeper_midseason_pickup_cost = int(
                k3.number_input(
                    "Mid-season pickup cost",
                    min_value=0,
                    max_value=10000,
                    value=max(
                        0,
                        int(
                            getattr(
                                inferred.keepers,
                                "midseason_pickup_cost",
                                10,
                            )
                        ),
                    ),
                    step=1,
                    key=(
                        f"{prefix}::keeper_pickup_cost::"
                        f"{selected_league_id}"
                    ),
                )
            )

            keeper_future_horizon_years = int(
                k4.selectbox(
                    "Keeper future horizon",
                    options=[2, 3],
                    index=(
                        0
                        if int(
                            getattr(
                                inferred.keepers,
                                "future_horizon_years",
                                3,
                            )
                        ) == 2
                        else 1
                    ),
                    format_func=lambda value: "{0} years".format(value),
                    key=(
                        f"{prefix}::keeper_future_horizon::"
                        f"{selected_league_id}"
                    ),
                )
            )


        st.markdown(
            "#### Valuation Weighting"
        )


        current_weight_percent = int(
            st.slider(
                "Current-season weight",
                min_value=0,
                max_value=100,
                value=int(
                    round(
                        inferred
                        .model
                        .current_season_weight
                        *
                        100
                    )
                ),
                step=5,
                help=(
                    "The remaining weight is "
                    "future/dynasty value."
                ),
                key=(
                    f"{prefix}::current_weight::"
                    f"{selected_league_id}"
                ),
            )
        )


        future_weight_percent = (
            100
            -
            current_weight_percent
        )


        st.caption(
            f"Current: {current_weight_percent}% • "
            f"Future: {future_weight_percent}%"
        )


        existing = registry.exists(
            str(
                selected_league_id
            )
        )


        overwrite = False


        if existing:

            st.warning(
                "This Sleeper league is already "
                "registered."
            )

            overwrite = st.checkbox(
                "Replace the existing LeagueProfile",
                value=False,
                key=(
                    f"{prefix}::overwrite::"
                    f"{selected_league_id}"
                ),
            )


        can_save = (
            not existing
            or overwrite
        )


        if st.button(
            (
                "Add League"
                if not existing
                else "Update League"
            ),
            type="primary",
            width="stretch",
            disabled=(
                not can_save
            ),
            key=(
                f"{prefix}::save::"
                f"{selected_league_id}"
            ),
        ):

            profile = (
                infer_league_profile_from_sleeper(
                    league=(
                        bundle[
                            "league"
                        ]
                    ),
                    draft=(
                        selected_draft
                    ),
                    users=(
                        bundle[
                            "users"
                        ]
                    ),
                    rosters=(
                        bundle[
                            "rosters"
                        ]
                    ),
                    season=int(
                        lookup[
                            "season"
                        ]
                    ),
                    my_sleeper_user_id=str(
                        user[
                            "user_id"
                        ]
                    ),
                    overrides={
                        "league_key": str(
                            selected_league_id
                        ),
                        "league_name": (
                            league_name.strip()
                            or inferred.league_name
                        ),
                        "auction": {
                            "base_budget": (
                                general_budget
                            ),
                            "minimum_bid": (
                                minimum_bid
                            ),
                            "roster_spots": (
                                inferred
                                .roster_size
                            ),
                        },
                        "keepers": {
                            "enabled": (
                                keeper_enabled
                            ),
                            "max_keepers": (
                                max_keepers
                                if keeper_enabled
                                else 0
                            ),
                            "escalation": (
                                keeper_escalation
                            ),
                            "midseason_pickup_cost": (
                                keeper_midseason_pickup_cost
                            ),
                            "future_horizon_years": (
                                keeper_future_horizon_years
                            ),
                        },
                        "model": {
                            "current_season_weight": (
                                current_weight_percent
                                /
                                100.0
                            ),
                            "future_value_weight": (
                                future_weight_percent
                                /
                                100.0
                            ),
                        },
                        "metadata": {
                            "added_via_ui": True,
                            "sleeper_account": (
                                lookup[
                                    "account"
                                ]
                            ),
                            "my_sleeper_user_id": str(
                                user[
                                    "user_id"
                                ]
                            ),
                        },
                    },
                )
            )


            registry.save(
                profile
            )


            st.session_state[
                "pending::{0}".format(selector_state_key)
            ] = (
                profile.league_key
            )


            st.session_state[
                f"{prefix}::lookup"
            ] = {
                "account": (
                    lookup[
                        "account"
                    ]
                ),
                "season": (
                    int(
                        lookup[
                            "season"
                        ]
                    )
                ),
            }


            st.success(
                f"Added {profile.league_name}."
            )

            st.rerun()
