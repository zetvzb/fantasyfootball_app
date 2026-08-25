from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import streamlit as st

from src.league_profile import (
    LeagueProfile,
    infer_league_profile_from_sleeper,
)
from src.league_registry import LeagueRegistry
from src.manual_league import build_manual_league_profile
from src.sleeper_client import SleeperClient


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

def render_add_manual_league(
    *,
    registry: LeagueRegistry,
    default_season: int,
    selector_state_key: str = "active_league_key",
) -> None:
    """Create and persist a Yahoo/off-platform auction league."""

    prefix = "add_manual_league"
    with st.sidebar.expander("➕ Add Yahoo / Manual League", expanded=True):
        st.caption(
            "No Yahoo or Sleeper league connection is required. Sleeper's "
            "global NFL player database is used only as the player universe."
        )
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
        rule_5, rule_6 = st.columns(2)
        keeper_escalation = int(
            rule_5.number_input(
                "Keeper value increase", min_value=0, max_value=1000,
                value=0, step=1,
                key="{0}::keeper_escalation".format(prefix),
            )
        )
        max_devy = int(
            rule_6.number_input(
                "Maximum devy players", min_value=0, max_value=100, value=0,
                step=1, key="{0}::max_devy".format(prefix),
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
                    max_devy_players=max_devy,
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
                st.success("Saved {0}.".format(profile.league_name))
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
    keeper/college rules, and model weighting. The Step 10
    setup editor then collects any team-specific budgets,
    finalized keepers, devy rights, or historical sales.
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
            "choose its auction draft, and save it "
            "as another LeagueProfile."
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


        auction_drafts = [
            draft

            for draft
            in drafts

            if str(
                draft.get(
                    "type"
                )
                or ""
            ).lower()
            == "auction"
        ]


        if not auction_drafts:

            st.warning(
                "This league does not currently "
                "have an auction draft available. "
                "The Auction Copilot only supports "
                "auction drafts right now."
            )

            return


        drafts_by_id = {
            str(
                draft.get(
                    "draft_id"
                )
            ): draft

            for draft
            in auction_drafts

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
                "Auction draft",
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
            "#### Keeper / College Rules"
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


        college_enabled = st.toggle(
            "College / devy rights",
            value=(
                inferred
                .college
                .enabled
            ),
            key=(
                f"{prefix}::college_enabled::"
                f"{selected_league_id}"
            ),
        )


        max_college_players = 0
        college_draft_rounds = 0
        college_eligibility_source = "manual"
        college_pick_trading_enabled = False


        if college_enabled:

            college_c1, college_c2 = st.columns(2)
            max_college_players = int(
                college_c1.number_input(
                    "Maximum college / devy players",
                    min_value=1,
                    max_value=100,
                    value=max(
                        1,
                        int(
                            inferred
                            .college
                            .max_college_players
                            or 1
                        ),
                    ),
                    step=1,
                    key=(
                        f"{prefix}::max_college::"
                        f"{selected_league_id}"
                    ),
                )
            )
            college_draft_rounds = int(
                college_c2.number_input(
                    "College draft rounds",
                    min_value=0,
                    max_value=100,
                    value=int(
                        getattr(inferred.college, "draft_rounds", 0) or 0
                    ),
                    step=1,
                    help="The app records pick assets but does not run this draft.",
                    key=(
                        f"{prefix}::college_rounds::"
                        f"{selected_league_id}"
                    ),
                )
            )
            college_c3, college_c4 = st.columns(2)
            eligibility_options = ["manual", "workbook", "import"]
            inferred_eligibility_source = str(
                getattr(inferred.college, "eligibility_source", "manual")
                or "manual"
            )
            if inferred_eligibility_source not in eligibility_options:
                inferred_eligibility_source = "manual"
            college_eligibility_source = college_c3.selectbox(
                "Eligibility source",
                options=eligibility_options,
                index=eligibility_options.index(inferred_eligibility_source),
                key=(
                    f"{prefix}::college_eligibility_source::"
                    f"{selected_league_id}"
                ),
            )
            college_pick_trading_enabled = college_c4.toggle(
                "College picks may be traded",
                value=bool(
                    getattr(
                        inferred.college,
                        "college_pick_trading_enabled",
                        True,
                    )
                ),
                key=(
                    f"{prefix}::college_pick_trading::"
                    f"{selected_league_id}"
                ),
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
                        "college": {
                            "enabled": (
                                college_enabled
                            ),
                            "max_college_players": (
                                max_college_players
                                if college_enabled
                                else 0
                            ),
                            "draft_rounds": (
                                college_draft_rounds
                                if college_enabled
                                else 0
                            ),
                            "eligibility_source": (
                                college_eligibility_source
                            ),
                            "college_pick_trading_enabled": (
                                college_pick_trading_enabled
                                if college_enabled
                                else False
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
                selector_state_key
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
