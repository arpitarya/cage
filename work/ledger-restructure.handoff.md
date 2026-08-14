# Handoff: ledger restructure — one shape per producer, and the end of the `calls` writer

**One-liner:** Give every usage producer the same on-disk shape — a per-producer directory under
`ledger/` — by (1) giving non-agent consumers their own ledger, (2) folding kiro's `credits` shard
into `ledger/kiro/`, (3) moving `imports.jsonl` to `state/` and lifting names for all three agents,
and only then (4) retiring the three agents' transcript→`calls` writer.

**Owner / executor:** Claude Code
**Model tier:** **Opus.** Two ADR reversals, a deletion with entanglements across four subsystems,
and three data migrations on append-only stores. The diagnosis is the work.
**Status:** Ready to build — P0 gates everything.
**Rides version:** v0.51.0 (unreleased; v0.50.0 current)
**Supersedes:** `work/calls-retirement.{handoff,prompt}.md` — folded in as **P4**.

**Stress-tested:**
- **Challenged:** all four asks, plus the sequencing between them.
- **What changed:**
  - **P1 rescues the original goal.** ADR 0006 — ratified two commits ago — says consumers
    *"resolve from `calls` permanently, are never given a metric ledger."* That decision is the
    single reason the `calls` kind had to survive forever. Giving consumers a ledger **reverses it**
    and turns "`calls` must live on" into "`calls` stops being written." So **P1 must land before
    P4**, and P4's scope grows accordingly.
  - **P2 is kiro-only.** Copilot writes **no** credit rows — `make_credit` defaults `agent="kiro"`
    and its only caller is the kiro-CLI parser. Copilot's credits already live in `ledger/copilot/`
    as `credits`/`session_credits`/`nano_aiu`. Half of ask (1) is already done.
  - **P3 is compatible with the state law, not in tension with it.** The law is *state can't move a
    reported **number***; the manifest carve-out is already *labels only, zero numeric cells*
    (pinned by `test_chats.py::test_deleting_manifest_changes_zero_numeric_cells`). The manifest is
    already behaving like a state file. **But it loses `cleanup.NEVER`'s `"ledger/"` umbrella** and
    must be re-protected explicitly.
- **What survived:** all four asks are sound. None was rejected.
- **Residual risks, accepted:**
  1. The 2026-09-13 freeze (`METRICS-DUAL-WRITE-END`) is knowingly forfeited. **P0.1 is the only
     mitigation** — it converts *unmeasurable forever* into *measured once, at the cut*.
  2. **`calls` can never be fully deleted, only stopped.** Retired-agent rows (codex, 373 in one
     real ledger) are append-only history and are never rewritten or re-homed. The reader and the
     shards are permanent. Anyone who "finishes the job" by deleting them has broken the law.

---

## Phase index

| # | Phase | Gate |
|---|---|---|
| **P0** | Evidence — cross-check snapshot + two store probes + research doc | **Blocks everything.** No real ledger ⇒ stop. |
| **P1** | Consumer ledger `ledger/consumer/`, dual-write | Anton-safe; reverses ADR 0006 |
| **P2** | Fold kiro `credits-*.jsonl` into `ledger/kiro/` | Row-count parity measured, not assumed |
| **P3** | Relocate the two unpartitioned files: `imports.jsonl` → `state/`, `provenance.jsonl` → `ledger/provenance/` (monthly) ; lift names for all three agents | Name lifting gated on P0.2 |
| **P4** | Move graphify savings to `ledger/graphify/` | Namespace collision resolved first |
| **P5** | Retire the three agents' transcript→`calls` writer | Requires P1 green |
| **P6** | Integrity chain — prev/current hash per file + its own lock | New ADR; lock must stay non-load-bearing |
| **P7** | ADRs 0003/0004/0005/**0006** + docs + archive | Reversals recorded, never deleted |

**The unifying shape this program produces:** every producer owns one directory under `ledger/` —
`claude/` `copilot/` `kiro/` (agent usage) · `consumer/` (library + proxy) · `graphify/` (tool
savings) · `provenance/` (authorship) — with month-partitioned shards and a per-producer reader.
`calls`, `credits`, `savings/` and `provenance.jsonl` remain as **readable history that is no
longer written**. The only file that leaves `ledger/` is `imports.jsonl`, which was never ledger
data — it is an audit trail, and P3 moves it to `state/` where its behaviour already said it belonged.

---

## P0 — Evidence (do this first; it gates every later phase)

**P0.1 — the cross-check snapshot.** Against the real `~/.cage`, publish
`work/regression/2026-08-14-calls-vs-metric-crosscheck.md`:
- per agent: `calls` count vs metric-ledger count, same absolute window, and the observed ratio
  (claude's is expected ≈2.00× — **record what you find, never what you expect**)
- count of rows whose agent is **not** in `SPEND_SOURCES`, broken out by agent (codex / `lib` /
  proxy / custom). This is the population P1 must carry and P4 must not break.
- kiro: `credits` row count vs `ledger/kiro/` `cli-conv` row count — the P2 parity baseline.

**P0.2 — two store probes**, for P3's name lifting. Currently only claude (transcript `summary`
→ cwd basename) and copilot **VS Code** (`customTitle`/`generatedTitle`) yield a name; copilot CLI
and kiro write honest `""`. **Unknown, and must be probed, not assumed:** does copilot CLI's
`events.jsonl` carry any title-bearing field? does kiro's `conversations_v2` carry one?

**P0.3 — the research doc.** House law: research gets its own dated doc in `work/research/`, cited
as evidence by the phases that act on it. Write up P0.2 there with paths, versions and sample
counts. **If a store has no title field, that is a finding — P3 keeps `""` for it and says so.
Never synthesize a name, and never fall back to a session id dressed as a name.**

**If P0.1 cannot run (no real ledger on this machine), STOP and report.** Do not substitute a
synthetic fixture — the measurement can never be taken again once P4 lands.

---

## P1 — Consumer ledger

**Ask:** the consumer meter gets its own directory under `ledger/`, shaped like the agent siblings.

**Why it goes first:** it is what makes P4 possible. ADR 0006 is the blocker, and P1 is its reversal.

**Decided design**
- New dir `ledger/consumer/` with month-partitioned shards, exactly like `ledger/{claude,copilot,kiro}/`.
- New row kind + constructor `schema.make_consumer_metric`, own id namespace (suggest `csm_`), own
  closed source enum. **Grain is `call`** — a library consumer meters per provider response, so
  `SPEND_SOURCES["consumer"] = ("call",)`.
- Reader `ledger.consumer_metrics` / `_raw`, mirroring `claude_metrics`.
- `metering.record_call` **dual-writes**: the `calls` row (unchanged, for rollback and for
  `join_table`'s receipt→call resolution) **and** the consumer metric row.
- `_spend_row` normalization and `agents.row_surface` handling for the new surface.

**Hard limits**
- **Dual-write, never a cutover.** AlphaForge Anton is a live consumer and this path is fail-open by
  law — a silent break produces no error anywhere. Dual-write makes the reversal one constant.
- **Retired-agent rows are NEVER migrated, re-homed or rewritten.** Codex rows stay in `calls`
  forever. This is the append-only law and ADR 0006's own words.
- **Custom `[sources.<name>]` tools:** OPEN QUESTION 10.1 — do they route into `consumer/`, or keep
  resolving from `calls`? They are arbitrary-named and user-declared. **Do not decide alone.**

**Done when:** a `record_call` writes both rows; `spend()` resolves the consumer row and no longer
double-counts its `calls` twin; a real ledger's codex/proxy rows resolve at unchanged counts.

---

## P2 — Fold kiro's `credits` into `ledger/kiro/`

**Ask:** `credits-YYYY-MM.jsonl` should come out of the per-agent ledger, not sit at top level.

**What P0 confirms:** `ledger/kiro/` `cli-conv` rows **already carry these credits, from the same
store, via the same shared reader `_kiro_cli_conversations`, under the same whitelist.** The
top-level shard is a duplicate. Copilot needs nothing — it has no credit rows.

**The two real differences — this is the crux, do not paper over it**
| | `credits` row (`_kiro_cli_credit_row`) | `cli-conv` metric row |
|---|---|---|
| skip rule | credits ≤ 0 **and** context ≤ 0 ⇒ **no row at all** | emits when `usage_info` is present, even summing to a real `0.0` (None-sentinel) |
| cumulative handling | `ledger.credits` collapses **last-write-wins per session**, highest turn count | `CUMULATIVE_SOURCES["kiro"] = ("cli-conv", …)` — **excluded from spend** as cumulative |

So `cli-conv` is a **superset** with a different collapse. Migrating means moving the last-write-wins
collapse into the kiro metric read path, and deciding what `CUMULATIVE_SOURCES` means afterwards.

**Decided:** keep the credits *semantics* (`method="measured"`, never priced, last-write-wins per
session, highest turns wins, ties by id) and re-home them onto the `cli-conv` reader. Retire the
top-level shard as a **writer**; keep `ledger.credits` reading existing shards forever.

**Hard limits**
- **Never delete or rewrite existing `credits-*.jsonl`.** Append-only. Read them forever.
- **Never sum a credit with a token, or a kiro credit with a copilot credit.** Cross-agent credit
  sums are refused in code, not by convention. That refusal survives this change unchanged.
- `chats.py` is the **only** reader (`ledger.credits`, CHATS-CREDITS). It must keep rendering the
  same values — a credits row gets its own bucket and never enters a token aggregate.
- **Measure parity before and after** against P0.1's baseline. A changed row count is a finding to
  investigate, not a diff to accept.

---

## P3 — Relocate the two unpartitioned files, and names for all three agents

**Grouped on purpose.** `imports.jsonl` and `provenance.jsonl` are the repo's only two
unpartitioned append-only files, both grow without bound, and both are scoped carve-outs to
`manifest.py`'s "never read by a derived view" rule. They move in one phase because they share one
migration shape — *stop writing here, start writing there, read both forever* — and one test.

**Ask A:** `imports.jsonl` → the state dir. **Ask B:** names for claude, copilot and kiro.
**Ask C:** `provenance.jsonl` → `ledger/provenance/`, month-partitioned.

**Part A — the move**
- Today: `ledger/imports.jsonl` (`paths.py` ~1111). Target: `Footprint.state`, beside
  `cursors.json` / `capture.log` / `attest.jsonl`.
- **This is consistent, not a violation.** The state law is *state files can't change a reported
  **number***; the manifest already only supplies **labels**, pinned by
  `test_chats.py::test_deleting_manifest_changes_zero_numeric_cells`. Moving it puts it where its
  behaviour already said it belonged.
- **⚠ It loses cleanup protection.** `cleanup.NEVER = ("ledger/", …)` covers it today purely by
  location. **Add `imports.jsonl` to `NEVER` explicitly in the same commit as the move.** An audit
  trail that becomes cleanup-eligible is a silent data-loss path — and cleanup is a closed
  allowlist, so nothing fails until someone adds a `state/` class years later.
- **Read both locations forever.** Every real install has rows at the old path. A one-way move
  makes every existing chat title fall back to a session id on the next read. Follow the
  `cage.toml`/`policy.toml` precedent: new path wins, old path still read, `cage doctor` names a
  leftover. **No migration that rewrites or deletes the old file.**
- Add an env override (`CAGE_IMPORTS_LOG`) matching the `capture.log`/`attest.jsonl` pattern.

**Part B — name lifting for all three**
- Gated on **P0.2/P0.3**. Implement only what the probe proves exists.
- If a store carries no title: **keep `""`.** Honest empty, documented in the research doc and in
  `manifest.py`'s docstring. Never fabricate, never use a session id as a name.
- The PII posture is unchanged and must stay stated: a name is user-authored prose, a deliberate
  recorded widening **for this local audit file only**; it never touches a call/receipt/savings row
  and never leaves the machine (`--team` excludes it by construction).

**Part C — `provenance.jsonl` → `ledger/provenance/provenance-<month>.jsonl`**

**⚠ This reverses an explicit in-code decision.** `paths.py` (~1218) states outright:
*"`provenance` is intentionally never partitioned (buffer)."* The reasoning was that the local file
is a *buffer* — canonical storage is `refs/notes/cage-provenance`, CI-sole-writer, merged by row id.
**The counter-argument that justifies the reversal:** nothing prunes it. `cleanup.NEVER` covers
`ledger/`, and no cleanup class touches it, so the "buffer" is an unbounded append-only file that
every read scans end-to-end. Partitioning gives it the same bounded `--since` re-scan every other
long-lived log already has. **Record the reversal in `paths.py` and plan §3.5 — do not just delete
the sentence.**

**Decided design**
- Use the **directory mechanism**, not `shard()` — i.e. `savings_dir`/`copilot_dir` style, the
  precedent `paths.py` already calls *"smallest diff, precedent already tested."* Add
  `Footprint.provenance_dir` + `provenance_shard(ts)`, and route `"provenance"` through
  `shard()`'s tuple/dir branch alongside `savings`/`copilot`/`kiro`/`claude`.
- Shard name from the **row's own `ts`**, never a write-time clock — the determinism law. A
  missing or unparseable `ts` falls back to the legacy unpartitioned file, exactly as `shard()`
  already does, so a malformed row still lands somewhere readable.
- `ledger.provenance()` (~645) reads the **union** of `ledger/provenance/provenance-*.jsonl` and the
  legacy `ledger/provenance.jsonl`, deterministic order, truncated-tail tolerant. Gains `since=`.
- `originrecord.py:178` (`ledger.append(foot.provenance, row)`) becomes a partition-aware append.

**Hard limits**
- **Never move, rewrite or delete the existing `provenance.jsonl`.** Read it forever. Frozen rows
  are never backfilled — `residual_lines`' absent-vs-recorded-`0` version gate depends on that.
- **Every reader must span shards**, or it silently sees a subset. Four of them:
  `ledger.provenance` (~645) · `originrecord.rows` (~91) · `chats.py` (~179, the `agent%` column) ·
  `doctorbundle.py` (~70-72, which reads `foot.provenance` **directly** and reports a row count —
  an easy miss, and it would under-report in a diagnostic bundle).
- **`notessync` merges by row id and must read every shard.** A partial read would re-push rows the
  note already has, or silently drop rows it doesn't. `refs/notes/cage-provenance` stays
  **CI-sole-writer** (`CAGE_NOTES_WRITE=1`); a dev machine still dry-runs. `cage authorship verify`
  still **always exits 0** — never a CI gate.
- **`agent%` must render identically** before and after. It reads counts, never re-derives them —
  no matcher and no git at render time — so a shard-spanning bug shows up as a *changed number*,
  not an error. Pin it.
- Counts-never-content is unchanged: no line bodies, **no line hashes**. The plant-string test in
  `tests/test_authorship_capture.py` greps every written shard — **make sure it greps the new
  directory**, or the strongest PII guard in the repo quietly stops covering the live path.

---

## P4 — Graphify savings → `ledger/graphify/`

**Ask:** graphify numbers live in `ledger/graphify/`, not `ledger/savings/graphify/`.

**Current shape:** `Footprint.savings_dir` = `ledger/savings/`, per-tool subdir
`ledger/savings/<tool>/savings-<month>.jsonl`; `ledger.savings()` globs
`savings/*/savings-*.jsonl` across every tool subdir. `paths.py` already describes the copilot/kiro
metric dirs as *"a capture-only sibling to `savings/`"* using *"the same `savings_dir`-style
mechanism"* — so the two shapes were always parallel. This phase makes them the same shape.

**Decided design**
- Write new graphify rows to `ledger/graphify/savings-<month>.jsonl`. Same row kind
  (`schema.make_savings`), same ids, same month partitioning, same determinism.
- `ledger.savings()` reads **both** the new per-tool dirs **and** the whole legacy
  `savings/*/savings-*.jsonl` tree, forever. Union, deterministic order.
- Update every push site (`graphifymeter`, `record_receipt`, `responsecache`, `compress`) to
  resolve through **one** path helper — never a second literal.

**⚠ The namespace collision — resolve this before writing a byte.** After P1 and P4, `ledger/` holds
a **flat namespace shared by agents, consumers and tools**: `claude/` `copilot/` `kiro/` `consumer/`
`graphify/`. A custom `[sources.<name>]` tool, or a future agent, named the same as a savings tool
would land two different row kinds in one directory. Options: reserve tool names against
`agents.SURFACES`; or namespace as `ledger/tools/<tool>/`; or validate at write time.
**OPEN QUESTION 10.5 — do not pick silently.**

**Hard limits**
- **Never move, rewrite or delete existing `savings/<tool>/` shards.** A savings row is
  unrecoverable — `test_cleanup.py` pins this at `days=0`. Read the old tree forever.
- **Cleanup protection holds only because the target is still under `ledger/`.** `cleanup.py`'s
  `NEVER` comment warns in as many words that *"moving the savings tree out from under `ledger/`
  without adding it back here would silently make it cleanable, with no test failing"*. This move
  stays inside `ledger/`, so protection survives — **but the comment names the old path and must be
  updated in the same commit**, and the `ledger/savings/<tool>/` survival case in `test_cleanup.py`
  must gain a twin for the new path. The standing rule is unchanged: **tool savings may never get a
  dedicated cleanup class.**
- **Only graphify was asked for.** `fux`, `compress` and `responsecache` also file receipts, so a
  graphify-only move leaves one row kind in two shapes. **OPEN QUESTION 10.6** — recommend moving
  all savings sources in this phase, or the inconsistency is permanent.
- `cage insights graphify` and `chats` must render identical values before and after. `graphifychat`
  joins `ledger.savings(tool="graphify")` by `session` alone — that join is untouched.

---

## P5 — Retire the three agents' transcript→`calls` writer

*(This is the original `calls-retirement` handoff, folded in. Requires P1 green.)*

**Scope**
- Delete `transcript.parse_calls`, `parse_copilot_calls`, `parse_copilot_vscode_calls`,
  `parse_kiro_calls` + helpers orphaned by their removal (`_composite_id`, `_usage_to_row`).
- Remove the `_ingest(...)` legs at the claude (~514), copilot (~852), kiro (~946) sites and
  `_parse_copilot_any` (~575). **`_PARSERS` (~603) is blocked on OPEN QUESTION 10.1.**
- **Repoint gate 3 and health** — `importcmd`'s `captured` set (~1290-1310 **and its twin in the
  kiro leg at ~1138-1150**; two sites) and `doctorcmd`'s capture health (~169, ~234). All derive
  from `ledger.calls`. Left alone, a healthy install reports all three agents as *never captured*:
  a silent false negative, the F1 class this repo has paid for twice.
- `taskcorr` / `hookcmd` degrade — **stated, not silent.** Metric rows carry no `task`
  (TASK-GRAIN-SPINE). Extend that OPEN-WORK item; do **not** file a new one, and do **not** invent
  a timestamp-proximity fallback (forbidden by house law).
- **Kiro's leg goes too**, justified by the 2026-08-14 field probe: 28 rows, 1,576 in / **0 out**,
  model `"agent"` on every row, a repeated byte-identical 6-row block — unsummable. *Arpit can
  override this in two lines without moving anything else.*

**Do not**
- Do not delete or modify any `calls-*.jsonl` shard.
- Do not touch `ledger.calls`, `ledger.join_table`, `ledger.append_row`, `schema.make_call`,
  `CALL_FIELDS`. P1 changes who *writes*; the substrate and reader are permanent (codex).
- **Do not "fix" `parse_calls` on the way out.** ADR 0003 forbids it — deleting it is what honours
  that rule. The 2.00× measurement must outlive the code.
- Do not remove `transcript.parse_kiro_ide_metrics` (upgrade-watch).
- Do not touch the authorship path or the graphify routes.

**The gate (two-strikes rule).** `tests/test_calls_retired.py`: a full sweep asserts **zero** new
`calls` rows for the three agents **and non-zero** from a `record_call` in the same ledger.

---

## P6 — Integrity chain: prev/current hash per file, and its lock

**Ask:** every file carries a previous hash and a current hash so a change is detectable, with a
lock file for it.

**Goes last on purpose.** P1–P4 move four files. Hashing a file that is about to relocate is wasted
work and a guaranteed false "changed" verdict.

### The design constraint that decides the shape

**A full-file rehash per append is not viable.** Cage appends row-by-row on a hot, fail-open capture
path and the ledger is 22k+ rows across multi-MB shards — rehashing the whole file per row makes
every append O(n).

**Decided: a hash chain over appended segments, not a file digest.**
`current = sha256(previous_hash ‖ appended_bytes)` — O(delta), tamper-evident, and it answers *"did
this change"* for free. Store `{path, prev, current, rows, ts}` per shard.

### ⚠ The house-law collision — read before designing

`lockutil`'s contract is explicit: *"the lock only closes the wasted-work window"*; the id-dedupe
backstop at each call site is the correctness guarantee, and on a lock-miss it **proceeds
unlocked**. A hash chain is **order-dependent**, so two processes appending to the same shard
without the lock would interleave and corrupt the chain. **That would make the lock load-bearing —
which `lockutil` is explicitly not built to be.**

**Decided resolution: a lock-miss marks the segment `unverified`, never breaks the chain.** A stated
unknown, never a fabricated verdict — the house pattern (`—` with a reason, never a `0`). Fail-open
survives, and the chain never lies.

### Hard limits

- **Report-only, never a gate.** Precedent is `cage authorship verify`, which is report-only and
  **always exits 0**. A mismatch surfaces in `cage doctor`; it must never refuse a read, block a
  write, or change an exit code.
- **Never turn fail-open into fail-loud.** `ledger.read` deliberately tolerates a truncated tail
  (a crash mid-write). The chain must classify that as *tolerated truncation*, distinct from
  *prefix rewritten* — which is the only real tamper signal, since rows are never rewritten.
- **Never read by a derived view.** It is state. Deleting the whole manifest must move zero numeric
  cells — pin it the way `test_chats.py` pins the manifest and provenance carve-outs.
- **`cleanup.NEVER` must protect it** the moment it lands in `state/`. Same lesson as P3a.
- **Reuse `lockutil.locked()`** — one implementation, three tiers. **Never hand-roll another
  `fcntl` block.**
- **Determinism:** the chain is a function of file bytes, never of a wall clock. A `ts` may be
  recorded as metadata but must not enter a hash.
- **ADR-DISCIPLINE applies:** this is a new module and a new decision. Claim it in
  `docs/adr/README.md`'s ownership table **and** `tests/test_adr_ownership.py`'s `OWNERS`, and give
  it a record with a veto condition, **in the same commit**.

### Open questions

- **10.7 — threat model.** *Detect corruption* and *detect tampering* are different features with
  different failure modes. Corruption-detection risks turning tolerated truncation into a scary
  report; tamper-detection is meaningful only because the append-only law says a changed prefix is
  never legitimate. **Recommend: tamper-evidence, report-only.** Decide before designing.
- **10.8 — which files?** Ledger shards only, or `state/` too, or config? `cage.toml` is *meant* to
  be user-edited, so a change there is normal — hashing it produces noise, not signal.
  **Recommend: append-only ledger data only.**
- **10.9 — where does the manifest live?** `state/integrity.json` (prunable-by-location, needs the
  `NEVER` entry) vs `ledger/integrity/` (protected, but then it is ledger-shaped data that is not a
  usage row). *Recommend `state/` + the `NEVER` entry.*

---

## ⚠ ADR-DISCIPLINE — landed 2026-08-14, mid-spec, and it changes how P7 works

A parallel session shipped **ADR-DISCIPLINE** (`02c3c98`) while this handoff was being written:
*"No behaviour change lands without its ADR updated in the same change."* It is **test-enforced** —
`tests/test_adr_ownership.py` (new, 160 lines) fails when a module in `cage/` is claimed by no
record, and `docs/adr/README.md` carries the ownership table it mirrors.

**Consequence for this program: P7 is not a trailing phase.** Each of P1–P6 updates its own owning
ADR **in its own commit**. P7 is what remains — the cross-cutting doc set, the archive, and the two
reversals' final wording. A phase that ships behaviour and defers its record is a defect of the same
class as a missing changelog entry.

**Also binding on P1 and P4:** *"a new module is a new decision."* `schema.make_consumer_metric`'s
home, any new reader module, and any new path helper must be claimed in **both**
`docs/adr/README.md`'s ownership table **and** `OWNERS` in `tests/test_adr_ownership.py`, or the
suite goes red — by design, at exactly the moment a new decision is being made with nothing to hold it.

**And the escape is explicit, not silent:** a change that touches no recorded decision must say
**`no ADR affected` out loud**. That sentence is the rule working, not an exemption from it.

**Second thing that landed:** `work/surface-cut.claude-md-diff.md` **no longer exists and its 24
false lines were applied** — it is archived at `work/archive/v0.50-surface-cut.claude-md-diff.md`
and CLAUDE.md is now accurate. Earlier drafts of this handoff told you to fold CLAUDE.md edits into
that pending diff. **Do not.** Edit CLAUDE.md directly — still *proposing* the diff for Arpit rather
than silently applying it, per the agent-steering rule.

---

## P7 — ADRs and docs

Two reversals. **Both recorded, neither deleted** — a silently-vanished rejected alternative is how
a future agent re-litigates it from first principles.

- **ADR 0007 (graphify)** — the interceptor behaviour contract. P4 moves where a receipt lands, so
  the twin-pair spec and any path it names must follow. **Change a twin ⇒ change the contract and
  `pathshim._INTERCEPTOR` together.** Verify no marker-set drift.
- **ADR 0006 (consumer) — the big one.** Its central decision (*"resolve from `calls` permanently,
  are never given a metric ledger"*) is **reversed by P1**. Rewrite the Decision, record the
  reversal with date + Arpit's call, and **restate what did not change**: retired-agent rows stay in
  `calls` forever, fail-open is still absolute, `cage.meter` is still the public name. Update the
  veto condition — the current one has no trigger for this reversal, which is itself a finding.
- **ADR 0003 (claude)** — `calls` to past tense; the rejected alternative *"Stop writing `calls`"*
  becomes a recorded reversal; update the mermaid **and** ASCII flow; frontmatter `status:`;
  CLAUDE-DEDUP / CLAUDE-SUBAGENT-KEY become **closed-by-deletion** with the 2.00× measurement kept.
- **ADR 0004 (copilot)** — same treatment. The CLI credit-delta loss was calls-parser-only and is
  **closed by deletion, not fixed.** Note copilot needed no P2 work and why.
- **ADR 0005 (kiro)** — P2's re-homing + P4's leg removal. Keep `ABSENT_SPINES` and the
  upgrade-watch language intact.
- **ADR 0001 (laws)** — check whether the state-dir law and the append-only law need P3/P1 wording.
  **Propose, don't unilaterally rewrite a law.**
- **`work/OPEN-WORK.md`** — METRICS-DUAL-WRITE-END is already marked picked-up; remove on
  completion, recording the outcome in IMPLEMENTATION.md **first**. Extend TASK-GRAIN-SPINE (P4).
  Close **TEST-COUNT**. Carry forward anything unresolved as its own item.
- **`work/IMPLEMENTATION.md`** — an entry per phase, not one at the end.
- **`work/WORKLOG.md`** — with a `Cost:` line. Note: `cage report` was deleted by SURFACE-CUT, so
  `Cost: unmeasured — no spend surface in this repo` is the honest value today.
- **`work/INTERVIEW.md`** — succession-critical. The next model must not try to restore either the
  calls writer or the top-level credits shard.
- **`CHANGELOG.md` + README "What's new"** (README keeps only the latest entry — replace, don't
  append) · **`docs/adr/0002_cli.md`** if any surface moved · **`docs/FORMULAS.md`** +
  **`cage/explain_data.py`** (it names `parse_calls` at ~496; the registry ships in the binary and
  must agree) · **`docs/architecture-flow.mermaid`** (three stages move) · **`docs/GLOSSARY.md`** ·
  **`work/DOC-REGISTRY.md`** (bump every touched row) · **`docs/example/toml-config.md`** if
  `[sources]` semantics move.
- **`CLAUDE.md`** — ⚠️ **PROPOSE, do not silently apply.** As of `5f4d3fc` it is *accurate* (the
  SURFACE-CUT diff was applied and archived), so edit it directly — but surface the diff for
  Arpit's review rather than rewriting the always-loaded contract unannounced.
- **`docs/adr/README.md` ownership table + `tests/test_adr_ownership.py` `OWNERS`** — required for
  every new module. Both, same change, or the suite goes red.
- **Archive this pair** to `work/archive/v0.51-ledger-restructure.{handoff,prompt}.md` with the
  archive header, linked from the CHANGELOG ("Built from: …"), and update the `docs/README.md` +
  `work/archive/README.md` indexes. Progress line → 100%.

---

## Current state

- Repo `/Users/arpitarya/my_programs/cage`, v0.50.0, `main`.
- **The CLI is far smaller than CLAUDE.md claims** (SURFACE-CUT removed `report`, `insights
  attrib`/`adoption`/`compare`/`estimate`/`calibration`, the whole `data` group). Live leaves:
  `import · setup · doctor · query · insights {chats,graphify,commits,commit,why} · task
  {outcome,time} · authorship {origin,summary,verify,notes-sync} · study {…} · policy {diff,sync} ·
  mcp · demo · debug · hook`. **`cli.build_parser()` is ground truth. CLAUDE.md is not.**

**Read first**

| file | why |
|---|---|
| `docs/adr/0006_consumer.md` Decision | the decision P1 reverses — read before writing code |
| `cage/ledger.py` `spend()` ~550-583, `join_table()` ~584-610, `credits()` ~201-219 | the three readers this program moves |
| `cage/ledger.py` `SPEND_SOURCES` / `ABSENT_SPINES` / `CUMULATIVE_SOURCES` ~475-506 | the tables P1 and P2 edit |
| `cage/importcmd.py` ~1290-1310 **and ~1138-1150** | gate 3, twice |
| `cage/transcript.py` `_kiro_cli_conversations`, `_kiro_cli_credit_row`, `parse_kiro_cli_metrics` | P2's shared reader and the skip-rule difference |
| `cage/manifest.py` docstring | P3's carve-out, stated in full |
| `cage/cleanup.py` `NEVER` ~313 | why P3 needs an explicit entry |
| `tests/conftest.py` `metric_twin` ~77-100 | names exactly which agents need no twin |

## Non-negotiables

- **Fail-open on write paths** — `append` returns `False`, never raises; `meter()` swallows in
  cleanup. **But never silent:** every swallow site logs under `CAGE_DEBUG`
  (`tests/test_debug_coverage.py` audits this).
- **Append-only, always.** No migration rewrites, re-homes or deletes an existing row. Every old
  path stays readable forever.
- **Counts-never-content.** No prompt bodies, no line bodies, no line hashes. The manifest's
  `session_name` is the one recorded widening and is local-only.
- **`$0` / stdlib-only** — `dependencies = []`.
- **Determinism** — no clocks/random in derived views; ids carry the only entropy.
- **`method` is sacred** — never let a projection read as `measured`.
- **No currency, no rate card, no unit conversion** (ADR 0011). `tests/test_usage_only.py` AST-scans
  for this.
- **A removed path is a wiring migration** — sweep `install.sh`, `justfile`, `tools/dummyrepo`, the
  steering `Doc` literals, `docs/adr/0002_cli.md`. And a **citation migration** —
  `grep -rho "docs/[a-z0-9-]*\.md" cage/*.py | sort -u`.
- **Do not touch:** existing `calls-*.jsonl` / `credits-*.jsonl` shards · `schema.make_call` ·
  `ledger.join_table` · `transcript.parse_kiro_ide_metrics` · the authorship path
  (`parse_provenance`, `parse_edits`, `linematch`, `commitjoin`) · the graphify savings routes.

## Edge cases & risks

| case | expected |
|---|---|
| Ledger with codex/proxy rows only | `spend()` unchanged row-for-row. Assert against P0.1. |
| Receipt with `call=<old calls id>` | Still resolves — `join_table` unions historical `calls`. |
| Existing `ledger/imports.jsonl` | Still read after P3. Titles must not regress to session ids. |
| Existing `credits-*.jsonl` | Still read after P2. Same rendered values in `insights chats`. |
| Existing `provenance.jsonl` | Still read after P3c. `agent%` and `authorship origin/summary/verify` render identically. |
| Provenance row with unparseable `ts` | Falls back to the legacy unpartitioned file — never dropped. |
| `notes-sync` after P3c | Reads every shard. A partial read re-pushes or drops rows in `refs/notes`. |
| Anton / a `cage.meter` consumer | Keeps working through P1's dual-write. **Fail-open ⇒ a break is silent.** Test it. |
| Kiro-routed sweep (`_kiro_leg`) | Has its **own** `seen`/`captured` build. Two sites. |
| Fresh install, no rows | doctor says *not yet captured*, never *broken*. Check wording. |
| Tests seeding `calls` for the 3 agents | **Pass while pinning nothing.** See below. |

**The named trap.** CLAUDE.md: *"A basis change is a fixture migration, and the tests will not tell
you politely."* It bit this repo once at ~80 tests. **Green is not evidence here.** Migrate fixtures
via `conftest.metric_twin` — never a per-file copy — across `test_import_unified.py`,
`test_transcript.py`, `test_universal_capture.py`, `test_capture_health.py`, `test_claude_metrics.py`,
`test_claude_request_grain.py`, `test_copilot_metrics.py`, `test_kiro_routing.py`, `test_chats.py`.

## Testing & validation

- `just test` (1571 + 10 Windows skips + 1 opt-in dogfood skip). Update the count in README's `$0`
  section and the CLAUDE.md diff; closes **TEST-COUNT**.
- **New:** `test_calls_retired.py` (P5 gate, both directions) · a P6 test that deleting the
  integrity manifest moves zero numeric cells, that a lock-miss yields `unverified` rather than a
  broken chain, and that a tolerated truncated tail is never reported as tampering · a P1 dual-write test · a P2 parity
  test vs P0.1 · a P3 test that the old `imports.jsonl` path is still read **and** that
  `cleanup.NEVER` protects the new one · a P3c test that `ledger.provenance` unions legacy +
  sharded rows and that all four readers span shards.
- **Extend, do not just keep green:** `tests/test_authorship_capture.py`'s plant-string test must
  grep the new `ledger/provenance/` directory. Left pointing at the old file it passes forever while
  covering nothing — the strongest PII guard in the repo, silently retired.
- **Keep green:** `test_chats.py::test_deleting_manifest_changes_zero_numeric_cells` (P3 must not
  weaken it) · `test_cleanup.py`'s survival cases · `test_floor.py` · `test_usage_only.py` ·
  `test_debug_coverage.py` · `test_cli_reference.py` · `test_queue_honesty.py`.
- **Goldens:** `CAGE_BLESS_GOLDENS=1 pytest tests/test_output_spec.py`. Re-bless **only** where
  output legitimately changed. An unexpected golden change is a finding, not a diff to accept.
- Manual: `cage import` then `cage doctor` on the real ledger after each phase.

## Open questions

- **10.1 — custom `[sources.<name>]` tools: `consumer/` or `calls`?** Also decides whether
  `_PARSERS` and the `format` key survive. Blocks only the `_PARSERS` deletion; every other step
  proceeds. *Recommend: leave both alone this program — smallest reversible diff. Escalate before
  choosing otherwise.*
- **10.2 — manifest FK.** `_ingest` stamps `import_id` on calls rows as the FK back to the manifest;
  P4 deletes that leg. Verify the manifest still coheres and that titles still land (`_lift_names`
  is parse-only and should be independent — **confirm, don't assume**).
- **10.3 — `CUMULATIVE_SOURCES` after P2.** If `cli-conv` becomes the credits home with a
  last-write-wins collapse, is its exclusion from `SPEND_SOURCES` still right, or does kiro-CLI gain
  a spine? **This is a spine decision — do not make it silently.** Kiro currently renders `—` with
  a stated reason; changing that changes user-visible output.
- **10.4 — consumer dir name.** `ledger/consumer/` (matches ADR 0006's vocabulary) vs `ledger/lib/`
  (matches `agent="lib"`). Cosmetic but permanent once written. *Recommend `consumer/`.*
- **10.5 — `ledger/` namespace collision (P3c + P4).** After this program `ledger/` holds **four
  categories** in one flat namespace: agent usage (`claude/` `copilot/` `kiro/`), consumer
  (`consumer/`), tool savings (`graphify/`) and authorship (`provenance/`). A custom
  `[sources.<name>]` tool, or a future agent, sharing a name with any of them lands two row kinds
  in one directory. Reserve names against `agents.SURFACES` + a reserved list, namespace as
  `ledger/tools/<tool>/`, or validate at write time. **Blocks P4; P3c should follow whatever is
  decided here.**
- **10.6 — do the other savings sources move too?** `fux`, `compress`, `responsecache` also file
  receipts. Graphify-only leaves one row kind in two shapes, permanently. *Recommend moving all in
  P4; escalate if you disagree.*
