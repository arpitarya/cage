# Claude Code prompt: ledger restructure — one shape per producer

**Model:** **Opus.** Two ADR reversals, a deletion with entanglements across four subsystems, and
four migrations on append-only stores. A wrong call here is expensive and partly irreversible.
**Progress:** 0% — not started. Eight phases (P0–P7); reaches 100% in the change that archives this pair.

---

You are restructuring `cage`'s ledger so **every usage producer owns one directory under
`ledger/`**, then giving every append-only file a tamper-evident hash chain. The full spec is **`work/ledger-restructure.handoff.md`** — read it first and treat its
phase gates, **Non-negotiables** and **Open questions** as binding.

Target shape: `ledger/{claude,copilot,kiro}/` (agent usage) · `ledger/consumer/` (library + proxy) ·
`ledger/graphify/` (tool savings) · `ledger/provenance/` (authorship). `calls`, `credits`,
`savings/` and `provenance.jsonl` become **readable history that is no longer written.** The only
file that *leaves* `ledger/` is `imports.jsonl` — an audit trail, not ledger data.

## ⛔ Read this before anything else

1. **Nothing on disk is ever moved, rewritten or deleted.** Every migration is *stop writing here,
   start writing there, read both forever*. `calls-*.jsonl`, `credits-*.jsonl`,
   `savings/<tool>/*.jsonl` and `ledger/imports.jsonl` all stay and stay readable. A savings row is
   unrecoverable; a codex row is history that still counts.
2. **`calls` can never be fully deleted, only stopped.** Retired-agent rows (codex — 373 in one real
   ledger) have no other home. The reader and the shards are permanent.
3. **P1 reverses ADR 0006**, ratified two commits ago (*"consumers resolve from `calls` permanently,
   are never given a metric ledger"*). That reversal is what makes P5 possible — so **P1 lands
   before P5**, and the ADR gets rewritten in P6, not quietly contradicted.
4. **Every write path here is fail-open by law.** Break one and nothing raises, nothing logs, and no
   test fails unless you write it. That is why each phase has a test, and why "I checked" is not
   evidence.

## P0 gate — do this first, or stop

Publish handoff §P0's three artifacts before touching code: the cross-check snapshot to
`work/regression/2026-08-14-calls-vs-metric-crosscheck.md` (indexed in that README), the two store
probes, and the `work/research/` doc that records them.

The snapshot is the **only** mitigation for a deliberately-overridden freeze
(`METRICS-DUAL-WRITE-END`, lifted early by Arpit on 2026-08-14). Claude Code sweeps transcripts at
~30 days, so the measurement can never be taken again once P5 lands.

**If no real `~/.cage` ledger is on this machine, STOP and report.** Do not substitute a fixture.

## Context to load first

- `docs/adr/0006_consumer.md` **Decision** — the record P1 reverses. Read before writing code.
- `cage/ledger.py` — `spend()` ~550-583, `join_table()` ~584-610, `credits()` ~201-219,
  `savings()` ~222-235, and the `SPEND_SOURCES` / `ABSENT_SPINES` / `CUMULATIVE_SOURCES` tables
  ~475-506. Read the comments, not just the code — `spend()`'s calls loop carries the warning that
  defines this program's boundary.
- `cage/paths.py` — `savings_dir` ~1114, `savings_shard` ~1120, `copilot_dir` ~1140 (the dir-style
  precedent P3c copies), `imports.jsonl` ~1111, `provenance` ~1102, `Footprint.state` ~1326, and
  `shard()` ~1214-1224 — whose docstring carries the *"provenance is intentionally never
  partitioned"* line P3c reverses.
- `cage/importcmd.py` — the `seen`/`captured` build at ~1290-1310 **and its twin in the kiro leg at
  ~1138-1150**. Two sites. Missing the second is the predictable failure.
- `cage/transcript.py` — `_kiro_cli_conversations`, `_kiro_cli_credit_row`, `parse_kiro_cli_metrics`
  (P2's shared reader and the skip-rule difference).
- `cage/cleanup.py` `NEVER` ~313 — why P3 needs an explicit entry and why P4's comment must change.
- `cage/manifest.py` docstring — P3's carve-out, stated in full.
- `tests/conftest.py` `metric_twin` ~77-100.
- `docs/adr/README.md` *Which record owns what* + `tests/test_adr_ownership.py` — the ownership map
  every phase must keep honest.
- **`cli.build_parser()` is ground truth for the CLI surface.** CLAUDE.md was stale but was
  corrected in `5f4d3fc`; still confirm any verb against the live parser rather than prose.
- **Check `git log` before you start.** A parallel session shipped three commits *during* this
  handoff's authoring. If the repo has moved again, **the code wins over this document.**

## Task — eight phases, in order

**P0 — Evidence.** Gate. See above.

**P1 — Consumer ledger.** `ledger/consumer/`, month-partitioned, `schema.make_consumer_metric`
(own id namespace, own closed source enum, grain `call`), reader `ledger.consumer_metrics`,
`SPEND_SOURCES["consumer"] = ("call",)`. `metering.record_call` **dual-writes** — the `calls` row
stays for `join_table` and rollback. **Never migrate retired-agent rows.**

**P2 — Kiro credits into `ledger/kiro/`.** Copilot needs nothing (no credit rows exist; its credits
already live in `ledger/copilot/`). Keep credits *semantics* — `method="measured"`, never priced,
last-write-wins per session by highest turn count, ties by id — and re-home onto the `cli-conv`
reader. **Handoff §P2's table names the two real differences** (the skip rule, and cumulative
handling); resolve them explicitly, and measure row-count parity against P0.1.

**P3 — Relocate the two unpartitioned files, and lift names.**

- **P3a `imports.jsonl` → `state/`.** Add an explicit `imports.jsonl` entry to `cleanup.NEVER` **in
  the same commit** — the move loses the `"ledger/"` umbrella. Read **both** locations forever. Add
  `CAGE_IMPORTS_LOG` matching the `capture.log`/`attest.jsonl` pattern.
- **P3b names for all three agents** — **only what P0.2 proves exists.** No title field ⇒ keep `""`.
  Never fabricate a name, never use a session id as one.
- **P3c `provenance.jsonl` → `ledger/provenance/provenance-<month>.jsonl`.** ⚠️ **This reverses an
  explicit in-code decision** — `paths.py` ~1218 says *"`provenance` is intentionally never
  partitioned (buffer)"*. **Record the reversal in `paths.py` and plan §3.5; do not just delete the
  sentence.** Use the **directory** mechanism (`savings_dir`/`copilot_dir` style), not `shard()`.
  Shard name from the **row's own `ts`**, never a write-time clock; unparseable `ts` falls back to
  the legacy file. **All four readers must span shards** — `ledger.provenance` (~645),
  `originrecord.rows` (~91), `chats.py` (~179, `agent%`), and `doctorbundle.py` (~70-72, which
  reads the file **directly** and would under-report in a diagnostic bundle). `notessync` merges by
  row id and **must** read every shard, or it re-pushes or drops rows in `refs/notes`.

**P4 — Graphify savings → `ledger/graphify/`.** `ledger.savings()` reads new per-tool dirs **and**
the whole legacy `savings/*/` tree. One path helper, never a second literal. **Blocked on OPEN
QUESTION 10.5** (the `ledger/` namespace collision between agents, consumers and tools) — ask
before writing. Update `cleanup.py`'s comment and add a `test_cleanup.py` survival twin for the new
path. **10.6:** whether `fux`/`compress`/`responsecache` move too — ask.

**P5 — Retire the three agents' transcript→`calls` writer.** Delete `transcript.parse_calls`,
`parse_copilot_calls`, `parse_copilot_vscode_calls`, `parse_kiro_calls` + orphaned helpers; remove
the `_ingest` legs (~514, ~852, ~946) and `_parse_copilot_any` (~575). **`_PARSERS` (~603) is
blocked on 10.1.** **Repoint gate 3 and doctor health** — otherwise a healthy install reports all
three agents as *never captured*, a silent false negative. Let `taskcorr`/`hookcmd` degrade,
**stated not silent**; no timestamp-proximity fallback. **Do not "fix" `parse_calls` on the way
out** — ADR 0003 forbids it; deleting it is what honours the rule.

**P6 — Integrity chain.** Every file carries a previous + current hash so a change is detectable,
with its own lock. **Goes last** — hashing files that P1–P4 are about to move is wasted work and a
guaranteed false "changed" verdict.

- **A full-file rehash per append is not viable** — cage appends row-by-row on a hot fail-open path
  over a 22k+ row ledger, so per-row rehash is O(n) per append. Use a **hash chain over appended
  segments**: `current = sha256(previous_hash ‖ appended_bytes)`. O(delta), tamper-evident.
- ⚠️ **The lock must not become load-bearing.** `lockutil`'s stated contract is that the lock only
  closes a wasted-work window and **proceeds unlocked** on a miss; the per-call-site backstop is the
  correctness guarantee. A chain is order-dependent, so a missed lock could corrupt it.
  **Decided: a lock-miss marks the segment `unverified`, never breaks the chain.** Reuse
  `lockutil.locked()` — **never hand-roll another `fcntl` block.**
- **Report-only, never a gate** — the `cage authorship verify` precedent (always exits 0). A
  mismatch surfaces in `cage doctor`; it never refuses a read, blocks a write, or changes an exit code.
- **Never turn fail-open into fail-loud.** `ledger.read` deliberately tolerates a truncated tail.
  Classify that as *tolerated truncation*, distinct from *prefix rewritten* — the only real tamper
  signal, since rows are never rewritten.
- **Never read by a derived view**; `cleanup.NEVER` must protect it; the chain is a function of file
  bytes, never of a wall clock.
- **STOP and ask on 10.7 (threat model), 10.8 (which files), 10.9 (where the manifest lives)** before
  designing.

**P7 — ADRs and docs.** Handoff §P7 lists them. All three reversals **recorded, never deleted**.

## Required workflow

1. **Explore before writing.** The handoff's line numbers are from v0.50.0 — verify each; do not
   trust them blind.
2. **Plan per phase** — lay out the change map and files, and **pause for my confirmation before
   implementing each phase.** Do not run P0→P6 in one pass.
3. **Implement incrementally.** Suite green between phases. An `IMPLEMENTATION.md` entry **per
   phase**, not one at the end.
4. **Update the owning ADR in the SAME commit as each phase.** **ADR-DISCIPLINE** landed
   2026-08-14 (`02c3c98`) and is test-enforced: *"no behaviour change lands without its ADR updated
   in the same change"*, with `tests/test_adr_ownership.py` failing when a `cage/` module is claimed
   by no record. **P6 is not a trailing phase** — it is only what's left over. A change touching no
   recorded decision must say **`no ADR affected` out loud**. Any new module must be claimed in
   **both** `docs/adr/README.md`'s ownership table **and** `OWNERS` in that test.
   ⚠️ **CLAUDE.md: propose the diff for review, don't silently apply it** — note it is now
   *accurate* (`5f4d3fc` applied and archived the SURFACE-CUT diff), so edit it directly; the old
   `work/surface-cut.claude-md-diff.md` is gone. ADR 0001 (laws): **propose, don't unilaterally
   rewrite a law.**
5. **Verify:** `just test`. Re-bless goldens **only** where output legitimately changed — an
   unexpected golden change is a finding to investigate, not a diff to accept.

## Constraints (hard)

- **Append-only, always.** No migration rewrites, re-homes or deletes an existing row or shard.
- **Do not modify:** existing `calls-*.jsonl` / `credits-*.jsonl` / `savings/<tool>/` shards ·
  `schema.make_call` · `ledger.join_table` · `ledger.append_row` ·
  `transcript.parse_kiro_ide_metrics` · the authorship path (`parse_provenance`, `parse_edits`,
  `linematch`, `commitjoin`).
- **Never sum across units** — a token, a credit, and a kiro credit vs a copilot credit. Refused in
  code, not by convention. That refusal survives unchanged.
- **No currency, rate card or unit conversion** (ADR 0011); `tests/test_usage_only.py` AST-scans.
- **Counts-never-content** — no prompt bodies, no line bodies, no line hashes. The manifest's
  `session_name` is the one recorded widening, local-only.
- `$0` / stdlib-only — `dependencies = []`. Determinism: no clocks/random in derived views.
- **Fail-open but never silent** — every swallow site logs under `CAGE_DEBUG`
  (`tests/test_debug_coverage.py` audits this).
- A removed path is a **wiring migration** (`install.sh`, `justfile`, `tools/dummyrepo`, the
  steering `Doc` literals, `docs/adr/0002_cli.md`) and a **citation migration**
  (`grep -rho "docs/[a-z0-9-]*\.md" cage/*.py | sort -u`).

## Acceptance criteria (self-check before finishing)

- [ ] P0's snapshot + probes + research doc published **before** any code change
- [ ] `record_call` dual-writes; a `cage.meter` consumer still works — **proven by a test**
- [ ] A real ledger's codex/proxy rows resolve in `spend()` at unchanged counts
- [ ] Kiro credits render identical values in `insights chats` before and after P2; row-count parity
      measured against P0.1
- [ ] Old `imports.jsonl` still read; titles do not regress to session ids; `cleanup.NEVER` protects
      the new path; `test_deleting_manifest_changes_zero_numeric_cells` still green
- [ ] Old `provenance.jsonl` still read; all four readers span shards; `agent%` and
      `authorship origin/summary/verify` render **identical values** before and after P3c;
      `notes-sync` pushes the same row set
- [ ] `test_authorship_capture.py`'s plant-string test **greps the new `ledger/provenance/`
      directory** — left pointing at the old file it passes forever while covering nothing
- [ ] `insights graphify` + `chats` render identical values before and after P4; legacy `savings/`
      tree still read; `test_cleanup.py` has a survival case for the new path
- [ ] No import path writes a `calls` row for claude/copilot/kiro; `test_calls_retired.py` exists
      and fails if the writer returns
- [ ] Gate 3 + doctor health report the three agents correctly on a healthy install
- [ ] No test seeds `calls` for the three agents as though capture produced it
      (use `conftest.metric_twin`, never a per-file copy)
- [ ] Integrity chain is report-only (never changes an exit code), a lock-miss yields
      `unverified` rather than a broken chain, a tolerated truncated tail is not reported as
      tampering, and deleting the manifest moves zero numeric cells
- [ ] **Each phase updated its owning ADR in its own commit** (ADR-DISCIPLINE), or said
      `no ADR affected` out loud; every new module claimed in `docs/adr/README.md` **and**
      `tests/test_adr_ownership.py`'s `OWNERS`
- [ ] ADRs 0003/0004/0005/0006/0007 corrected; **all three reversals recorded, not deleted**
      (ADR 0006's consumer decision · ADR 0003's "stop writing calls" · `paths.py`'s
      "provenance is intentionally never partitioned")
- [ ] `just test` green; test count updated in README + the CLAUDE.md diff; **TEST-COUNT** closed
- [ ] CHANGELOG · README "What's new" (latest entry only — replace) · IMPLEMENTATION.md (per phase) ·
      WORKLOG.md (with `Cost:`) · INTERVIEW.md · OPEN-WORK.md · DOC-REGISTRY.md · FORMULAS.md ·
      `explain_data.py` · `architecture-flow.mermaid` · GLOSSARY.md all updated
- [ ] This pair archived to `work/archive/v0.51-ledger-restructure.{handoff,prompt}.md` with the
      archive header, linked from CHANGELOG ("Built from: …"), `docs/README.md` +
      `work/archive/README.md` indexes updated, **Progress → 100%**

## Guardrails

- **STOP and ask** before: resolving any OPEN QUESTION (10.1 `_PARSERS` · 10.3 whether kiro-CLI
  gains a spine · 10.4 dir name · **10.5 namespace collision, blocks P4** · 10.6 other savings
  sources · **10.7 integrity threat model · 10.8 which files · 10.9 manifest location, all block P6**) · touching anything in the do-not-modify list · any change that would rewrite, move or
  delete an existing ledger row or shard · starting a phase before the previous one is green.
- **10.3 is a spine decision** — kiro currently renders `—` with a stated reason. Changing that
  changes user-visible output. Never decide it silently.
- If the handoff conflicts with what you find in the code, **the code wins — say so, don't silently
  adapt.** The handoff was written from a static read, not from running it.
