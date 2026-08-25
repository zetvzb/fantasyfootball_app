from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

from src.keeper_domain import (
    KeeperContract,
    KeeperDomainRules,
    build_keeper_contract,
)

from src.league_config import (
    MAX_KEEPERS as LEGACY_MAX_KEEPERS,
    MINIMUM_AUCTION_BID as LEGACY_MINIMUM_AUCTION_BID,
    ROSTER_SIZE as LEGACY_ROSTER_SIZE,
)
if TYPE_CHECKING:
    from src.league_data import ManagerLeagueData

try:
    from src.league_profile import LeagueProfile
except ImportError:  # pragma: no cover - keeps the legacy module importable mid-migration
    LeagueProfile = None


@dataclass
class SelectedKeeper:
    player_name: str
    position: str
    cost: int
    contract: Optional[KeeperContract] = None


@dataclass
class TeamDraftSetup:
    manager_id: str
    pre_keeper_budget: int
    keepers: List[SelectedKeeper] = field(default_factory=list)
    college_promotions: List[str] = field(default_factory=list)
    college_promotion_cost: int = 0
    roster_size: int = LEGACY_ROSTER_SIZE
    minimum_auction_bid: int = LEGACY_MINIMUM_AUCTION_BID
    entering_auction_cash: Optional[int] = None
    traded_dollars: int = 0
    budget_source: str = "default"
    budget_source_detail: str = ""

    @property
    def keeper_cost(self) -> int:
        return sum(keeper.cost for keeper in self.keepers)

    @property
    def college_cost(self) -> int:
        return len(self.college_promotions) * self.college_promotion_cost

    @property
    def committed_cost(self) -> int:
        return self.keeper_cost + self.college_cost

    @property
    def auction_cash(self) -> int:
        if self.entering_auction_cash is not None:
            return int(self.entering_auction_cash)
        return self.pre_keeper_budget - self.committed_cost

    @property
    def entering_cash(self) -> int:
        return self.auction_cash

    @property
    def keeper_commitments(self) -> int:
        return self.keeper_cost

    @property
    def required_reserve(self) -> int:
        return self.open_roster_spots * self.minimum_auction_bid

    @property
    def discretionary_cash(self) -> int:
        return max(0, self.auction_cash - self.required_reserve)

    @property
    def base_cash_before_trades(self) -> int:
        return self.entering_cash - self.traded_dollars

    @property
    def keeper_count(self) -> int:
        return len(self.keepers)

    @property
    def college_promotion_count(self) -> int:
        return len(self.college_promotions)

    @property
    def roster_spots_used(self) -> int:
        return self.keeper_count + self.college_promotion_count

    @property
    def open_roster_spots(self) -> int:
        return max(0, self.roster_size - self.roster_spots_used)

    @property
    def max_bid(self) -> int:
        if self.open_roster_spots <= 0:
            return 0
        reserve_needed = (
            self.open_roster_spots - 1
        ) * self.minimum_auction_bid
        return max(0, self.auction_cash - reserve_needed)


def build_team_draft_setup(
    manager_id: str,
    manager_data: "ManagerLeagueData",
    selected_keeper_names: List[str],
    college_promotions: List[str],
    league_profile: Optional["LeagueProfile"] = None,
    team_budget: Optional[Any] = None,
) -> TeamDraftSetup:
    """
    Build a team's starting auction state.

    league_profile is optional during the migration. If omitted, the current
    Bishop Sycamore constants are used so the existing app keeps working.
    """
    if league_profile is None:
        max_keepers = LEGACY_MAX_KEEPERS
        roster_size = LEGACY_ROSTER_SIZE
        minimum_bid = LEGACY_MINIMUM_AUCTION_BID
        college_promotion_cost = 0
    else:
        max_keepers = league_profile.keepers.max_keepers
        roster_size = league_profile.roster.roster_size
        minimum_bid = league_profile.auction.minimum_bid
        college_promotion_cost = league_profile.college.during_draft_promotion_cost

    if max_keepers >= 0 and len(selected_keeper_names) > max_keepers:
        raise ValueError(f"Maximum keepers is {max_keepers}.")

    keeper_lookup = {
        keeper.player_name: keeper
        for keeper in manager_data.keeper_options
    }

    keepers = []
    for player_name in selected_keeper_names:
        keeper = keeper_lookup.get(player_name)
        if keeper is None:
            raise ValueError(
                f"{player_name} is not a valid keeper option for {manager_id}."
            )
        if keeper.keeper_cost is None:
            raise ValueError(
                f"{player_name} does not have a valid keeper salary."
            )
        keepers.append(
            SelectedKeeper(
                player_name=keeper.player_name,
                position=keeper.position,
                cost=keeper.keeper_cost,
            )
        )

    keeper_commitments = sum(
        keeper.cost for keeper in keepers
    )
    college_commitments = (
        len(college_promotions) * college_promotion_cost
    )
    total_commitments = keeper_commitments + college_commitments

    if team_budget is None:
        pre_keeper_budget = int(manager_data.pre_keeper_budget)
        entering_auction_cash = (
            pre_keeper_budget
            - total_commitments
        )
        traded_dollars = 0
        budget_source = "legacy"
        budget_source_detail = "Manager league data"
    else:
        budget_amount = int(team_budget.amount)
        if team_budget.budget_kind == "pre_keeper":
            pre_keeper_budget = budget_amount
            entering_auction_cash = budget_amount - total_commitments
        elif team_budget.budget_kind == "auction_cash":
            entering_auction_cash = budget_amount
            pre_keeper_budget = budget_amount + total_commitments
        else:
            raise ValueError(
                "Unknown budget kind: {0}".format(team_budget.budget_kind)
            )
        traded_dollars = int(getattr(team_budget, "traded_dollars", 0))
        source = getattr(team_budget, "source", None)
        budget_source = str(getattr(source, "source", "default"))
        budget_source_detail = str(getattr(source, "detail", ""))

    open_spots = max(
        0,
        roster_size - len(keepers) - len(college_promotions),
    )
    required_reserve = open_spots * minimum_bid
    if entering_auction_cash < required_reserve:
        raise ValueError(
            "Entering auction cash ${0} cannot fund the ${1} minimum-bid "
            "reserve for {2} open roster spots.".format(
                entering_auction_cash,
                required_reserve,
                open_spots,
            )
        )

    return TeamDraftSetup(
        manager_id=manager_id,
        pre_keeper_budget=pre_keeper_budget,
        keepers=keepers,
        college_promotions=college_promotions,
        college_promotion_cost=college_promotion_cost,
        roster_size=roster_size,
        minimum_auction_bid=minimum_bid,
        entering_auction_cash=entering_auction_cash,
        traded_dollars=traded_dollars,
        budget_source=budget_source,
        budget_source_detail=budget_source_detail,
    )


def build_team_draft_setup_from_setup_data(
    manager_id: str,
    league_setup_data: Any,
    selected_keeper_names: List[str],
    college_promotions: List[str],
    league_profile: "LeagueProfile",
) -> TeamDraftSetup:
    """Build draft state directly from normalized, workbook-optional setup."""

    keeper_rules = KeeperDomainRules.from_league_profile(league_profile)

    keeper_records = league_setup_data.keepers_for(manager_id)
    keeper_lookup = {
        keeper.player_name: keeper
        for keeper in keeper_records
    }
    selected = []
    for player_name in selected_keeper_names:
        keeper = keeper_lookup.get(player_name)
        if keeper is None:
            raise ValueError(
                "{0} is not a valid keeper option for {1}.".format(
                    player_name,
                    manager_id,
                )
            )
        contract = build_keeper_contract(keeper, keeper_rules)
        selected.append(
            SelectedKeeper(
                player_name=keeper.player_name,
                position=keeper.position or "",
                cost=contract.current_cost,
                contract=contract,
            )
        )

    keeper_rules.validate_keeper_count(len(selected))

    budget = league_setup_data.budgets.get(manager_id)
    keeper_cost = sum(keeper.cost for keeper in selected)
    college_cost = (
        len(college_promotions)
        * league_profile.college.during_draft_promotion_cost
    )
    commitments = keeper_cost + college_cost
    if budget is None:
        budget_amount = int(league_profile.auction.base_budget)
        budget_kind = "pre_keeper"
        traded_dollars = 0
        budget_source = "default"
        budget_source_detail = "League profile default"
    else:
        budget_amount = int(budget.amount)
        budget_kind = budget.budget_kind
        traded_dollars = int(getattr(budget, "traded_dollars", 0))
        budget_source = str(getattr(budget.source, "source", "default"))
        budget_source_detail = str(getattr(budget.source, "detail", ""))

    if budget_kind == "pre_keeper":
        pre_keeper_budget = budget_amount
        entering_cash = budget_amount - commitments
    elif budget_kind == "auction_cash":
        entering_cash = budget_amount
        pre_keeper_budget = budget_amount + commitments
    else:
        raise ValueError("Unknown budget kind: {0}".format(budget_kind))

    roster_size = league_profile.roster.roster_size
    minimum_bid = league_profile.auction.minimum_bid
    open_spots = max(
        0,
        roster_size - len(selected) - len(college_promotions),
    )
    reserve = open_spots * minimum_bid
    if entering_cash < reserve:
        raise ValueError(
            "Entering auction cash ${0} cannot fund the ${1} minimum-bid "
            "reserve for {2} open roster spots.".format(
                entering_cash,
                reserve,
                open_spots,
            )
        )

    return TeamDraftSetup(
        manager_id=manager_id,
        pre_keeper_budget=pre_keeper_budget,
        keepers=selected,
        college_promotions=list(college_promotions),
        college_promotion_cost=(
            league_profile.college.during_draft_promotion_cost
        ),
        roster_size=roster_size,
        minimum_auction_bid=minimum_bid,
        entering_auction_cash=entering_cash,
        traded_dollars=traded_dollars,
        budget_source=budget_source,
        budget_source_detail=budget_source_detail,
    )
