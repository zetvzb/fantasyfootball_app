from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple


class ReadinessStatus(str, Enum):
    READY = "READY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ReadinessCheck:
    key: str
    label: str
    status: ReadinessStatus
    summary: str
    detail: str


@dataclass(frozen=True)
class PreDraftReadiness:
    ready_for_draft: bool
    checks: Tuple[ReadinessCheck, ...]
    blocking_reasons: Tuple[str, ...]
    warning_reasons: Tuple[str, ...]

    def check(self, key: str) -> ReadinessCheck:
        for check in self.checks:
            if check.key == key:
                return check
        raise KeyError(key)


def _check(
    key: str,
    label: str,
    status: ReadinessStatus,
    summary: str,
    detail: str,
) -> ReadinessCheck:
    return ReadinessCheck(
        key=key,
        label=label,
        status=status,
        summary=summary,
        detail=detail,
    )


def build_pre_draft_readiness(
    *,
    league_profile: Any,
    league_setup_data: Any,
    team_setups: Mapping[str, Any],
    persisted_setup: Mapping[str, Any],
    sleeper_player_count: int,
    projection_count: int,
    setup_source_summary: Mapping[str, int],
    workbook_loaded: bool,
    data_as_of: Optional[str] = None,
) -> PreDraftReadiness:
    """Summarize whether core auction inputs are usable before draft mode."""

    managers = tuple(league_profile.managers.keys())
    checks = []

    scoring_label = str(league_profile.scoring_label or "custom")
    checks.append(
        _check(
            "scoring",
            "Scoring",
            ReadinessStatus.READY,
            scoring_label.upper(),
            "League scoring is loaded; {0} custom numeric rule(s).".format(
                len(league_profile.scoring.raw)
            ),
        )
    )

    roster_size = int(league_profile.roster.roster_size)
    starting_slots = tuple(league_profile.roster.starting_lineup)
    roster_valid = roster_size > 0 and len(starting_slots) <= roster_size
    checks.append(
        _check(
            "roster",
            "Roster Rules",
            ReadinessStatus.READY if roster_valid else ReadinessStatus.BLOCKED,
            "{0} roster spots / {1} starters".format(
                roster_size,
                len(starting_slots),
            ),
            (
                "Roster capacity can support the configured starting lineup."
                if roster_valid
                else "Roster size must be positive and at least the starting-slot count."
            ),
        )
    )

    budget_ids = set(league_setup_data.budgets)
    setup_ids = set(team_setups)
    missing_budget_ids = [manager_id for manager_id in managers if manager_id not in budget_ids]
    missing_setup_ids = [manager_id for manager_id in managers if manager_id not in setup_ids]
    budgets_ready = not missing_budget_ids and not missing_setup_ids and bool(managers)
    budget_detail_parts = []
    if missing_budget_ids:
        budget_detail_parts.append(
            "Missing budgets: {0}.".format(
                ", ".join(missing_budget_ids)
            )
        )
    if missing_setup_ids:
        budget_detail_parts.append(
            "Invalid or missing team setup: {0}.".format(
                ", ".join(missing_setup_ids)
            )
        )
    checks.append(
        _check(
            "budgets",
            "Team Budgets",
            ReadinessStatus.READY if budgets_ready else ReadinessStatus.BLOCKED,
            "{0}/{1} teams resolved".format(len(setup_ids), len(managers)),
            " ".join(budget_detail_parts)
            if budget_detail_parts
            else "Every team has a legal entering budget and reserve-aware setup.",
        )
    )

    keeper_rules = league_profile.keepers
    finalized_by_manager = {
        manager_id: len(
            league_setup_data.keepers_for(manager_id, finalized_only=True)
        )
        for manager_id in managers
    }
    keeper_decisions_saved = bool(
        league_setup_data.metadata.get("keepers_configured", False)
    ) or any(
        bool((persisted_setup.get(manager_id, {}) or {}).get("keepers", []))
        for manager_id in managers
    )
    if not keeper_rules.enabled:
        keeper_status = ReadinessStatus.READY
        keeper_summary = "Disabled"
        keeper_detail = "This league has no keeper system."
    elif keeper_decisions_saved or any(finalized_by_manager.values()):
        keeper_status = ReadinessStatus.READY
        keeper_summary = "{0} finalized".format(sum(finalized_by_manager.values()))
        keeper_detail = "Keeper decisions are represented in the auction setup."
    else:
        keeper_status = ReadinessStatus.WARNING
        keeper_summary = "Not confirmed"
        keeper_detail = (
            "No finalized keeper decisions are recorded; zero keepers remains legal, "
            "but confirm this is intentional."
        )
    checks.append(
        _check("keepers", "Keeper Readiness", keeper_status, keeper_summary, keeper_detail)
    )

    college_rules = league_profile.college
    if not college_rules.enabled:
        devy_status = ReadinessStatus.READY
        devy_summary = "Disabled"
        devy_detail = "No college/devy setup is required for this league."
    else:
        active_rights = [
            right
            for right in league_setup_data.college_players
            if right.promotion_status != "promoted"
        ]
        unknown_eligibility = sum(
            1 for right in active_rights if right.eligibility_status == "unknown"
        )
        capacity_valid = all(
            sum(1 for right in active_rights if right.manager_id == manager_id)
            <= int(college_rules.max_college_players)
            for manager_id in managers
        )
        if not capacity_valid:
            devy_status = ReadinessStatus.BLOCKED
            devy_detail = "At least one manager exceeds the college-roster capacity."
        elif unknown_eligibility:
            devy_status = ReadinessStatus.WARNING
            devy_detail = "{0} right(s) have unknown promotion eligibility.".format(
                unknown_eligibility
            )
        else:
            devy_status = ReadinessStatus.READY
            devy_detail = "College rights and promotion eligibility are resolved."
        devy_summary = "{0} active rights".format(len(active_rights))
    checks.append(
        _check("devy", "College / Devy", devy_status, devy_summary, devy_detail)
    )

    source_names = sorted(
        source for source, count in setup_source_summary.items() if count > 0
    )
    source_text = ", ".join(source_names) if source_names else "defaults"
    data_loaded = sleeper_player_count > 0
    if not data_loaded:
        freshness_status = ReadinessStatus.BLOCKED
        freshness_detail = "Sleeper player data is unavailable."
    elif projection_count == 0:
        freshness_status = ReadinessStatus.WARNING
        freshness_detail = (
            "Sleeper data is loaded, but current projection data is unavailable."
        )
    else:
        freshness_status = ReadinessStatus.READY
        freshness_detail = "Sleeper and projection data are loaded for this session."
    if data_as_of:
        freshness_detail += " As of {0}.".format(data_as_of)
    checks.append(
        _check(
            "freshness",
            "Data Freshness",
            freshness_status,
            "{0} players / {1} projections".format(
                sleeper_player_count,
                projection_count,
            ),
            freshness_detail,
        )
    )

    history_count = len(league_setup_data.historical_sales)
    checks.append(
        _check(
            "history",
            "Auction History",
            ReadinessStatus.READY if history_count else ReadinessStatus.WARNING,
            "{0} historical sales".format(history_count),
            (
                "Historical market calibration is available."
                if history_count
                else "History is optional; recommendations will run without market calibration."
            ),
        )
    )

    checks.append(
        _check(
            "sources",
            "Setup Sources",
            ReadinessStatus.READY,
            source_text,
            "Workbook enrichment is {0}; source priority remains manual/import, "
            "workbook, Sleeper, then defaults.".format(
                "active" if workbook_loaded else "optional and inactive"
            ),
        )
    )

    blocking = tuple(
        check.detail for check in checks if check.status is ReadinessStatus.BLOCKED
    )
    warnings = tuple(
        check.detail for check in checks if check.status is ReadinessStatus.WARNING
    )
    return PreDraftReadiness(
        ready_for_draft=not blocking,
        checks=tuple(checks),
        blocking_reasons=blocking,
        warning_reasons=warnings,
    )
