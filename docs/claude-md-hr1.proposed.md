---
doc: proposed CLAUDE.md edit — HR1 (agent-vs-human v2)
status: AWAITING ARPIT'S REVIEW — not applied
raised: 2026-08-02 (Claude Code, executing agent-vs-human-v2.prompt.md)
---

# Proposed CLAUDE.md edit — HR1

**Not applied.** The prompt's §9.5 is explicit: *"For CLAUDE.md: PROPOSE the edit and
flag it for Arpit's review — do not silently rewrite steering files."* Everything else
in the checklist is done and committed; this is the one item held.

**Apply, amend, or decline.** If applied, delete this file in the same change and bump
the CLAUDE.md row in [DOC-REGISTRY.md](DOC-REGISTRY.md) — its row already carries a
2026-08-02 entry saying the edit was *proposed*, which must then be corrected to say it
landed.

---

## 1. New architecture bullet

Insert after the **Provenance (authorship attribution)** bullet, since it is the
capture half of the same subject.

> - **Authorship, per commit** ([linematch.py](cage/linematch.py) matcher,
>   [commitjoin.py](cage/commitjoin.py) windows + call join,
>   [authorcapture.py](cage/authorcapture.py) the pass,
>   [commitview.py](cage/commitview.py) the views;
>   [ADR 0008](docs/adr/0008-line-match-authorship-counts-persisted-content-transient.md),
>   FORMULAS §2.14) — the agent-vs-human axis, rebuilt at a unit you can `git show`.
>   **Never observe the human; observe the agent precisely and let the human be the
>   residual.** A Claude transcript records the exact text an `Edit`/`Write`/
>   `MultiEdit`/`NotebookEdit` block proposed; at import that text is matched
>   **transiently, in memory** against the added lines of the commit whose *window*
>   contains the edit. **Only counts persist — no line body and no line *hash*** (a hash
>   is a membership oracle over the source; it is named because it is the obvious "safe"
>   shortcut and is not one). Five additive-optional provenance counts, omitted at 0, so
>   `schema_ver` stays 1. **Windows, never `HEAD`-at-import**: commit *i* owns
>   `(ts_{i-1}, ts_i]`, upper bound inclusive, and work after the newest commit is left
>   **unrecorded** this sweep — idempotency picks it up exactly once when its commit
>   exists, and guessing a commit that does not exist yet would be wrong forever.
>   **FOUR line buckets, never three, and none is redistributed:** `agent` (matched a
>   proposal — read from the row, *never* re-matched at render time) · `human~` (in a
>   file that session *did* propose, matching nothing — a real human tweak, `estimated`
>   by construction) · `unattributed` (in a file **no** session proposed: a person, a
>   vendored tree, or generated output — cage does not guess) · `unknown` (sub-gate or
>   binary). The fourth bucket exists **because it was measured**: a single `human`
>   bucket printed 76.6% on cage's own repo, 89% of it one commit of generated JSON
>   ([dogfood](docs/regression/2026-08-02-p1-authorship-dogfood.md)) — a residual
>   presented as a finding is the v1 mistake in new clothes. **Coverage is per-agent and
>   stated** (`authorcapture.COVERAGE_GAPS`): claude only; copilot and kiro persist no
>   edit payload and render `—` with the reason, never `0%`. The call→commit join reuses
>   `taskgroup.join_rows` (task-id first, window fallback) and **never forks a second
>   join**; a task closed on a **dirty tree** is not trusted (its sha is the *prior*
>   commit), and a call with **no `project` stamp is *unconfirmable*, not adopted** —
>   otherwise a global ledger would pull every other repo's spend onto these commits.
>   **`[authorship] capture` / `CAGE_AUTHORSHIP` is its own consent switch**, separate
>   from `[capture] enabled`: this is the one path that reads a repository's *diffs*,
>   and metering spend is a different permission from reading code. `cage query
>   agent-authorship` explains it.

## 2. Amend the existing v0.36 amputation bullet

The bullet **"The Tier-1 human axis is GONE (v0.36)"** currently ends with the list of
what survives. It is still true and must stay — but a reader now meets `cage insights
commits` and needs to know it is not a reintroduction. Append:

> **A v2 exists and it is a different question (v0.43).** `cage insights commits` /
> `commit <sha>` rebuilt agent-vs-human **per commit**, and nothing amputated came back:
> no rate, no USD, no `gap_ms`, no `minutes` unit, no derived attention, no `cage human`.
> What it adds is *line-level evidence* and a human that is an explicitly-labelled
> residual. **The standing guard is the load-bearing part: no USD, rate or valuation
> appears on any authorship surface** — structurally, not by policy (`commitview.py`
> imports no pricing module, asserted by AST in the suite). Hours exist only as an
> attestation (`cage task time`, rendered `*`) or a guarded `~` estimate that **refuses
> four ways** rather than print fog — including when no agent span joined, where
> `wall − nothing` would render the raw commit gap as effort. That last refusal is v1's
> exact mistake, caught in this build by smoking the real repo.

## 3. Two counts to refresh

- `just test` comment: **1148 → 1354 tests**.
- The flow diagram's derive line gains the new views:
  `… · compare · verdict · why · origin · chats · commits · commit`.

---

## What I am *not* proposing, and why

- **No new Must-Know rule.** Everything here follows rules that already exist
  (counts-never-content, method-is-sacred, refusals render, one-implementation). Adding
  a rule for a feature that obeys the current ones would dilute the list.
- **No change to the `paths.py`-splits-on-contact seam list.** HR1 touched `paths.py`
  not at all, so it has no seam to claim.
