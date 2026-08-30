# Auction price: the three-input blend

Every price-sensitive recommendation (bid caps, nomination scoring, keeper
surplus) reasons about a player's **fair value**. Fair value is built from three
inputs:

1. **ML scenario price** — `src/scenario_price_model.py`. A gradient-boosted
   quantile model of what *this league* historically pays, given the player's
   FantasyPros rank + position, the auction stage, and the buyer's cash / open
   roster spots. Trained on 583 completed sales across Bishop Sycamore
   2023–2025 and GDFM 2026.
2. **Rankings value** — the FantasyPros / Sleeper-ECR-derived `baseline_value`
   already on every auction value (`src/auction_values.py`).
3. **Deterministic evidence** — personal need, bidder threat, positional
   scarcity, run-hot pressure, the legal-max ceiling, and the live-market
   calibration multipliers. Unchanged; applied *on top* of the blend by the
   existing engine (`src/recommendation.py`, `src/nomination_strategy.py`).

## How they combine

`src/scenario_fair_value.py::blend_fair_value`:

```
fair_value = w * ml_price + (1 - w) * rankings_value        (w = SCENARIO_ML_WEIGHT, default 0.60)
```

with a clean fallback to `rankings_value` whenever there is no ML price (no rank
match, model file missing, or pricing disabled).

`src/scenario_market_values.py::apply_scenario_fair_values` rewrites
`expected_market_value` on the market-value list with this blend. It runs in
both price pipelines — `app.py` (live cockpit) and
`draft_simulator.build_simulation_state` (Monte Carlo) — **immediately after
`calculate_historical_market_values` and before `apply_live_market_calibration`**,
so the live-learning multiplier layer still corrects the blended prior from
in-draft sales. Bidding and nomination both read the same `market_values` list,
so no per-engine wiring is needed.

### Buyer-state proxy

The model was trained on the *winning* team's pre-purchase cash / spots. At
inference the winner is unknown, so `contender_state()` uses the team at the
~75th percentile of cash-per-open-spot among teams that can still buy — winners
skew rich, so this beats "my team" or the league average.

## Environment knobs

| Variable | Default | Effect |
|---|---|---|
| `SCENARIO_ML_PRICING` | on | `0` / `false` disables the blend entirely — recommendations revert to rankings-only. Master kill-switch for mid-draft use. |
| `SCENARIO_ML_WEIGHT` | `0.60` | ML share of the blend, clamped to `[0, 1]`. Walk-forward sweep puts the optimum at 0.6–0.7. |

## Backtest (walk-forward, each season predicted from earlier seasons only)

| | 2024 BS | 2025 BS | 2026 GDFM |
|---|---|---|---|
| Rank-neighbour baseline MAE | $12.4 | $9.6 | $9.1 |
| ML model MAE | $10.1 | $8.1 | $8.2 |
| 0.6 blend MAE (all seasons) | \_ | **$8.6** | \_ |
| Saved app market value MAE (GDFM) | | | $13.8 |

## The pipeline

`data/HISTORY_DATASET_FOR_ML.xlsx` → (manual) canonical CSVs in
`data/ml_pipeline/canonical/` → `python scripts/run_scenario_pipeline.py`
rebuilds `auction_state_features.csv`, the baseline, the walk-forward report,
and the deployed `data/ml_pipeline/models/scenario_price_model.joblib`.

- The xlsx → canonical conversion (`src/ml_history_dataset.py`) and the
  Sleeper-reconciled `opening_team_states.csv` are upstream **manual** steps.
- `scripts/tune_scenario_price_model.py --hyperparams --blend` reproduces the
  model / weight tuning.
- `python scripts/run_scenario_pipeline.py --live-sales <csv>` appends a partial
  in-progress draft for a one-off refit.

## Mid-draft retrain

`src/scenario_retrain.py` + the **"🔄 Retrain the model from this draft"**
button in Draft History. Replays the sales recorded so far into feature rows
(ranked from the live FantasyPros index), appends them to the 583 historical
sales, refits, and rewrites the model file. `ScenarioPriceInferenceService`
hot-reloads it on the next nomination via its mtime-keyed cache.

This is a break-glass tool — the live-market calibration layer already adapts
the blend every rerun, and a partial draft is thin, early-skewed data. Reach
for it only when the room is pricing very differently from history.
