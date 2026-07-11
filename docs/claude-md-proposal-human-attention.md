# Proposed CLAUDE.md edits — derived human attention (v0.18.0, plan §4.10)

**Status: applied to CLAUDE.md on 2026-07-11** (edits 1–4 below; edit 5 was a
no-change note). Kept for the record of what changed and why.

## 1. Architecture map — extend the *Tier-1 human axis* bullet

Current bullet starts: `**Tier-1 human axis** ([human.py](cage/human.py), …`.
Append to that bullet (after the `matrix --human` sentence):

```markdown
  The passive side of the axis (plan §4.10): call rows carry an additive
  optional `gap_ms` (previous assistant end → the human turn that led to the
  call), stamped at import only where the log has per-turn timestamps (claude
  yes; codex/copilot/kiro no — absence explicit, never fabricated; never in an
  id). [attention.py](cage/attention.py) is the ONE place gap math lives —
  derived minutes = Σ min(gap_ms, idle cap), always `estimated`, labelled
  `derived (turn-gaps, capped)`; the cap is policy `[human] idle_cap_minutes`
  with the `constants.IDLE_CAP_MINUTES` fallback. Attested minutes
  (`human-record`, `cage outcome --minutes N`) beat derived per task — never
  summed. `compare`/`verdict`/`study report` print a total-cost line (agent $ +
  human minutes × rate, `--agent-only` suppresses); `cage calibration --human`
  is the measured accuracy of the heuristic (refuses below `MIN_ESTIMATE_N`).
  No watcher-shaped capture, ever: transcript timestamps only.
```

## 2. Constants bullet — add the new constant

In the **Constants** bullet's enumeration, add `IDLE_CAP_MINUTES` after
`SINCE_WINDOW_DAYS` (it follows the same policy-preferred pattern as
`DEFAULT_CONFIDENCE` / `warn_mb`: policy `[human] idle_cap_minutes` wins).

## 3. Substrate bullet — mention the additive field

In the **Substrate** bullet, extend the sentence about `scope`/`project` with:

```markdown
  Calls also carry an additive optional `gap_ms` (turn gap → derived human
  attention, plan §4.10; absent = legacy contract, never part of an id).
```

## 4. Dev section — test count

```markdown
just test          # python -m pytest -q   (441 passing)
```

## 5. (No change) release rules

CHANGELOG + README "What's new" + README test count are already updated
in-tree for v0.18.0 by this change; no release has been tagged or published
(no commits were made).
