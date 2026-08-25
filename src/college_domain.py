from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, List, Sequence, Tuple

from src.auction_pool import normalize_player_name


COLLEGE_STAGE_IN_COLLEGE = "in_college"
COLLEGE_STAGE_IN_NFL = "in_nfl"
COLLEGE_STAGE_UNKNOWN = "unknown"
VALID_COLLEGE_STAGES = (
    COLLEGE_STAGE_IN_COLLEGE,
    COLLEGE_STAGE_IN_NFL,
    COLLEGE_STAGE_UNKNOWN,
)

COLLEGE_ELIGIBILITY_ELIGIBLE = "eligible"
COLLEGE_ELIGIBILITY_INELIGIBLE = "ineligible"
COLLEGE_ELIGIBILITY_UNKNOWN = "unknown"
VALID_COLLEGE_ELIGIBILITY = (
    COLLEGE_ELIGIBILITY_ELIGIBLE,
    COLLEGE_ELIGIBILITY_INELIGIBLE,
    COLLEGE_ELIGIBILITY_UNKNOWN,
)

COLLEGE_PROMOTION_TAXI = "taxi"
COLLEGE_PROMOTION_PROMOTED = "promoted"
VALID_COLLEGE_PROMOTION_STATUSES = (
    COLLEGE_PROMOTION_TAXI,
    COLLEGE_PROMOTION_PROMOTED,
)

VALID_ELIGIBILITY_SOURCES = (
    "manual",
    "workbook",
    "import",
)


@dataclass(frozen=True)
class CollegeDomainRules:
    enabled: bool
    max_college_players: int
    draft_rounds: int
    eligibility_source: str
    college_pick_trading_enabled: bool
    pre_draft_promotion_cost: int
    during_draft_promotion_cost: int

    @classmethod
    def from_league_profile(cls, league_profile: Any) -> "CollegeDomainRules":
        college = league_profile.college
        rules = cls(
            enabled=bool(getattr(college, "enabled", False)),
            max_college_players=int(
                getattr(college, "max_college_players", 0) or 0
            ),
            draft_rounds=int(getattr(college, "draft_rounds", 0) or 0),
            eligibility_source=str(
                getattr(college, "eligibility_source", "manual") or "manual"
            ),
            college_pick_trading_enabled=bool(
                getattr(college, "college_pick_trading_enabled", True)
            ),
            pre_draft_promotion_cost=int(
                getattr(college, "pre_draft_promotion_cost", 0) or 0
            ),
            during_draft_promotion_cost=int(
                getattr(college, "during_draft_promotion_cost", 0) or 0
            ),
        )
        rules.validate()
        return rules

    def validate(self) -> None:
        if self.max_college_players < 0:
            raise ValueError("Maximum college/devy players cannot be negative.")
        if self.enabled and self.max_college_players == 0:
            raise ValueError(
                "Enabled college/devy leagues require a positive player capacity."
            )
        if self.draft_rounds < 0:
            raise ValueError("College draft rounds cannot be negative.")
        if self.eligibility_source not in VALID_ELIGIBILITY_SOURCES:
            raise ValueError(
                "Unknown college eligibility source: {0}".format(
                    self.eligibility_source
                )
            )
        if self.pre_draft_promotion_cost < 0:
            raise ValueError("Pre-draft promotion cost cannot be negative.")
        if self.during_draft_promotion_cost < 0:
            raise ValueError("During-draft promotion cost cannot be negative.")


@dataclass(frozen=True)
class CollegeStartupResult:
    setup_data: Any
    validation_error: str = ""


def apply_college_rules_for_startup(
    *,
    league_profile: Any,
    setup_data: Any,
) -> CollegeStartupResult:
    """Preserve unresolved rights at startup so Pre-Draft can repair them."""

    try:
        normalized = apply_college_rules(
            league_profile=league_profile,
            setup_data=setup_data,
        )
        return CollegeStartupResult(setup_data=normalized)
    except ValueError as error:
        message = str(error)
        warnings = list(setup_data.warnings)
        warnings.append(
            "College/devy setup needs Pre-Draft review: {0}".format(message)
        )
        return CollegeStartupResult(
            setup_data=replace(setup_data, warnings=warnings),
            validation_error=message,
        )


def _validate_right(right: Any, manager_ids: Sequence[str]) -> None:
    if not str(right.manager_id):
        raise ValueError("College rights require a current owner.")
    if manager_ids and right.manager_id not in manager_ids:
        raise ValueError(
            "Unknown college-right owner: {0}".format(right.manager_id)
        )
    if not normalize_player_name(right.player_name):
        raise ValueError("College rights require a player name.")
    if right.status not in VALID_COLLEGE_STAGES:
        raise ValueError("Unknown college player stage: {0}".format(right.status))
    if right.eligibility_status not in VALID_COLLEGE_ELIGIBILITY:
        raise ValueError(
            "Unknown college eligibility status: {0}".format(
                right.eligibility_status
            )
        )
    if right.promotion_status not in VALID_COLLEGE_PROMOTION_STATUSES:
        raise ValueError(
            "Unknown college promotion status: {0}".format(
                right.promotion_status
            )
        )
    if (
        right.promotion_status == COLLEGE_PROMOTION_PROMOTED
        and right.eligibility_status == COLLEGE_ELIGIBILITY_INELIGIBLE
    ):
        raise ValueError(
            "An explicitly ineligible college player cannot be marked promoted."
        )
    original_manager_id = right.original_manager_id or right.manager_id
    if manager_ids and original_manager_id not in manager_ids:
        raise ValueError(
            "Unknown original college-right owner: {0}".format(
                original_manager_id
            )
        )


def _validate_pick(
    pick: Any,
    rules: CollegeDomainRules,
    manager_ids: Sequence[str],
) -> None:
    if int(pick.season) <= 0:
        raise ValueError("College picks require a positive season.")
    if int(pick.round_number) <= 0:
        raise ValueError("College picks require a positive round number.")
    if rules.draft_rounds and int(pick.round_number) > rules.draft_rounds:
        raise ValueError(
            "College pick round {0} exceeds the configured {1} rounds.".format(
                pick.round_number,
                rules.draft_rounds,
            )
        )
    if int(pick.pick_number or 0) < 0:
        raise ValueError("College pick number cannot be negative.")
    if manager_ids and pick.manager_id not in manager_ids:
        raise ValueError("Unknown college-pick owner: {0}".format(pick.manager_id))
    if manager_ids and pick.original_manager_id not in manager_ids:
        raise ValueError(
            "Unknown original college-pick owner: {0}".format(
                pick.original_manager_id
            )
        )
    if pick.is_traded and not rules.college_pick_trading_enabled:
        raise ValueError("Traded college picks are disabled for this league.")


def apply_college_rules(
    *,
    league_profile: Any,
    setup_data: Any,
) -> Any:
    """Apply optional devy rules and validate normalized rights and picks."""

    rules = CollegeDomainRules.from_league_profile(league_profile)
    if not rules.enabled:
        removed_count = (
            len(setup_data.college_players)
            + len(getattr(setup_data, "college_picks", ()))
            + len(setup_data.college_thresholds)
        )
        warnings = list(setup_data.warnings)
        if removed_count:
            warnings.append(
                "College/devy is disabled; ignored {0} stale college record(s)."
                .format(removed_count)
            )
        return replace(
            setup_data,
            college_players=[],
            college_picks=[],
            college_thresholds=[],
            warnings=warnings,
        )

    manager_ids = tuple(getattr(league_profile, "managers", {}).keys())
    owner_counts = Counter()
    right_names = set()
    for right in setup_data.college_players:
        _validate_right(right, manager_ids)
        normalized_name = normalize_player_name(right.player_name)
        if normalized_name in right_names:
            raise ValueError(
                "A college right cannot be owned by multiple managers: {0}."
                .format(right.player_name)
            )
        right_names.add(normalized_name)
        if right.promotion_status != COLLEGE_PROMOTION_PROMOTED:
            owner_counts[right.manager_id] += 1

    for manager_id, count in owner_counts.items():
        if count > rules.max_college_players:
            raise ValueError(
                "{0} owns {1} active college rights; maximum is {2}.".format(
                    manager_id,
                    count,
                    rules.max_college_players,
                )
            )

    pick_ids = set()
    for pick in getattr(setup_data, "college_picks", ()):
        _validate_pick(pick, rules, manager_ids)
        identity = pick.identity
        if identity in pick_ids:
            raise ValueError("Duplicate college draft pick: {0}.".format(identity))
        pick_ids.add(identity)

    return setup_data


def validate_college_promotions(
    *,
    league_profile: Any,
    setup_data: Any,
    manager_id: str,
    promotion_names: Sequence[str],
) -> Tuple[Any, ...]:
    """Resolve legal promotions without recommending whether to promote."""

    rules = CollegeDomainRules.from_league_profile(league_profile)
    if not promotion_names:
        return ()
    if not rules.enabled:
        raise ValueError("College promotions are disabled for this league.")

    owned_rights = {
        normalize_player_name(right.player_name): right
        for right in setup_data.college_for(manager_id)
    }
    resolved: List[Any] = []
    seen = set()
    for player_name in promotion_names:
        normalized_name = normalize_player_name(player_name)
        if normalized_name in seen:
            raise ValueError("College promotions must be unique.")
        seen.add(normalized_name)
        right = owned_rights.get(normalized_name)
        if right is None:
            raise ValueError(
                "{0} is not a college right owned by {1}.".format(
                    player_name,
                    manager_id,
                )
            )
        if right.eligibility_status == COLLEGE_ELIGIBILITY_INELIGIBLE:
            raise ValueError(
                "{0} is explicitly ineligible for promotion.".format(
                    right.player_name
                )
            )
        if right.promotion_status == COLLEGE_PROMOTION_PROMOTED:
            raise ValueError(
                "{0} is already marked promoted.".format(right.player_name)
            )
        resolved.append(right)
    return tuple(resolved)
