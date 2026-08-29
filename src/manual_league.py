from __future__ import annotations

from typing import Iterable, Optional

from src.league_profile import (
    AuctionRules,
    KeeperRules,
    LeagueProfile,
    ManagerIdentity,
    ModelRules,
    RosterRules,
    ScoringRules,
)
from src.league_setup_data import LeagueSetupData, normalize_player_name
from src.projections import STANDARD_SCORING_DEFAULTS


def slugify(value: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "_"
        for character in str(value).strip()
    )
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "league"


def build_manual_league_profile(
    *,
    league_name: str,
    season: int,
    team_names: Iterable[str],
    current_team_name: str,
    scoring_format: str,
    roster_size: int,
    auction_budget: int,
    minimum_bid: int,
    max_keepers: int,
    keeper_escalation: int,
    league_key: Optional[str] = None,
) -> LeagueProfile:
    """Build a persistent off-platform league from its minimum inputs."""

    name = str(league_name).strip()
    if not name:
        raise ValueError("League name is required.")
    cleaned_teams = []
    for team_name in team_names:
        cleaned = str(team_name).strip()
        if cleaned and cleaned not in cleaned_teams:
            cleaned_teams.append(cleaned)
    if len(cleaned_teams) < 2:
        raise ValueError("Manual leagues require at least two teams.")
    if current_team_name not in cleaned_teams:
        raise ValueError("Current team must be one of the configured teams.")
    if scoring_format not in {"ppr", "half_ppr"}:
        raise ValueError("Scoring format must be PPR or Half PPR.")
    if int(roster_size) <= 0:
        raise ValueError("Roster size must be positive.")
    if int(auction_budget) <= 0 or int(minimum_bid) <= 0:
        raise ValueError("Auction budget and minimum bid must be positive.")
    if int(max_keepers) < 0:
        raise ValueError("Keeper limit cannot be negative.")

    managers = {}
    manager_id_by_name = {}
    for team_name in cleaned_teams:
        base = slugify(team_name)
        manager_id = base
        suffix = 2
        while manager_id in managers:
            manager_id = "{0}_{1}".format(base, suffix)
            suffix += 1
        manager_id_by_name[team_name] = manager_id
        managers[manager_id] = ManagerIdentity(
            manager_id=manager_id,
            sleeper_team_name=team_name,
            historical_aliases=(team_name,),
        )

    reception_points = 1.0 if scoring_format == "ppr" else 0.5
    starters = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF")
    starting_lineup = starters[:min(len(starters), int(roster_size))]
    return LeagueProfile(
        league_key=str(
            league_key or "manual_{0}_{1}".format(slugify(name), int(season))
        ),
        league_name=name,
        season=int(season),
        source_mode="manual",
        scoring=ScoringRules(
            reception_points=reception_points,
            format_label=scoring_format,
            raw={
                **STANDARD_SCORING_DEFAULTS,
                "rec": reception_points,
            },
        ),
        roster=RosterRules(
            roster_size=int(roster_size),
            starting_lineup=starting_lineup,
            bench_slots=max(0, int(roster_size) - len(starting_lineup)),
        ),
        auction=AuctionRules(
            base_budget=int(auction_budget),
            minimum_bid=int(minimum_bid),
            roster_spots=int(roster_size),
        ),
        keepers=KeeperRules(
            enabled=int(max_keepers) > 0,
            max_keepers=int(max_keepers),
            escalation=int(keeper_escalation),
            midseason_pickup_cost=10,
            future_horizon_years=3,
        ),
        model=ModelRules(current_season_weight=0.60, future_value_weight=0.40),
        managers=managers,
        metadata={
            "platform": "yahoo_or_manual",
            "manual_draft": True,
            "current_manager_id": manager_id_by_name[current_team_name],
            "uses_sleeper_player_universe": True,
        },
    )


def manual_runtime_ids(profile: LeagueProfile) -> tuple[str, str]:
    return (
        "manual::{0}".format(profile.league_key),
        "manual::{0}::{1}".format(profile.league_key, profile.season),
    )


def permitted_setup_overrides(
    profile: LeagueProfile,
    setup_data: LeagueSetupData,
    baseline: Optional[LeagueSetupData] = None,
) -> LeagueSetupData:
    """Keep protected-player entry manual only for off-platform leagues.

    Sleeper-backed leagues may still override team budgets and import auction
    history. Keeper *ownership* stays source-driven -- Sleeper decides who is
    kept -- but the manual setup may attach an explicit keeper cost to a
    player Sleeper already flags as a keeper (Sleeper does not carry keeper
    salaries).

    A manual keeper record is permitted when either:
      * it matches a player the current Sleeper roster keeps (a cost overlay
        on a source-driven keeper), or
      * it matches a player currently on that team's Sleeper roster (the team
        set some keepers on Sleeper but not this one -- e.g. Sleeper's keeper
        list is incomplete -- yet the player is still rostered), or
      * the manager has no Sleeper keepers at all (that team never set
        keepers on Sleeper, so manual entry is the only way in).

    A finalized manual keeper for a player that is no longer on the team's
    Sleeper roster is dropped (so a stale selection can never override a
    refreshed roster) and a warning is recorded so the drop is visible rather
    than silent.
    """

    if profile.source_mode != "sleeper":
        return setup_data

    warnings = list(setup_data.warnings)

    if baseline is None:
        # Nothing to validate the manual keepers against -- stay
        # conservative and drop them all rather than trust a possibly
        # stale selection.
        permitted_keepers = []
        dropped_keepers = list(setup_data.keepers)
    else:
        sleeper_keeper_keys = {
            (record.manager_id, normalize_player_name(record.player_name))
            for record in baseline.keepers
        }
        managers_with_sleeper_keepers = {
            record.manager_id for record in baseline.keepers
        }
        roster_player_keys = {
            (record.manager_id, normalize_player_name(record.player_name))
            for record in baseline.roster_players
        }
        permitted_keepers = []
        dropped_keepers = []
        for record in setup_data.keepers:
            key = (
                record.manager_id,
                normalize_player_name(record.player_name),
            )
            if (
                record.manager_id not in managers_with_sleeper_keepers
                or key in sleeper_keeper_keys
                or key in roster_player_keys
            ):
                permitted_keepers.append(record)
            else:
                dropped_keepers.append(record)

    for record in dropped_keepers:
        if record.status != "finalized":
            continue
        warnings.append(
            "Keeper '{0}' ({1}) was dropped from auction setup: that player is "
            "not on the team's current Sleeper roster. Re-pull roster changes, "
            "or update the keeper in League Setup Data -> Keepers.".format(
                record.player_name,
                record.manager_id,
            )
        )

    metadata = dict(setup_data.metadata)
    metadata["keepers_configured"] = bool(permitted_keepers)
    return LeagueSetupData(
        league_key=setup_data.league_key,
        budgets=dict(setup_data.budgets),
        keepers=permitted_keepers,
        historical_sales=list(setup_data.historical_sales),
        warnings=warnings,
        metadata=metadata,
        unavailable_players=list(setup_data.unavailable_players),
    )
