# AGENTS.md

## Project
Fantasy Football Auction Copilot: a Python 3.9 + Streamlit multi-league dynasty auction recommendation system intended for Posit Connect Cloud.

## Product goal
Maximize roster value and give fast, explainable auction recommendations. The recommendation is the product; analytics support the decision.

## Hard rules
- Python 3.9 only. Do not use `X | Y`; use `Optional`, `Union`, etc.
- Preserve multi-league support.
- Do not reintroduce hard-coded Bishop-only behavior.
- Workbook/Google Sheet is optional enrichment, never a runtime requirement.
- Source priority for setup: explicit manual > import/workbook > Sleeper inference > defaults.
- Sleeper is authoritative for completed live auction sales.
- No hidden `globals()` coupling.
- Prefer dataclasses/services/explicit parameters.
- Avoid circular imports.
- Keep Streamlit files UI-focused; move business math to services/domain modules.
- One roadmap item per branch. Avoid unrelated refactors.
- Namespace league/user-specific state appropriately.
- College/devy is optional and never part of the regular auction pool.
- Never claim a feature works without validation.

## League/product rules

### Budgets
- Bishop historically originated from a $400 league budget, but actual entering budgets are team-specific.
- Budgets may change through historical moves and traded auction dollars.
- Keeping fewer than the maximum does NOT create bonus money; it simply creates another auction roster spot.
- Enforce minimum-bid reserve for all remaining roster spots.

### Keepers
- Bishop max keepers: 6.
- Returning keeper price: prior-year price + $11.
- Mid-season pickup price next season: $10.
- No maximum tenure.
- Pre-Draft must compare best 4, 5, and 6 keeper combinations.
- Strategy modes: Win Now, Hybrid, Win Later.
- Future horizon: 2-3 years, age-adjusted by position.
- Elite young players get future optionality value.

### College / devy
- Bishop allows up to 6 college players per manager.
- College players are acquired in a separate college draft, never in the regular auction.
- College picks may be traded.
- Bishop eligibility may come from workbook; other leagues may use manual rules.
- Some leagues have no devy.
- Pre-Draft should recommend Promote Now vs Leave on Taxi.
- The app does not run the college draft.

### Roster
- Full roster required at draft end.
- Starting slots may remain unfilled.
- K/DEF need not be drafted if IR strategy makes that rational.
- Bye weeks are a soft optimization factor, not a hard constraint.

### Rankings/projections
Desired ensemble:
1. Sleeper-derived source/data
2. spreadsheet/import ranking
3. third practical source/API
Start equal-weighted. Ranking disagreement is informational, not a risk penalty. Use league-scoring-adjusted projections where possible.

### Context
Relevant signals include injuries/history, off-field issues, preseason hype, snap share, target share, routes, OL quality, coaching changes, SOS, depth charts/movement, news, and user-uploaded files.
Classify evidence as hard evidence, strong analytical signal, or soft signal.
Context may materially change value, but adjustments must be explainable.

### Historical/opponent intelligence
Prioritize league inflation, positional/tier inflation, manager tendencies, unused cash behavior, predicted target profiles, and run-hot warnings. Do not predict exact opponent bids.

### Live auction recommendation
Primary decision:
- Target Value
- Soft Cap
- Hard Cap

Allow current-bid input. Recompute on meaningful thresholds. Caps may rise or fall based on scarcity, roster need, alternatives, cash, auction stage, context, and room inflation.
PASS should name alternatives, availability probability, and regret risk.

### Nomination
Support Drain Cash, Acquire Target, Create Chaos, Hide Need, and Attack Manager strategies.

### Simulation
Support large auction simulation, strategy comparisons, position budgets, target tiers, fallback chains, action plans, and ideal-roster blueprints.

### Learning/evaluation
Persist meaningful recommendation snapshots. Grade purchases and passes. Support replay and year-over-year calibration.

### Reliability
Live sync must be idempotent. Restart recovery must reconcile persisted state with Sleeper. Optional API failures must not corrupt draft state.

### Productization
Laptop-first. Keyboard shortcuts desirable. Refresh stale intelligence on open and via one Refresh Draft Intelligence action. Support multiple users/managers eventually without leaking private strategy. Deploy to Posit Connect Cloud.

## Expected architecture
Treat the repository as source of truth, but current shape is roughly:

```text
app.py
src/
  app_runtime.py
  league_profile.py
  league_registry.py
  league_setup_data.py
  draft_setup.py
  views/
    router.py
    league_setup.py
    pre_draft.py
    draft_mode.py
    draft_history.py
    draft_components/
      live_economy.py
      roster_plan.py
      nomination.py
      sale_input.py
      live_team_state.py
      auction_board.py
      bid_copilot.py
      bid_components/
        state.py
        selection.py
        price_decision.py
        buy_vs_pass.py
        player_context.py
        signals_intelligence.py
        bidder_threats.py
        manual_sale.py
```

## Execution protocol
For every task:
1. Read `AGENTS.md` and the relevant `docs/ROADMAP.md` item.
2. Inspect current code before editing.
3. State a short plan.
4. Make the smallest coherent change that completes the item.
5. Add/update tests.
6. Run validation.
7. Fix failures before stopping unless blocked by unavailable credentials/services.
8. Mark roadmap item DONE only if fully implemented and validated.
9. Summarize behavior, files changed, tests, limitations, and recommended next task.

Minimum validation:
```bash
python -m compileall app.py src
pytest
```
If tests are not configured, say so explicitly and still run compile/import checks.
When modifying view imports, verify imports resolve.
When modifying persistence/live state, test restart/reconciliation where feasible.
