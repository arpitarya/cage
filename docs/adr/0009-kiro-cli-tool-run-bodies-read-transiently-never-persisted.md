# ADR 0009 — kiro-CLI tool-run bodies are read **transiently**; nothing but hashes and counts persists

- **Status:** Accepted (v0.47.0, plan §3.3 / §4.5)
- **Date:** 2026-08-07
- **Deciders:** Arpit (ratifier), Claude Code (Opus 5, GFX-COV/P2)

## Context

- `transcript.py` carries a standing law for the kiro-CLI SQLite store: the parser touches
  **only a closed whitelist of numeric/metadata keys** inside `conversations_v2.value`,
  and *never* `history[].user`, `history[].assistant`, `content`, `text`, `transcript`, or
  `next_message`. It is written down beside the parser because, uniquely in this store,
  **content and metadata share one row** — there is no schema boundary to hide behind.
- graphify's savings ledger was dark on kiro entirely. Not partially: **there was no
  detection path at all.** `import_kiro` reads the IDE token log, which carries no
  commands and no results; the CLI store had only the credits parser, bound by the law
  above. Any cross-agent reading of "does graphify pay" was structurally
  claude + copilot-CLI only (OPEN-WORK GF-AGENT-FIELD; NET-1 depends on it).
- The 2026-08-07 field probe settled what the store actually holds
  ([research](../../work/research/2026-08-07-graphify-store-evidence.md)): a graphify run's
  command lives at `history[].assistant.ToolUse.tool_uses[].args.command` and its output
  at `history[].user.content.ToolUseResults.tool_use_results[].content[].Json.stdout`.
  **Both are inside the whitelist's exclusion zone.** There is no adjacent metadata field
  that carries either one — the law and the feature are in direct conflict.
- The precedent already exists and is not new: the **claude transcript route** has read
  Bash commands and `tool_result` bodies since GC2, and the **copilot** routes since F1.
  Nothing about kiro makes it a harder case *in kind*; what differs is only that kiro's
  law is written down explicitly, so the carve-out has to be too.
- **The principle itself is already ratified** —
  [ADR 0008](0008-line-match-authorship-counts-persisted-content-transient.md) settled
  *counts are persisted, content is transient* for line-match authorship, and went
  further than this record needs to (it forbids even a line **hash**, because a hash over
  a source line is a membership oracle). This ADR does not re-argue that principle; it
  records **where the boundary falls in this store**, which is the part 0008 could not
  answer — kiro's is the one store whose law is written as a key whitelist, so an
  exception must be named against that list or it is invisible.

## Decision

**Reading a kiro-CLI tool run's command and stdout is permitted, in one named function,
and only ever transiently — a body may be hashed and token-counted in memory, and may
never be returned to a writer, stamped on a row, or logged.**

- The carve-out is exactly one function: `transcript.parse_kiro_cli_tool_runs` (and its
  helper `_kiro_cli_tool_runs`). It is named in the whitelist comment itself, so a reader
  of the law meets the exception at the same moment.
- `_kiro_cli_credit_row` — the *credits* parser, and **every** function in cage that
  writes a ledger row from this store — is unchanged and still fully bound by the
  whitelist. The carve-out widens what may be *read*, never what may be *written*.
- What persists is what persists on every other graphify route and nothing more:
  `args_hash`, `answer_hash`, a token count, `source_files` as an integer, `op`, and the
  deterministic `receipt_id`. No command string, no output byte, no file path.
- The store stays **read-only** — `mode=ro&immutable=1`, the same connection discipline
  the credits parser uses. cage never writes, migrates, or locks a kiro DB.
- **A truncated stdout files nothing.** kiro caps tool output at ~2000 tokens and appends
  `... (truncated to ~2000 token budget)`. A truncated answer under-counts `actual` and
  would *inflate* the modeled saving, so it is `unmeasurable`. The marker is matched
  **anchored at the end of the string**, never as a substring.

## Consequences

- kiro-CLI joins claude and copilot as a first-class graphify savings surface — the
  three-agent invariant now holds for this capture path instead of being aspirational.
- **This route will refuse often, and that is correct.** Most real `graphify query` output
  exceeds kiro's ~2000-token cap, so the query route files nothing on those runs. The
  `fs_read` report-read route is unaffected (it needs no result body). A thin kiro column
  in `cage insights attrib` is therefore expected, and the reason is named out loud in
  `cage doctor` and `cage query graphify-coverage` rather than left as a silent zero.
- The whitelist comment is now **load-bearing in two directions** — it states a law and
  its single exception. A future contributor adding a second exception must add it here,
  or the comment starts lying about the store's cardinality (the same failure the chats
  carve-out produced in CLAUDE.md, where one amendment silently became two).
- cage now reads the kiro store twice per sweep (credits, then tool runs). Both are
  read-only immutable connections over a store measured at ~1 MB / 19 conversations; the
  cost is not material at that scale. See the veto trigger.
- It does **not** commit cage to reading bodies from any *other* store under this ADR.
  Each store's law is its own.

## Alternatives rejected

- **Leave kiro dark.** Lost because it is not a limitation, it is an absence — cage would
  keep publishing per-tool savings that silently exclude a whole agent, which is the
  failure mode cage exists to catch in other tools.
- **Detect from the credits row's metadata alone** (turn counts, context %). Lost because
  none of it identifies *which command ran*. Any saving derived from it would be a guess
  wearing a number — the exact thing `method` tagging exists to prevent.
- **Persist the command string to make receipts auditable.** Lost outright:
  counts-never-content is a product invariant, not an ergonomics tradeoff, and an
  auditable receipt that leaks a prompt is worth less than an opaque one that doesn't.
- **File a partial saving from truncated stdout, marked lower-confidence.** Lost because
  confidence grades *inference quality*, not *missing data*. A truncated answer produces
  a number that is wrong in a known direction; a lower confidence would dress that up
  rather than refuse it.
- **Write a separate mini-parser rather than touching `transcript.py`.** Lost because it
  would put a second sqlite access idiom and a second copy of `_under`/`_norm_cwd_key`
  in the tree, and — worse — the carve-out would then sit somewhere the law does not
  mention, which is precisely how an undocumented exception becomes an unnoticed one.

## Reference

- The field probe that established the shapes, the truncation marker, and that no
  metadata alternative exists:
  [work/research/2026-08-07-graphify-store-evidence.md](../../work/research/2026-08-07-graphify-store-evidence.md)
  (kiro-cli 2.16.0, two live `execute_bash` runs, 19 conversations).
- [ADR 0008](0008-line-match-authorship-counts-persisted-content-transient.md) — the
  ratified statement of *counts persisted, content transient*, and the stricter reading
  (no line hashes) that shows where this record's limits come from.
- The identical discipline already shipped for two other agents:
  `graphifytx.detect_and_file` (claude, GC2) and `detect_and_file_copilot` (F1) — both
  read tool commands and result bodies transiently and persist only hashes.
  [ADR 0005](0005-graphify-receipt-ids-session-inclusive-cross-route-deferral.md) governs how the
  routes converge on one receipt.
- The routing this ADR deliberately does not re-decide:
  [ADR 0006](0006-kiro-rows-are-machine-facts-not-project-facts.md) — the detection hangs
  off the credits leg precisely so the sink and tree question stays answered there.

## Veto condition (when to revisit)

**1 · Falsifiable triggers (numbered).**

- **Read cost.** The second read is justified while the kiro-CLI store is small: measured
  at **1.0 MB / 19 conversations** on 2026-08-07. If a real store reaches **≥ 200 MB or
  ≥ 5,000 conversations**, or the two reads add **> 250 ms** to a sweep, fold both into a
  single pass over `conversations_v2` in `transcript.py`. That is a *performance* change
  and lands there — it must not become a reason to reopen the persistence rule.
- **The truncation cap.** The guard is keyed to the literal marker
  `... (truncated to ~2000 token budget)`. If a kiro-cli release changes that string or
  removes the cap, `tests/test_graphify_kiro.py::test_truncated_stdout_files_nothing`
  keeps passing while the *real* store silently starts filing inflated savings — a green
  test asserting nothing. Re-probe the marker on any kiro-cli major bump, and record the
  probed version in the research doc.
- **Coverage.** If, after a real evidence run, the kiro query route files on **< 10%** of
  observed graphify invocations, the honest product answer may be report-read-only plus a
  named gap. Reopen with the measured hit rate, not an impression.

**2 · Contingent vs. invariant.**

- **Contingent** (auto-revisits on evidence): the second read pass, the marker literal,
  whether the query route earns its place at the observed hit rate, and the ~2000-token
  cap itself.
- **Invariant** (moves only by ratified reversal of this ADR): **no command or output byte
  is ever persisted**; the store is **never written to**; a truncated or failed run files
  **nothing**; the credits parser stays bound by the whitelist. These are the
  counts-never-content and method laws applied here, not local design choices — a future
  agent may not trade them for coverage.

**3 · Deliberately not taken.**

- **Kiro IDE.** Its `workspace-sessions/` store was probed and persists **no** assistant
  output at all (26/26 `promptLogs[].completion` are the empty string, zero tool blocks),
  so there is nothing to carve out and no route to build — it ships as a named gap. This
  is left open, not dogmatically closed: **if a future Kiro IDE release persists tool
  calls with their results, that store becomes eligible under exactly the terms of this
  ADR** — transient read, hashes only, truncation refuses — and needs no new decision,
  only a probe and a route.
