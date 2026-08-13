---
doc: how Kiro numbers are captured — the standing reference
status: current as of 2026-08-13 · shipped calls/credits capture + shipped KIRO-METRICS
update-rule: ANY change to kiro capture (parser · source · schema field · routing · pricing) updates this doc in the same change, and bumps its DOC-REGISTRY row
---

# Kiro capture — how the numbers are made

One page: what cage records for Kiro, from where, and what it means.
Deep detail lives in the linked research/spec docs — not here.

## Captured today (shipped)

**`calls`/`credits` rows — priced, the money surface.**

| number | store → prop | lands as |
|---|---|---|
| tokens in/out (IDE) | `kiro.kiroagent/dev_data/tokens_generated.jsonl` → `promptTokens`/`generatedTokens` per call | `calls` row (`c_kiro…`, surface `ide`) — **machine ledger only** (ADR 0006) |
| credits (CLI, per conversation) | `kiro-cli/data.sqlite3` → `conversations_v2.value` → `user_turn_metadata.usage_info[]` (unit `credit`, summed) | `credits` row (`k_cred…`, surface `cli`), workspace-scoped, last-write-wins per session |
| context % · turns · model (CLI) | same conversation JSON → `request_metadata.context_usage_percentage` (last) · `len(history)` · `model_info` | same `credits` row |
| tool savings (CLI, graphify) | `history[]` tool runs, read transiently (ADR 0009) | `savings/graphify/` receipts |

- Capture is pull-based (`cage import` / capture-on-read) — no hooks, no network, $0.
- **IDE rows are machine facts** (the log has no project/session/ts) — they route to
  the machine ledger; a per-project kiro number would be fiction and cage refuses to
  invent it (ADR 0006). CLI rows ARE cwd-keyed, so those attribute honestly.
- Dollars from credits = recorded count × your `[billing.kiro] usd_per_credit` —
  always **modeled**; rate unset ⇒ credits render as a count. Absence ≠ zero.

**`.cage/ledger/kiro/` rows — capture-only, KIRO-METRICS (shipped 2026-08-13).**
A second, deliberately separate row kind (`schema.make_kiro_metric`) — never a widened
`calls`/`credits` row, never priced, **not yet read by any derived view**. Store-verbatim
per-chat facts at three grains:

| source | store | what lands |
|---|---|---|
| `ide` | IDE `dev_data/devdata.sqlite`, table `tokens_generated` (SQLite, read-only) | per-call tokens — the SAME counter the jsonl already reads, plus a `timestamp` and a cursorable `id` the jsonl never carried |
| `cli-conv` | CLI SQLite store, per conversation | credits (`usage_info` sum, None-sentinel when the list is absent), context%, turn count — cumulative-verbatim, like `credits` rows |
| `cli-turn` | same store, per `history[]` turn | populated timing/size/tool-use fields (`chunks`, `prompt_bytes`, `response_bytes`, `tool_uses`, `context_pct`), PLUS the token slots that are NULL on every real store probed so far — the **upgrade-watch** |

`ledger.kiro_metrics()` collapses last-write-wins per `(source, session, turn,
row_ref)`; `cage doctor`'s `kiro-metrics` check names per-source coverage and surfaces
the upgrade-watch state (armed vs. tripped). `cage query kiro-metrics` explains it.
Routing is inherited from ADR 0006, never re-decided: `ide` rows ride the routed kiro
sink (machine ledger); `cli-conv`/`cli-turn` rows ride the same workspace scoping the
`credits` leg already resolves.

## Known gaps (open)

- **IDE log is coarse by the vendor's doing** — output tokens usually 0, model
  usually the generic `"agent"` (real 16-call probe: 198 in / 0 out). Not fixable
  from this store, `ide`-source metrics rows included.
- **Cache tokens + per-chat IDE credits: persisted by NO kiro store.** They exist
  only on the wire (`metadataEvent.tokenUsage`, `meteringEvent`) — proxy capture is
  the only path; permanently honest-empty from disk. Not a cage gap.
- **CLI token slots are still NULL** on every real store probed so far (kiro-cli
  2.16.0) — `cli-turn` rows record them the moment Kiro starts filling them
  (upgrade-watch armed, zero code change needed); `cage doctor` announces the flip.
- **No read surface yet for `.cage/ledger/kiro/`** — a `cage insights kiro` view or
  new chats-view columns, and `cage data export --csv kiro`, are parked in
  `work/OPEN-WORK.md`, not built.
- **Two real-store probes still pending** (`devdata.sqlite`'s exact column list
  beyond the four assumed; whether IDE session JSONs embed per-message usage) —
  research doc §6 has the commands; the IDE parser is written to survive either
  answer (explicit-column SELECT, fail-open).

## Executive summary (for the meeting)

- We meter Kiro from its **own on-disk records** — no vendor API, no network, zero
  infra cost. Numbers are the vendor's, recorded verbatim.
- **Credits are the billing truth** for Kiro CLI: AWS's own per-conversation credit
  charge, captured exactly. Dollar figures are **modeled** (credits × our plan
  rate), never invoiced, and cage labels them so.
- **Kiro's IDE keeps the thinnest records of any agent we meter**: output tokens
  usually 0, and the model usually the generic `"agent"`. We report what AWS
  persists; where its log has no project dimension we count at machine level rather
  than invent a per-project split.
- **Token/cache precision exists but AWS throws it away**: the backend streams exact
  token and cache counts plus per-request credits with every response — Kiro
  persists almost none of it. Full fidelity needs cage's proxy in the path; that is
  a vendor limitation, not a metering gap.
- **A second, richer ledger now exists alongside the priced one**: IDE calls now
  carry a timestamp for the first time, and every CLI turn's timing/size/tool-use
  detail is recorded — plus a standing watch that starts capturing exact per-turn
  CLI tokens automatically, no rebuild required, the day Kiro's own store starts
  persisting them. Recorded, not yet surfaced: no report reads it yet, so today it
  is evidence banked for the next read-surface build, not a number anyone sees.

## Maintenance

Standing rule (frontmatter `update-rule`): a change to any kiro parser, source
path, schema field, routing decision, or pricing updates this doc **in the same
change** — stale here = a missing changelog entry. Tracked in
[DOC-REGISTRY.md](../work/DOC-REGISTRY.md).
