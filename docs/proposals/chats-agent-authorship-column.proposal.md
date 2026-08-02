---
doc: proposal — a human-vs-agent authorship column on `cage insights chats`
status: proposed
raised: 2026-08-02
owner: unclaimed (Opus tier when picked up — touches the provenance substrate and three standing guards)
---

> **Picked up 2026-08-02** — packaged (Arpit's ask) as the live pair
> [chats-author.handoff.md](../chats-author.handoff.md) ·
> [chats-author.prompt.md](../chats-author.prompt.md) (Opus). The pair encodes the
> REV-TS sequencing as a hard Phase-0 gate: **the build STOPs unless
> [timestamp-utc-normal-form](../archive/v0.45-rev-ts.proposal.md) has landed.** This
> entry stays put until implemented, per the lifecycle rule.

# Proposal — `cage insights chats` gains an `agent%` column (code authorship per chat)

**The question the chats view cannot answer today:** this chat spent 2.1M tokens —
*did any of it become code, and whose code is it?*

The per-commit surfaces (`cage insights commits`, FORMULAS §2.14) answer it per
**sha**. Nothing answers it per **conversation** — the unit the chats view exists
for.

**The claim:** the v2 authorship substrate already carries the join key.

Provenance rows are recorded per `(sha, agent, session_id)` (`originrecord.record`,
idempotency key); the chats view buckets per `(agent, surface, session)`
(`chats._bucket_key`).

For claude-code both sides stamp the **same** session id — the transcript stem
(`importcmd._PARSERS`: `session=f.stem`; `authorcapture.capture`:
`parse_edits(f, session=f.stem)`).

So a per-chat authorship column is a pure ledger join — **no git at render time**,
keeping chats' "pure derive" character.

## The metric — scope it honestly or don't ship it

Per chat: **of the matchable added lines that landed in files this chat proposed,
what share matched the agent's own proposals?**

```
agent_lines_chat = Σ provenance.agent_lines      over rows with session_id == chat's session
residual_chat    = Σ provenance.residual_lines   (NEW count — see substrate change)
agent%           = agent_lines_chat / (agent_lines_chat + residual_chat)
```

- The remainder is exactly §2.14's `human~` — a person's tweak *inside files the
  session touched*. Direct evidence on one side, labelled residual on the other.
- `unattributed` and `unknown` are **commit-scoped, not chat-scoped** — a file no
  session proposed belongs to no chat, so they are structurally outside this
  denominator. That is not redistribution; it is scope. The column header/footnote
  must say "of evidenced lines in files this chat touched", never "of this chat's
  work".

## Substrate change — ONE new additive count, always written

`residual_lines` joins `schema.PROVENANCE_COUNT_FIELDS`: per `(sha, session)` row,
the matchable added lines in that row's landed files **minus** its `agent_lines`.
Computed in `authorcapture.capture` step 4, where `diff["added"]` and the landed
paths are already in hand — the same one-git-call-per-commit pass, zero new reads.

**Deliberate deviation from omitted-at-0:** the five existing counts omit at 0;
`residual_lines` is **always written, including 0**.

Presence of the key is the version gate — a row lacking it predates this change and
its chat renders `—`; a row carrying `0` is the real fact *everything matchable
matched the agent*. Same absent-vs-recorded-zero law as `credits`' `None` sentinel
(§1.1a).

Recorded rows are frozen by the idempotency key, so old rows can never be backfilled
and must stay distinguishable forever.

## Render

- Text: one compact column, `agent%`, after `credits` — default **on** (it is the
  differentiator column; alternative, behind an `--authorship` flag, is named as a
  fork for pickup). Renders `62%`; refusals render `—`, each with its reason
  footnoted, never a 0%:
  - **coverage** — copilot/kiro chats: `authorcapture.COVERAGE_GAPS` verbatim
    (their stores persist no edit text). Kiro-IDE's collapsed row is doubly `—`.
  - **no landed evidence** — no provenance row joined: the chat produced no code,
    or its edits haven't been committed yet (the `_authorship` cursor's
    uncovered state), or its commits live in a different ledger root. "Nothing
    landed" ≠ "the agent wrote nothing".
  - **pre-upgrade rows** — rows without `residual_lines` are excluded from both
    sums and counted in one footnote (`· N provenance row(s) predate residual
    counts — excluded`). Mixed chats compute over the carrying rows only.
- CSV (`render_csv`, FORMULAS §2.13 column contract): `agent_lines`,
  `residual_lines`, `agent_pct` — raw counts always, `agent_pct` empty when
  refused, empty-not-dash per the existing credits rule. Untruncated as ever.
- Join normalization: provenance stamps `agent="claude-code"`, chats buckets on
  `agents.row_surface(...)` = `"claude"` — the join must pass both through
  `row_surface` (the same normalization, one function). Bucket key includes
  `surface`; provenance rows carry none, so counts attach to every bucket sharing
  `(agent, session)` — footnoted if a session ever splits across surfaces.

## The three standing guards this must answer (and how)

1. **The v0.36 human-axis removal** (FORMULAS §3). Nothing priced returns: no
   rate, no minutes, no `gap_ms`, and `agent%` never multiplies into `cost` — no
   "human-equivalent $", no cost-split-by-author. Structural test in the §2.14
   style: no formula in `chats.py` may combine an authorship count with a USD
   value (`tests/test_chats.py` assertion, mirroring `test_commitview.py`'s
   no-pricing-import guard in spirit — chats legitimately imports `prices` for
   `cost`, so the guard is per-formula, not per-import).
2. **"Counts, not a score"** (`authorship summary`'s footer). Still true: no
   acceptance rate (`kept/suggested`) is derived here. `agent%` is the landed-line
   composition split — the same split `insights commits` already renders as
   percentages of classified lines (`commitview._pct`) — re-keyed by session
   instead of sha.
3. **The chats money-independence carve-out** (`manifest.py` docstring: labels are
   the ONE non-calls read). This adds a second: `provenance.jsonl`, counts-only.
   The law extends rather than breaks: deleting `provenance.jsonl` must move **zero
   pre-existing cell** — only the new authorship cells fall to `—`. Extend the
   pinned money-independence test in `tests/test_chats.py` to assert exactly that.

## Honesty limits, stated not fixed

- **No cross-session clamp.** Per commit, `commitview._buckets` clamps
  Σ`agent_lines` to `matchable − unattributed` so two agents can't both claim one
  line. Per chat there is no diff to clamp against — two chats that proposed the
  same landed line each count it. Rare, footnoted in `cage query` prose; the
  commit view stays the arbiter for any single sha.
- **Claude-code only** — the same coverage boundary as every authorship surface;
  a new parser moves an agent out of `COVERAGE_GAPS`, nothing else does.
- **Landed commits only.** A live chat's proposals show `—` until they are
  committed and the next sweep covers them — by design (the commit is the unit
  you can `git show`).
- **Inherits [timestamp-utc-normal-form](../archive/v0.45-rev-ts.proposal.md).** The
  window join that buckets edits into commits is offset-skewed on non-UTC
  machines (IST included) at HEAD. **Sequencing: the UTC fix ships first**, or
  this column publishes wrong joins with a new, friendlier face.

## Tests (sketch)

- Goldenseed: single-session fixture — chat-level `agent_lines`/`residual_lines`
  sums equal the per-commit §2.14 buckets summed over that session's shas.
- Refusal triad: no-provenance chat → `—` (never 0%) · copilot chat → `—` +
  coverage footnote · pre-upgrade-row fixture → excluded + counted footnote.
- Money-independence extension (guard 3) and the no-USD-combination assertion
  (guard 1). Plant-string test untouched — `residual_lines` is an integer; line
  bodies still never persisted (ADR 0008).

## Trigger

**Picked up** — the pair is written and its Phase-0 REV-TS gate now passes (REV-TS
shipped 2026-08-03). Ready to execute.

On implement: FORMULAS §2.13 (column contract) and §2.14 (counts table) get their rows
in the same change, and `cage query chats-view` + `cage query agent-authorship` both
gain the scope sentence.

## Evidence

Read against HEAD, 2026-08-02:

- `cage/chats.py` — bucket key, render, CSV
- `cage/authorcapture.py` — capture step 4, cursor, `COVERAGE_GAPS`
- `cage/commitview.py` `_buckets` — clamp, four buckets
- `cage/originrecord.py` — idempotency, the `**counts` boundary
- `cage/schema.py` `PROVENANCE_COUNT_FIELDS`
- `cage/importcmd.py` `_PARSERS` + `cage/agents.py` `row_surface` — the join key
-
[FORMULAS §2.13 / §2.14 / §3](../FORMULAS.md).
