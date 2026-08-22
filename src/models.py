from dataclasses import dataclass, field
from typing import Optional


MINIMUM_BID = 1


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    position: str
    nfl_team: Optional[str] = None
    is_rookie: bool = False


@dataclass
class DraftedPlayer:
    player: Player
    price: int


@dataclass
class TeamState:
    team_id: str
    team_name: str

    starting_budget: int
    roster_limit: int

    keeper_count: int = 0
    keeper_cost: int = 0

    drafted_players: list[DraftedPlayer] = field(default_factory=list)

    @property
    def auction_spent(self) -> int:
        return sum(player.price for player in self.drafted_players)

    @property
    def total_spent(self) -> int:
        return self.keeper_cost + self.auction_spent

    @property
    def remaining_budget(self) -> int:
        return self.starting_budget - self.total_spent

    @property
    def filled_slots(self) -> int:
        return self.keeper_count + len(self.drafted_players)

    @property
    def open_slots(self) -> int:
        return max(0, self.roster_limit - self.filled_slots)

    @property
    def max_bid(self) -> int:
        """
        Maximum amount the team can legally spend on one player
        while still reserving $1 for every remaining roster spot.
        """

        if self.open_slots <= 0:
            return 0

        dollars_needed_for_other_slots = (
            self.open_slots - 1
        ) * MINIMUM_BID

        return max(
            0,
            self.remaining_budget - dollars_needed_for_other_slots
        )


@dataclass
class AuctionSale:
    player: Player
    team_id: str
    team_name: str
    price: int


@dataclass
class DraftState:
    teams: dict[str, TeamState]
    available_players: dict[str, Player]

    sales: list[AuctionSale] = field(default_factory=list)

    def sell_player(
        self,
        player_id: str,
        team_id: str,
        price: int,
    ) -> AuctionSale:

        if player_id not in self.available_players:
            raise ValueError("Player is no longer available.")

        if team_id not in self.teams:
            raise ValueError("Team does not exist.")

        if price < MINIMUM_BID:
            raise ValueError(
                f"Minimum bid is ${MINIMUM_BID}."
            )

        team = self.teams[team_id]
        player = self.available_players[player_id]

        if team.open_slots <= 0:
            raise ValueError(
                f"{team.team_name} has no open roster spots."
            )

        if price > team.max_bid:
            raise ValueError(
                f"{team.team_name}'s maximum legal bid is "
                f"${team.max_bid}."
            )

        drafted_player = DraftedPlayer(
            player=player,
            price=price,
        )

        team.drafted_players.append(drafted_player)

        sale = AuctionSale(
            player=player,
            team_id=team_id,
            team_name=team.team_name,
            price=price,
        )

        self.sales.append(sale)

        del self.available_players[player_id]

        return sale