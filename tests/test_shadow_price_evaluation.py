from types import SimpleNamespace

from src.shadow_price_evaluation import evaluate_shadow_prices


def _snapshot(player, sale_count, target, predicted, low=10, high=30, blend=None):
    return SimpleNamespace(
        player_name=player,
        target_value=target,
        roster_state={"sale_count": sale_count},
        context_state={
            "scenario_price_shadow": {
                "low": low,
                "predicted_price": predicted,
                "high": high,
                "model_version": "model-v1",
                "blend_target_value": blend,
            }
        },
    )


def test_shadow_evaluation_uses_latest_snapshot_before_sale():
    sales = [
        SimpleNamespace(sale_number=2, player_name="A.J. Brown", price=25),
        SimpleNamespace(sale_number=3, player_name="Other", price=10),
    ]
    snapshots = [
        _snapshot("AJ Brown", 0, 20, 21),
        _snapshot("A.J. Brown", 1, 23, 24, blend=25),
        _snapshot("A.J. Brown", 2, 99, 99),
    ]

    result = evaluate_shadow_prices(sales, snapshots)

    assert len(result.results) == 1
    assert result.results[0].app_target_value == 23
    assert result.results[0].shadow_predicted_price == 24
    assert result.app_mean_absolute_error == 2
    assert result.shadow_mean_absolute_error == 1
    assert result.blend_preview_mean_absolute_error == 0
    assert result.blend_preview_bias == 0
    assert result.interval_coverage == 1.0


def test_shadow_evaluation_ignores_snapshots_without_predictions():
    sale = SimpleNamespace(sale_number=1, player_name="Player", price=12)
    snapshot = SimpleNamespace(
        player_name="Player", target_value=10, roster_state={"sale_count": 0},
        context_state={},
    )

    result = evaluate_shadow_prices([sale], [snapshot])

    assert result.results == ()
    assert result.shadow_mean_absolute_error is None
