# ADR 0008 — Line-match authorship: counts are persisted, content is transient, and human is a residual

- **Status:** Accepted (v0.42, plan §3.5)
- **Date:** 2026-08-02
- **Deciders:** Arpit (ratifier), Claude Code (executor)

## Context

- The **v1 human axis was removed in v0.36 for inventing precision** — a turn-gap
  heuristic multiplied by an hourly rate, rendered so it read as measured. Anything
  answering "agent vs human" again has to survive that autopsy first.
- **The read surface was live and the capture was dead.** `cage authorship origin`,
  notes-sync and verify all shipped and worked; `transcript.parse_provenance` and
  `originrecord.record_transcript` had **zero callers** after the hookless rebuild
  removed the SessionEnd trigger. Every commit answered `unknown`. Nothing was wrong
  with the read side — nothing was writing.
- **There is no honest way to observe the human.** Keystroke and editor telemetry are
  sources cage is not allowed to want; git author identity proves nothing (agents
  commit as you). Every direct measurement of human authorship is either unavailable
  or a lie.
- **The agent, by contrast, is observable exactly.** A Claude transcript's
  `Edit`/`Write`/`MultiEdit`/`NotebookEdit` blocks carry the precise text proposed.
- **A late import must not resolve against `HEAD`.** Transcripts are swept minutes or
  days after the work; attributing an edit to whatever was checked out when
  `cage import` happened to run turns a capture path into a random-number generator.

## Decision

**Cage measures the agent precisely, persists only counts, and reports the human as an
explicitly-labelled residual it never claims to have measured.**

- **Direct evidence, transiently held.** At import, proposed lines are compared —
  in process memory — against the added lines of the commit whose window contains the
  edit. The strings are dropped when the match ends.
- **No line body and no line *hash* is ever written**, logged, or shipped. The row
  carries five integers (`schema.PROVENANCE_COUNT_FIELDS`). Hashes are named
  explicitly because a hash is the obvious "safe" shortcut and it is not one: a line
  hash is a membership oracle over the source file.
- **Human is a residual and is spelled `human~`.** The observation is "matched no
  agent proposal"; the label says so. It is `estimated`, never `human`, and the only
  path to an unmarked `human` remains explicit attestation (`--attest`,
  `method="heuristic"`, enforced in `make_provenance`).
- **The residual splits in two, because one bucket would lie.** `human~` covers files
  the session *did* propose; `unattributed` covers files **no** session proposed —
  human-written, vendored, or generated, and cage does not guess which.
- **Unknown is first-class and never redistributed** — sub-gate lines and binary files
  are shown, never folded into either side.
- **Windows, never HEAD.** Commit *i* owns `(ts_{i-1}, ts_i]`, upper bound inclusive.
  Work after the newest commit is left **unrecorded this sweep** and picked up, exactly
  once, by the next import after its commit exists.
- **One repository per sweep**, resolved from the cwd. A provenance row carries a short
  sha and repo-relative paths but no repo identity, so recording two repos into one
  ledger would make those shas ambiguous.
- **No USD, no rate, no valuation** on any surface built from these rows.

## Consequences

- `provenance.jsonl` gains automated rows for the first time; `origin`/`verify`/
  notes-sync answer from real data instead of absence.
- **The substrate stays additive.** Counts are omitted at 0, `schema_ver` stays 1, and
  a row from any other path is byte-identical to the pre-v2 contract.
- **The agent share can only be under-counted, never over-counted.** Work proposed in
  one window but committed in a later one is counted `dropped`. Inflation would require
  a human to type a ≥4-char line byte-identical to an agent proposal *in a file that
  same session proposed in that same commit*. The safe direction is the one it fails in.
- Cage now reads a repository's **diffs** — its widest PII surface. That buys its own
  consent switch, `[authorship] capture` / `CAGE_AUTHORSHIP`, separate from
  `[capture] enabled`: metering spend and letting cage read your code are different
  permissions.
- **Coverage is per-agent and stated.** Claude only; Copilot and Kiro persist no edit
  payload, so they render `—` with the reason named, never `0%`.
- Repeated in-session edits to one file depress the verbatim rate (only the final state
  is committed) — measured at **44.3%** repo-wide, and that is the honest shape, not a
  miss.

## Alternatives rejected

- **Persist line hashes instead of bodies** — *lost on PII, not on cost.* A hash set is
  a membership oracle: anyone holding the notes can test whether a given line was in
  your source. "Counts, never content" has to mean counts.
- **Resolve edits against `HEAD` at import time** — *lost on correctness.* It is what
  the orphaned code did, and it makes attribution a function of when the sweep ran.
- **Guess a commit for work not yet committed** — *lost on being wrong forever.* Not
  recording is reversible; a wrong sha in an append-only log is not.
- **Fuzzy / similarity line matching** — *lost on method law.* A similarity threshold
  is a tunable that silently moves the headline. Exact match with a content gate is
  the resolution the source actually supports.
- **A single `human` bucket, per the handoff's mock** — *lost to measurement.* On cage's
  own repo it printed **human~ 76.6%**, 89% of which was one commit of generated JSON
  ([dogfood](../regression/2026-08-02-p1-authorship-dogfood.md) §4). A residual
  presented as a finding is precisely the v1 mistake.
- **Detect generated files (`linguist-generated`, `.gitignore`, a size heuristic)** —
  *lost on inventing a fact.* `unattributed` already says the true thing.
- **Per-line accept *percentages* as a single score** — *lost on resolution.* The
  counts enum is what the source supports; 84% renders as "verbatim share of
  suggested", never as an acceptance score.

## Reference

- Measured, on cage's own 103-commit repo against 81 real transcripts:
  [docs/regression/2026-08-02-p1-authorship-dogfood.md](../regression/2026-08-02-p1-authorship-dogfood.md).
  The join test is §2 (68.7% match inside proposed files); the gate sweep is §3; the
  rejected single-bucket split is §4.
- The autopsy this decision answers to: `docs/archive/v0.36-human-removal.handoff.md`
  and `cage query savings-axis`.
- Plan §3.5 (provenance: the PII line, corroboration, unknown-by-absence).

## Veto condition (when to revisit)

**Contingent — auto-revisits on a named measurement:**

1. **The exact matcher.** If a dogfood run over ≥50 commits shows the verbatim match
   rate inside *proposed files* below **40%** (it is 68.7% today), exact matching has
   stopped describing how agents edit and a similarity matcher earns a compare doc.
   **Only with that number**, not from the argument that fuzzy matching sounds better.
   The change lands in `linematch.match_file` alone — windows, buckets and the PII
   line are out of scope for that revisit.
2. **`MIN_MATCH_CHARS = 4`.** Reopens if a measured sweep shows the gate moving the
   match rate by more than **2 points** between 3 and 6 (today: 0.1 points). A gate
   that steers the headline is a tuning knob, and a tuning knob must not be a constant.
3. **Per-agent coverage.** Copilot or Kiro persisting edit payloads moves that agent
   out of `authorcapture.COVERAGE_GAPS` and into the pass — additive, no ADR needed.

**Invariant — moves only by ratified reversal of this ADR:**

- **No line body and no line hash is ever persisted.** Not volume-gated, not
  performance-gated. It is why this feature is allowed to exist.
- **`human` is never written without an attestation.** The automated path may only
  ever produce `human~`/`unattributed`.
- **No USD, rate, or valuation on any authorship surface.** This is the v1 veto, kept.
- **Unknown is never redistributed** into agent or human to make a split total 100%.

**Deliberately not taken:**

- **Hunk-range fingerprints** (line *ranges*, not just per-file counts) would sharpen
  a commit where a file has two authors. Declined for now because the counts already
  answer the asked question and ranges widen the persisted surface toward "where in the
  file". Threshold to reopen: a real commit where two agents' claims on one file
  overlap and the per-file split is materially wrong — not a hypothetical one.
- **Patch-id chasing across rewritten history.** A squashed or rebased sha dangles and
  is counted `unmatched`, never chased. Reopens only if dangling shas exceed **10%** of
  attributed commits on a real repo.
