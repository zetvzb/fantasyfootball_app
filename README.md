# Fantasy Football Draft Copilot

A dynasty auction draft is fast and unforgiving: someone nominates a player, and from that moment you're deciding whether to bid, how high, and why -- with real money and a room full of opponents watching. This app is a live decision cockpit for that moment: it turns rosters, budgets, rankings, news, and injury/depth-chart signals from every league you're in into a bid/pass call in seconds, with a number you can actually defend, not a black box.

It's built as a decision system, not just a dashboard. Every score, cap, and legal check is deterministic Python -- the same inputs always produce the same output, and you can trace exactly why a number moved. An optional AI layer can turn an already-final decision into a more natural sentence; it never sees or changes a number. Leagues can connect to Sleeper for live sync, or run entirely off-platform (Yahoo or a home league) with a spreadsheet doing the heavy lifting: drop a league workbook in and it auto-fills teams, budgets, keepers, and history, prompting you only for what it genuinely can't find.

Open the app and click **💡 How This Works** for a plain-language walkthrough with a real worked example (age curves, evidence weighting, bounded value adjustments) -- built for a non-engineering reader in a few minutes.

## What makes this interesting

- **Deterministic core, bounded AI edge.** Recommendations, caps, and grades are pure functions of typed inputs -- reproducible, testable, and fully explainable without an LLM in the loop. AI is opt-in and structurally incapable of altering a number (see [Decision engines](docs/DECISION_ENGINES.md)).
- **Multi-source reconciliation with provenance.** Manual entry, spreadsheet import, Sleeper, and third-party rankings all merge through one explicit precedence order, and every value keeps a record of where it came from (see [Data and RAG](docs/DATA_AND_RAG.md)).
- **Evidence-weighted context, not vibes.** News and injury reports are classified as hard evidence / strong signal / soft signal, decayed over time, and superseded by newer, more specific updates -- all before touching a dollar figure.
- **Fast by construction.** Each view declares exactly which services it needs; a setup page never pays for a live-draft computation it doesn't use (see [Architecture](docs/ARCHITECTURE.md)).
- **Multi-league, multi-user, private by identity.** No hard-coded league logic; strategy state and recommendation history are isolated per league and per manager.

## Current capabilities

- Manage multiple Sleeper and Yahoo/manual leagues without hard-coding league-specific behavior.
- Create a persistent manual league from its teams, PPR format, roster size, keeper escalation/limit, devy limit, auction budget, and minimum bid -- or drop a spreadsheet and let it auto-fill everything it can detect, prompting for the rest.
- Compare every opponent's keepers against your own at the same position and see which ones are real upgrades, not just trade bait.
- Review manager tendencies and copilot self-grading (post-draft purchase/pass review) in one Manager Intelligence view.
- Load only the services required by the active League Setup, Pre-Draft, Draft Mode, Draft History, Manager Intelligence, or Player Context view.
- Track each team's entering cash, keeper commitments, live cash, minimum-bid reserve, discretionary cash, traded dollars, and budget provenance.
- Start with full, partial, or minimal setup data; a workbook is never required at runtime.
- Keep user-private preferences and strategy state isolated by league and user/manager identity.
- Apply configurable keeper rules, including prior-year price + $11, $10 next-season cost for mid-season pickups, no tenure limit, and no bonus cash for unused keeper slots.
- Configure Win Now, Hybrid, or Win Later strategy weights.
- Produce deterministic, typed keeper recommendations with current and future value, age, cost, auction value, surplus, scarcity, roster fit, strategy score, explanations, and reason codes.
- Exhaustively compare legal best-4, best-5, and best-6 keeper combinations, including spend, remaining cash and roster spots, current/future value, surplus, and opportunity cost.
- Project keeper costs, player values, annual and cumulative surplus, break-even year, and keeper runway across a configurable two-to-three-year horizon.
- Configure optional college/devy capacity, eligibility and promotion state, right ownership, and traded college-pick ownership while keeping all devy rights out of the regular auction pool.
- Reconcile completed live auction sales from Sleeper or record every nomination/sale manually, with isolated local state per league.
- Search any NFL player in a standalone Player Context view using the Sleeper player universe and available FantasyPros rankings, projections, news, and injury context.

See [ROADMAP.md](ROADMAP.md) for completed work and planned features.

## Engineering portfolio

The implementation is documented as a decision system rather than only a UI:

- [Architecture](docs/ARCHITECTURE.md): composition root, lazy views, domain boundaries, identity, and persistence.
- [Data and RAG](docs/DATA_AND_RAG.md): source priority, provenance, ranking ensemble, uploaded-file retrieval, and evidence quality.
- [Decision engines](docs/DECISION_ENGINES.md): live bidding, keepers, devy promotion, simulation, learning, and deterministic/generative boundaries.
- [Reliability and deployment](docs/RELIABILITY_AND_DEPLOYMENT.md): idempotent sync, recovery, private state, durable hosted storage, and operational checks.
- [Posit deployment runbook](DEPLOYMENT.md): environment variables, health check, and durable-state endpoint contract.
- [Portfolio demo walkthrough](demo/README.md): synthetic league, expected decisions, optional AI narrative, and screenshot workflow.
- [Portfolio screenshots](docs/SCREENSHOTS.md): captured Pre-Draft, keeper, and live-auction views from the runnable fixture.

## Requirements

- Python 3.9
- [`uv`](https://docs.astral.sh/uv/) (recommended)

Optional integrations:

- A league workbook for historical rules, prices, or rankings
- A Sleeper account and auction league for automatic roster and live-sale sync
- A FantasyPros API key for FantasyPros enrichment

The app remains usable when optional integrations are absent or temporarily unavailable.

## Install and run

From the repository root:

```bash
uv sync
uv run streamlit run app.py
```

The initial bootstrap Sleeper values are in `src/config.py`. After startup, open the sidebar league form and choose either **Add Sleeper League** or **Add Yahoo / Manual League**. Manual league profiles are saved under `data/leagues/` and remain selectable after an app restart.

For a Yahoo/manual league, use **League Setup** to enter team-specific budgets and finalized keepers/devy rights. An optional CSV/XLSX resource can preload keeper candidates, devy players, valuations, and draft history. Supported columns are `Type`, `Team`, `Player`, `Position`, `Value`, `Keeper Cost`, `Prior Year Cost`, `Year`, and `Price`; `Type` may be `keeper`, `devy`, or `history`. A teamless keeper row is assigned to the current user's team. History may be omitted entirely.

In **Draft Mode**, manual leagues expose manual sale entry only. Sleeper is still used for the global NFL player universe, and its last cached player universe remains usable during a temporary API outage. College/devy rights stay strictly outside the regular auction player pool.

For a Sleeper-backed league, keeper/devy ownership is source-driven. Update Sleeper and any configured workbook, then use **Refresh Draft Intelligence**; the refresh clears both active league and workbook source caches. Team budgets and optional draft history may still be overridden manually.

To enable FantasyPros enrichment for the current shell:

```bash
export FANTASYPROS_API_KEY="your-api-key"
uv run streamlit run app.py
```

Do not commit API keys, private strategy data, or local draft databases.

To enable optional AI-polished explanations, set `OPENAI_API_KEY`. The app sends only the displayed computed decision facts and reason codes to the Responses API. `OPENAI_EXPLANATION_MODEL` defaults to `gpt-5.4`. Generated prose cannot change any numeric score, legal check, target, or cap; without a key or on API failure, the deterministic explanation remains available.

## Data behavior

Setup values follow this priority:

1. Explicit manual input
2. Import or workbook enrichment
3. Sleeper inference
4. Application defaults

Sleeper is authoritative for completed live auction sales in Sleeper-backed leagues. Manual leagues use the local sale ledger. Optional source failures do not replace or corrupt persisted draft state.

Local runtime data is stored under `data/`, including league profiles, league setup, league-and-user strategy profiles, draft state, and player context. Back up that directory if the local history matters, and treat it as private league data. A hosted Connect Cloud deployment restores/checkpoints authoritative state through the configured external durable-state endpoint.

College/devy players are optional and are not included in the regular auction pool.

## Development and validation

Project rules and contributor guidance are in [AGENTS.md](AGENTS.md). The short Codex workflow handoff remains in [README_CODEX.md](README_CODEX.md).

Run the required checks with the Python 3.9 environment:

```bash
uv run python -m compileall app.py src
uv run pytest
```

Provider integration checks require network access and any applicable credentials; deterministic domain and service tests run offline.

## Current limitations

- The app maps authenticated Posit identities but does not implement its own sign-in, user administration, or invitation flow.
- The durable archive prevents stale overwrites with ETags, but it is a single-object design rather than a horizontally scalable transactional database.
- Yahoo roster and auction APIs are not integrated. Yahoo/manual leagues require setup imports/manual entry and manual sale entry.
- External data freshness and quality depend on the configured provider; failures degrade enrichment rather than preventing startup.

The recommended next task is the reproducible portfolio demo described in roadmap item 62.
