from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Tuple

from src.dynamic_cap import DynamicCapInput, DynamicCapResult, adjust_dynamic_cap
from src.keeper_domain import KeeperContract, KeeperDomainRules
from src.keeper_optimizer import (
    KeeperOptimizationInput,
    KeeperOptimizationResult,
    optimize_keeper_combinations,
)
from src.keeper_recommendation import (
    KeeperRecommendation,
    KeeperRecommendationInput,
    recommend_keeper,
)
from src.league_profile import LeagueProfile
from src.league_registry import LeagueRegistry
from src.league_setup_data import (
    HistoricalSale,
    KeeperRecord,
    LeagueSetupData,
    LeagueSetupStore,
    SourceInfo,
    TeamBudget,
)
from src.manual_league import build_manual_league_profile
from src.strategy_profile import StrategyMode, StrategyProfile
from src.valuation import PlayerValue


DEMO_LEAGUE_KEY = "portfolio_demo_2026"
DEMO_MANAGER_ID = "fourth_long_labs"


@dataclass(frozen=True)
class PortfolioDemoScenario:
    profile: LeagueProfile
    setup: LeagueSetupData
    keeper_recommendations: Tuple[KeeperRecommendation, ...]
    keeper_optimization: KeeperOptimizationResult
    live_cap: DynamicCapResult
    target_value: int
    soft_cap: int
    hard_cap: int


def build_demo_profile() -> LeagueProfile:
    profile = build_manual_league_profile(
        league_name="Portfolio Auction Lab",
        season=2026,
        team_names=(
            "Fourth & Long Labs",
            "Zero RB Research",
            "Sunday Signal",
            "Market Makers",
            "Taxi Squad Labs",
            "Value Over Replacement",
            "The Bid Shapers",
            "Future Firsts",
        ),
        current_team_name="Fourth & Long Labs",
        scoring_format="ppr",
        roster_size=18,
        auction_budget=400,
        minimum_bid=1,
        max_keepers=6,
        keeper_escalation=11,
        league_key=DEMO_LEAGUE_KEY,
    )
    metadata = dict(profile.metadata)
    metadata.update(
        {
            "portfolio_demo": True,
            "demo_walkthrough": "demo/README.md",
            "current_manager_id": DEMO_MANAGER_ID,
        }
    )
    return replace(profile, metadata=metadata)


def _keeper(
    manager_id: str,
    player_name: str,
    position: str,
    cost: int,
    future_values: Tuple[float, float, float],
) -> KeeperRecord:
    return KeeperRecord(
        manager_id=manager_id,
        player_name=player_name,
        position=position,
        cost=cost,
        future_values=future_values,
        status="candidate",
        source=SourceInfo("manual", detail="Portfolio demo fixture"),
    )


def build_demo_setup(profile: LeagueProfile) -> LeagueSetupData:
    manager_ids = tuple(profile.managers)
    entering_budgets = (424, 387, 405, 396, 411, 400, 378, 419)
    budgets = {
        manager_id: TeamBudget(
            manager_id=manager_id,
            amount=budget,
            budget_kind="pre_keeper",
            source=SourceInfo("manual", detail="Demo budget ledger"),
        )
        for manager_id, budget in zip(
            manager_ids, entering_budgets
        )
    }
    my_keepers = (
        _keeper(DEMO_MANAGER_ID, "Ja'Marr Chase", "WR", 38, (96.0, 94.0, 91.0)),
        _keeper(DEMO_MANAGER_ID, "Bijan Robinson", "RB", 45, (94.0, 91.0, 87.0)),
        _keeper(DEMO_MANAGER_ID, "Brock Bowers", "TE", 21, (93.0, 95.0, 94.0)),
        _keeper(DEMO_MANAGER_ID, "Jayden Daniels", "QB", 29, (91.0, 93.0, 92.0)),
        _keeper(DEMO_MANAGER_ID, "Puka Nacua", "WR", 33, (89.0, 86.0, 82.0)),
        _keeper(DEMO_MANAGER_ID, "Jahmyr Gibbs", "RB", 56, (92.0, 86.0, 79.0)),
        _keeper(DEMO_MANAGER_ID, "Lamar Jackson", "QB", 72, (88.0, 82.0, 76.0)),
    )
    opponent_groups = (
        (
            ("Justin Jefferson", "WR"), ("Trey McBride", "TE"),
            ("Jalen Hurts", "QB"), ("Jonathan Taylor", "RB"),
            ("Garrett Wilson", "WR"), ("Brian Thomas Jr.", "WR"),
            ("Ashton Jeanty", "RB"),
        ),
        (
            ("CeeDee Lamb", "WR"), ("Breece Hall", "RB"),
            ("Joe Burrow", "QB"), ("DeVonta Smith", "WR"),
            ("Kyren Williams", "RB"), ("George Kittle", "TE"),
            ("Ladd McConkey", "WR"),
        ),
        (
            ("Josh Allen", "QB"), ("Amon-Ra St. Brown", "WR"),
            ("Derrick Henry", "RB"), ("Tee Higgins", "WR"),
            ("Travis Kelce", "TE"), ("James Cook", "RB"),
            ("Zay Flowers", "WR"),
        ),
        (
            ("Malik Nabers", "WR"), ("Drake Maye", "QB"),
            ("Kenneth Walker III", "RB"), ("Rome Odunze", "WR"),
            ("Tucker Kraft", "TE"), ("Omarion Hampton", "RB"),
            ("Rashee Rice", "WR"),
        ),
        (
            ("Saquon Barkley", "RB"), ("Sam LaPorta", "TE"),
            ("Dak Prescott", "QB"), ("Mike Evans", "WR"),
            ("Josh Jacobs", "RB"), ("DJ Moore", "WR"),
            ("David Montgomery", "RB"),
        ),
        (
            ("Nico Collins", "WR"), ("De'Von Achane", "RB"),
            ("Baker Mayfield", "QB"), ("Terry McLaurin", "WR"),
            ("Mark Andrews", "TE"), ("James Conner", "RB"),
            ("Xavier Worthy", "WR"),
        ),
        (
            ("Marvin Harrison Jr.", "WR"), ("Caleb Williams", "QB"),
            ("Alvin Kamara", "RB"), ("DK Metcalf", "WR"),
            ("Dalton Kincaid", "TE"), ("Rhamondre Stevenson", "RB"),
            ("Jordan Addison", "WR"),
        ),
    )
    opponent_names = tuple(
        (manager_ids[group_index + 1], player, position, 18 + player_index * 7)
        for group_index, group in enumerate(opponent_groups)
        for player_index, (player, position) in enumerate(group)
    )
    opponent_keepers = tuple(
        _keeper(
            manager,
            player,
            position,
            cost,
            (
                88.0 - (index % 7) * 4.0,
                85.0 - (index % 7) * 4.0,
                81.0 - (index % 7) * 4.0,
            ),
        )
        for index, (manager, player, position, cost) in enumerate(opponent_names)
    )
    return LeagueSetupData(
        league_key=profile.league_key,
        budgets=budgets,
        keepers=list(my_keepers + opponent_keepers),
        historical_sales=[
            HistoricalSale(2025, "Elite WR A", 91, manager_ids[3], position="WR"),
            HistoricalSale(2025, "Feature RB A", 84, manager_ids[5], position="RB"),
            HistoricalSale(2025, "Top QB A", 68, manager_ids[3], position="QB"),
            HistoricalSale(2024, "Elite WR B", 87, manager_ids[1], position="WR"),
            HistoricalSale(2024, "Feature RB B", 79, manager_ids[6], position="RB"),
        ],
        metadata={
            "portfolio_demo": True,
            "keepers_configured": True,
            "demo_note": "Synthetic portfolio data; not current player advice.",
        },
    )


def build_demo_scenario() -> PortfolioDemoScenario:
    profile = build_demo_profile()
    setup = build_demo_setup(profile)
    strategy = StrategyProfile.for_mode(
        profile.league_key, "portfolio-user", StrategyMode.HYBRID
    )
    rules = KeeperDomainRules.from_league_profile(profile)
    inputs = (
        ("Ja'Marr Chase", "WR", 25.0, 96.0, 94.0, 0.94, 1.00),
        ("Bijan Robinson", "RB", 24.0, 94.0, 91.0, 0.92, 1.00),
        ("Brock Bowers", "TE", 23.0, 88.0, 95.0, 1.00, 1.00),
        ("Jayden Daniels", "QB", 25.0, 90.0, 93.0, 0.86, 1.00),
        ("Puka Nacua", "WR", 25.0, 87.0, 86.0, 0.80, 0.80),
        ("Jahmyr Gibbs", "RB", 24.0, 93.0, 86.0, 0.95, 0.80),
        ("Lamar Jackson", "QB", 29.0, 91.0, 78.0, 0.82, 0.45),
    )
    setup_costs = {
        record.player_name: int(record.cost or 0)
        for record in setup.keepers_for(DEMO_MANAGER_ID)
    }
    recommendations = tuple(
        recommend_keeper(
            KeeperRecommendationInput(
                contract=KeeperContract(
                    manager_id=DEMO_MANAGER_ID,
                    player_name=name,
                    position=position,
                    cost_basis="explicit",
                    current_cost=setup_costs[name],
                    prior_year_cost=None,
                    future_horizon_years=3,
                    future_values=(future, max(0.0, future - 3), max(0.0, future - 7)),
                ),
                strategy_profile=strategy,
                position=position,
                age=age,
                current_value=current,
                future_value=future,
                scarcity=scarcity,
                roster_fit=fit,
                auction_budget=424,
                minimum_bid=1,
                keeper_rules=rules,
            )
        )
        for name, position, age, current, future, scarcity, fit in inputs
    )
    ordered = tuple(
        sorted(recommendations, key=lambda value: -value.strategy_score)
    )
    optimization = optimize_keeper_combinations(
        KeeperOptimizationInput(
            manager_id=DEMO_MANAGER_ID,
            recommendations=ordered,
            strategy_profile=strategy,
            pre_keeper_budget=424,
            roster_size=18,
            minimum_bid=1,
            max_keepers=6,
            starting_lineup=profile.roster.starting_lineup,
        )
    )
    live_cap = adjust_dynamic_cap(
        DynamicCapInput(
            base_cap=54,
            legal_max_bid=68,
            need_score=0.88,
            scarcity_score=0.84,
            has_comparable_alternative=False,
            cash_flexibility=0.68,
            auction_stage=0.42,
            room_inflation_index=1.08,
            current_weight=0.50,
            future_weight=0.50,
            future_value_score=0.92,
            context_adjustment_pct=0.03,
        )
    )
    return PortfolioDemoScenario(
        profile=profile,
        setup=setup,
        keeper_recommendations=ordered,
        keeper_optimization=optimization,
        live_cap=live_cap,
        target_value=49,
        soft_cap=54,
        hard_cap=live_cap.adjusted_cap,
    )


def build_demo_player_values(setup: LeagueSetupData) -> Tuple[PlayerValue, ...]:
    """Provide reproducible offline VORP inputs for the synthetic league."""

    current_scores = {
        "Ja'Marr Chase": 96.0,
        "Bijan Robinson": 94.0,
        "Brock Bowers": 88.0,
        "Jayden Daniels": 90.0,
        "Puka Nacua": 87.0,
        "Jahmyr Gibbs": 93.0,
        "Lamar Jackson": 91.0,
    }
    values = []
    for rank, record in enumerate(setup.keepers, start=1):
        future = next(
            (float(value) for value in record.future_values if value is not None),
            60.0,
        )
        vorp = current_scores.get(record.player_name, future)
        values.append(
            PlayerValue(
                player_name=record.player_name,
                position=str(record.position or "UNKNOWN"),
                projected_points=150.0 + vorp,
                replacement_points=150.0,
                vorp=vorp,
                starter_rank=rank,
            )
        )
    return tuple(values)


def install_portfolio_demo(
    registry: LeagueRegistry,
    setup_store: LeagueSetupStore,
) -> LeagueProfile:
    scenario = build_demo_scenario()
    registry.save(scenario.profile)
    setup_store.save(scenario.setup)
    return scenario.profile


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Install the portfolio demo league.")
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()
    root = Path(args.data_root)
    profile = install_portfolio_demo(
        LeagueRegistry(root / "leagues"),
        LeagueSetupStore(root / "league_setup"),
    )
    print("Installed {0} ({1})".format(profile.league_name, profile.league_key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
