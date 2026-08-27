from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple


EXPLICIT_COST = "explicit"
RETURNING_KEEPER = "returning"
MIDSEASON_PICKUP = "midseason_pickup"
VALID_COST_BASES = (
    EXPLICIT_COST,
    RETURNING_KEEPER,
    MIDSEASON_PICKUP,
)


@dataclass(frozen=True)
class KeeperDomainRules:
    """League-specific keeper rules used by setup and future valuation."""

    max_keepers: int
    annual_escalation: int = 11
    midseason_pickup_cost: int = 10
    future_horizon_years: int = 3

    @classmethod
    def from_league_profile(cls, league_profile: Any) -> "KeeperDomainRules":
        keeper_rules = league_profile.keepers
        if hasattr(keeper_rules, "escalation"):
            escalation = getattr(keeper_rules, "escalation")
            annual_escalation = (
                0 if escalation is None else int(escalation)
            )
        else:
            annual_escalation = 11
        pickup_cost = getattr(
            keeper_rules,
            "midseason_pickup_cost",
            10,
        )
        horizon = getattr(
            keeper_rules,
            "future_horizon_years",
            3,
        )
        if pickup_cost is None:
            pickup_cost = 10
        if horizon is None:
            horizon = 3
        rules = cls(
            max_keepers=int(keeper_rules.max_keepers),
            annual_escalation=annual_escalation,
            midseason_pickup_cost=int(pickup_cost),
            future_horizon_years=int(horizon),
        )
        rules.validate()
        return rules

    def validate(self) -> None:
        if self.max_keepers < 0:
            raise ValueError("Maximum keepers cannot be negative.")
        if self.annual_escalation < 0:
            raise ValueError("Keeper escalation cannot be negative.")
        if self.midseason_pickup_cost < 0:
            raise ValueError("Mid-season pickup cost cannot be negative.")
        if self.future_horizon_years not in (2, 3):
            raise ValueError("Keeper future horizon must be 2 or 3 years.")

    def validate_keeper_count(self, keeper_count: int) -> None:
        if keeper_count > self.max_keepers:
            raise ValueError(
                "Maximum keepers is {0}.".format(self.max_keepers)
            )


@dataclass(frozen=True)
class KeeperContract:
    """Resolved current keeper terms with slots for future valuation engines."""

    manager_id: str
    player_name: str
    position: Optional[str]
    cost_basis: str
    current_cost: int
    prior_year_cost: Optional[int]
    future_horizon_years: int
    future_values: Tuple[Optional[float], ...]

    def future_value(self, year: int) -> Optional[float]:
        if year < 1 or year > self.future_horizon_years:
            raise ValueError(
                "Future keeper year must be between 1 and {0}.".format(
                    self.future_horizon_years
                )
            )
        return self.future_values[year - 1]


def derive_keeper_cost(
    *,
    cost_basis: str,
    explicit_cost: Optional[int],
    prior_year_cost: Optional[int],
    rules: KeeperDomainRules,
) -> int:
    if cost_basis not in VALID_COST_BASES:
        raise ValueError("Unknown keeper cost basis: {0}".format(cost_basis))

    if cost_basis == RETURNING_KEEPER:
        if prior_year_cost is None:
            raise ValueError(
                "Returning keepers require a prior-year cost."
            )
        cost = int(prior_year_cost) + rules.annual_escalation
    elif cost_basis == MIDSEASON_PICKUP:
        cost = rules.midseason_pickup_cost
    else:
        if explicit_cost is None:
            raise ValueError("Explicit keeper cost is required.")
        cost = int(explicit_cost)

    if cost < 0:
        raise ValueError("Keeper cost cannot be negative.")
    return cost


def build_keeper_contract(
    keeper_record: Any,
    rules: KeeperDomainRules,
) -> KeeperContract:
    cost_basis = str(
        getattr(keeper_record, "cost_basis", EXPLICIT_COST)
        or EXPLICIT_COST
    )
    prior_year_cost = getattr(keeper_record, "prior_year_cost", None)

    supplied_values = tuple(
        None if value is None else float(value)
        for value in (
            getattr(keeper_record, "future_values", ()) or ()
        )
    )
    if len(supplied_values) > rules.future_horizon_years:
        raise ValueError(
            "Keeper future values exceed the {0}-year horizon.".format(
                rules.future_horizon_years
            )
        )
    future_values = supplied_values + (None,) * (
        rules.future_horizon_years - len(supplied_values)
    )

    return KeeperContract(
        manager_id=str(keeper_record.manager_id),
        player_name=str(keeper_record.player_name),
        position=getattr(keeper_record, "position", None),
        cost_basis=cost_basis,
        current_cost=derive_keeper_cost(
            cost_basis=cost_basis,
            explicit_cost=getattr(keeper_record, "cost", None),
            prior_year_cost=prior_year_cost,
            rules=rules,
        ),
        prior_year_cost=(
            int(prior_year_cost) if prior_year_cost is not None else None
        ),
        future_horizon_years=rules.future_horizon_years,
        future_values=future_values,
    )
