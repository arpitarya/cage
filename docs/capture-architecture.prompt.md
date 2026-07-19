# Claude Code prompt: capture architecture — Phase 1

You are implementing **Phase 1** of `docs/capture-architecture.handoff.md`. Read that handoff
first, and `docs/capture-architecture.plan.md` (the design of record) before it — the plan
carries the reasoning, the handoff is the spec. Its Definition of Done (§2 Phase 1), Scope (§3)
and Non-negotiables (§6) are binding.

**Objective:** make capture correct **without depending on hooks** — every read lazily sweeps
the log registry into one canonical ledger; push (graphify/fux/proxy) and pull converge on that
same ledger; and capture becomes *visible* instead of silent.

## ⛔ Phase 1 is ADDITIVE. Do not touch a single hook file.

Phase 2 (deleting the token-capture hooks) is a **separate, later release**, deliberately.
The reason is the gate finding that blocked the original shape:

> If capture-on-read ships with a bug *and* the hooks are already deleted, capture stops
> **entirely and silently** — the exact failure this design exists to prevent.

Both paths are idempotent (`hooks.append_new` dedupes by id), so they coexist harmlessly.
**If you find yourself editing `.claude/settings.json`, `.codex/hooks.json`,
`~/.copilot/hooks`, `.kiro/hooks/*`, any `*wire.py`, or `agents.py` wiring — stop. You are out
of scope.** `tests/test_portable_wiring.py` failing is your tripwire.

## Do NOT build these (rejected with reasons — handoff §3, plan §9)

- Shim-exported `CAGE_BASE` (can't reach graphify — it runs as its own process, not via `cage-run`).
- A blind global→project union (over-attributes: `project` is a colliding *basename*).
- Push-to-global-always (mixes tenants, no partition key).
- An OS scheduler of any kind. The "cage installs no scheduler" invariant **holds**.
- Printing on a library / proxy / hook request path.
- Any change to a derived number, or to CSV.

If you think one of these is necessary, **stop and make the case to me** — each was killed by a
debate for a documented reason.

## Context to load first

- `docs/capture-architecture.plan.md` §2, §3, §9, §11, §12 — model, decisions, audit, observability.
- `cage/importcmd.py:108-140` (`_scan`), `:73-105` (cursors / `last_import`), `:372`
  (`_last_import` write — your throttle precedent), `:35` (`_import_lock`).
- `cage/clicmds.py:55,67` — how reads are assembled and state is passed in.
- `cage/metering.py:42-70` — `record_call` / `record_receipt` / `_resolve_root` (push path).
- `cage/graphifymeter.py:105-140` — the before/after receipt-id diff that already knows when a
  saving landed. **This is your confirmation hook point.**
- `cage/paths.py:104-165` — `find_project_root` / `resolve_root` / `active_ledger_source`.
- `cage/proxy.py:56-61`, `cage/schema.py:27,43-73`, `cage/debuglog.py`, `cage/doctorcmd.py`.
- `CLAUDE.md` — $0/stdlib-only, fail-open, determinism, four agents, CSV never gates.

## ⚠️ Prerequisite refactors — land these FIRST (handoff §9.6)

An audit found structures whose shape encodes "hooks are the capture path." Building the new
features on top of them would carry a false model forward. **Do these before any new feature:**

1. **Move `hooks.append_new` → `ledger.py`.** `importcmd.py:245` depends on it and it is the
   documented "correctness backstop" — but it lives in `hooks.py`, which is Claude-specific
   (`_AGENT = "claude"`). The universal import path must not depend on one agent's hook module.
   Pure move + a re-export shim for compatibility. No behavior change. Suite must stay green.
2. **Do NOT build the doctor timeline on `agents.backfill_status()` / `realtime_status()`.**
   Those answer *"is a backfill/real-time hook wired?"* — a question the new design makes
   meaningless (backfill and real-time are both capture-on-read now). Build §12.4's timeline
   fresh from per-source/per-mode capture facts. Stop feeding these two into any new surface;
   they are deleted in Phase 2.
3. **Rewrite `doctorcmd.py:105`** — `"capture health: never imported — run \`cage import\`"`.
   Under capture-on-read, doctor sweeps before rendering, so this branch becomes reachable only
   when capture is **disabled or failed**. Change the message to say that. Leaving the old
   string makes the tool lie.

Report these three as a separate first commit so they're reviewable independently.

## Task

1. **`ensure_captured(root, pol)`** — one shared function running the existing incremental
   sweep. Call it from `cage report`, `cage insights *`, `cage doctor`, and **the MCP read
   tools**. Throttle via the existing `_last_import` cursor timestamp (a `constants` window with
   a policy `[capture]` preferred-fallback — the `DEFAULT_CONFIDENCE` pattern, **no new state
   file**). Fail-open. Suppressible via `CAGE_CAPTURE=0` and `--no-import`. Reuse
   `_import_lock`.
2. **`canonical_ledger()`** — one resolver that push *and* pull both call. No direct
   `resolve_root` left in a push path.
3. **Project routing key** — a stable **non-PII hash of the resolved ledger-root path**, stamped
   on pushed receipts. **Not** the basename. Additive/optional (absent = legacy contract, like
   `scope`/`project`), and **never part of any id**. A read-time reclaim backstop matches on
   **exact key only** — never a blind union.
4. **Observability (plan §12):**
   - graphify/fux wrapper → one **stderr** line when a receipt lands (counts only, never content).
     stderr so graphify's parseable stdout is never corrupted.
   - capture-on-read → `· captured N new calls (claude, codex) + M graphify savings since last
     read` above a read. **Zero new rows ⇒ completely silent.**
   - MCP responses → the same summary as a **structured field**. Never stray stdout in the MCP
     server (it would corrupt the protocol).
   - `CAGE_DEBUG` → log **ledger-resolution decisions** (which ledger + why), every sweep, and
     every routing-key reclaim.
   - `cage doctor` → capture timeline: per-source, per-**mode** (pull/push) last-seen + counts.
   - `--why-ledger` → print the resolution decision on demand. `CAGE_QUIET=1`/`--quiet` suppresses.

## Required workflow

1. **Explore first.** Line numbers may have drifted — verify, don't trust.
2. **Plan** — steps + files you'll change, and **pause for my confirmation before implementing.**
   This touches both the capture and read paths; I want the plan first. Include how you keep
   determinism tests isolated from capture-on-read.
3. **Implement incrementally**, keeping the suite green at each step.
4. **Re-bless goldens** — a new confirmation line changes rendered output:
   `CAGE_BLESS_GOLDENS=1 pytest tests/test_output_spec.py` then
   `python -m tools.docgen --target spec`. **Never hand-edit the spec blocks.**
5. **Update docs** — `docs/capture-architecture.plan.md` (record the Phase 1/2 split),
   `docs/debugging-capture.md`, `cage query capture` + a new `capture-on-read` concept entry
   (`explain_data.py`), `CHANGELOG.md` + README "What's new" (replace the latest entry),
   `__version__`, the "N tests passing" count in README **and** CLAUDE.md, and
   `docs/README.md` *Active work*.
   **`CLAUDE.md`: PROPOSE the edit and show me the diff — do not silently rewrite it.**
6. **Run the full suite (§ below) and report the actual output.** Not "tests pass" — paste the
   summary lines.

## 🔬 Full test suite — HARD GATE, run ALL of it

This is an explicit requirement. A subset is not acceptable. Do not report done until every one
of these passes:

```bash
just test                          # python -m pytest -q   (791 passing — refresh count if it moves)
python -m tools.dummyrepo          # scenario runner S1–S17
python -m tools.docgen --check     # generated docs vs sources
python -m tools.skillgen --check   # rendered skill assets, no drift
just demo                          # must still reproduce the plan's §4.4 tables
just lint                          # ruff if available
```

CI additionally runs this on **3 OS × 3 Python** (ubuntu/macos/windows × 3.11/3.12/3.13). The
OS-dependent surfaces you're touching — ledger resolution, path hashing — are exactly the class
that breaks on Windows. Write the routing-key hash to be OS-stable (normalize separators/case
deliberately) and say in your report how you did it.

**Suites most likely to break — check explicitly:** `test_universal_capture.py`,
`test_debug_coverage.py`, `test_output_spec.py` + goldens, `test_capture_health.py`,
`test_portable_wiring.py` / `test_launcher_mode.py` (**green = you stayed in scope**), and
dummyrepo **S1** (all four agents wire; planted CLI logs import to exact rows).

**New tests required:**
- `tests/test_capture_on_read.py` — sweep runs before a read · throttle suppresses the second ·
  `CAGE_CAPTURE=0` / `--no-import` disable · capture error ⇒ read still succeeds ·
  **warm cache ⇒ byte-identical output to today** · concurrent reads don't double-append.
- `tests/test_canonical_ledger.py` — **make the verify-first test permanent**: push a receipt
  from a repo subdirectory, assert a repo-root read sees it. Plus routing key stable, non-PII,
  absent-by-default, never in an id; reclaim matches on exact key only.
- `tests/test_capture_observability.py` — graphify line on **stderr** not stdout · zero-new ⇒
  silent · `CAGE_QUIET` suppresses · no content anywhere · **no confirmation text in CSV** ·
  MCP writes no stray stdout.
- **Determinism guard** — derived views byte-identical with capture-on-read warm vs off.

## Constraints (hard)

- **Stdlib only.** `dependencies = []`.
- **Fail-open everywhere on capture**; every new swallow site logs under `CAGE_DEBUG`
  (`tests/test_debug_coverage.py` enforces it).
- **Determinism:** derived numbers stay a pure function of the ledger. **Every determinism and
  golden test must run with capture-on-read OFF against a fixed ledger.** Non-negotiable.
- **PII:** counts / ids / hashes only. Never a prompt body. The routing key is a hash, not a path.
- **Four agents, always** — and any single agent or any combination. No asymmetric per-agent
  behavior anywhere.
- **CSV never gates** — no confirmation text in any CSV output.
- **Do not touch:** any hook file or wiring module (Phase 2); the provenance/git-hook subsystem;
  `policysync`; the `NEVER` cleanup list; `pathprobe._why()` strings.

## Acceptance criteria (self-check before finishing)

- [ ] `ensure_captured` wired into report / insights / doctor / MCP; throttled; fail-open;
      suppressible by `CAGE_CAPTURE=0` and `--no-import`
- [ ] Warm cache ⇒ **byte-identical** output to today
- [ ] `canonical_ledger()` is the only resolver in the push path
- [ ] Routing key: stable, OS-stable, non-PII, optional, never in an id; reclaim = exact match only
- [ ] Subdir-push → root-read test passes (permanent)
- [ ] graphify confirmation on stderr; silent when zero new; `CAGE_QUIET` respected
- [ ] MCP: structured summary field, **zero** stray stdout
- [ ] `CAGE_DEBUG` logs ledger-resolution decisions, sweeps, reclaims
- [ ] doctor timeline shows per-source **and** per-mode (pull/push) last-seen
- [ ] Derived views byte-identical; no confirmation text in any CSV
- [ ] Goldens re-blessed + `docgen --target spec` regenerated
- [ ] **Entire suite above green**, output pasted in your report
- [ ] Docs updated; CLAUDE.md edit **proposed, not applied**
- [ ] **No hook/wiring file modified** (`git diff --stat` proves it)

## Guardrails

- **Ask before:** touching any wiring/hook file, adding a state file, changing `record_*`
  signatures, adding a schema field beyond the routing key, or altering a derived number.
- If a requirement conflicts with the code, **STOP and ask** — don't guess.
- Handoff §10 has three open questions (Phase 2 task-close; doctor sweep ordering; throttle
  default). Bring me the doctor-ordering one rather than picking; the throttle default you may
  choose conservatively (~60s) and tell me.
- Report the **actual** test output, not a summary claim. If something fails and you can't fix
  it in scope, say so plainly rather than working around it.
