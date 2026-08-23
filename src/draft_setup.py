from dataclasses import dataclass, field
from typing import List

from src.league_config import (
    MAX_KEEPERS,
    MINIMUM_AUCTION_BID,
    ROSTER_SIZE,
)

from src.league_data import (
    ManagerLeagueData,
)


@dataclass
class SelectedKeeper:
    player_name: str
    position: str
    cost: int


@dataclass
class TeamDraftSetup:
    manager_id: str
    pre_keeper_budget: int

    keepers: List[SelectedKeeper] = field(
        default_factory=list
    )

    college_promotions: List[str] = field(
        default_factory=list
    )

    college_promotion_cost: int = 0

    # -----------------------------------------------------
    # MONEY
    # -----------------------------------------------------

    @property
    def keeper_cost(self) -> int:
        return sum(
            keeper.cost
            for keeper in self.keepers
        )

    @property
    def college_cost(self) -> int:
        return (
            len(self.college_promotions)
            * self.college_promotion_cost
        )

    @property
    def committed_cost(self) -> int:
        return (
            self.keeper_cost
            + self.college_cost
        )

    @property
    def auction_cash(self) -> int:
        return (
            self.pre_keeper_budget
            - self.committed_cost
        )

    # -----------------------------------------------------
    # ROSTER
    # -----------------------------------------------------

    @property
    def keeper_count(self) -> int:
        return len(
            self.keepers
        )

    @property
    def college_promotion_count(self) -> int:
        return len(
            self.college_promotions
        )

    @property
    def roster_spots_used(self) -> int:
        return (
            self.keeper_count
            + self.college_promotion_count
        )

    @property
    def open_roster_spots(self) -> int:
        return max(
            0,
            ROSTER_SIZE
            - self.roster_spots_used
        )

    # -----------------------------------------------------
    # AUCTION
    # -----------------------------------------------------

    @property
    def max_bid(self) -> int:
        """
        Maximum legal bid while preserving $1 for
        every OTHER remaining auction roster spot.
        """

        if self.open_roster_spots <= 0:
            return 0

        reserve_needed = (
            self.open_roster_spots - 1
        ) * MINIMUM_AUCTION_BID

        return max(
            0,
            self.auction_cash
            - reserve_needed
        )


def build_team_draft_setup(
    manager_id: str,
    manager_data: ManagerLeagueData,
    selected_keeper_names: List[str],
    college_promotions: List[str],
) -> TeamDraftSetup:

    if len(selected_keeper_names) > MAX_KEEPERS:
        raise ValueError(
            f"Maximum keepers is {MAX_KEEPERS}."
        )

    keeper_lookup = {
        keeper.player_name: keeper
        for keeper
        in manager_data.keeper_options
    }

    keepers = []

    for player_name in selected_keeper_names:

        keeper = keeper_lookup.get(
            player_name
        )

        if keeper is None:
            raise ValueError(
                f"{player_name} is not a valid "
                f"keeper option for {manager_id}."
            )

        if keeper.keeper_cost is None:
            raise ValueError(
                f"{player_name} does not have "
                f"a valid keeper salary."
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
        pre_keeper_budget=(
            manager_data.pre_keeper_budget
        ),
        keepers=keepers,
        college_promotions=college_promotions,

        # We're modeling players called up
        # during the draft here.
        college_promotion_cost=0,
    )