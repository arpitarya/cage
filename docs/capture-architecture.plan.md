# Design plan: capture architecture — hooks optional, one common place

**Status:** Design of record for the capture rework. Not yet a build handoff — the
approach is settled here first; the `<feature>.handoff.md` + `.prompt.md` pair comes after.

**Decided by Arpit (the two load-bearing calls):**
1. **Trigger = import the logs from a common place.** Not per-agent hooks. One canonical
   sweep over one canonical location.
2. **Eventual is fine** — real-time is not a requirement. **But graphify savings must be
   captured too**, not just LLM tokens.

Everything below follows from those two.

---

## 1. The problem, stated cleanly

Capture today has **two mechanisms that don't converge**, and **four hook systems that
mostly don't fire.**

**Two mechanisms:**
- **Pull** — an agent writes its own session log (`~/.claude/projects`, `~/.codex/sessions`,
  `~/.copilot/session-state`, Kiro's `tokens_generated.jsonl`); `cage import` reads them into
  the ledger. This is the "common place" idea — except it's *four* places, one per agent.
- **Push** — graphify and fux shims call `record_receipt` (`graphifymeter.py:96`) **directly
  into the ledger** at the moment they run. No log, no import. The ledger they hit is whatever
  `paths.resolve_root` returns *at that instant* (`--ledger`/`CAGE_BASE` → project `.cage/` →
  global `~/.cage`).

**The gap the user named:** a pushed graphify receipt lands in the ledger the cwd resolved to
*when graphify ran*. A `cage report` resolves the ledger *independently*, later, possibly from
a different cwd. If they differ, **the saving is captured but invisible** — the same silent
class as a wrong log path, but for push instead of pull.

**Four flaky hook systems** (verified in the wire modules):

| Agent | Hook reality | Fires when |
|---|---|---|
| **Claude** | Stop / SessionStart / SessionEnd in `.claude/settings.json` | CLI only — **never under the VS Code extension** |
| **Codex** | `.codex/hooks.json`, Stop + SessionStart | CLI; not under a GUI/extension |
| **Copilot** | **user-level** `~/.copilot/hooks` only (repo hooks *never* fire); usage written *after* hooks run | CLI; always a session late |
| **Kiro** | one-hook-per-file, **only `agentStop`** (no session-start), coarse log | agentStop only; IDE PATH quirks |

No two agents' hooks have the same shape, trigger set, location, or timing. They are four
special cases, each with its own scar tissue, and the user's own experience is that they
"aren't working properly." **The plan stops treating hooks as a capture mechanism at all.**

## 2. The ideal model: lazy capture-on-read over one canonical ledger

**One sentence:** capture happens when someone reads, by sweeping a canonical registry of log
locations into a single canonical ledger — and every push (graphify/fux) targets that *same*
canonical ledger. Hooks become a pure latency optimization that the correctness of the system
never depends on.

```
        ┌─────────────────── the ONE canonical ledger ───────────────────┐
        │   resolved ONCE, deterministically, per machine/project         │
        └────────────────────────────────────────────────────────────────┘
              ▲ push (record_receipt)                 ▲ pull (import sweep)
              │                                       │
       graphify / fux shims                    log registry ([sources]):
       (Tier-0 savings receipts)               ~/.claude · ~/.codex ·
                                               ~/.copilot · Kiro log · …
                                                       ▲
                                                       │ triggered by:
                          ┌────────────────────────────┼───────────────────────────┐
                    capture-on-read              `cage import`               optional hooks
                 (every report/MCP/doctor      (manual / user's own cron)   (real-time, best-effort,
                  lazily imports first)                                       never load-bearing)
```

Three triggers, one sweep, in strict priority of reliability:

1. **Capture-on-read (the new primary).** Every read that matters — `cage report`, the MCP
   read tools, `cage doctor`, `cage insights *` — runs a fast **incremental** import first,
   then answers. Because cursors already make a no-op sweep nearly free (`cursors.json`
   skips unchanged files by `(size, mtime)`), "nothing new" costs a `stat` per file. This is
   the mechanism that makes "eventual is fine" hold: capture is guaranteed to have happened
   the instant before any number is shown. It needs **no daemon, no scheduler, no cron, no
   background process** — it fits $0/stdlib/fail-open exactly.
2. **`cage import` (the explicit verb).** Unchanged. The manual path, and the thing a user's
   *own* cron/schtasks line calls if they want it hands-off. cage still installs no scheduler.
3. **Hooks (demoted to optional real-time).** Where a hook *does* fire, it just calls the same
   import sweep earlier, so mid-session spend lands sooner. It is a **cache-warming
   optimization.** If every hook on the machine is broken, capture is still correct and
   complete — just as fresh as the last read. This is the property the current design gestures
   at ("pull-based, hooks demoted") but doesn't fully deliver, because reads don't self-import.

**What this deletes conceptually:** the need for hooks to be reliable, symmetric, or even
present. Their per-agent divergence stops mattering because they're no longer a correctness
path — they're an optional speedup on top of a path that always works.

## 3. The two things that must converge on ONE ledger

This is the heart of the user's ask. "A common place" is not primarily about log locations
(the `[sources]` registry already unifies those) — it's about the **ledger** that push and
pull both land in and every read reads from.

### 3.1 One deterministic ledger resolution, everywhere

`paths.resolve_root` already defines the precedence: `--ledger`/`CAGE_BASE` → nearest project
`.cage/` from cwd → global `~/.cage`. The rule is sound; the **failure is that different
processes resolve it differently** because they run from different cwds:

- graphify invoked from a subdirectory resolves to global `~/.cage` (no project `.cage/` above
  it) while `cage report` from the repo root resolves to the project `.cage/`. **Split
  ledger, stranded saving.**

**Ideal:** capture and read must resolve to the *same* ledger for the *same logical project*,
independent of the cwd the tool happened to launch from. Options to decide in the handoff:
- **(a) Project-anchored env.** When a project `.cage/` is wired, `cage-run` / the shim exports
  `CAGE_BASE` pointing at it, so every child (graphify, fux, a nested `cage`) inherits the same
  sink regardless of cwd. Cleanest; leans on the shim that already exists.
- **(b) Read-time union.** A read over the project ledger *also* sweeps the global `~/.cage`
  for rows tagged to this project and folds them in (by row id, the existing
  `mergeutil.union_by_id`). Catches strays without changing where anything writes.
- **(c) Push-to-global-always.** graphify/fux always write global `~/.cage`; project reads
  union the global. Simple mental model ("savings live in one machine-wide place") at the cost
  of per-project isolation.

Recommendation to carry into the debate: **(a) as the mechanism, (b) as the safety net.**
Anchor writes deterministically, and still union at read so a pre-anchor stray is never lost.

### 3.2 graphify/fux savings ride the canonical ledger, not a cwd guess

graphify's receipt is a **push**, and it's the more fragile of the two because it has no log to
re-import — if it lands in the wrong ledger, there is no second chance to pull it later. So:

- graphify/fux `record_receipt` must resolve the **same** canonical ledger as reads (§3.1).
- **Belt-and-suspenders:** graphify already writes `graphify-out/` (manifest, cache) in the
  project. If a saving is ever pushed to the wrong ledger, a read-time reconciliation could
  recover it — but the primary fix is §3.1, so a receipt is never misfiled in the first place.
- **Determinism preserved:** the receipt still carries its own method/confidence; capture
  location is not part of any id, so anchoring the sink changes nothing about the numbers.

**This is the concrete answer to "graphify saving should be captured as well":** it's captured
by making push and pull share one resolved ledger, so a savings receipt is always in the same
place the report reads from — the exact property that fails today.

## 4. Per-agent hooks, if we keep them (as optimization only)

Since hooks are now optional speedups, the design goal flips from "make them symmetric and
reliable" (impossible — the clients differ) to **"each agent's hook, when it fires, does the
one safe thing: trigger the canonical sweep. Nothing more."**

- **Every hook, every agent, collapses to one action:** `cage import` (the global all-agent
  sweep, `paths.cage_import_all`). No per-agent cleverness, no session banners on the
  correctness path, no dependence on *which* event fired. A hook that fires warms the cache; a
  hook that doesn't costs nothing because the next read captures anyway.
- **Claude** — keep Stop for real-time warmth; drop reliance on SessionStart/SessionEnd
  backfill (capture-on-read *is* the backfill now). Under the VS Code extension where none
  fire: fully covered by read-time capture.
- **Codex** — keep Stop; same demotion.
- **Copilot** — the "usage written after the hook, so always a session late" quirk **stops
  mattering** — the next read captures the prior session regardless. Keep the user-level hook
  only if it's free to maintain; otherwise drop it and rely on read-time.
- **Kiro** — `agentStop` re-importing the whole coarse log is fine as a warmer; the proxy
  stays the higher-fidelity fallback. No session-start gap to worry about anymore.

**Litmus test for keeping any hook:** does it reduce *latency* enough to justify its
maintenance? If a hook's only job was *correctness* (backfill), capture-on-read has replaced
it — delete it. Fewer committed hook files = less portability surface, less scar tissue.

## 5. How it works with NO hooks at all (the primary path, stated explicitly)

This is the user's direct question. With zero hooks wired on the machine:

1. Agents write their own logs as they always do (cage does nothing here — it never captured
   the write, only read the result).
2. graphify/fux push savings receipts into the canonical ledger at run time (§3).
3. The user runs `cage report` (or opens the MCP read tools, or `cage doctor`). **That read
   lazily runs the incremental import first** — sweeping the `[sources]` registry into the
   canonical ledger — then renders. Everything the agents logged since the last read is now
   captured.
4. Result: **complete and correct capture with not a single hook installed.** The only thing
   the user gives up is intra-session freshness, which they said they don't need.

For a user who wants it *fully* hands-off (captured even if they never open a report), the
answer stays: **their own** `cron`/`schtasks`/launchd line calling `cage import` — cage prints
the OS-appropriate hint (`render.scheduler_hint()`) but installs nothing. `cage data watch`
remains the opt-in foreground loop for a live terminal. The product invariant "cage installs no
OS scheduler" is **kept** — capture-on-read is what makes keeping it painless.

## 6. What changes, what's deleted, what's kept

**New:**
- **Capture-on-read**: a shared, throttled, fail-open `ensure_captured(root)` that read
  commands and the MCP server call before answering. Throttled (once per N seconds via a
  cursor timestamp — `_last_import` already exists) so back-to-back reads don't re-sweep.
  Fail-open: a capture error must never block a read.
- **Deterministic sink anchoring** (§3.1) so push and pull converge.

**Deleted / demoted:**
- Hooks as a correctness path. SessionStart/SessionEnd *backfill* logic where its only role
  was correctness. Per-agent hook divergence as a thing that has to be reasoned about for
  completeness.
- The mental model that a user must run `cage import` or wire a hook to see accurate numbers.

**Kept (non-negotiable invariants):**
- $0 / stdlib-only / deterministic / fail-open-on-write.
- **cage installs no OS scheduler.** Capture-on-read replaces the need, doesn't reverse the
  rule.
- Four agents first-class in the `[sources]` registry and the sweep.
- Counts-never-content PII guard; method/confidence tagging; `mergeutil.union_by_id` for any
  fold.
- The pull sweep and its cursors; `[sources]` as the one log registry (incl. the v0.29
  commented block + globs).

## 7. Interaction with the other in-flight work

- **`capture-health`** (silent-zero-capture warning) becomes *more* correct here: capture-on-
  read means `_health` is refreshed on every read, so the warning reflects the true latest
  state, not the last time a hook happened to fire. The triple gate is unchanged; its data is
  just fresher. **Sequence capture-on-read to land with or before capture-health.**
- **`sources-defaults` (v0.29, staged)** already unified the *log* locations. This plan unifies
  the *ledger* and the *trigger*. They compose cleanly; no conflict.

## 8. Stress test (proportional — architecture change)

**Devils-advocate — "capture-on-read adds latency and hidden I/O to every read."**
Answer: incremental cursors make a warm no-op a `stat` per source file (tens of files), sub-
millisecond, and it's throttled to once per N seconds. `cage report` already reads the whole
ledger; a bounded stat-sweep in front of it is noise. If it ever isn't, the throttle window is
the dial. It stays fail-open, so worst case a read is exactly as fresh as today.

**Devils-advocate — "you're coupling reads to a write path; determinism law says derived views
don't mutate state."** Real tension. Resolution: capture-on-read writes the *ledger* (append-
only capture), not any *derived* artifact, and the derived *numbers* are still a pure function
of the ledger it reads. The law is "same ledger + same policy ⇒ same tables," and that holds:
capture-on-read changes *when* rows arrive, never how they're computed. But it must be
**suppressible** — `CAGE_CAPTURE=0`, `--no-import`, and every determinism/golden test must run
with capture-on-read **off**, reading a fixed ledger. This is a hard requirement, not a nicety.

**Pre-mortem — "6 months out, capture-on-read silently swallowed a real import error and a user
under-reported spend for a quarter."** Cause: fail-open ate the error with no trace. Mitigation
(from day one): every capture-on-read swallow logs under `CAGE_DEBUG` (audited by
`test_debug_coverage.py`), and `capture-health` surfaces "import last errored" the same way it
surfaces zero-capture. Fail-open, never silent — the existing house rule, enforced here too.

**Pre-mortem — "graphify savings still went missing."** Cause: the sink-anchoring (§3.1) shipped
but a code path bypassed the shim and resolved a different cwd. Mitigation: a single
`canonical_ledger()` resolver that graphify/fux/reads **all** call — no direct `resolve_root` in
the push path — plus the read-time union (§3.1b) as the net, plus a test that pushes a receipt
from a subdirectory and asserts a repo-root read sees it.

**Residual risk:** capture-on-read means the *first* read after a long gap does the heavy sweep
and is slower. Acceptable and honest — show a one-line "importing…" only if it exceeds a
threshold; never fake instantaneous.

## 9. Decisions (council + research, resolved)

**Q1 — sink mechanism: route by identity, do NOT relocate. VERIFIED.**
A verify-first test settled it: a graphify receipt pushed from a repo *subdirectory* is seen
by a repo-root read — because `_resolve_root` walks *up* for `.cage/`, so push and pull already
converge in the normal case. **The "graphify gap" is a phantom for the common case.** My
earlier subdir example was wrong.
- Every option that *relocates* graphify's write is rejected: **(a) shim-exported `CAGE_BASE`
  can't reach graphify** (it runs as its own process, not through `cage-run`); **(b) blind
  global→project union over-attributes** (the only project key on a receipt is `project`, a
  *basename* — two repos named `api` collide); **(c) push-to-global mixes tenants** with no
  partition key.
- **The fix is identity, not plumbing:** the two narrow real gaps (graphify run *outside* the
  tree; a nested monorepo `.cage/`) get one primitive — a stable, **non-PII project routing
  key = hash of the resolved ledger-root path**, stamped on pushed receipts. A read-time
  reclaim is allowed *only* filtered by that exact key, as a backstop — never the main path.
  This is the sole new schema surface.

**Q2 — delete all four token-capture hooks (symmetric). Keep provenance + MCP.**
Reframed by the invariant: cage must serve any single agent OR any combination, so a
per-agent "proof-of-life" warmer (the tenth-man's Claude-`Stop`-only idea) is **out** — it
would privilege Claude and leave a Codex-/Kiro-only user with nothing. The only symmetric
options are *all four* or *none*; latency is unwanted and dead optional code misreports its own
health, so → **none.** But the audit (§11) forces a precise scope: delete **token-capture
lifecycle hooks only**. See §11 for what must survive.

**Q3 — capture-on-read throttle:** a `constants` value with a policy-preferred `[capture]`
fallback (the `DEFAULT_CONFIDENCE`/`IDLE_CAP_MINUTES` house pattern). Not open.

**Q4 — which reads capture:** all of report / insights / doctor / **MCP read tools**. The MCP
tools are the agent-facing surface and become the *de facto* real-time path — an agent querying
spend mid-session triggers a fresh sweep. Not open.

## 10. Next step

This document is the design of record. With §9 resolved and §11–§12 folded in, it converts to a
`capture-architecture.handoff.md` + `.prompt.md` pair via the implementation-handoff flow.

## 11. Audit — what we have today, and what the new design was missing

The word "hooks" hid **three subsystems** that `agents.install` writes into the same files.
The original design would have deleted all three. Only the first should go.

| Subsystem | Hook subcommands | What it really is | Fate |
|---|---|---|---|
| **Token capture** | `hook-stop`, `hook-session-start`, `hook-session-end`, agentStop | latency — import tokens sooner | **DELETE** (capture-on-read replaces) |
| **Provenance / authorship** | `hook-post-tool-use` → `hook-post-commit` → `hook-prepare-commit-msg` | **trust tier**, not latency: a live `hooked` row is strictly higher trust than the `transcript` fallback (`PROVENANCE_METHOD_TRUST` 2 vs 1) | **KEEP** |
| **Task close / git snapshot** | `hook-session-end` → `tasks.record(snapshot=True)` | folds a git snapshot at session end | **KEEP a path** (see C) |

**Gaps the new design missed — must be in the handoff:**

- **A. Provenance is capture *quality*, not latency (the big miss).** `claudewire` bundles
  `PostToolUse` (the authorship edit-buffer, plan §3.5) into the *same* `.claude/settings.json`
  block as the token hooks, and `gitcommithook` (post-commit resolution + prepare-commit-msg
  stamping) rides along in `agents.install`. Deleting these does **not** trade latency — it
  silently downgrades every commit's authorship from `hooked` to the `transcript` fallback.
  **Scope Q2 precisely: remove Stop/SessionStart/SessionEnd/agentStop entries only; the
  PostToolUse + git-commit hooks stay.** capture-on-read cannot substitute — reads don't buffer
  live edits.

- **B. SessionEnd is doing double duty.** It is both a token backstop (deletable) *and* the
  trigger for task-close git snapshots (not). Splitting them: automatic task-close disappears
  with the token hook. Decision for the handoff — either (i) accept task close as explicit-only
  via `cage outcome` (tasks were always semi-manual), or (ii) derive task boundaries from
  transcript session edges at import time. Lean (i) for now; flag (ii) as follow-on. **Do not
  let "delete SessionEnd" silently kill task snapshots.**

- **C. The proxy meter is a third capture mode the design omitted.** `proxy.py` +
  `usageparse.py` push via `record_call` (`proxy.py:61`) — real-time wire capture for any
  client pointed at its base URL, independent of both logs and hooks. It's opt-in and already
  routes through the canonical ledger (`record_call` → `_resolve_root`). The model is **pull
  (logs) + push (graphify/fux/proxy)**, not just pull+graphify. Name it as first-class so the
  handoff doesn't accidentally strand it; it needs the same §3.1 canonical-ledger discipline.

- **D. Proof-of-life must become symmetric.** `hook-session-start` printed the spend banner —
  the only ambient "cage is alive" signal, and Claude-only. Deleting it (correctly) removes
  that. Replace it symmetrically, never per-agent: `cage doctor` + `capture-health` own the
  "wired but capturing nothing / haven't captured lately" signal for all four equally, and
  `cage setup` promotes the unattended-capture cron/schtasks line (`render.scheduler_hint()`,
  already exists) as the honest hands-off path. Honesty replaces a half-firing banner.

- **E. capture-on-read is the agents' real-time path (a strength, name it).** With the MCP read
  tools calling `ensure_captured` first, an agent asking cage about spend mid-session gets a
  fresh sweep — the real-time capture the deleted hooks provided, delivered on-demand and
  symmetric across all four agents. This is why deleting the token hooks costs the agent-facing
  experience nothing.

**Net after the audit:** delete four token-capture hook entries; keep the provenance + git
subsystem, the MCP read servers, the proxy, and task-close-via-`cage outcome`; add
capture-on-read + the non-PII project routing key. The portability surface shrinks (fewer
committed token-hook files) without touching the authorship trust tier.

## 12. Observability & debugging — make capture *visible*

Deleting the hooks removes the ambient "cage is alive" signal, and capture-on-read is
invisible by nature (it happens *before* a read, silently). So the design must actively
**show** capture, or a user can't tell working-and-quiet from broken-and-quiet. This is the
same failure `capture-health` fights, extended from "did it break?" to "prove it worked."

### 12.1 The one law that governs all of this

cage's meter is **fail-open and silent on any request path** — a library/proxy/hook meter must
never print into a request/turn. A visible "captured" line would violate that *if applied
everywhere*. The rule that keeps it consistent:

> **Confirmation prints only on user-invoked surfaces (a CLI command the human/agent ran on
> purpose), never on a library, proxy, or hook request path.** The request path stays silent
> and fail-open; it records to the debug trace only.

That single distinction is what lets us add the visibility the user wants without breaking the
metering law.

### 12.2 Capture confirmation surfaced to the chat/agent (the ask)

- **graphify / fux (user-invoked, wrapped):** `graphifymeter` already snapshots receipt ids
  before/after the wrapped run and *knows* when a new saving was filed (`graphifymeter.py`
  before/after diff). After the child exits, if a receipt landed, print **one line to stderr**
  (not stdout — never corrupt graphify's own parseable output):
  ```
  ✔ cage: graphify saving captured — ~900 tokens (→ project ledger .cage/)
  ```
  Because graphify runs as a bash command in the agent's turn, that line lands in the tool
  result the agent (and the human) sees — "graphify details captured," exactly as asked.
  Counts only, never content (PII law). Suppressible: `CAGE_QUIET=1` / `--quiet`. On by default
  for the interactive/wrapped path because the whole point is proof it worked.
- **capture-on-read (user-invoked read):** when the pre-read sweep on `cage report` /
  `insights` / `doctor` imports new rows, print a dim one-liner *above* the output; **zero new
  rows ⇒ silent** (no nagging on a warm cache):
  ```
  · captured 240 new calls (claude, codex) + 3 graphify savings since last read
  ```
  This makes the lazy sweep trustworthy — the user sees it happened, and sees the dedup
  (implicitly: only *new* rows are announced).
- **The MCP read tools (agent-invoked):** the same "N new captured" summary is returned as a
  structured field on the MCP response, so an agent asking cage about spend mid-session gets
  both the numbers *and* the confirmation capture just ran. This is the agent-facing
  proof-of-life that replaces the deleted per-turn hooks — symmetric across all four agents.

### 12.3 The debug trace (`CAGE_DEBUG`) extended to every new path

Every new capture path joins the existing metadata-only trace (`debuglog.py`, audited by
`tests/test_debug_coverage.py` — "fail-open but never silent" is *tested*):

- **Ledger-resolution decisions** — the single most useful new diagnostic, because it targets
  the exact stranding class we're designing against. Every push and every read logs *which*
  ledger it resolved and *why*: `resolved ledger: project /repo/.cage (walked up from
  /repo/pkg/deep)` vs `global ~/.cage (no project .cage above cwd)`. A "my graphify saving
  vanished" mystery becomes one grep.
- **Every capture-on-read sweep** — src probed, files matched, rows appended, rows deduped
  (reuse the existing `probe`/`import` event shapes).
- **The routing-key backstop** — when a receipt is reclaimed from global by exact key match,
  log it: `reclaimed 1 graphify receipt (routing-key <hash>)`. The backstop is observable,
  never magic.
- **Every fail-open swallow** on the new paths logs under `CAGE_DEBUG` (the house rule; the
  test enforces it).

### 12.4 `cage doctor` — a capture timeline, symmetric across modes

Add a per-source, per-*mode* last-seen table so "is it working?" is answerable at a glance for
every agent and every capture mode equally (not just the ones with hooks):

```
capture timeline (last seen):
  claude    pull (read-sweep)   2m ago    12,400 rows
  codex     pull (read-sweep)   5m ago     3,100 rows
  copilot   pull                never      —   (⚠ ~/.copilot exists, 0 captured — see capture-health)
  kiro      pull                never      —   (home absent — not installed)
  graphify  push (record_receipt) 40s ago    47 receipts
  proxy     push (wire)         never      —   (not configured)
```

This folds the §11-C proxy and the graphify push into the *same* observability surface as the
agent logs — one place answers "what has cage captured, how, and when," for the whole
pull+push model. It also exports into `cage doctor --bundle` (the redacted, counts-never-content
archive) so a support report carries it.

### 12.5 Extra observability worth adding (beyond the ask)

- **`cage data tail`** — a live one-line-per-capture stream (foreground, Ctrl-C, exit 130 —
  mirrors `cage data watch`). Watch captures happen in real time while debugging a wiring
  problem, without `CAGE_DEBUG` noise.
- **Dedup made visible** — the "captured N new / skipped M already-seen" pairing everywhere a
  count is shown, so the #1 fear of a lazy re-sweep (double-counting) is *visibly* answered by
  the tool rather than asserted in docs.
- **`--why-ledger` on any read** — print the resolution decision (§12.3) on demand, not just
  under `CAGE_DEBUG`. The user-facing form of the stranding diagnostic.

### 12.7 Phase 1 as shipped (v0.31.0) — the split + resolved open questions

The design landed **phased** (handoff §2): Phase 1 is **additive — no hook file or wiring
module was touched** — precisely because shipping the new path and deleting the old one in
one release would, on a Phase-1 bug, stop capture entirely and silently. Both paths are
idempotent (`ledger.append_new` id-dedupe), so they coexist at the cost of a redundant
sweep. **Phase 2** (deleting the token-capture hooks) is a separate later release, gated on
Phase 1 proving in the field that capture-on-read captures everything the hooks did. Until
then this plan + the handoff/prompt pair stay **active in `docs/`** (not archived).

Open questions resolved at build time (Arpit):

- **`cage doctor` does NOT sweep.** Doctor's job is to *diagnose* capture; a pre-render
  sweep could mask the very breakage being diagnosed (§8/§10). So capture-on-read is wired
  into `report` / `insights *` / the MCP read tools only — **not** doctor. Doctor still
  gains the §12.4 timeline, built **read-only** from the ledger it already holds.
- **A dedicated determinism switch.** Capture-on-read is gated by `[capture] on_read` /
  `CAGE_CAPTURE_ON_READ` (default on) — a *separate* knob from `capture_enabled`. The whole
  golden/determinism suite pins it **off** (conftest), so every determinism test reads a
  fixed ledger and a warm read is byte-identical to before. `CAGE_CAPTURE=0` still pauses
  all capture; `--no-import` is the per-invocation form.
- **Throttle default 60s** (`constants.CAPTURE_ON_READ_THROTTLE_SECS`, policy `[capture]
  read_throttle_secs`), keyed on the existing `_last_import` cursor — no new state file.
- **Routing key is row-only.** The receipt `route_key` is stamped into the JSON row (for
  reclaim) but deliberately kept **out of `RECEIPT_FIELDS`**, so the reporting CSV is
  byte-unchanged — additive like `gap_ms`, included only when set, never part of an id.
- **The confirmation goes to stderr**, not "above the output on stdout" — safer than the
  §12.2 sketch: it can never corrupt a `--json`/`--csv`/piped stdout stream, and still lands
  in the terminal (and the agent's tool result). The MCP surface returns it as
  `structuredContent.capture` instead of any stdout.
- **Prerequisite refactors landed first** (§9.6): `hooks.append_new` → `ledger.py` (+
  re-export shim); the `doctor` "never imported" string rewritten to "capture off/errored".
  `backfill_status`/`realtime_status` were **not** fed into the new timeline (they're Phase-2
  deletions).

### 12.6 What this deliberately does NOT do

- No content, ever — every confirmation and trace line is counts/ids/paths, never a prompt
  body (PII law, unchanged).
- No printing on a library/proxy/hook request path (§12.1).
- No new always-on background process — `tail`/`watch` are opt-in foreground; nothing is
  installed (the no-scheduler invariant holds).
- No confirmation that fires on a warm cache (zero new rows ⇒ silent) — visibility, not nagging.
