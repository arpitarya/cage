---
doc: proposal — agent-vs-human measurement, v2 (per-commit)
status: proposed
raised: 2026-08-01 (Arpit)
supersedes-context: the Tier-1 human axis, removed v0.36 (archive/v0.36-human-removal.handoff.md)
---

# Proposal — agent-vs-human, rebuilt per-commit

**The v1 axis died because it invented precision** (a turn-gap heuristic priced at an
hourly rate, read as measured). **v2 anchors every number to a commit** — a real,
inspectable unit of work — and grades each of the four asks by what its source can
actually carry. Two are buildable on existing substrate; one is genuinely new capture;
one is the trap that killed v1 and gets the strictest treatment.

## The four asks, graded

| # | ask | source exists? | honest method | verdict |
|---|---|---|---|---|
| 1 | tokens per commit | mostly | `measured` calls, `modeled` join | **build** |
| 2 | human vs agent authorship per commit | **yes — provenance** | `transcript`/`heuristic` | **mostly built** |
| 3 | suggested vs accepted | partially | `estimated`, counts only | **build, coarse** |
| 4 | time: human vs agent vs combined | **no** | see below | **strict limits** |

### 1. Tokens per commit

Cage already has both ends: calls carry `ts`/`session`, and the task record
git-snapshots a SHA at task close (`tasks.py`). What's missing is the join.

- **Design:** a commit's tokens = calls in the window between the previous task-close
  SHA and this one, joined task-id-first, session-window fallback — the *same* join
  `taskgroup.py` already implements for the cost-impact surface. Reuse it; do not
  build a second join.
- **Method:** token counts `measured`; the commit attribution `modeled` (the window is
  an inference). A commit with no joinable calls reads **unattributed**, never zero.
- **Surface:** `cage report --by commit` (or `insights commits`), CSV column parity.

### 2. Human vs agent authorship per commit

**Provenance already answers this** (plan §3.5): `origin ∈ {human, agent,
agent-autonomous}` per file per commit, `origin="human"` only by attestation, unknown
derived from absence. What v2 adds is only an *aggregation*: per-commit file/line
counts by origin, and a repo-level trend.

- **Design:** a derived view over `provenance.jsonl` — zero new capture, zero schema
  change. `cage authorship summary [--since]`: N commits, files by origin, the
  unknown-rate stated first (it is the honesty headline, not a footnote).
- **Trap to preserve:** `unknown` is a read-time default, never a written row. The
  summary must show unknown as unknown — an "agent wrote 80%" claim with a 40%
  unknown-rate is fog.

### 3. Suggested vs accepted

New capture, and only coarsely knowable. The transcript contains what the agent
*proposed* (tool-use edit blocks); the commit contains what *landed*. Neither contains
what happened in between (manual tweaks, partial staging, rebases).

- **Design:** at task close, per file: agent-proposed edit count (from the transcript
  cage already parses) vs whether the file appears in the commit diff — yielding
  **proposed · landed · landed-modified · dropped** *counts* (PII guard: counts and
  paths only, never bodies — same widening provenance already justified).
- **Method: `estimated`, always.** Line-level accept-rates are NOT claimable — a
  landed-but-modified file is not "accepted 80%", it is `landed-modified`. The enum is
  the honest resolution; percentages of it are not.
- **This is the genuinely novel metric** — nothing on the market reports it — and the
  most likely to be over-read. The view ships with the caveat in the output, K3-style.

### 4. Time — human vs agent vs combined

**The v1 killer. The source for "human time" still does not exist** — a turn gap is
not attention (lunch, meetings, another repo). What each column can honestly be:

- **agent time:** `measured` — transcript turn durations / `latency_ms` already
  captured. Buildable today.
- **combined wall-clock per commit:** `measured` — commit-to-commit timestamps, with
  the multi-tasking caveat stated (wall-clock ≠ effort).
- **human time:** **not derivable passively. Refuse it.** Two honest options only:
  (a) explicit attestation, `cage task time 45m` (the `--attest` pattern provenance
  already uses — user-asserted, labelled as such); (b) absent attestation, the column
  prints `—` with "not recorded", never a gap-derived guess.
- **The v1 mistake — a rate × an inferred idle-capped gap — is explicitly out.**
  Reopening it requires new *evidence* the gap signal can be validated (e.g. a user
  study correlating gaps with attested time), not a new heuristic.

## Shape of the build (if accepted)

Order: **#2 (aggregation only) → #1 (join reuse) → #4 agent+wall columns → #3 (new
capture) → #4 human-attestation**. Each stage ships alone; none blocks the next.
Substrate impact: #1/#2/#4 none; #3 adds one additive optional task-record field
(proposed/landed counts) — plan §3 change, additive like `scope`/`project`.

## Deliberately not proposed

- Any hourly-rate valuation of human time (v1's `[human.rate]`) — valuation belongs to
  the reader's spreadsheet, not cage's ledger.
- Gap-derived attention in any form, per the veto above.
- Line-level accept percentages (#3's enum is the resolution the source supports).

## Trigger / next step

Arpit accepts (possibly amending grades) → #2 graduates to a handoff first — it is
aggregation over existing rows, provable in an afternoon, and its unknown-rate line
will immediately show how good the provenance capture actually is on a real repo.
