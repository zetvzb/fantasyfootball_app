from dataclasses import dataclass, field
from typing import List, Optional

from src.league_config import (
    MAX_KEEPERS as LEGACY_MAX_KEEPERS,
    MINIMUM_AUCTION_BID as LEGACY_MINIMUM_AUCTION_BID,
    ROSTER_SIZE as LEGACY_ROSTER_SIZE,
)
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


@dataclass
class TeamDraftSetup:
    manager_id: str
    pre_keeper_budget: int
    keepers: List[SelectedKeeper] = field(default_factory=list)
    college_promotions: List[str] = field(default_factory=list)
    college_promotion_cost: int = 0
    roster_size: int = LEGACY_ROSTER_SIZE
    minimum_auction_bid: int = LEGACY_MINIMUM_AUCTION_BID

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
        return self.pre_keeper_budget - self.committed_cost

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
    manager_data: ManagerLeagueData,
    selected_keeper_names: List[str],
    college_promotions: List[str],
    league_profile: Optional["LeagueProfile"] = None,
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

    return TeamDraftSetup(
        manager_id=manager_id,
        pre_keeper_budget=manager_data.pre_keeper_budget,
        keepers=keepers,
        college_promotions=college_promotions,
        college_promotion_cost=college_promotion_cost,
        roster_size=roster_size,
        minimum_auction_bid=minimum_bid,
    )
