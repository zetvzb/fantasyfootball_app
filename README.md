# Fantasy Football Auction Copilot

A laptop-first Streamlit app for managing multi-league dynasty auction drafts and making fast, explainable keeper and auction decisions. Sleeper supplies league and live-draft data; workbook and third-party ranking data are optional enrichment.

## Current capabilities

- Manage multiple Sleeper leagues without hard-coding league-specific behavior.
- Load only the services required by the active League Setup, Pre-Draft, Draft Mode, or Draft History view.
- Track each team's entering cash, keeper commitments, live cash, minimum-bid reserve, discretionary cash, traded dollars, and budget provenance.
- Start with full, partial, or minimal setup data; a workbook is never required at runtime.
- Keep user-private preferences and strategy state isolated by league and user/manager identity.
- Apply configurable keeper rules, including prior-year price + $11, $10 next-season cost for mid-season pickups, no tenure limit, and no bonus cash for unused keeper slots.
- Configure Win Now, Hybrid, or Win Later strategy weights.
- Produce deterministic, typed keeper recommendations with current and future value, age, cost, auction value, surplus, scarcity, roster fit, strategy score, explanations, and reason codes.
- Exhaustively compare legal best-4, best-5, and best-6 keeper combinations, including spend, remaining cash and roster spots, current/future value, surplus, and opportunity cost.
- Project keeper costs, player values, annual and cumulative surplus, break-even year, and keeper runway across a configurable two-to-three-year horizon.
- Reconcile completed live auction sales from Sleeper and retain manual draft state and history locally.

See [ROADMAP.md](ROADMAP.md) for completed work and planned features.

## Requirements

- Python 3.9
- A Sleeper account and league for live data
- [`uv`](https://docs.astral.sh/uv/) (recommended)

Optional integrations:

- A league workbook for historical rules, prices, or rankings
- A FantasyPros API key for FantasyPros enrichment

The app remains usable when optional integrations are absent or temporarily unavailable.

## Install and run

From the repository root:

```bash
uv sync
uv run streamlit run app.py
```

The initial bootstrap Sleeper values are in `src/config.py`. After startup, use **League Setup** to add or select a league and review inferred settings before entering Pre-Draft or Draft Mode.

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

Sleeper is authoritative for completed live auction sales. Optional source failures do not replace or corrupt persisted draft state.

Local runtime data is stored under `data/`, including league profiles, league setup, league-and-user strategy profiles, draft state, and player context. Back up that directory if the local history matters, and treat it as private league data.

College/devy players are optional and are not included in the regular auction pool.

## Development and validation

Project rules and contributor guidance are in [AGENTS.md](AGENTS.md). The short Codex workflow handoff remains in [README_CODEX.md](README_CODEX.md).

Run the required checks with the Python 3.9 environment:

```bash
uv run python -m compileall app.py src
uv run pytest
```

Some legacy integration-style tests access external fantasy APIs while pytest collects them. Those tests require network access and any applicable credentials; deterministic domain and service tests can run offline.

## Current limitations

- Identity is modeled explicitly, but full authentication and hosted multi-user access control are not implemented.
- Devy promotion recommendations, the three-source ranking ensemble, and the live Target Value / Soft Cap / Hard Cap engine remain roadmap work.
- External data freshness and quality depend on the configured provider; failures degrade enrichment rather than preventing startup.

The recommended next task is roadmap item 10: model optional college/devy configuration, eligibility and promotion state, college-pick ownership and trades, and strict exclusion from the regular auction pool.
