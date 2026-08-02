---
doc: proposal — agent-vs-human measurement, v2 (per-commit)
status: accepted 2026-08-02 (amended in session; graduated to handoff)
raised: 2026-08-01 (Arpit)
amended: 2026-08-02 (Arpit — commit views, line-match capture, §4 estimator lifted with guards)
supersedes-context: the Tier-1 human axis, removed v0.36 (archive/v0.36-human-removal.handoff.md)
handoff: ../agent-vs-human-v2.handoff.md · prompt: ../agent-vs-human-v2.prompt.md
---

# Proposal — agent-vs-human, rebuilt per-commit

**The v1 axis died because it invented precision** (a turn-gap heuristic priced at an
hourly rate, read as measured). **v2 anchors every number to a commit** — a real,
inspectable unit of work — and grades each ask by what its source can actually carry.
**No USD appears anywhere on these surfaces** (Arpit, 2026-08-02): tokens and hours
only; valuation stays in the reader's spreadsheet.

## Two findings that re-graded the build (2026-08-02 code audit)

1. **Provenance capture is orphaned.** `transcript.parse_provenance` and
   `originrecord.record_transcript` have **zero callers** — the hookless rebuild
   removed the SessionEnd trigger and nothing re-wired it. `provenance.jsonl` gains
   rows only via `--attest` today. So ask #2 is *read-surface built, capture dead*:
   on a real repo the unknown-rate is ~100% until the import sweep learns to write
   provenance. The sha-resolution question (which commit does a late-imported edit
   belong to?) is the real design decision — answered below by the same
   commit-window join #1 uses.
2. **`latency_ms` is set only by the library meter** (`metering.py`). Transcript-
   imported calls — the dominant real source — carry `latency_ms=0`. "Agent time:
   measured, already captured" holds only for lib-metered traffic; everywhere else
   agent time is a **turn-span** (first→last turn ts in the joined window), which
   includes human think-time between turns and is therefore `modeled`, labeled.

## The four asks, re-graded

| # | ask | source exists? | honest method | verdict |
|---|---|---|---|---|
| 1 | tokens per commit | mostly | `measured` counts, `modeled` join | **build** (task-join reuse + new commit-window fallback) |
| 2 | human vs agent authorship per commit | read side yes, **capture orphaned** | `transcript` + line-match, `estimated` residual | **build: re-wire capture, then aggregate** |
| 3 | suggested vs kept | partially | `estimated`, counts + line-match | **build — line-grain now honest via exact-match** |
| 4 | time: human vs agent vs wall | agent: partial · human: no | see §4 (amended) | **build with guards** |

## The line-match capture design (the mechanism behind #2 and #3)

Never observe the human — observe the agent precisely; the human emerges as the
residual.

- **Agent lines (direct evidence).** Claude transcript `Edit`/`Write`/`MultiEdit`/
  `NotebookEdit` tool-use blocks carry the exact proposed text. At import: normalize
  each proposed line (strip whitespace), compare **transiently, in memory** against
  the added lines of `git show <sha>` for commits in the session's window. A match =
  agent-kept line. **Only counts are persisted — never line bodies, never hashes.**
- **Suggested vs kept falls out free.** `suggested` = proposed-line count; `kept` =
  exact-match count; `landed-modified` = file landed, lines diverged; `dropped` =
  proposed file absent from the diff; `not-proposed` = in the commit, never proposed
  (the human-contribution shadow, for free from the same set-difference).
- **Human lines = residual, always `~`.** An added line matching no joined agent
  proposal is human-or-unknown. "Not the agent" is the actual observation, so the
  label is `human~` (`estimated`), never `human`.
- **Unknown is a first-class bucket.** Lines below the minimum-content gate (`}`,
  blanks, bare imports), formatter-reflowed lines, binary files, and rebased/squashed
  commits whose recorded shas dangle. Unknown is shown, **never redistributed**.
- **Corroboration & override.** Where CLI hooks fire, `hooked` rows corroborate and
  bump confidence (machinery already in `originrecord`). `--attest` stays the only
  path to an unmarked `human`.
- **Out:** keystroke/editor telemetry (no source cage is allowed to want); git author
  identity (agents commit as you — proves nothing).
- **Coverage is per-agent and stated:** Claude transcripts are edit-parseable today;
  Copilot/Kiro are not — their rows read `—` with the reason named, never 0.

## §4 amended — time (Arpit, 2026-08-02: estimator lifted, with guards)

- **wall-clock**: commit-to-commit timestamps — `measured`, elapsed-not-effort caveat.
- **agent**: `latency_ms` sum where present (`measured`, lib-metered only); else
  turn-span, rendered with `~` and named as a span.
- **human**: two tiers, visibly distinct —
  `*` **attested** (`cage task time 45m`) — user-asserted, always wins;
  `~` **estimated** = wall-clock − agent span, floored at 0, and **refused (`—`)
  when the commit gap exceeds `[authorship] max_est_gap`** (default 4h) — beyond
  that the estimate is fog, and fog is not rendered.
- **Standing guards (the v1 lesson, kept):** no hourly rate, no USD, no valuation —
  ever, on any of these surfaces. The estimator's method is named in the view's own
  footnote, not a doc. Config kill-switch (`[authorship] estimate_hours = false`).
  The v1 mistake — a rate × an inferred gap read as measured — stays dead.

## The two surfaces (spec'd 2026-08-02; mocks in the handoff)

1. **List — `cage insights commits`**: one row per commit: sha · date·time ·
   tok in / tok out / cache read / cache write · human hrs (`*`/`~`/`—`) ·
   agent/human/unknown % split (share of classified kept added-lines; unknown shown,
   never folded). Σ totals row; unattributed commits excluded-and-counted, never
   zeroed. Footnotes carry: estimator method, join method (task-id vs window vs
   unattributed), per-agent exclusions (copilot-CLI shutdown ts, kiro import-time ts).
2. **Detail — `cage insights commit <sha>`**: tokens block (in/out/cache r/w) ·
   origin line (confidence + method; human only by attestation, unknown by absence) ·
   lines block (total +/−, agent / human~ / unknown) · suggested vs kept
   (verbatim / landed-modified / dropped / not-proposed **counts** — never an
   accept-%) · per-file table · time line (wall / agent span~ / human `*`|`~`|`—`) ·
   Σ suggested/kept totals.

Both: `--json` in the `cage.v1` envelope, CSV column parity, deterministic output.

## Scenario honesty matrix (what each ask renders, per situation)

| scenario | tokens | authorship / lines | suggested-kept | time |
|---|---|---|---|---|
| clean loop (task closed, 1 commit) | full join | agent lines matched | full | wall · span~ · human `*`/`~` |
| multi-commit task | per-commit via ts sub-windows, `modeled` | per-commit via edit-ts | per-commit | span unsplittable → task grain |
| pure human commit | **unattributed** | 100% human~/unknown | "no proposals recorded" | wall only |
| no task discipline | commit-window join carries all | same | same | wall + span~ |
| copilot CLI / kiro | excluded + counted (unjoinable ts) | `—`, reason named | `—` | wall only |
| copilot VS Code | window-joinable (per-request ts) | `—` (no edit parsing) | `—` | wall |
| two agents interleaved | split by session | residual after **all** agents | per-agent; both-proposed = contested | spans never summed |
| squash/rebase/amend | anchors gone → unattributed | **unmatched** bucket (own honesty line) | unreliable, flagged | skipped |
| human tweaks agent files | normal | agent stands at file grain; line grain catches the tweak | landed-modified | normal |

## Shape of the build (graduated — see handoff)

**P1** capture re-wire + line-match into the import sweep (substrate; ends with a
dogfood run on cage's own repo reporting match/unknown rates) → **P2** commit-window
join (`commitjoin.py`) → **P3** the two views + `authorship summary` → **P4** time:
attestation verb + guarded estimator. Each phase ships alone, suite green.
Substrate impact: additive-optional fields only (provenance counts; task
`human_minutes`); no new row kinds; `CALL_FIELDS` untouched.

## Deliberately not proposed

- Any USD/valuation on these surfaces (list, detail, summary) — reader's spreadsheet.
- Line-level accept **percentages** — the counts enum is the resolution the source
  supports; 84% renders as "verbatim share of suggested", never a score.
- Rewritten-history reconciliation (patch-id chasing) — dangling shas are counted
  as `unmatched`, never chased.
- Keystroke, editor, or attention telemetry of any kind.
