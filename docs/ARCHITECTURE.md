# Architecture

The Auction Copilot is a Python 3.9 Streamlit application organized around typed domain services. `app.py` composes the active league runtime and routes to one lazily imported view; view modules render results but do not own auction or keeper math.

```mermaid
flowchart LR
    U[User] --> ST[Streamlit composition root]
    ST --> R[Lazy view router]
    R --> LS[League Setup]
    R --> PD[Pre-Draft]
    R --> DM[Draft Mode]
    R --> DH[Draft History]
    R --> PC[Player Context]
    ST --> AR[Explicit AppRuntimeContext]
    AR --> D[Domain and recommendation services]
    AR --> I[Optional integrations]
    D --> P[League-scoped persistence]
    I --> SL[Sleeper]
    I --> FP[FantasyPros]
    I --> WB[Workbook/import]
```

## Runtime boundaries

- `src/app_runtime.py` declares per-view requirements and constructs only the services required by the selected view.
- `src/views/router.py` imports only the active renderer. This keeps League Setup and history views from initializing draft intelligence integrations.
- `src/runtime_identity.py`, `src/auth_identity.py`, and `src/private_state.py` separate league identity, user identity, and manager identity. Private records require the full league+user+manager scope.
- `src/league_profile.py` represents normalized multi-league rules. Bishop defaults are data, not branching logic.
- `src/league_setup_data.py` merges values using explicit manual input, import/workbook, Sleeper inference, then defaults.

## Domain/service map

```mermaid
flowchart TB
    LP[LeagueProfile] --> KD[Keeper domain]
    LP --> CD[College/devy domain]
    LP --> AD[Auction domain]
    SP[Private strategy profile] --> KR[Keeper recommendation]
    KD --> KR
    KR --> KO[Keeper combination optimizer]
    AD --> BR[Live bid recommendation]
    CT[Context evidence] --> BR
    HM[Historical market] --> BR
    BR --> SNAP[Recommendation snapshot]
    SNAP --> LEARN[Purchase/pass grading and calibration]
    AD --> SIM[Deterministic auction simulation]
```

Numeric decisions are deterministic and testable. Optional external context can adjust a bounded valuation input, while recommendation caps, legality, reserve enforcement, keeper selection, and simulations remain service-owned calculations.

## Persistence boundary

Local operation stores runtime state below `FANTASYFOOTBALL_DATA_DIR`. Hosted operation can mirror authoritative setup, draft ledgers, recommendation snapshots, league profiles, and private preferences to an authenticated state object. ETag conditional writes reject stale writers. Rebuildable player-context caches are not part of the durable archive.

See [Data and RAG](DATA_AND_RAG.md), [Decision Engines](DECISION_ENGINES.md), and [Reliability and Deployment](RELIABILITY_AND_DEPLOYMENT.md).
