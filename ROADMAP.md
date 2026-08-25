# Fantasy Football Auction Copilot — Product Roadmap

Architecture cleanup is substantially complete. Work in order unless dependencies justify otherwise.

## Phase 1 — Runtime Foundation

### 1. Lazy per-view loading
Status: DONE

Only initialize data/services needed by the active view. League Setup=profile/setup; Pre-Draft=setup+pre-draft intelligence; Draft Mode=full live stack; Draft History=history/review only.

### 2. Generalized team-budget model
Status: DONE

Model team-specific entering cash, keeper commitments, live cash, required reserve, discretionary cash, traded dollars, and provenance. No bonus for unused keeper slots.

### 3. Remove workbook hard dependencies
Status: DONE

App must work with full, partial, or minimal information. Workbook remains optional enrichment for Bishop rules/history/rankings.

### 4. User/manager-aware runtime identity
Status: DONE

Separate league identity from current user/manager and namespace private preferences/state without implementing full auth yet.

## Phase 2 — Keeper & Pre-Draft Intelligence

### 5. Keeper domain model V2
Status: DONE

Support +$11 escalation, $10 mid-season pickups, no tenure max, configurable max keepers, unused slots becoming auction spots, and 2-3 year future hooks.

### 6. Strategy profiles
Status: DONE

Add Win Now / Hybrid / Win Later with configurable current/future weights stored per user+league and exposed through explicit models.

### 7. Keeper Recommendation Engine
Status: DONE

Typed deterministic recommendation per keeper: current value, future value, age adjustment, cost, auction value, surplus, scarcity, roster fit, strategy score, explanation.

### 8. Best 4/5/6 keeper optimizer
Status: DONE

Evaluate legal combinations, not greedy ranking. Compare spend, remaining cash/spots, value, future value, surplus, opportunity cost, and recommend one scenario.

### 9. Multi-year keeper economics
Status: DONE

Project costs/value/surplus 2-3 years, break-even year, keeper runway, and strategy-adjusted economics.

### 10. College/devy rules V2
Status: DONE

Optional devy configuration, Bishop 6-player capacity, eligibility/promotion representation, college-pick ownership/trades, and strict exclusion from regular auction.

### 11. Promote Now vs Leave on Taxi
Status: DONE

Recommend promotion using NFL role, draft capital, depth chart, roster need, rules, future value, and opportunity cost.

### 12. Pre-Draft readiness UX
Status: DONE

Show scoring, roster rules, budgets, keeper/devy readiness, freshness, history availability, and Ready for Draft state.

## Phase 3 — Rankings / Context

### 13. Three-source ranking ensemble
Status: DONE

Sleeper-derived + spreadsheet/import + third practical API/source; equal weights initially; missing source tolerated.

### 14. League-scoring-adjusted projections
Status: DONE

Raw stats -> league scoring -> points -> replacement value -> auction value.

### 15. Expanded context ingestion
Status: TODO

Injury history, off-field issues, preseason hype, snaps, targets, routes, OL, coaching, SOS, depth charts.

### 16. Evidence-quality model
Status: TODO

Classify hard evidence / analytical signal / soft signal and weight downstream impact.

### 17. File-drop RAG
Status: TODO

Upload PDF/text/rankings/research -> parse/chunk -> embed -> entity link -> structured valuation signal.

### 18. Explainable context valuation
Status: TODO

Every context adjustment exposes signal, evidence class, direction, magnitude, explanation, and source metadata.

## Phase 4 — Historical / Opponent Intelligence

### 19. League inflation model V2
Status: TODO

Track expected vs actual by season/position/tier/auction stage and calculate live room inflation.

### 20. Manager tendency model V2
Status: TODO

Position premiums, stars-vs-depth, timing, keeper habits, unused cash, historical aggression with time decay.

### 21. Predicted opponent target profiles
Status: TODO

Estimate likely target types/tiers from roster needs, budgets, keepers, tiers, and history; no exact bid predictions.

### 22. Run-hot detection
Status: TODO

Warn when cash-rich teams overlap on scarce tiers and feed that into availability/ceiling logic.

## Phase 5 — Live Auction Decision Engine V2

### 23. Target / Soft Cap / Hard Cap
Status: TODO

Replace simplistic ceiling with three explicit live price thresholds.

### 24. Current-bid interaction
Status: TODO

Allow current bid entry/buttons and update recommendations at meaningful thresholds.

### 25. Dynamic cap adjustment
Status: TODO

Raise/lower cap based on need, scarcity, alternatives, cash, stage, inflation, strategy, future value, and context.

### 26. Buy-vs-pass alternatives
Status: TODO

When passing, name comparable alternatives and expected price ranges.

### 27. Alternative availability probability
Status: TODO

Estimate probability that comparable alternatives remain realistically acquirable.

### 28. Pass regret risk
Status: TODO

LOW/MEDIUM/HIGH or calibrated score based on scarcity, need, competitors, alternatives, and tier drop.

### 29. Nomination strategy V2
Status: TODO

Drain Cash, Acquire Target, Create Chaos, Hide Need, Attack Manager with player+target+reason.

### 30. My Guys
Status: TODO

Optional user list with configurable premium; default premium zero.

## Phase 6 — Simulation / Planning

### 31. Scalable auction simulator
Status: TODO

Hundreds/thousands of reproducible simulations with price distributions and roster outcomes.

### 32. Opening strategy comparison
Status: TODO

Compare elite-RB, elite-WR, balanced, value-waiting, youth-heavy, stars-and-scrubs strategies.

### 33. Position-budget optimizer
Status: TODO

Generate initial and continuously updated position spending bands.

### 34. Pre-Draft action plan
Status: TODO

Recommended strategy, budget bands, priority tiers, nomination plan, fallback plan.

### 35. Target tiers / fallback chains
Status: TODO

Explicit position/tier hierarchy linked to live pass decisions.

### 36. Ideal roster blueprint
Status: TODO

Expected-price optimized planning roster, not a rigid target.

## Phase 7 — Auction UX

### 37. Laptop-first cockpit
Status: TODO

Recommendation-first live screen with current bid, target/soft/hard cap, why, alternatives, regret risk, room threat.

### 38. Keyboard shortcuts
Status: TODO

Player search, bid increment, pass, sale, refresh, nomination without conflicting with text entry.

### 39. Collapsible evidence/details
Status: TODO

Keep deep intelligence available but secondary during live bidding.

### 40. Data freshness UI
Status: TODO

Last refresh/status/age/stale threshold for external sources.

### 41. Refresh Draft Intelligence
Status: TODO

One action refreshes stale/selected Sleeper, rankings, projections, news, injuries, depth, usage/context.

### 42. Refresh-on-open
Status: TODO

Refresh only stale sources when app opens.

## Phase 8 — Learning / Evaluation

### 43. Recommendation snapshot persistence
Status: TODO

Persist player, time, bid, target/soft/hard caps, decision, alternatives, roster/budget state, inflation, context, reasons.

### 44. Purchase grading
Status: TODO

Grade purchases using price, fit, alternatives, and downstream outcomes.

### 45. Pass grading
Status: TODO

Grade passes based on actual later alternative availability/cost.

### 46. Copilot post-draft review
Status: TODO

Summarize correct/incorrect decisions and calibration/model errors.

### 47. Historical replay framework
Status: TODO

Replay sales sequentially and generate pre-sale recommendations for evaluation.

### 48. Year-over-year calibration
Status: TODO

Recalibrate inflation, scarcity, manager behavior, source bias, and price distributions from completed drafts.

## Phase 9 — Reliability / Testing

### 49. Sleeper-authoritative reconciliation
Status: TODO

Completed Sleeper results override conflicting provisional local/manual sale state.

### 50. Idempotent live sync
Status: TODO

Repeated polling never duplicates a sale.

### 51. Restart recovery
Status: TODO

Persisted state + Sleeper -> reconciled current draft state after restart.

### 52. External API failure handling
Status: TODO

Optional feeds can fail without corrupting auction state.

### 53. Unit test expansion
Status: TODO

League/scoring/budget/keeper/devy/reserve/sync/recommendation coverage.

### 54. Synthetic scenario tests
Status: TODO

Aggressive/passive rooms, inflation, position runs, unused cash, budget imbalance, no-history/devy/workbook.

### 55. Full auction rehearsal
Status: TODO

Complete simulation/replay including restart/reconnect failures.

## Phase 10 — Productization / Portfolio

### 56. Multi-user preferences
Status: TODO

User+league scoped manager identity, strategy, My Guys, planning, recommendation history.

### 57. Private strategy isolation
Status: TODO

Never expose another user's private strategy/preferences.

### 58. Posit Connect Cloud deployment
Status: TODO

Dependency lock, env vars, secrets, storage, health checks, runtime paths.

### 59. Authentication identity mapping
Status: TODO

Safely map authenticated users to league managers.

### 60. Production persistence
Status: TODO

Ensure setup/draft/recommendation state survives deployment restarts.

### 61. Portfolio documentation
Status: TODO

README, architecture/data/RAG/recommendation/simulation/keeper/reliability/deployment diagrams and write-up.

### 62. Portfolio demo
Status: TODO

Demo league/data, screenshots, walkthrough, hybrid deterministic+AI explanation.
