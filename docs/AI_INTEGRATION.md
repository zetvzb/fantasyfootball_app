# AI integration

The Draft Copilot is a deterministic decision system with an **optional,
strictly bounded** generative layer. This document describes exactly what the
LLM does, what it is shown, what it is structurally prevented from doing, and
how it fails.

> **One-line summary:** the AI is a *narrator and a chooser-among-given-options*,
> never a *calculator or a decision-maker*. If you delete the API key, every
> number, cap, target, grade, and legal check in the app is byte-for-byte
> identical — you just get the terser deterministic sentence instead of a
> polished one.

- [The boundary](#the-boundary)
- [Configuration](#configuration)
- [The four services](#the-four-services)
  - [1. Decision explanation](#1-decision-explanation)
  - [2. Draft Strategist (snake)](#2-draft-strategist-snake)
  - [3. Auction Strategist](#3-auction-strategist)
  - [4. Nomination Strategist](#4-nomination-strategist)
- [Tool-calling contract](#tool-calling-contract)
- [Guardrails and validation](#guardrails-and-validation)
- [Failure behavior](#failure-behavior)
- [What data leaves the process](#what-data-leaves-the-process)
- [Prompt-injection posture](#prompt-injection-posture)
- [Caching and determinism](#caching-and-determinism)
- [Testing](#testing)

---

## The boundary

```mermaid
flowchart LR
    subgraph DET["Deterministic core (always runs, no network)"]
      P[Projections + VORP] --> V[Baseline / market value]
      V --> C[Context adjustment ±6/8%]
      C --> CAP[Target / Soft cap / Hard cap]
      CAP --> D[BID / PASS + reasons + snapshot]
    end
    D -->|"finished facts only"| AI
    subgraph AI["Optional generative layer (opt-in, network)"]
      AI[LLM] -->|"prose, or a pick from the given list"| OUT[Displayed narrative]
    end
    D -->|"deterministic explanation"| OUT
    AI -.->|"invalid / unreachable / disabled"| FB[Fallback = deterministic output]
    FB --> OUT
```

**Hard invariants** (enforced in code, covered by tests):

1. The LLM is called **only after** the deterministic decision is complete.
2. The LLM is given **computed facts**, never raw data to compute from.
3. The LLM's numeric output is **re-validated against the deterministic caps**
   and rejected if it violates them.
4. A strategist may only **select among candidates the engine supplied** — it
   cannot name a player outside the set.
5. Any failure, timeout, malformed response, missing key, or disabled toggle
   returns the **deterministic result** with a `warning`, and the app keeps
   working.
6. The LLM cannot submit a pick or bid, record a sale, or mutate any persisted
   state. It returns a dataclass that the UI renders; nothing else.

---

## Configuration

All secrets come from environment variables (`os.getenv`) — Posit Connect Cloud
does not support `st.secrets`.

| Variable | Default | Effect |
|---|---|---|
| `OPENAI_API_KEY` | *(unset)* | Enables all four services. Unset → deterministic-only, no network calls. |
| `OPENAI_EXPLANATION_MODEL` | `gpt-5.4` | Model for decision explanations and the default for strategists. |
| `OPENAI_DRAFT_STRATEGIST_MODEL` | *(falls back to explanation model)* | Overrides the model for the three strategist agents. |

The AI is **off by default in the UI** even when a key is present — the user
clicks "Generate optional AI explanation" / opens the strategist panel. The
`configured` property (`bool(api_key and model)`) gates every network path.

Endpoint: `POST https://api.openai.com/v1/responses`, `timeout=20s`,
`store=False` (no server-side retention), `max_output_tokens` 250–350.

---

## The four services

### 1. Decision explanation

`src/explanation_service.py` — `DecisionExplanationService`

Rewrites a **completed** deterministic decision as a readable paragraph.

- **Input** (`DecisionExplanationInput`): `subject`, `decision`,
  `numeric_facts` (a flat `{name: number}` map), `reason_codes`, and the
  `deterministic_explanation` string.
- **Instruction:** *"Write a concise fantasy-football decision explanation using
  only the supplied computed facts and reason codes. Do not change, recalculate,
  or invent any decision, score, price, player fact, injury, or news. State that
  the numeric result comes from the deterministic engine."*
- **Output:** free text. `source` is `"openai"` on success, `"deterministic"`
  on fallback.
- No tools, single request. This is the only pure text-polish service; the
  other three are constrained choosers.

### 2. Draft Strategist (snake)

`src/draft_strategist.py` — `DraftStrategistService`

A read-only agent over the deterministic snake-draft board (§16 of the math
reference).

- **Candidate set:** top **5** `DraftBoardEntry` rows (`vorp`, `need_bonus`,
  `utility`, `projected_points`). Must pick one of these by name.
- **Tools it must call first:** `inspect_draft_candidates`,
  `inspect_roster_needs`. Skipping either is a hard error → fallback.
- **Structured output** (`json_schema`, `strict`): `player_name`, `confidence`
  ∈ {low, medium, high}, `explanation` (< 80 words), `alternatives` (≤ 3, must
  also be from the candidate set).
- **Validation:** selected player must normalize to a candidate; alternatives
  filtered to the candidate set; explanation trimmed.
- **Fallback** (`_fallback`): the deterministic board leader, with confidence
  `high` if its utility strictly beats #2, and an explanation quoting utility /
  VORP / need bonus.

### 3. Auction Strategist

`src/draft_strategist.py` — `AuctionStrategistService`

A read-only agent over **one completed** deterministic auction price decision
for the currently nominated player.

- **Tools it must call first:** `inspect_price_decision` (player, current bid,
  decision, target/soft/hard cap, legal max, expected market, strategy label,
  reasons), `inspect_roster_and_alternatives` (source mode, live/discretionary
  cash, open spots, regret risk, room threat, up to 3 pass alternatives with
  price range + availability, and the manager's free-text context, truncated to
  2000 chars).
- **Structured output:** `decision` ∈ {BID, CAUTION, PASS}, `max_bid`
  (integer), `confidence`, `explanation` (< 80 words), `alternatives` (≤ 3).
- **Numeric guardrails — the response is rejected (→ fallback) if:**
  - `max_bid > min(hard_cap, legal_max_bid)` — *"exceeded the deterministic
    hard cap"*
  - `current_bid > cap` and `decision != PASS` — must pass above the hard cap
  - `decision ∈ {BID, CAUTION}` and `current_bid > max_bid` — can't advise
    bidding past its own stated max
- **Fallback** (`_fallback_auction`): the deterministic cockpit decision
  verbatim (`DISCIPLINED BID` normalized to `BID`), `max_bid = hard_cap`,
  quoting target/soft/hard and the deterministic "why".

### 4. Nomination Strategist

`src/draft_strategist.py` — `NominationStrategistService`

Chooses **who to nominate** among the deterministic nomination engine's top 5
options (`src/nomination_strategy.py`: Drain Cash / Acquire Target / Create
Chaos / Hide Need / Attack Manager).

- **Tool it must call first:** `inspect_nomination_options` (each option's
  score, action, reason, expected market, ceiling, target manager) plus the
  manager's context, *"treated as unverified manager-supplied information."*
- **Structured output:** `player_name` (must be a supplied option),
  `confidence`, `explanation` (< 60 words).
- **Fallback:** the top-scored deterministic option with its reason string.

---

## Tool-calling contract

The strategists run a bounded agentic loop (`max_rounds = 3`) against the
Responses API:

1. Send instructions + user turn + tool definitions (all tools take **no
   parameters** — they are read-only inspectors).
2. If the model emits `function_call` items, the app answers each with the
   **pre-serialized, deterministic** `tool_results[name]` (`json.dumps(...,
   sort_keys=True)`) — the model never triggers a fresh computation.
3. Loop until the model returns final structured text, or 3 rounds elapse.
4. **Every declared tool must have been called**, or the response is rejected:
   *"The strategist skipped required tool(s): …"*.
5. An unknown tool name raises immediately.

This design means the model's entire factual universe is the JSON the app
handed it — there is no retrieval, no browsing, no open-ended function surface.

---

## Guardrails and validation

| Guardrail | Where | On violation |
|---|---|---|
| `configured` gate (`api_key and model`) | all services | deterministic fallback + warning |
| Must call all inspection tools | strategists | `ValueError` → fallback |
| Selected player ∈ candidate set | draft + nomination strategists | `ValueError` → fallback |
| `max_bid ≤ min(hard_cap, legal_max)` | auction strategist | `ValueError` → fallback |
| No bid advice above hard cap / own max | auction strategist | `ValueError` → fallback |
| `strict` JSON schema with `additionalProperties: false` | strategists | parse failure → fallback |
| Alternatives intersected with engine's list | all strategists | silently dropped if not in set |
| Explanation word caps (60–80) | prompt instruction | soft (not enforced post-hoc) |
| `store: false`, 20s timeout | all services | timeout → fallback |
| User free-text truncated to 2000 chars, tagged "unverified" | auction + nomination | — |

The deterministic decision object (`summary`, `bid_state.recommendation`) is
always the source of truth passed to `_fallback_*`, so a rejected AI response
never degrades the answer below the deterministic baseline.

---

## Failure behavior

Caught exception classes: `requests.RequestException`, `KeyError`, `TypeError`,
`ValueError`, `json.JSONDecodeError`. Any of these → the corresponding
`_fallback*` with `warning = "AI … unavailable: {error}"`.

Observable result in the UI:

- The panel still renders, showing the **deterministic** recommendation.
- A warning line explains why AI output isn't shown (no key / API error /
  invalid response / skipped tool / exceeded cap).
- Nothing about draft state, persistence, or other views is affected.

There is no retry loop against the provider beyond the 3 tool-resolution rounds;
a hard failure fails fast to the deterministic path.

---

## What data leaves the process

Only **displayed, computed decision facts** for the current screen. Concretely:

- **Explanation:** the numeric facts already on screen, reason codes, and the
  deterministic explanation string.
- **Draft Strategist:** top-5 board rows (name, position, VORP, need bonus,
  utility, projected points) and the viewer's open starter/flex/bench gaps.
- **Auction Strategist:** the nominated player's price decision, the viewer's
  cash/roster state, up to 3 pass alternatives, regret risk, room threat, and
  any free-text the manager typed into the context box.
- **Nomination Strategist:** the 5 nomination options and the manager's
  free-text context.

**Not sent:** API keys, the durable state archive, other leagues, other
managers' private strategy profiles, raw uploaded research files, full rosters
beyond what the screen shows, or historical ledgers. `store: false` asks the
provider not to retain the request. Sending anything to an external model is a
network egress of league information — treat the context box accordingly.

Because Sleeper-backed and manual leagues both normalize into the **same**
deterministic engines, the AI payloads are identical in shape regardless of
league source.

---

## Prompt-injection posture

- Manager free-text is explicitly labeled to the model as **unverified
  manager-supplied information** and truncated (2000 chars).
- Uploaded research files feed the **deterministic** context pipeline
  (`src/file_drop_rag.py`), not the LLM. They are chunked, hash-embedded
  locally, entity-linked, and converted to typed context documents — a
  paragraph of "ignore previous instructions" in a PDF becomes a low-confidence
  soft signal at most, and can only move a price within the ±6/8% cap.
- The strategists cannot act on any instruction embedded in tool output: their
  only degrees of freedom are (a) pick one of N supplied players, (b) pick a
  decision from a 3-value enum, (c) a `max_bid` that is then bounds-checked, and
  (d) prose. There is no tool that writes, submits, or fetches.
- Structured outputs use `strict` schemas with `additionalProperties: false`,
  so the model cannot smuggle extra fields into the parsed result.

---

## Caching and determinism

`src/agent_cache.py` fingerprints strategist requests
(`auction_advice_fingerprint`, `nomination_advice_fingerprint`) with a
`sha256` over the sorted, serialized decision facts + truncated context (first
16 hex chars). The UI reuses a prior AI answer while the underlying
deterministic decision is unchanged, so re-renders under the bidding clock don't
re-hit the API or show a flickering answer.

The LLM itself is not deterministic across calls; the **cache key is**, and the
**fallback is**. Tests inject a fake `session` to make the whole path
reproducible.

---

## Testing

| Concern | Test |
|---|---|
| Explanation boundary (numeric side) + demo narrative path | `tests/test_explainable_context_valuation.py`, `tests/test_portfolio_demo.py` |
| Draft + auction strategist tool-use, cap enforcement, fallback | `tests/test_draft_strategist.py` |
| Auction agent manager-context handling | `tests/test_auction_agent_context.py` |
| Nomination strategist option-only selection | `tests/test_nomination_strategy_v2.py` |
| Agent response caching | `tests/test_agent_cache.py` |
| Deterministic engines unchanged without a key | the entire offline suite runs with `OPENAI_API_KEY` unset |

Provider integration tests require network + credentials; the deterministic and
boundary tests run fully offline.

See also [Decision engines](DECISION_ENGINES.md) and
[Deterministic math](DETERMINISTIC_MATH.md).
