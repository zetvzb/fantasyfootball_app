# Documentation index

The Draft Copilot is documented as a decision system, in four layers. Start
wherever matches your question.

## Business-facing

- **[Business overview](BUSINESS_OVERVIEW.md)** — what the product is, who it's
  for, the core promise, what the manager gets at each moment of a draft, data
  precedence, and stated limitations.
- **[Portfolio demo walkthrough](../demo/README.md)** — a runnable synthetic
  league with expected decisions.
- **[Portfolio screenshots](SCREENSHOTS.md)** — captured views from that
  fixture.

## Technical-facing

- **[Architecture](ARCHITECTURE.md)** — composition root, lazy per-view service
  loading, domain boundaries, identity, persistence.
- **[Data and RAG](DATA_AND_RAG.md)** — multi-source reconciliation, provenance,
  the ranking ensemble, and the local (no external embedding service) retrieval
  pipeline for uploaded research.
- **[Decision engines](DECISION_ENGINES.md)** — live bidding, keepers, devy,
  simulation, and learning in narrative form.
- **[Reliability and deployment](RELIABILITY_AND_DEPLOYMENT.md)** — idempotent
  Sleeper sync, restart reconciliation, private state, durable hosted storage.
- **[Posit Connect Cloud runbook](../DEPLOYMENT.md)** — env vars, health check,
  durable-state endpoint contract.
- **[Contributor guide](../AGENTS.md)** — project rules and league/product
  rules.

## AI integration

- **[AI integration](AI_INTEGRATION.md)** — the optional generative layer: the
  four services, the deterministic/generative boundary, the tool-calling
  contract, numeric guardrails, failure behavior, exactly what data leaves the
  process, prompt-injection posture, and caching.

## Deterministic math

- **[Deterministic math reference](DETERMINISTIC_MATH.md)** — the authoritative
  catalog of every formula, constant, and threshold: projections/VORP, baseline
  and market value, evidence weighting and recency decay, the bounded context
  adjustment, live caps and the dynamic cap, keeper scoring/economics/combination
  optimization, snake-draft math, grading, regret, inflation, tendencies, and
  year-over-year calibration — each with its module path and test.

The in-app **💡 How This Works** view (`src/views/how_it_works.py`) is the
plain-language version of that reference, with worked examples.
