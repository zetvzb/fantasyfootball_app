# Fantasy Football Auction Copilot

A laptop-first Streamlit app for managing multi-league dynasty auction drafts and making fast, explainable keeper and auction decisions. Leagues may be connected to Sleeper or run entirely through manual entry (including Yahoo leagues); workbook and third-party ranking data are optional enrichment.

## Current capabilities

- Manage multiple Sleeper and Yahoo/manual leagues without hard-coding league-specific behavior.
- Create a persistent manual league from its teams, PPR format, roster size, keeper escalation/limit, devy limit, auction budget, and minimum bid.
- Load only the services required by the active League Setup, Pre-Draft, Draft Mode, Draft History, or Player Context view.
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

## Data behavior

Setup values follow this priority:

1. Explicit manual input
2. Import or workbook enrichment
3. Sleeper inference
4. Application defaults

Sleeper is authoritative for completed live auction sales in Sleeper-backed leagues. Manual leagues use the local sale ledger. Optional source failures do not replace or corrupt persisted draft state.

Local runtime data is stored under `data/`, including league profiles, league setup, league-and-user strategy profiles, draft state, and player context. Back up that directory if the local history matters, and treat it as private league data.

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

- Identity is modeled explicitly, but full authentication and hosted multi-user access control are not implemented.
- League profiles and draft state are persisted on local disk; a multi-instance hosted deployment needs shared durable storage.
- Yahoo roster and auction APIs are not integrated. Yahoo/manual leagues require setup imports/manual entry and manual sale entry.
- External data freshness and quality depend on the configured provider; failures degrade enrichment rather than preventing startup.

The recommended next task is an export/backup workflow for manual league profiles, setup data, and draft ledgers before hosted deployment.
