# Deterministic math reference

Every dollar figure, score, cap, grade, and legal check in the Draft Copilot
is a **pure function of typed inputs**. No randomness (except explicitly seeded
simulation), no wall-clock dependence (except explicit recency decay against a
supplied `as_of`), and no LLM in the numeric path. The same inputs always
produce the same output, and each output ships with an `explanation` string and
`reason_codes`/`reasons` so a number can be traced back to the terms that
produced it.

This document is the authoritative catalog of those formulas: the constants,
the arithmetic, and the intent behind each term. Module paths are given so the
code and this document can be checked against each other.

- [Conventions](#conventions)
- [1. Projections and league scoring](#1-projections-and-league-scoring) — `src/projections.py`, `src/sleeper_fantasypros_fallback.py`
- [2. Replacement level and VORP](#2-replacement-level-and-vorp) — `src/valuation.py`
- [3. Baseline auction value](#3-baseline-auction-value) — `src/auction_values.py`
- [4. Historical market blend](#4-historical-market-blend) — `src/historical_market.py`
- [5. Evidence classification and recency decay](#5-evidence-classification-and-recency-decay) — `src/evidence_quality.py`, `src/context_interpreter.py`
- [6. Context valuation adjustment](#6-context-valuation-adjustment) — `src/context_valuation.py`
- [7. Live bid recommendation](#7-live-bid-recommendation) — `src/recommendation.py`
- [8. Price thresholds and the dynamic cap](#8-price-thresholds-and-the-dynamic-cap) — `src/price_thresholds.py`, `src/dynamic_cap.py`
- [9. Bidder threat and run-hot](#9-bidder-threat-and-run-hot) — `src/bidder_threat.py`, `src/run_hot.py`
- [10. Room and league inflation](#10-room-and-league-inflation) — `src/league_inflation.py`
- [11. Ranking ensemble](#11-ranking-ensemble) — `src/ranking_ensemble.py`
- [12. Keeper age curve](#12-keeper-age-curve) — `src/keeper_recommendation.py`
- [13. Keeper recommendation score](#13-keeper-recommendation-score) — `src/keeper_recommendation.py`
- [14. Keeper economics projection](#14-keeper-economics-projection) — `src/keeper_economics.py`, `src/keeper_domain.py`
- [15. Keeper combination optimizer](#15-keeper-combination-optimizer) — `src/keeper_optimizer.py`
- [16. Snake draft: pick order, roster need, draft board](#16-snake-draft-pick-order-roster-need-draft-board) — `src/snake_draft.py`, `src/context_store.py`
- [17. Pass regret risk](#17-pass-regret-risk) — `src/pass_regret.py`
- [18. Purchase and pass grading](#18-purchase-and-pass-grading) — `src/purchase_grading.py`, `src/pass_grading.py`
- [19. Manager tendencies](#19-manager-tendencies) — `src/manager_tendencies.py`
- [20. Year-over-year calibration](#20-year-over-year-calibration) — `src/year_over_year_calibration.py`
- [21. Strategy weights](#21-strategy-weights) — `src/strategy_profile.py`
- [Testing the math](#testing-the-math)

---

## Conventions

- **`clamp(x, lo, hi)`** = `max(lo, min(hi, x))`. Where a range is not stated it
  is `[0, 1]`.
- **Shares / fractions** are unitless `[0, 1]`. **Scores** are usually `0–100`.
  **Signals** are `[-1, 1]`. **Dollars** are integers unless a projection.
- **VORP** = Value Over Replacement Player, in projected fantasy points.
- **`normalize_player_name`** (`src/auction_pool.py`) lower-cases, strips
  punctuation/suffixes, and is applied before every cross-source join so
  "D.J. Moore", "DJ Moore", and "dj moore" reconcile.
- Rounding is applied only at the boundary of a result object (`round(x, 2)`,
  `int(round(x))`), never mid-computation, so intermediate precision is kept.
- League structure defaults (`src/league_config.py`): 12 teams, 18 roster
  spots, starting lineup `QB / RB×2 / WR×2 / TE / FLEX×2 / K / DEF`, 8 bench,
  2 IR, `$1` minimum bid, `$400` base budget, 6 max keepers, `$11` keeper
  escalation. These are **defaults / bootstrap values**; the live
  `LeagueProfile` (`src/league_profile.py`) carries the actual per-league
  numbers and nothing branches on a hard-coded league.

---

## 1. Projections and league scoring

`src/projections.py` — `score_offensive_projection`, `normalize_fantasypros_projections`

FantasyPros supplies raw projected stat lines. Each is re-scored against the
**league's own scoring settings** so a value reflects your league, not
half-PPR.

```
custom_points = Σ  stat_value(k) · scoring_weight(k)
                k
```

over the supported categories `SCORING_STAT_MAP`: passing yards/TD/INT, rushing
yards/TD, receptions, receiving yards/TD, fumbles lost, and the yardage
milestone bonuses (`bonus_pass_yd_400`, `bonus_rush_yd_100/200`,
`bonus_rec_yd_100/200`).

- **Unconfigured category → standard default.** If a league's settings never
  mention a category (distinct from setting it to `0`), `STANDARD_SCORING_DEFAULTS`
  fills it: `pass_yd 0.04`, `pass_td 4`, `pass_int −2`, `rush_yd 0.1`,
  `rush_td 6`, `rec_yd 0.1`, `rec_td 6`, `fum_lost −2`. This exists because
  off-platform leagues historically recorded only reception points.
- **`custom_scoring_exact`** is `False` and a `scoring_warnings` entry is added
  when a non-zero league rule can't be reproduced from the available raw stats
  (`unsupported_offensive_scoring_keys`). The value is still produced; the
  caller is told it's approximate.
- **K / DEF** cannot be scored exactly (bracketed points-allowed, no raw
  component stats), so they fall back to the FantasyPros half-PPR points with a
  warning.
- `scoring_breakdown` retains the per-category point contribution for display.

### 1.1 Sleeper fallback (when FantasyPros is down)

`src/sleeper_fantasypros_fallback.py` — `build_projections`,
`fetch_sleeper_projections`

When FantasyPros is rate-limited/blocked and there's no cached pull, the app
rebuilds projections from Sleeper's own per-player season stat lines rather
than going dark. `fetch_sleeper_projections` keeps the **full raw stats
dict** (not just Sleeper's generic `pts_half_ppr` total), and `build_projections`
translates it through the same `SCORING_STAT_MAP` (§1) and calls the same
`score_offensive_projection` — so a fallback-sourced projection is scored
against the league's real settings identically to a FantasyPros-sourced one,
not a generic half-PPR proxy silently standing in for it. Only when
`scoring_settings` is entirely unavailable does it fall back further, to
Sleeper's raw half-PPR total, with `custom_scoring_exact=False`.

---

## 2. Replacement level and VORP

`src/valuation.py` — `calculate_replacement_levels`, `calculate_player_values`

**Replacement level** is the projected points of the *first player at a
position who is not a starter* across the whole league.

1. **Core starter demand** per position = `starters_in_lineup × num_teams`.
   With the default lineup and 12 teams: QB 12, RB 24, WR 24, TE 12.
2. **Flex allocation is dynamic.** For each flex slot in the lineup
   (`FLEX`/`W/R/T` → RB/WR/TE, `SUPER_FLEX`/`OP` → +QB, `REC_FLEX` → WR/TE,
   `WRRB_FLEX` → RB/WR), and for each team, the highest-projected still-unclaimed
   eligible player is taken. **Narrower slots are filled first** (sorted by
   eligibility-set size) so a WR/TE-only slot isn't consumed by a player who was
   only needed for a later superflex opening.
3. **Final demand** = core demand + flex players actually allocated to that
   position.
4. **Replacement points** = `custom_points` of the player at index
   `final_demand` in that position's descending-points list (or the last
   player if the pool is shorter).

```
vorp(player) = player.custom_points − replacement_points[player.position]
```

`starter_rank` is the 1-indexed position rank. VORP can be negative; downstream
consumers `max(0, vorp)` where a floor is wanted.

---

## 3. Baseline auction value

`src/auction_values.py` — `calculate_auction_values`

Converts VORP + dynasty rank into a **dollar** value, constrained by the actual
money and roster spots left in the room.

**Model weights:** `CURRENT_WEIGHT = 0.60`, `FUTURE_WEIGHT = 0.40`.

### 3.1 The auction economy

```
total_auction_cash   = Σ team.auction_cash
total_open_spots     = Σ team.open_roster_spots
reserve_dollars      = Σ team.required_reserve         (default: open_spots · $1)
minimum_bid          = min(team.minimum_auction_bid)   (default $1)
discretionary_dollars = max(0, total_auction_cash − reserve_dollars)
```

`discretionary_dollars` is the money that will actually be *spent above the
minimum* — the pool the model distributes.

### 3.2 Expected draft pool

`select_expected_draft_pool` ranks available players by FantasyPros half-PPR ECR
(unranked players appended in original order) and keeps the top
`total_open_spots`. Only these players are "expected to be drafted" and
therefore assigned value above the minimum bid.

### 3.3 Current and future raw scores

For each expected player:

- **Current:** `current_raw = max(0, vorp)`.
- **Future:** from dynasty ECR, mapped into this league's remaining pool and
  squared to separate true elite assets:

  ```
  percentile  = max(0, (total_open_spots + 1 − dynasty_ecr) / total_open_spots)
  future_raw  = percentile²
  ```

  K/DEF and players without a dynasty rank get `future_raw = 0`.

### 3.4 Normalize, blend, price

Each raw vector is normalized to a **share** of its column total:

```
current_share = current_raw / Σ current_raw
future_share  = future_raw  / Σ future_raw
blended_share = 0.60 · current_share + 0.40 · future_share
```

```
baseline_value = minimum_bid + discretionary_dollars · blended_share      (expected players)
baseline_value = minimum_bid                                              (everyone else)
```

Because shares sum to 1, `Σ baseline_value ≈ total_auction_cash` by
construction — the board is always priced to the money in the room.

---

## 4. Historical market blend

`src/historical_market.py` — `calculate_historical_market_values`

`baseline_value` is what the model thinks a player is worth. **Expected market
value** nudges that toward what *this league has historically actually paid*.

```
sample_confidence  = n / (n + 20)                 n = usable historical sales for the peer group
historical_weight  = 0.35 · sample_confidence     (MAX_HISTORICAL_WEIGHT = 0.35)

expected_market_value = (1 − historical_weight) · baseline_value
                      +      historical_weight  · historical_expected
```

- Historical influence is **capped at 35%** and only approached with a large
  sample — the model never blindly chases historical overpayment.
- With no usable history, `expected_market_value = baseline_value`.
- `historical_expected` comes from position/tier price curves fit to prior
  drafts (`build_historical_market_model`), which requires
  `MIN_USABLE_YEAR_SALES = 20` sales in a season for that season to count.
- Player-name aliases (`HISTORICAL_PLAYER_ALIASES`) repair spreadsheet typos
  before the join.

---

## 5. Evidence classification and recency decay

### 5.1 Evidence class → weight

`src/evidence_quality.py` — `classify_evidence`

| Class | Weight | Assigned when |
|---|---|---|
| `HARD_EVIDENCE` | **1.00** | explicit class from a normalized source, `verified` flag, or `source_type ∈ {injury, depth_chart, official_news}` |
| `STRONG_ANALYTICAL_SIGNAL` | **0.75** | `source_type ∈ {usage, beat_report, news}` **and** `confidence ≥ 0.60` |
| `SOFT_SIGNAL` | **0.40** | everything else (unverified, low-confidence, social, narrative) |

### 5.2 Event extraction and recency weight

`src/context_interpreter.py`

Documents are parsed into typed **events** with a `dimension`
(`role` / `usage` / `health` / `dynasty`), an `impact ∈ [−1, 1]`, and an
`occurred_at`. Each event type has a base half-life (`BASE_HALF_LIFE_DAYS`),
e.g. `INJURY_OUT` 14d, `USAGE_UP/DOWN` 30d, `ROLE_UP/DOWN` 60d, `TEAM_CHANGE`
120d, `INJURY_SEVERE` 180d, `DYNASTY_UP/DOWN` 180d.

**Off-season stretch:** during the off-season, structural signals decay slower —
`×2.0` for dynasty, `×1.8` for role/depth/team-change, `×1.35` for injuries,
`×1.25` otherwise (`adjusted_half_life`).

**Exponential decay** (`event_recency_weight`):

```
decay  = ln(2) / half_life_days
weight = exp(−decay · age_days)            (0.50 if the event has no date)
```

`event_weight` multiplies this recency weight by the evidence-class weight and
event confidence.

### 5.3 State supersession

`resolve_event_states` lets a newer, more specific event retire an older one
(`INJURY_RESOLVED` supersedes `INJURY_OUT`; a newer depth-chart reading
supersedes an older one) so a stale injury report doesn't outweigh its own
resolution.

### 5.4 Dimension scores and confidence

```
dimension_score(d) = Σ (impact · event_weight)  /  Σ event_weight        (over events with dimension d)
```

Each is clamped to `[−1, 1]`.

```
overall_context_score = clamp( 0.35·role + 0.25·usage + 0.25·health + 0.15·dynasty , −1, 1)

evidence_confidence   = 1 − exp(−Σ event_weight / 1.6)
diversity_multiplier  = min(1.0, 0.76 + 0.07 · number_of_distinct_dimensions)
confidence            = clamp(evidence_confidence · diversity_multiplier, 0, 0.97)
```

Confidence rises with **total evidence mass** and with **corroboration across
independent dimensions**, and is hard-capped at `0.97` — the engine never claims
certainty.

---

## 6. Context valuation adjustment

`src/context_valuation.py` — `calculate_context_valuation_adjustment`

Turns the context summary into a **bounded percentage adjustment** on a player's
deterministic ceiling. This is the *only* path by which news/injury information
touches a dollar figure, and it is capped hard.

### 6.1 Caps and confidence gate

```
MAX_POSITIVE_ADJUSTMENT_PCT = +0.06
MAX_NEGATIVE_ADJUSTMENT_PCT = −0.08
MIN_CONTEXT_CONFIDENCE      = 0.35        below this → no change at all
FULL_CONTEXT_CONFIDENCE     = 0.85        at/above this → full strength
```

```
strength = clamp( (confidence − 0.35) / (0.85 − 0.35) , 0, 1)
```

If `strength ≤ 0`, the adjustment is `0.0` and the ceiling is unchanged (only
the legal max can still cap it).

### 6.2 Current / future / blended signals

```
current_signal = clamp( 0.30·role + 0.25·usage + 0.45·health , −1, 1)
future_signal  = clamp( 0.25·role + 0.10·usage + 0.20·health + 0.45·dynasty , −1, 1)
blended_signal = clamp( 0.60·current_signal + 0.40·future_signal , −1, 1)
```

Health dominates the current-season view; dynasty dominates the future view.

### 6.3 Raw percentage and material-event floors

```
raw_pct = blended_signal · (0.06 if blended_signal ≥ 0 else 0.08) · strength
```

Then `apply_material_event_rules` imposes **floors** (most negative wins) and
**ceilings** for specific active events, each scaled by `strength`:

| Active event | Effect on `raw_pct` |
|---|---|
| `INJURY_SEVERE` | `≤ −0.08 · strength` |
| `INJURY_OUT` | `≤ −0.05 · strength` |
| `INJURY_LIMITED` | `≤ −0.025 · strength` |
| `ROLE_DOWN` | `≤ −0.03 · strength` |
| `USAGE_DOWN` | `≤ −0.02 · strength` |
| `DYNASTY_DOWN` | `≤ −0.025 · strength` |
| `ROLE_UP` (no unresolved severe/out injury) | `≥ +0.02 · strength` |
| `USAGE_UP` (") | `≥ +0.0125 · strength` |
| `DYNASTY_UP` (") | `≥ +0.015 · strength` |

Positive role/usage/dynasty bumps are **suppressed while a severe or out injury
is unresolved** — the engine won't talk itself into optimism over an injured
player.

### 6.4 Apply

```
bounded_pct       = clamp(raw_pct, −0.08, +0.06)
adjusted_ceiling  = max(1, round(base_ceiling · (1 + bounded_pct)))
adjusted_ceiling  = min(adjusted_ceiling, legal_max)        if legal_max given
```

The result records `adjustment_dollars`, `adjustment_pct`, both signals, the
confidence, `capped_by_context_limit`, `capped_by_legal_max`, up to 6 plain
`reasons`, and per-signal `signal_details` with source document IDs.

---

## 7. Live bid recommendation

`src/recommendation.py` — `calculate_bid_recommendations`

Produces, per available player, a defensible personal ceiling (`do_not_exceed`)
plus `target_value / soft_cap / hard_cap`.

**Cap constant:** `MAX_MARKET_PREMIUM = 1.20`.

### 7.1 Scarcity

`calculate_scarcity` — for a player at position rank `i` (players sorted by VORP
descending within position):

```
vorp_gap      = max(0, vorp[i] − vorp[i+1])
gap_score     = clamp( vorp_gap / max(|vorp[i]|, 25) )
nearby        = count of following players within 15 VORP of vorp[i]  (until the first that isn't)
alt_pressure  = 1 − clamp(nearby / 4)
scarcity      = clamp( 0.70·gap_score + 0.30·alt_pressure )
```

Last player at a position → `scarcity = 1.0`. The "next best" player is also
returned as the named PASS alternative.

### 7.2 Personal ceiling

```
fair_anchor            = 0.65 · expected_market + 0.35 · baseline_value
need_multiplier        = 0.92 + 0.13 · need                 (need ∈ [0,1] from the roster-need profile)
scarcity_multiplier    = 1.00 + 0.10 · scarcity
competition_premium    = 0.03 · threat_fraction · need · scarcity
competition_multiplier = 1.00 + competition_premium
run_hot_multiplier     = 1.00 + 0.05 · run_hot_pressure · need · scarcity

raw_ceiling  = fair_anchor · need_multiplier · scarcity_multiplier
             · competition_multiplier · run_hot_multiplier

raw_ceiling  = min(raw_ceiling, expected_market · 1.20)     # never pay >20% over market
do_not_exceed = max(1, round( min(raw_ceiling, legal_max_bid) ))
value_edge    = do_not_exceed − expected_market
```

Key design points:

- **Bidder competition alone cannot make you overpay.** `competition_premium`
  is a product of `threat · need · scarcity`; if you don't need the player or
  alternatives exist, competition contributes ~nothing.
- **The `1.20 × market` cap** is the runaway-overpayment stop, applied before
  the legal max.
- `legal_max_bid` (= team cash − reserve for remaining spots) is the final hard
  constraint.

### 7.3 Strategy label

`recommendation_strategy(expected_market, ceiling, need)`:

| Condition | Label |
|---|---|
| `ceiling ≥ 1.08 · market` and `need ≥ 0.80` | `AGGRESSIVE BUY` |
| `ceiling ≥ 1.08 · market` | `PURSUE` |
| `ceiling ≥ market` | `BUY AT MARKET` |
| `ceiling ≥ 0.90 · market` | `DISCIPLINED` |
| else | `LET SOMEONE ELSE PAY` |

`reasons` are assembled from thresholds on need (`≥0.95` major, `≥0.75`
meaningful, `≤0.25` low), scarcity (`≥0.70` / `≥0.40` / `≤0.20`), threat
(`≥75` / `≥60`), model-vs-market divergence (`±8–15%`), legal-max binding, and
the named next-best alternative.

---

## 8. Price thresholds and the dynamic cap

### 8.1 Static thresholds

`src/price_thresholds.py` — `build_live_price_thresholds`

```
hard   = max(1, min(deterministic_ceiling, legal_max_bid))
target = clamp( round((expected_market_value + baseline_value) / 2) , 1, hard)
soft   = clamp( round(target + 0.65 · (hard − target)) , target, hard)
```

`target` = the midpoint of market and model value; `soft` sits 65% of the way
from target to the hard cap; `hard` = deterministic legal ceiling.

`evaluate_current_bid` maps a live bid into a zone: `VALUE` (< target),
`TARGET` (< soft), `SOFT CAP` (< hard), `HARD CAP` (= hard), `PASS` (> hard),
with `should_bid = bid < hard_cap` and `dollars_to_hard_cap`.

`constrain_thresholds` re-clamps all three down if a later, lower final hard cap
arrives.

### 8.2 Dynamic cap adjustment

`src/dynamic_cap.py` — `adjust_dynamic_cap`

Adjusts a base cap by a **bounded sum of small percentage components**. Each
input is clamped to `[0,1]` and centered at `0.5`.

| Component | Formula | Range |
|---|---|---|
| `roster_need` | `0.06 · (need − 0.5)` | ±0.03 |
| `scarcity` | `0.06 · (scarcity − 0.5)` | ±0.03 |
| `alternatives` | `−0.025` if a comparable alternative exists, else `+0.025` | ±0.025 |
| `cash` | `0.03 · (cash_flexibility − 0.5)` | ±0.015 |
| `auction_stage` | `0.035 · (stage − 0.5) · (scarcity − 0.25)` | small |
| `room_inflation` | `clamp((inflation_index − 1) · 0.12, −0.03, 0.03)` | ±0.03 |
| `strategy_future` | `0.03 · (future_value_score − 0.5) · future_weight` | small |
| `context` | reported only (already baked into `base_cap`) | 0 |

```
total_pct    = clamp( Σ components (excluding context) , −0.12, +0.12)
adjusted_cap = max(1, min( legal_max_bid , round(base_cap · (1 + total_pct)) ))
```

Total swing is **capped at ±12%**, and context is reported but never
double-counted because it is already in `base_cap` (from §6).

---

## 9. Bidder threat and run-hot

### 9.1 Bidder threat

`src/bidder_threat.py` — `calculate_bidder_threats`

Per opponent, per player, a `threat_score` on `0–100` (never a predicted bid):

```
score = 0.35·need_score
      + 0.25·affordability
      + 0.15·cash_strength
      + 0.15·aggressiveness_score
      + 0.10·position_tendency
```

- **Star multiplier:** for elite assets, `score ·= 0.90 + 0.20·star_chase`.
- **Suppression:** if `expected_market > 1` and `team.max_bid < 0.50 ·
  expected_market`, `score ·= 0.60` — teams that can't realistically get near
  the closing price are damped.
- `threat_score = clamp(score) · 100`.

`aggressiveness_score`, `position_tendency`, and `star_chase` each default to
`0.50` (neutral) when there's no historical read on that manager, and are pulled
toward observed behavior otherwise. `need_score` comes from the opponent's
still-open starting slots and roster construction (`build_team_need_profiles`).

### 9.2 Run-hot

`src/run_hot.py` — `detect_run_hot`

Flags a positional tier where **multiple cash-rich opponents are converging on
too few players**.

```
competitors = opponents with cash_strength ≥ 0.65
              and this position in their likely_positions
              and this tier in their likely_tiers

fire only if  len(competitors) ≥ 2  and  available ≤ len(competitors)

pressure = min(1.0,  len(competitors) / (available + 1))
```

`position_pressure[pos]` = the max pressure across that position's tiers, and
feeds `run_hot_multiplier` in §7.2. Tier cutoffs (`build_available_tier_counts`):
`elite ≥ $40`, `starter ≥ $15`, else `depth`.

---

## 10. Room and league inflation

`src/league_inflation.py`

```
inflation_index = actual_price / expected_price          (1.0 when expected ≤ 0)
```

- **`build_league_inflation_model`** aggregates historical observations into an
  overall index plus `(season, position, tier, stage)` segments.
- **`calculate_live_room_inflation`** does the same for completed sales *in the
  current draft*: `room_inflation_index = Σ actual / Σ expected` over mapped
  sales, plus a per-position breakdown. Sales whose player can't be matched to
  an expected value are returned in `unmapped_sales` rather than silently
  dropped. Stage is assigned by sale index: `early` (< ⅓), `middle` (< ⅔),
  `late`; tier by expected price (`elite ≥ 40`, `starter ≥ 15`, else `depth`).

This index is what feeds `room_inflation` in the dynamic cap (§8.2), where its
effect is clamped to ±3%.

---

## 11. Ranking ensemble

`src/ranking_ensemble.py` — `build_ranking_ensemble`

```
ensemble_rank        = position in the ascending sort of  average_source_rank
average_source_rank  = mean of one rank per source
rank_disagreement    = max(source_ranks) − min(source_ranks)     (0 with one source)
```

- **One vote per source.** A later duplicate row from the same source replaces
  the earlier one deterministically; it does not increase that source's weight.
- Sources start **equal-weighted** (`Sleeper` search rank, `FantasyPros`
  half-PPR ECR). A missing configured source just drops out and the rest are
  effectively renormalized; a `warning` is emitted.
- **Disagreement is informational** — it is surfaced, not turned into a risk
  penalty.

---

## 12. Keeper age curve

`src/keeper_recommendation.py` — `keeper_age_adjustment(position, age)`

A deterministic future-value multiplier. `age is None → 1.0`.

| Age | QB | RB | WR | TE |
|---|---|---|---|---|
| ≤ 23 | 1.08 (≤27) | **1.12** | 1.10 (≤24) | 1.08 (≤25) |
| 24 | 1.08 | 1.05 (≤25) | 1.10 | 1.08 |
| 25 | 1.08 | 1.05 | 1.03 (≤27) | 1.08 |
| 26 | 1.08 | 0.95 | 1.03 | 1.02 (≤29) |
| 27 | 1.08 | 0.85 | 1.03 | 1.02 |
| 28 | 1.00 (≤33) | `max(0.55, 0.80 − 0.05·(age−28))` | 0.95 (≤29) | 1.02 |
| 29 | 1.00 | ↓ | 0.95 | 1.02 |
| 30+ | 1.00 → 0.90 (≤35) → 0.78 | ↓ | `max(0.65, 0.90 − 0.05·(age−30))` | 0.92 (≤31) → 0.80 |

RB decline is steepest and floored at `0.55`; WR decline is floored at `0.65`.
Unknown positions → `1.0`.

---

## 13. Keeper recommendation score

`src/keeper_recommendation.py` — `recommend_keeper`

Inputs are clamped: `current_value, future_value ∈ [0,100]`,
`scarcity, roster_fit ∈ [0,1]`.

```
age_adjustment  = keeper_age_adjustment(position, age)
adjusted_future = clamp(future_value · age_adjustment, 0, 100)

neutral_value   = 0.45·current_value + 0.45·adjusted_future + 0.10·(scarcity·100)

auction_ceiling = max(minimum_bid, auction_budget · 0.30)      # MAX_KEEPER_AUCTION_BUDGET_SHARE
auction_value   = minimum_bid + (auction_ceiling − minimum_bid) · (neutral_value / 100)
surplus         = auction_value − keeper_cost
```

`keeper_cost` is resolved by `src/keeper_domain.py`:
`explicit` → as entered; `returning` → `prior_year_cost + annual_escalation`
(`$11`); `midseason_pickup` → `midseason_pickup_cost` (`$10`).

```
strategy_value  = current_weight·current_value + future_weight·adjusted_future
surplus_signal  = clamp(50 + 50 · surplus / max(1, auction_ceiling), 0, 100)

strategy_score  = clamp( 0.55·strategy_value
                       + 0.20·surplus_signal
                       + 0.15·(scarcity·100)
                       + 0.10·(roster_fit·100) , 0, 100)
```

### Decision

```
KEEP        if surplus ≥ 0  and  strategy_score ≥ 60
PASS        if surplus < −0.10 · auction_ceiling  or  strategy_score < 45
BORDERLINE  otherwise
```

`reason_codes` fire on: surplus sign, `current_value ≥ 65`, `adjusted_future ≥
65`, `age_adjustment >1.02 / <0.98`, `scarcity ≥ 0.70`, `roster_fit ≥ 0.80`,
`strategy_value ≥ 65`, and missing current/future data.

### Adapter

`build_keeper_recommendations` derives the numeric inputs from repository data:
`current_value = 100 · vorp / max_vorp`; `scarcity = vorp / position_max_vorp`;
`future_value` from explicit values or `100 · (dynasty_ceiling + 1 −
dynasty_ecr) / dynasty_ceiling`; `roster_fit` from `_roster_fit_score` (1.0 if a
direct starting-slot gap, 0.80 if only a flex/superflex gap, 0.45 otherwise).
Results are sorted by `(−strategy_score, −surplus, name)`.

---

## 14. Keeper economics projection

`src/keeper_economics.py` — `project_keeper_economics`

A deterministic 2–3 year contract projection. Year 1 is the upcoming season.

```
projected_cost(year_i)   = current_cost + i · annual_escalation       (i = 0-indexed)
yearly_surplus(i)        = projected_player_value(i) − projected_cost(i)
cumulative_surplus       = running Σ yearly_surplus
```

**Strategy weighting** spreads the future weight across the future years:

```
weights = ( current_weight,  future_weight/(H−1),  …  )      H = horizon years
strategy_adjusted_surplus(i) = yearly_surplus(i) · weights[i]
```

- **`break_even_year`** = first year `yearly_surplus ≤ 0` (else "beyond
  horizon").
- **`keeper_runway_years`** = count of leading consecutive positive-surplus
  years (stops at the first non-positive year).

A mid-season pickup enters at `$10` in year 1 and escalates by `$11`/yr from
year 2. Horizon must be 2 or 3 (`KeeperDomainRules.validate`).

---

## 15. Keeper combination optimizer

`src/keeper_optimizer.py` — `optimize_keeper_combinations`

**Exhaustively** enumerates every legal keeper set of size 4, 5, and 6
(`TARGET_KEEPER_COUNTS`, bounded by `max_keepers`, roster size, and candidate
count) via `itertools.combinations`.

### Feasibility filter (`_build_scenario`)

```
keeper_spend    = Σ keeper.cost
remaining_cash  = pre_keeper_budget − keeper_spend
remaining_spots = roster_size − keeper_count
minimum_reserve = remaining_spots · minimum_bid

reject if  remaining_spots < 0  or  remaining_cash < minimum_reserve
```

Unused keeper slots become auction roster spots — **never bonus cash**.

### Objective

```
current_value   = Σ keeper.current_value
future_value     = Σ keeper.age_adjusted_future_value
surplus          = Σ keeper.surplus
opportunity_cost = Σ max(0, surplus) over the keepers you did NOT keep
strategy_value   = current_weight·current_value + future_weight·future_value
roster_fit       = clamp(0.70·avg(keeper.roster_fit) + 0.30·core_position_coverage)

objective_score  = surplus + 0.10·strategy_value + 5.0·roster_fit − opportunity_cost
```

The best scenario per count is kept (tie-break:
`objective, surplus, roster_fit, remaining_cash, names`), then the overall
recommendation is the best across counts, tie-breaking toward **fewer keepers**
(`−keeper_count`) so it doesn't hoard slots for a marginal gain.
`discretionary_cash = remaining_cash − minimum_reserve` is reported per
scenario.

---

## 16. Snake draft: pick order, roster need, draft board

`src/snake_draft.py` (pure math, fully tested); `src/context_store.py` for the
one overlay (§16.6) that reads live-ingested data instead of derived values.

### 16.1 Serpentine pick math

```
round        = (pick_no − 1) // team_count + 1
pos_in_round = (pick_no − 1) %  team_count + 1
slot         = pos_in_round            if round is odd
             = team_count − pos_in_round + 1   if round is even
```

`pick_no_for_slot` is the exact inverse. Both are pure integer arithmetic and
fully tested (`tests/test_snake_draft.py`).

### 16.2 Roster need

`build_roster_need` — from what a manager has drafted:

```
starter_gaps[pos] = max(0, required_starters[pos] − filled[pos])
```

Flex gaps are computed after assigning surplus starters greedily to the
narrowest flex slot first (same discipline as §2). `flex_gap` = Σ unfilled flex
slots; `open_spots = max(0, roster_size − total_filled)`.

### 16.3 Draft board

`build_draft_board` — reuses the same `PlayerValue` VORP as the auction cockpit;
no dollar concept.

```
need_bonus     = 6.0   if this position fills an open starting slot   (NEED_BONUS_STARTER)
               = 3.0   elif it fills an open flex slot                (NEED_BONUS_FLEX)
               = 0.0   otherwise

remaining[pos] = count of undrafted players at `pos` with vorp > 0
                 (i.e. still above replacement level)

scarcity_bonus = SCARCITY_WEIGHT · max(0, SCARCITY_FLOOR − remaining[pos]) / SCARCITY_FLOOR
               (SCARCITY_WEIGHT = 4.0, SCARCITY_FLOOR = 10 — zero once ≥ 10
                startable players remain at that position, ramping linearly
                toward 4.0 as the position empties out)

utility        = vorp + need_bonus + scarcity_bonus
```

Sorted by `utility` descending. `scarcity_bonus` is recomputed against the
*live* undrafted pool on every call (it is a function of `player_values` and
`drafted_player_names`, not a stored field), so it reacts in real time to
positional runs regardless of which position is running out — it is not
hard-coded to any one position. It generalizes the finding of an ADP-variance
Monte Carlo draft simulation (sampling each player's slot from
`Normal(average_rank, rank_stddev)` and comparing a fixed-position-priority
rule against pure best-player-available across thousands of simulated
12-team/PPR/2-FLEX drafts): once a position's startable depth drops into
single digits, taking the best remaining player at that position beats a
marginally-higher-VORP player elsewhere, both in expected value and in
variance. The simulation is exploratory tooling (run ad hoc, not part of the
codebase); `scarcity_bonus` is the permanent, generalized result of it.

### 16.4 Remaining-roster plan

`optimize_snake_roster_plan` — a **beam search** (`beam_width = 60`) over slot
assignments. Unlike the auction optimizer there is no cash trade-off (every
remaining pick is "free"), so it maximizes `Σ utility · slot_multiplier` subject
to each player being used once, inserting a `(best available at pick time)`
filler when a slot has no eligible candidate left.

### 16.5 Bye-week collision warning

`load_bye_weeks` / `bye_week_stack_warnings` — a **display overlay**, deliberately
excluded from `utility` (§16.3). A bye collision your bench can absorb later in
the draft shouldn't talk a manager out of the best player on the board right
now; surfacing it as a warning keeps the trade-off with the human.

```
my_byes[week]   = count of the viewer's already-drafted players on that bye
warn(candidate) if my_byes[candidate.bye_week] ≥ stack_threshold (default 2)
                   → "you'd have {my_byes[week] + 1} rostered players out that week"
```

Bye weeks are read from the current season's FantasyPros rankings export
(`data/ml_pipeline/fantasypros_{season}_*_draft_rankings.csv`, resolved by glob
so the loader is season-agnostic). Player names are matched via the shared
`normalize_player_name` (`src/auction_pool.py`) so naming variance between
Sleeper and FantasyPros (suffixes, punctuation) doesn't silently drop a match.
Missing or malformed CSV → `{}`, never an exception: this feature is strictly
additive over the board it decorates.

### 16.6 Recent injury/news flag

`ContextStore.get_recent_flag` (`src/context_store.py`) — a second display
overlay, sourced from `data/player_context.db` (the same ingested
injury/depth-chart/news corpus §5's evidence classification runs over
elsewhere in the app).

```
flag(player) = title of the most recent context_documents row where
                 player_name = player
                 AND source_type IN ('injury', 'news')
                 AND published_at ≥ now − 21 days
               ORDER BY published_at DESC LIMIT 1
             = None if no such row (silently — DB errors and name misses
               both degrade to "no flag", never a broken board)
```

Exact-match on `player_name` (no normalization) — a naming mismatch with the
ingestion source just means the flag doesn't surface for that player, which is
the acceptable failure mode for a nice-to-have overlay.

### 16.7 Runout-risk (survival probability)

`load_adp_distribution` / `survival_probability` — a closed-form stand-in for a
full Monte Carlo simulation (§16.3's exploratory tooling), cheap enough to run
inline on every board row every render.

```
target_pick_no = next_pick_no_for_slot(current_pick_no, viewer_slot, team_count)
                 (first future pick_no whose serpentine slot is the viewer's —
                 §16.1's slot_for_pick_no walked forward pick by pick)

z              = (target_pick_no − average_rank) / max(rank_stddev, 0.5)
P(survive)     = 1 − Φ(z)                          (Φ = standard normal CDF)
```

Treats a player's true draft position as `Normal(average_rank, rank_stddev)` —
both published per-player by FantasyPros ECR, read from the same rankings CSV
as §16.5. This is an **independent-per-player** approximation: it does not
model that picks are without replacement across the field, so it answers "how
worried should I be about this one player" rather than "what's the joint
probability of the board falling a specific way" (that joint question is what
the full Monte Carlo simulation is for). `viewer_slot` is resolved once in
`build_snake_draft_state` from the live draft's `slot_to_roster_id` /
`roster_id_to_manager` maps, so it is correct even before the viewer has made
a single pick.

### 16.8 Live team value leaderboard

`build_team_value_leaderboard` — sums each manager's drafted picks by this
league's own `PlayerValue.vorp` (§2), not generic ADP:

```
total_vorp[manager] = Σ vorp(player)  for player in manager's drafted picks,
                       matched by normalize_player_name; unmatched picks
                       contribute 0 rather than raising
```

Sorted by `total_vorp` descending. Because it reuses the same VORP the draft
board ranks by, it reflects *this league's* scoring and roster construction
(§2's replacement levels), unlike a cross-league ECR-based comparison — but it
is a live, in-progress read of picks made so far, not a season forecast.

---

## 17. Pass regret risk

`src/pass_regret.py` — `calculate_pass_regret_risk`

```
competitor_value = clamp(competitor_pressure / 100)
alternative_risk = 1 − max(alt.availability_probability)
tier_drop        = clamp( (player_vorp − max(alt.vorp)) / max(1, |player_vorp|) )

score = 100 · ( 0.30·scarcity
              + 0.25·roster_need
              + 0.20·competitor_value
              + 0.15·alternative_risk
              + 0.10·tier_drop )

level = HIGH   if score ≥ 67
      = MEDIUM if score ≥ 34
      = LOW    otherwise
```

`reasons` fire at `scarcity ≥ 0.65`, `need ≥ 0.75`, `competitor_value ≥ 0.65`,
`alternative_risk ≥ 0.60`, `tier_drop ≥ 0.30`; if none fire, "Comparable paths
remain available."

---

## 18. Purchase and pass grading

Both operate on **persisted recommendation snapshots** vs. **recorded sales** —
the copilot grading its own prior advice.

### 18.1 Purchase grade

`src/purchase_grading.py` — `grade_purchase`

```
price_score = 100                          if price ≤ target_value
            = 85                           elif price ≤ soft_cap
            = 65                           elif price ≤ hard_cap
            = clamp(50 − 8·(price − hard_cap), 0, 100)   else

fit_score         = clamp(roster_fit · 100)
alternative_score = clamp(70 + 4·(min(actual_alt_costs) − price))    (75 if no alts recorded)
downstream_score  = clamp(downstream_outcome_score)                  (avg of later same-manager
                                                                     buys' value-vs-price, else 50)

total = 0.35·price_score + 0.25·fit_score + 0.15·alternative_score + 0.25·downstream_score
```

### 18.2 Pass grade

`src/pass_grading.py` — `grade_recorded_passes`

Graded only once the passed player *and* (usually) an alternative have later
sold; otherwise `PENDING`.

```
discipline = 100  if target later sold > hard_cap      (great pass)
           = 85   elif > soft_cap
           = 65   elif > target_value
           = 25   else                                 (you passed on a value)

availability = 100 if an alternative was later acquired, else 20
cost_score   = clamp(100 − 5·max(0, alt_price − target_value), 0, 100)   (20 if none)

total = 0.45·discipline + 0.35·availability + 0.20·cost_score
```

### 18.3 Letter grades (both)

`A ≥ 90`, `B ≥ 80`, `C ≥ 70`, `D ≥ 60`, else `F`.

---

## 19. Manager tendencies

`src/manager_tendencies.py` — `build_manager_tendency_model`

Half-life-weighted profile of how a manager bids, `as_of` a season:

```
w(season)  = 0.5 ^ ( (as_of_season − season) / half_life_years )      half_life default 2.0
```

```
historical_aggression = Σ(actual·w) / Σ(expected·w)
position_premiums[p]   = Σ(actual·w | p) / Σ(expected·w | p)
confidence             = Σ w / (Σ w + 8)
stars_spend_share      = weighted spend on "star"-tier / total weighted spend
auction_timing_share   = weighted share of buys in early / middle / late stage
```

Observations are derived from the same recorded historical sales that power the
Historical Market view (`build_tendency_observations_from_market`), with tier
assigned by the position's price distribution (`≥ p75 → star`, `≥ avg →
starter`, else `depth`).

---

## 20. Year-over-year calibration

`src/year_over_year_calibration.py` — `build_year_over_year_calibration`

Learns market adjustments from completed draft ledgers.

```
inflation_multiplier        = mean( sale.price / sale.modeled_market_value )   over all seasons
scarcity_multipliers[pos]   = avg_price(pos) / overall_avg_price
manager.aggressiveness_mult  = avg_price(manager) / overall_avg_price
source_bias[src]            = mean( sale.price − source_estimate )            (signed dollar error)
```

```
calibrated_price(base, pos, manager, source) =
    max(0, (base + source_bias[source]) · inflation_multiplier
                 · scarcity_multipliers[pos] · manager.aggressiveness_mult )
```

Per-season inflation and per-position price distributions (min / p25 / median /
p75 / max, via linear-interpolation `_percentile`) are also returned.
**Calibration changes explicit inputs to the next run — it never rewrites
recorded history.**

---

## 21. Strategy weights

`src/strategy_profile.py`

| Mode | `current_weight` | `future_weight` |
|---|---|---|
| `WIN_NOW` | 0.75 | 0.25 |
| `HYBRID` | 0.50 | 0.50 |
| `WIN_LATER` | 0.25 | 0.75 |

`current_weight + future_weight` must equal `1.0` (validated). A league can also
supply its own default split via `ModelRules`; the user's per-league choice
overrides it. `with_current_weight(x)` sets `future_weight = 1 − x` for a custom
slider position. Profiles are stored per `(league_key, user_key)`.

The bootstrap `CURRENT_SEASON_WEIGHT = 0.60 / FUTURE_VALUE_WEIGHT = 0.40`
(`src/league_config.py`) is the blend used by `context_valuation` for the
current/future signal mix, independent of the per-user strategy slider.

---

## Testing the math

Every engine above has a dedicated deterministic test that runs offline:

| Area | Test |
|---|---|
| Projections | `tests/test_projections.py`, `tests/test_scoring_projection_service.py`, `tests/test_sleeper_fantasypros_fallback.py` |
| Auction pool / values | `tests/test_auction_pool.py` |
| Recommendation | `tests/test_recommendation.py`, `tests/test_recommendation_unit.py`, `tests/test_recommendation_snapshots.py` |
| Dynamic cap / thresholds | `tests/test_dynamic_cap.py`, `tests/test_price_thresholds.py` |
| Context valuation | `tests/test_explainable_context_valuation.py`, `tests/test_live_evidence.py`, `tests/test_evidence_quality.py` |
| Keepers | `tests/test_keeper_domain.py`, `tests/test_keeper_economics.py`, `tests/test_keeper_recommendation.py`, `tests/test_keeper_recommendations.py`, `tests/test_keeper_optimizer.py`, `tests/test_keeper_trade_candidates.py` |
| Snake draft | `tests/test_snake_draft.py` |
| Grading / regret / calibration | `tests/test_purchase_grading.py`, `tests/test_pass_grading.py`, `tests/test_pass_regret.py`, `tests/test_pass_alternatives.py`, `tests/test_year_over_year_calibration.py` |
| Inflation / tendencies / run-hot | `tests/test_league_inflation.py`, `tests/test_manager_tendencies.py`, `tests/test_run_hot.py` |
| Ranking ensemble | `tests/test_ranking_ensemble.py` |
| Simulation determinism | `tests/test_scalable_simulator.py`, `tests/test_synthetic_scenarios.py`, `tests/test_historical_replay.py` |

```bash
uv run python -m compileall app.py src
uv run pytest
```

See also [Decision engines](DECISION_ENGINES.md) for the narrative overview and
[AI integration](AI_INTEGRATION.md) for the deterministic/generative boundary.
