---
adr: copilot
status: current as of 2026-08-14 · five stores captured · spine is chat + cli-delta · one open CLI defect
audience: §1 humans (skim) · §2 agents (build)
update-rule: ANY change to copilot capture (parser · store · schema field · routing · unit) updates this doc in the same change, and bumps its DOC-REGISTRY row
---

# ADR-COPILOT — five stores, one spine, and the credit is the vendor's own arithmetic

> The five laws in [ADR-LAWS](0001_laws.md) bind this record already and are **not**
> restated here. Cite this record in prose as its NAME, never by number.

---

## §1 · For humans

**In one line:** Copilot is the only agent that records what it actually charged you —
GitHub writes a **credit** figure per request — and cage captures that number verbatim,
alongside tokens from up to five different on-disk stores.

Two things shape everything here. First, Copilot's CLI writes **running totals**, not
per-turn numbers, so a resumed session re-reports everything it already reported —
cage stores the difference, never overwrites the earlier row. Second, three of the five
stores only exist if you turned on a VS Code debug setting; cage reads them when they are
there and says which are missing when they are not.

### For the meeting

> Absorbed from `docs/copilot-capture.md`, which is removed.

- We meter Copilot from its **own on-disk records** — no vendor API, no network, zero
  infra cost. The numbers are the vendor's, recorded verbatim.
- Per chat we can state **tokens in/out**, and — where GitHub recorded it — the **actual
  billed credits** (premium requests). Credits are the billing truth.
- **Coverage is partial by the vendor's doing:** only some requests carry a credit
  (**~3% observed on real data**, all on the auto-router). Cage reports what exists; it
  never fills gaps with guesses, and never derives a credit from tokens or the reverse.
- **A second, richer ledger sits alongside the spine:** per-chat cached tokens,
  authoritative session credits, and — where three optional VS Code settings are on —
  per-model-call detail from three more stores. Recorded, not surfaced: evidence banked
  for the next read-surface build, not a number anyone sees.
- **Nothing here is a dollar.** Cage measures usage; the credit is GitHub's own
  computation and cage reports it as a count.

### The flow

```mermaid
flowchart TD
    subgraph always["Always present"]
        CS["VS Code chatSessions<br/>4 roots swept"]
        CLI["~/.copilot/session-state<br/>events.jsonl — CUMULATIVE"]
    end
    subgraph gated["Only if you enabled the setting"]
        SC["agentHostUsage sidecar"]
        DL["debug-logs"]
        OT["agent-traces.db (SQLite)"]
    end
    CS --> MM["ledger/copilot/<br/>metric rows + credits verbatim"]
    CLI -->|"delta vs previous shutdown"| MM
    SC --> MM
    DL --> MM
    OT --> MM
    MM -->|"chat + cli-delta ONLY"| SP["ledger.spend()"]
    MM -.->|"sidecar · debuglog · otel<br/>finer views of the SAME traffic<br/>NEVER a spine"| SP
    SP --> V["cage insights chats · commits · commit"]
```

<details><summary>Same diagram, ASCII</summary>

```text
  ALWAYS PRESENT
    VS Code chatSessions (4 roots) ---------> ledger/copilot/ metric rows (+ credits verbatim)
    ~/.copilot/session-state/events.jsonl --> ledger/copilot/ metric rows, as a DELTA vs previous shutdown
        (CUMULATIVE at source)                (never an overwrite)

  ONLY IF THE SETTING IS ON
    agentHostUsage sidecar  \
    debug-logs               >-------------> ledger/copilot/ metric rows
    agent-traces.db (SQLite)/
                                                     |
                             spine = "chat" + "cli-delta" ONLY
                             sidecar/debuglog/otel are finer views
                             of the SAME traffic -> never a spine
                                                     |
                                              ledger.spend()
                                                     |
                                cage insights chats | commits | commit
```
</details>

### What we can say, and how much to trust it

| number | where it comes from | trust |
|---|---|---|
| tokens in / out, VS Code chat | per-request fields in the chat store | vendor-recorded |
| **credits per request** | GitHub's own charge, copied verbatim | vendor-recorded |
| tokens + cached, CLI | running totals, differenced per shutdown | derived by cage (from vendor totals) |
| session credits | max/last, **never summed** | vendor-recorded |
| the real routed model | the sidecar store, when enabled | vendor-recorded |
| time-to-first-token, wait time | debug logs / chat store, when enabled | vendor-recorded |
| **cache-write tokens** | — | **absent: no Copilot store persists them** |
| **dollars** | — | **absent by decision: cage measures usage, never cost** |

### What we can't say, and why

- **Most requests carry no credit at all** — about **3% do**, observed on real data, all
  on the auto-router. Cage reports what exists and never back-fills a credit from tokens,
  in either direction. An absent credit stays absent; it is never a `0`.
- **Cache-write tokens are persisted by no Copilot store.** Claude records them; Copilot
  does not. Permanently honest-empty — a vendor limitation, not a cage gap.
- **A Copilot credit cannot be added to a Kiro credit.** One is GitHub's tokens×rates
  computation, the other is an AWS credit. They share a column heading and nothing else,
  and cage refuses the total rather than inventing a unit.
- **The three optional stores are off by default.** When they are off cage names the
  setting that would enable each, rather than showing a silent zero.

---

## §2 · For agents

### Context

- Copilot writes a **cumulative** `session.shutdown` per shutdown. A resumed session
  (`--continue`, or a VS Code chat spanning restarts) appends a second shutdown whose
  `modelMetrics` already include the first. Keying the call id on session+model index
  alone made the second, higher shutdown collide with the first and get dedup-dropped —
  a **16–18% undercount**, unbounded in principle. Verified on real session `8073abba`:
  shutdown-1 `inputTokens=70,071`, shutdown-2 `107,581`.
- The tempting fix — "on re-seeing a session id, *update* the row to the last cumulative"
  — mutates a ledger row, breaking append-only, determinism, crash-safety and
  concurrent-import safety at once, and is *less* precise: it collapses the per-turn
  breakdown into one moving number.
- **Since 2026-06-01 a Copilot credit *is* GitHub's own tokens×rates computation**, done
  with rates cage cannot see. Cage's price table was reconstructing a number the provider
  had already computed correctly and recorded.
- Copilot's stores overlap heavily: the sidecar, debug-log and OTel stores are **finer
  views of the same traffic** the chat store already describes. A machine that enabled one
  would silently double its own spend if all were spined.
- Chats were being swept from only two `chatSessions` roots; two more exist.

### Decision

**A cumulative source is reconciled with append-only delta rows; the vendor's recorded
credit is captured verbatim and never derived; and only two of the five sources are a
spend spine.**

- **Delta rows, never mutation.** Each `session.shutdown` yields a row carrying the
  per-shutdown delta (`cumulative_n − cumulative_{n-1}` per model). The id encodes the
  shutdown **ordinal**, and **ordinal 0 is byte-identical to the pre-fix id** — so a
  legacy ledger *self-heals* on re-import: ord 0 dedupes against the row already there,
  only ord≥1 appends, and the rows sum to the true cumulative. `totalPremiumRequests` is
  cumulative too and gets the same treatment. **No row is ever mutated.**
- **The reset rule, not a clamp.** A decrease means the counter reset, so the new value
  *is* the delta. Clamping a negative delta to 0 silently discards real spend.
- **`SPEND_SOURCES["copilot"] = ("chat", "cli-delta")`.** `chat` is per-request, durable
  and ungated. `cli-delta` is the point-in-time twin `parse_copilot_cli_metrics` emits
  beside every cumulative `cli` row — the `cli` row itself is preserved verbatim (that is
  why the kind exists) and is listed in `CUMULATIVE_SOURCES` as deliberately excluded.
  **Never sum the two.** `sidecar`/`debuglog`/`otel` are opt-in finer views and are
  never a spine.
- **Four chatSessions roots are swept**, not two: the per-workspace store,
  `no-workspace/`, `emptyWindowChatSessions/` and `transferredChatSessions/`.
- **Credits are a recorded count, captured verbatim and never converted.** Session credits
  collapse as **max/last, never summed**. Absence stays absence — a request with no
  recorded credit is never given one derived from tokens, and pro-rata splitting of a
  group credit by token share is refused.
- **Credits are never summed or ranked across agents** (`units.summable`). The column name
  is the whole of the temptation, so the rule is enforced in code, not by convention.
- **Group billing** carries one `billed_with` carrier row per multi-model shutdown;
  siblings are named, not silently dropped.
- **The metric rows are a separate kind** (`schema.make_copilot_metric`), never a widened
  `calls` row. `ledger.copilot_metrics` collapses last-write-wins per
  `(source, session, surface, request, call)`.
- **Cache-write is honest-empty**: no Copilot store persists it. Not modelled, not zeroed.

> **⟲ The transcript→`calls` leg is RETIRED (P5, v0.51).**
> `ledger/copilot/` carries the same traffic, and the two writers already agreed
> **row-for-row** before the change (`chat` 57 + `cli-delta` 26 = 83 calls, measured on the
> real store) — so unlike claude there was not even an inflation to remove, just a
> duplicate to stop. Verified after: 83 copilot rows in `spend`, zero in `calls`.
>
> `parse_copilot_calls` / `parse_copilot_vscode_calls` are **kept** for the
> `[sources.<name>] format` contract. The reported count is now the **non-overlapping
> grain** (`chat` + `cli-delta`): `cli` is cumulative and its delta twin covers the same
> session, so counting every written row would report a number no view can reproduce.

### Consequences

- History self-heals rather than double-counting — the one property that made shipping the
  delta fix safe against ledgers already in the field.
- A grown cumulative source costs one extra row per shutdown. Rows are cheap; precision
  is not.
- `cage doctor`'s `copilot-metrics` check names per-source coverage **and the enabling
  setting for each gated store**, so a missing optional source reads as *off*, not as
  *empty*.
- Copilot is the only agent carrying both units, which makes it the one place a
  cross-agent credit total looks arithmetically plausible. `units.cross_agent_note` states
  the refusal in one fixed phrasing — a re-worded refusal reads as a different rule.
- **Metric rows carry no `task`** (TASK-GRAIN-SPINE) and no route field, exactly as for
  claude.
- Enabling a gated store adds capture and changes **no** number, by construction. That is
  the point of keeping the spine at two sources.

### Capture reference — store → property → row

> Absorbed from `docs/copilot-capture.md`, which is removed. Capture is pull-based
> (`cage import` / capture-on-read) — no hooks, no network, `$0`. **Absence ≠ zero:** a
> request with no recorded credit stays absent, never derived from tokens in either
> direction.

**`calls` rows** — the priced-shaped surface (now a usage surface):

| number | store → property | lands as |
|---|---|---|
| tokens in/out (VS Code chat) | `workspaceStorage/*/chatSessions/*.jsonl` → per-request `promptTokens`/`completionTokens` | `calls` row (`c_cop<hash>`, surface `vscode`) |
| credits per request (VS Code) | same row → `copilotCredits` (float, verbatim) | `calls.credits` — the only thing that meters `copilot/auto`, where the routed model is unknown |
| tokens + cached (CLI) | `~/.copilot/session-state/*/events.jsonl` → `session.shutdown` per-model cumulative, delta'd | `calls` rows incl. `cached_in` (surface `cli`) |
| credits (CLI) | `session.shutdown` → `totalPremiumRequests` (float, cumulative, delta'd) | `calls.credits` (+ legacy int `premium` — no rendered column since COPILOT-PREMIUM-DEAD, but still summed into the payload and still in `--json`) |
| group billing | `billed_with` — one carrier row per multi-model shutdown | siblings named, never silently dropped |

Chats land from **four** `chatSessions` roots: the per-workspace store, `no-workspace/`,
`emptyWindowChatSessions/` and `transferredChatSessions/` — previously only the first two
were swept.

**`.cage/ledger/copilot/` rows** — a deliberately separate kind
(`schema.make_copilot_metric`), never a widened `calls` row, verbatim from all five
on-disk stores:

| source | store | what lands |
|---|---|---|
| `chat` | VS Code chatSessions (same 4 roots) | per-request `model_totals` (per-model cached tokens), `session_credits` (max/last, **never summed**), `elapsed_ms`/`waiting_ms` |
| `cli` | `session-state/*/events.jsonl` | per-shutdown **cumulative-verbatim** `model_totals`, `credits`, `nano_aiu` — no delta math |
| `cli-delta` | derived twin of `cli` | the point-in-time delta row — **the spine source**; never summed with `cli` |
| `sidecar` | `agentHostUsage/*.jsonl` *(gated: `chat.agentHost.agentDebugLog.enabled`)* | per-model-call tokens + cached + `nano_aiu`, the REAL routed model |
| `debuglog` | `.../debug-logs/<sessionId>/*.jsonl` *(gated: `github.copilot.chat.agentDebugLog.fileLogging.enabled`)* | per-request tokens + ttft (**whitelist read** — the same lines carry prompt bodies) |
| `otel` | `agent-traces.db`, SQLite read-only *(gated: `github.copilot.chat.otel.dbSpanExporter.enabled`)* | per-model-call tokens + cached — the only per-call cached-token source for classic-extension chats |

Parsers: `transcript.parse_copilot_calls` · `parse_copilot_vscode_calls` ·
`parse_copilot_vscode_metrics` · `parse_copilot_cli_metrics` ·
`parse_copilot_sidecar_metrics` · `parse_copilot_debuglog_metrics` ·
`parse_copilot_otel_metrics`.
Reader: `ledger.copilot_metrics` collapses last-write-wins per
`(source, session, surface, request, call)`.
Health: `cage doctor`'s `copilot-metrics` check names per-source coverage **and the
enabling setting for each gated store**. `cage query copilot-metrics` explains it.

### Field-level trace — data point → source file → exact key → function

> Drills the two tables above to the exact on-disk key and the function that reads it.
> **Vendor-recorded** = quoted verbatim from a Copilot store; **cage-derived** =
> computed, reshaped, or delta'd by cage — never a literal field on disk. *(gated)* rows
> only populate when the named VS Code setting is on.

| Data point | Source file (on disk) | Field/key read | Extracted by | Vendor-recorded / cage-derived |
|---|---|---|---|---|
| Input tokens (chat) | `<vscode-user>/…/chatSessions/*.jsonl` (4 roots) | `promptTokens` / `inputTokens` | `_vscode_chat_requests` → `parse_copilot_vscode_calls` / `parse_copilot_vscode_metrics` | vendor-recorded |
| Output tokens (chat) | same | `completionTokens` / `outputTokens` | same | vendor-recorded |
| Cached tokens (chat, agent-host sessions only) | same | `modelTotals[].cachedTokens` | `_copilot_model_totals` → `parse_copilot_vscode_metrics` | vendor-recorded — honest-0 when `modelTotals` is absent (classic-extension sessions) |
| Credits per request (chat) | same | `copilotCredits` | `parse_copilot_vscode_calls` / `_vscode_metrics` | vendor-recorded, verbatim |
| Session credits (running total) | same | `sessionCopilotCredits` | `parse_copilot_vscode_metrics` | vendor-recorded — collapsed max/last, never summed |
| Model id (chat) | same | `modelId` | both VS Code parsers | vendor-recorded |
| Provider (openai/anthropic/google) | — | no such field on disk | `_copilot_provider(model)` | **cage-derived** — string-prefix heuristic on the model id |
| Timestamp (chat) | same | `timestamp` (epoch ms) | `_epoch_ms_iso()` in both VS Code parsers | vendor-recorded value; ISO string is a format conversion |
| Session id (chat) | same | `kind:0` record's `v.sessionId` (fallback: file stem) | `_vscode_chat_requests` | vendor-recorded |
| Elapsed / waiting ms | same | `elapsedMs` / `timeSpentWaiting` | `parse_copilot_vscode_metrics` | vendor-recorded |
| Project (calls row) | `workspaceStorage/<hash>/workspace.json` → `folder`, or same chatSessions row → `toolSpecificData.cwd.path` | — | `_vscode_project()` | **cage-derived** — basename/decode of a URI, no vendor "project" field |
| Tokens in/out/cached, cumulative (CLI) | `~/.copilot/session-state/*/events.jsonl` | `modelMetrics[model].usage.{inputTokens,outputTokens,cacheReadTokens}` | `parse_copilot_cli_metrics` (`source="cli"`) | vendor-recorded, verbatim cumulative |
| Tokens in/out/cached, per-shutdown delta (CLI) | same | same keys, differenced against the prior shutdown | `parse_copilot_calls`; `cli-delta` twin in `parse_copilot_cli_metrics` | **cage-derived** — arithmetic over a vendor cumulative counter |
| Credits, cumulative (CLI) | same | `totalPremiumRequests` (float) | `parse_copilot_cli_metrics` (`source="cli"`) | vendor-recorded, verbatim cumulative |
| Credits, per-shutdown delta (CLI) | same | same key, differenced | `parse_copilot_calls`; `cli-delta` twin | **cage-derived** — delta of a vendor counter |
| `nano_aiu` (CLI) | same | `totalNanoAiu` | `parse_copilot_cli_metrics` | vendor-recorded, verbatim |
| Real routed model + tokens + `nano_aiu`, per call *(gated: agentHost debug log)* ※ | `<vscode-user>/agentHostUsage/<sanitizedSessionId>.jsonl` | `model` / `inputTokens` / `outputTokens` / `cacheReadTokens` / `totalNanoAiu`, keyed by `turnId` | `parse_copilot_sidecar_metrics` | vendor-recorded |
| Tokens + model + time-to-first-token, per call *(gated: agentDebugLog file logging)* | `.../debug-logs/<sessionId>/*.jsonl` | `attrs.inputTokens` / `attrs.outputTokens` / `attrs.model` / `attrs.ttft` | `parse_copilot_debuglog_metrics` | vendor-recorded — whitelist read, same lines carry prompt bodies |
| Tokens + cached + ttft + model, per call *(gated: OTel sqlite exporter)* ※ | `agent-traces.db` (SQLite, table `spans` WHERE `operation_name='chat'`) | `input_tokens` / `output_tokens` / `cached_tokens` / `ttft_ms` / `COALESCE(response_model, request_model)` | `parse_copilot_otel_metrics` | vendor-recorded |

**※ The paths for these three gated stores are `UNVERIFIED-LAYOUT` on Windows** —
`agentHostUsage`, `debug-logs` and `agent-traces.db` are *inferred from the VS Code
user-dir convention, never pinned on a real Windows install*, which is what
`paths.copilot_metric_sources` says in its own words. The table above states them flat
because that is how the resolver reads them; the hedge belongs beside them, since a
path stated as fact is precisely how the F1 class (a capture route that is silently
absent rather than loudly broken) has bitten this project before. macOS/Linux layouts
are verified.

### Known gaps (open)

- ~~**CLI credit-delta loss**~~ — **CLOSED 2026-08-03** (REV-CREDITS defect 1), verified
  against code 2026-08-18. The gap read "the credit delta is dropped when the first-listed
  model has no token delta"; both halves are now false. `transcript._place_billing_delta`
  picks the carrier as the **largest token mover** (ties on model name) — deterministic and
  **independent of `modelMetrics`' dict order**, so "first-listed" names nothing — and when
  *every* model idled with a non-zero credit delta it **appends a zero-token carrier row**
  rather than dropping the credit. Kept struck rather than deleted: it was a live veto
  trigger, and a reader who remembers the defect needs to find its resolution, not a
  silence.
- **Cache-write tokens** — persisted by **no** Copilot store. Permanently honest-empty;
  not a cage gap. (Measured: 0 of 57 vscode rows carried `cached_in`, 2026-08-14.)
- **No read surface for `.cage/ledger/copilot/`** — a `cage insights copilot` view, or new
  chats-view columns, are parked in `work/OPEN-WORK.md`, not built. No view reads the four
  gated stores' detail today: recorded, not surfaced.
- **TASK-GRAIN-SPINE** — metric rows carry no `task`; task-grouped analysis sees zero.

### Alternatives rejected

- **Mutate the row to the latest cumulative** — breaks append-only, determinism,
  crash-safety and concurrent-import safety, and is *less* precise. Rejected outright.
- **A fresh id for every shutdown** (dropping ord-0 identity) — a legacy ledger would then
  add ord 0 twice (70,071 double-counted). Byte-identity of ord 0 is exactly what makes
  self-heal work.
- **Clamp a negative delta to 0** — silently discards real spend. The reset rule is
  correct and is reused from `parse_copilot_cli_calls`.
- **Spine every source cage captures** — the sidecar, debug-log and OTel stores describe
  the same traffic as `chat`; a machine that enabled one would double its own spend.
- **Spine the cumulative `cli` row instead of its delta twin** — a cumulative row carries
  its session's entire life stamped at the latest capture, so a straddling session lands
  twice, invisibly, because both figures are individually correct.
- **A separate ledger per agent** — separation by *source* is arbitrary; the real axis is
  the *shape* of the number.
- **Derive a credit from tokens where one is absent** (or tokens from a credit) — that is
  a conversion between units, forbidden in both directions.
- **Pro-rata splitting of a group credit by token share** — same objection; it derives
  per-row credits from tokens.

### Reference

- **Worked example, real data:** session `8073abba` — delta rows sum to 107,581
  (`70,071 + 37,510`), recovering the exact undercount and reaching the hand-counted
  truth 227,298. Self-heal proven end to end: legacy row → re-import → exact total →
  third import adds 0.
  [work/regression/2026-07-28-finding-copilot-resumed-undercount.md](../../work/regression/2026-07-28-finding-copilot-resumed-undercount.md) ·
  [work/regression/2026-07-28-capture-precision-fixes.md](../../work/regression/2026-07-28-capture-precision-fixes.md)
- **Cache-write measured absent** — 0 of 57 vscode rows carried `cached_in` on
  2026-08-14: `cage/units.py` module docstring.
- Ratified as archived ADRs 0004 (delta rows, separate by schema) and 0010
  (`SPEND_SOURCES`, point-in-time-never-cumulative) — **named, not cited**. Both are live
  as [ADR-LAWS](0001_laws.md) Law 3 and this record's own §2 respectively.

### Veto condition (when to revisit)

**1 · Falsifiable triggers, numbered.**

1. **The delta-row design** reopens only on a **measured** case where per-shutdown deltas
   cannot reconstruct the true cumulative — a source that *rewrites* an earlier
   shutdown's figure **downward**, so the delta goes negative and the reset rule
   misreads it as a reset. **Name the session and the two figures** when reopening; an
   argument that it "might" happen is not enough. The change lands in
   `transcript.parse_copilot_calls` (negative handling), not a storage redesign.
2. ~~**The open CLI credit-delta defect**~~ — **FIRED AND RESOLVED, 2026-08-03**
   (REV-CREDITS defect 1; confirmed against `transcript._place_billing_delta`
   2026-08-18). The trigger asked for "the count of affected shutdowns from a real
   store" before acting; the defect was instead fixed outright, so the count was never
   needed and this trigger can no longer fire. Struck, not deleted — a numbered trigger
   that silently vanishes reads as an oversight. **Nothing replaces it**: no successor
   condition was identified, and inventing one to keep the slot filled would be exactly
   the aspirational veto this record's own rules forbid.
3. **`SPEND_SOURCES` membership.** A new store joins the spine **only** if it is
   point-in-time **and** covers a surface no existing spine covers. Adding a store to the
   metric kind does **not** add it to the spine — that separation is the design.
4. **Cage displays a currency figure again** only when a store carries a per-request
   currency amount on **≥ 80% of its rows**, measured on a real install and written up in
   `work/research/` before any code moves. It would land as an additive optional field on
   the metric row and one rendered column — **never** a price table, a rate config, or a
   `prices` command group.

**2 · Contingent vs. invariant.**

- **Contingent (auto-revisits on evidence):** which sources are cumulative; which stores
  are gated and by which setting; the four chatSessions roots; whether cache-write ever
  becomes available. *(The CLI credit-delta defect was listed here until 2026-08-18 — it
  has been fixed since 2026-08-03, so it can no longer auto-revisit anything; see
  trigger 2 above.)*
- **Invariant (moves only by ratified reversal of this ADR):** **absence is never
  rendered as `0`**; a spine source is **point-in-time, never cumulative**.
  - Also binding here, but **owned by ADR-LAWS and deliberately not restated** — a second
    copy can drift, and drift in a law is invisible until it prints a wrong number:
    append-only (**Law 3**) and usage-never-cost, which carries both *credits are never
    summed or ranked across agents* and *no conversion between units in any direction*
    (**Law 5**, enforced in code by `units.summable`).

**3 · Deliberately not taken.**

- **A read surface dedicated to `.cage/ledger/copilot/`** — the four gated stores hold
  detail (per-model-call cached tokens, real routed model, ttft) that no view renders.
  Recorded now, surfaced never yet: it is evidence banked, and the absence of a view is a
  scoping choice, not an oversight. **Threshold to reopen:** a question a user actually
  asks that the spine cannot answer and one of these stores can.
- **A user-supplied credit→currency rate, applied locally and labelled `modeled`.**
  Declined, not dogmatically rejected — a user asserting their own contract is honest in
  a way a shipped rate card is not. Not taken because it reintroduces the entire pricing
  surface to serve a number only its author can check. **Threshold to reconsider:** more
  than one user asks for it *by name*, and it lands as a display multiplier over an
  existing recorded count — never a second pricing basis a total can silently span.
