from src.scalable_simulator import SimulationPlayer, run_simulations


PLAYERS = tuple(
    SimulationPlayer("P{0}".format(index), "RB" if index % 2 else "WR", 8 + index, 2, 15 + index)
    for index in range(12)
)


def test_simulator_is_reproducible_and_reports_distributions():
    first = run_simulations(PLAYERS, budget=80, roster_spots=5, simulations=100, seed=42)
    second = run_simulations(PLAYERS, budget=80, roster_spots=5, simulations=100, seed=42)
    assert first == second
    assert len(first.player_price_distributions["P0"]) == 100
    assert 0.0 <= first.full_roster_rate <= 1.0


def test_simulator_scales_to_thousands_and_preserves_minimum_reserve():
    result = run_simulations(PLAYERS, budget=80, roster_spots=5, simulations=1000, seed=7)
    assert len(result.outcomes) == 1000
    assert all(outcome.spend <= 80 for outcome in result.outcomes)
    assert all(outcome.unspent_cash >= 0 for outcome in result.outcomes)
