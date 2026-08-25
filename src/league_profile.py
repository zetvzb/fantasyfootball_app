from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ManagerIdentity:
    manager_id: str
    sleeper_user_id: Optional[str] = None
    sleeper_roster_id: Optional[int] = None
    sleeper_username: Optional[str] = None
    sleeper_team_name: Optional[str] = None
    historical_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoringRules:
    reception_points: float = 0.0
    format_label: str = "standard"
    raw: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_sleeper(cls, scoring_settings: Optional[dict]) -> "ScoringRules":
        scoring_settings = scoring_settings or {}
        reception_points = float(scoring_settings.get("rec", 0) or 0)

        if abs(reception_points - 1.0) < 1e-9:
            label = "ppr"
        elif abs(reception_points - 0.5) < 1e-9:
            label = "half_ppr"
        elif abs(reception_points) < 1e-9:
            label = "standard"
        else:
            label = "custom"

        numeric = {}
        for key, value in scoring_settings.items():
            if isinstance(value, (int, float)):
                numeric[str(key)] = float(value)

        return cls(
            reception_points=reception_points,
            format_label=label,
            raw=numeric,
        )


@dataclass(frozen=True)
class RosterRules:
    roster_size: int
    starting_lineup: tuple[str, ...] = ()
    bench_slots: int = 0
    ir_slots: int = 0
    taxi_slots: int = 0


@dataclass(frozen=True)
class AuctionRules:
    base_budget: int = 200
    minimum_bid: int = 1
    roster_spots: Optional[int] = None


@dataclass(frozen=True)
class KeeperRules:
    enabled: bool = False
    max_keepers: int = 0
    escalation: Optional[int] = 11
    midseason_pickup_cost: int = 10
    future_horizon_years: int = 3
    lock_hours_before_draft: Optional[int] = None


@dataclass(frozen=True)
class CollegeRules:
    enabled: bool = False
    max_college_players: int = 0
    draft_rounds: int = 0
    eligibility_source: str = "manual"
    college_pick_trading_enabled: bool = True
    pre_draft_promotion_cost: int = 0
    during_draft_promotion_cost: int = 0
    next_year_keeper_cost: Optional[int] = None
    lock_hours_before_draft: Optional[int] = None
    pro_thresholds: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelRules:
    current_season_weight: float = 1.0
    future_value_weight: float = 0.0


@dataclass(frozen=True)
class LeagueProfile:
    league_key: str
    league_name: str
    season: int
    source_mode: str
    sleeper_league_id: Optional[str] = None
    sleeper_draft_id: Optional[str] = None
    scoring: ScoringRules = field(default_factory=ScoringRules)
    roster: RosterRules = field(default_factory=lambda: RosterRules(roster_size=16))
    auction: AuctionRules = field(default_factory=AuctionRules)
    keepers: KeeperRules = field(default_factory=KeeperRules)
    college: CollegeRules = field(default_factory=CollegeRules)
    model: ModelRules = field(default_factory=ModelRules)
    managers: Dict[str, ManagerIdentity] = field(default_factory=dict)
    historical_draft_sheets: Dict[int, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def scoring_label(self) -> str:
        return self.scoring.format_label

    @property
    def minimum_auction_bid(self) -> int:
        return self.auction.minimum_bid

    @property
    def roster_size(self) -> int:
        return self.roster.roster_size

    @property
    def max_keepers(self) -> int:
        return self.keepers.max_keepers

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "LeagueProfile":
        managers = {
            manager_id: ManagerIdentity(**manager_data)
            for manager_id, manager_data in (payload.get("managers") or {}).items()
        }

        return cls(
            league_key=payload["league_key"],
            league_name=payload["league_name"],
            season=int(payload["season"]),
            source_mode=payload.get("source_mode", "manual"),
            sleeper_league_id=payload.get("sleeper_league_id"),
            sleeper_draft_id=payload.get("sleeper_draft_id"),
            scoring=ScoringRules(**(payload.get("scoring") or {})),
            roster=RosterRules(**payload["roster"]),
            auction=AuctionRules(**(payload.get("auction") or {})),
            keepers=KeeperRules(**(payload.get("keepers") or {})),
            college=CollegeRules(**(payload.get("college") or {})),
            model=ModelRules(**(payload.get("model") or {})),
            managers=managers,
            historical_draft_sheets={
                int(year): name
                for year, name in (payload.get("historical_draft_sheets") or {}).items()
            },
            metadata=payload.get("metadata") or {},
        )


def _slug(value: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "_"
        for character in value.strip()
    )
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "league"


def _extract_budget(draft: Optional[dict]) -> int:
    draft = draft or {}
    settings = draft.get("settings") or {}
    metadata = draft.get("metadata") or {}

    for source in (settings, metadata, draft):
        for key in (
            "budget",
            "auction_budget",
            "draft_budget",
            "salary_cap",
        ):
            value = source.get(key)
            if value is None:
                continue
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue

    return 200


def _infer_roster_rules(league: dict) -> RosterRules:
    roster_positions = list(league.get("roster_positions") or [])
    settings = league.get("settings") or {}

    bench_slots = sum(1 for slot in roster_positions if str(slot).upper() == "BN")
    ir_slots = int(settings.get("reserve_slots", 0) or 0)
    taxi_slots = int(settings.get("taxi_slots", 0) or 0)

    non_starting = {"BN", "IR", "TAXI"}
    starters = tuple(
        str(slot).upper()
        for slot in roster_positions
        if str(slot).upper() not in non_starting
    )

    roster_size = len(roster_positions)
    if roster_size == 0:
        roster_size = int(settings.get("roster_size", 16) or 16)

    return RosterRules(
        roster_size=roster_size,
        starting_lineup=starters,
        bench_slots=bench_slots,
        ir_slots=ir_slots,
        taxi_slots=taxi_slots,
    )


def _build_manager_map(
    users: Iterable[dict],
    rosters: Iterable[dict],
    my_sleeper_user_id: Optional[str] = None,
) -> Dict[str, ManagerIdentity]:
    users_by_id = {
        str(user.get("user_id")): user
        for user in users
        if user.get("user_id") is not None
    }

    managers: Dict[str, ManagerIdentity] = {}

    for roster in rosters:
        owner_id = roster.get("owner_id")
        if owner_id is None:
            continue

        owner_id = str(owner_id)
        user = users_by_id.get(owner_id, {})
        metadata = user.get("metadata") or {}

        username = user.get("display_name") or user.get("username") or owner_id
        team_name = (
            metadata.get("team_name")
            or user.get("display_name")
            or user.get("username")
            or owner_id
        )

        base = _slug(str(username))
        manager_id = base
        suffix = 2
        while manager_id in managers:
            manager_id = f"{base}_{suffix}"
            suffix += 1

        aliases = tuple(
            value
            for value in {
                str(username).strip(),
                str(team_name).strip(),
            }
            if value
        )

        managers[manager_id] = ManagerIdentity(
            manager_id=manager_id,
            sleeper_user_id=owner_id,
            sleeper_roster_id=roster.get("roster_id"),
            sleeper_username=str(username),
            sleeper_team_name=str(team_name),
            historical_aliases=aliases,
        )

    return managers


def infer_league_profile_from_sleeper(
    league: dict,
    draft: Optional[dict],
    users: Iterable[dict],
    rosters: Iterable[dict],
    *,
    season: int,
    my_sleeper_user_id: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> LeagueProfile:
    """
    Build a normalized league profile from Sleeper metadata.

    Sleeper can describe scoring, roster shape, managers, and much of the
    draft configuration. Keeper economics and custom college/devy rules are
    intentionally overrideable because Sleeper often cannot represent them.
    """
    overrides = overrides or {}

    league_name = str(league.get("name") or "Sleeper League")
    league_id = league.get("league_id")
    draft_id = (draft or {}).get("draft_id")

    scoring = ScoringRules.from_sleeper(
        overrides.get("scoring_settings")
        or league.get("scoring_settings")
        or {}
    )

    roster = _infer_roster_rules(league)
    roster_override = overrides.get("roster") or {}
    if roster_override:
        roster = RosterRules(
            roster_size=int(roster_override.get("roster_size", roster.roster_size)),
            starting_lineup=tuple(roster_override.get("starting_lineup", roster.starting_lineup)),
            bench_slots=int(roster_override.get("bench_slots", roster.bench_slots)),
            ir_slots=int(roster_override.get("ir_slots", roster.ir_slots)),
            taxi_slots=int(roster_override.get("taxi_slots", roster.taxi_slots)),
        )

    auction_override = overrides.get("auction") or {}
    auction = AuctionRules(
        base_budget=int(auction_override.get("base_budget", _extract_budget(draft))),
        minimum_bid=int(auction_override.get("minimum_bid", 1)),
        roster_spots=int(auction_override.get("roster_spots", roster.roster_size)),
    )

    keeper_override = overrides.get("keepers") or {}
    keepers = KeeperRules(
        enabled=bool(keeper_override.get("enabled", False)),
        max_keepers=int(keeper_override.get("max_keepers", 0)),
        escalation=keeper_override.get("escalation", 11),
        midseason_pickup_cost=int(
            keeper_override.get("midseason_pickup_cost", 10)
        ),
        future_horizon_years=int(
            keeper_override.get("future_horizon_years", 3)
        ),
        lock_hours_before_draft=keeper_override.get("lock_hours_before_draft"),
    )

    college_override = overrides.get("college") or {}
    college = CollegeRules(
        enabled=bool(college_override.get("enabled", False)),
        max_college_players=int(college_override.get("max_college_players", 0)),
        draft_rounds=int(college_override.get("draft_rounds", 0)),
        eligibility_source=str(
            college_override.get("eligibility_source", "manual")
        ),
        college_pick_trading_enabled=bool(
            college_override.get("college_pick_trading_enabled", True)
        ),
        pre_draft_promotion_cost=int(college_override.get("pre_draft_promotion_cost", 0)),
        during_draft_promotion_cost=int(college_override.get("during_draft_promotion_cost", 0)),
        next_year_keeper_cost=college_override.get("next_year_keeper_cost"),
        lock_hours_before_draft=college_override.get("lock_hours_before_draft"),
        pro_thresholds=college_override.get("pro_thresholds") or {},
    )

    model_override = overrides.get("model") or {}
    current_weight = float(model_override.get("current_season_weight", 1.0))
    future_weight = float(model_override.get("future_value_weight", max(0.0, 1.0 - current_weight)))
    total = current_weight + future_weight
    if total <= 0:
        current_weight, future_weight = 1.0, 0.0
    else:
        current_weight /= total
        future_weight /= total

    managers = _build_manager_map(
        users=users,
        rosters=rosters,
        my_sleeper_user_id=my_sleeper_user_id,
    )

    return LeagueProfile(
        league_key=str(overrides.get("league_key") or league_id or _slug(league_name)),
        league_name=str(overrides.get("league_name") or league_name),
        season=int(season),
        source_mode="sleeper",
        sleeper_league_id=str(league_id) if league_id is not None else None,
        sleeper_draft_id=str(draft_id) if draft_id is not None else None,
        scoring=scoring,
        roster=roster,
        auction=auction,
        keepers=keepers,
        college=college,
        model=ModelRules(
            current_season_weight=current_weight,
            future_value_weight=future_weight,
        ),
        managers=managers,
        historical_draft_sheets={
            int(year): str(sheet)
            for year, sheet in (overrides.get("historical_draft_sheets") or {}).items()
        },
        metadata={
            "inferred": True,
            "my_sleeper_user_id": my_sleeper_user_id,
            **(overrides.get("metadata") or {}),
        },
    )
