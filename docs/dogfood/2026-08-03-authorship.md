---
doc: dogfood snapshot — 2026-08-03 (authorship reconciliation)
snapshot_date: 2026-08-03
snapshot_version: 0.46.1
window: all-time (this repo's 115 commits, 2026-06-14 → 2026-08-03)
ledger: project (.cage/) — this repo's own project ledger, not the maintainer's
        global ~/.cage used in 2026-08-02.md
---

# Dogfood snapshot — 2026-08-03: authorship reconciliation

**Supplements [2026-08-02.md](2026-08-02.md), does not replace it** — that snapshot
is the report/adoption ritual against the maintainer's global ledger; this one is a
single-question deep-dive against this repo's own project ledger, prompted by asking
cage "how much of this repo did the agent write" and getting a headline (72% UNKNOWN)
that reads more damning than the underlying capture gap actually is.

**The finding, first:**

1. `cage authorship summary` shows 83 of 115 commits (72%) `UNKNOWN` — not because
   most commits weren't agent-authored, but because provenance capture only started
   writing rows on **2026-08-02**, one day before this snapshot (§2).
2. A one-off full re-scan of the 94 Claude transcripts still sitting on disk recovers
   **69 commits (60%)** instead of the live ledger's **32 (28%)** — **41 more commits**
   are recoverable *right now* from evidence that already exists, blocked only by an
   authorship cursor that has no way to know a file is worth re-reading (§3).
3. That points at a real gap in the code, not just a documentation caveat: the cursor
   marks a transcript file "covered" and never re-reads it — even after a capture bug
   is fixed or the matching logic improves — unless the file's bytes change (§4).

## 1. `cage authorship summary` (verbatim)

```
$ cage authorship summary --why-ledger --no-import
· ledger: project (.cage/) → /Users/arpitarya/my_programs/cage/.cage (route-key d5aabe5fb3a94216)
Authorship · 115 commit(s)

  UNKNOWN     83 of 115 commit(s) (72%) have no authorship row at all
              — unknown by ABSENCE, never a stored row
  recorded    32 commit(s) · 79 row(s)

agent        rows
-----------  ----
claude-code    79

method      rows
----------  ----
transcript    79

  suggested 59,964 · kept 25,415 verbatim · 13,292 landed-modified · 21,257 dropped
  counts, not a score — no acceptance percentage is derived from them

· `unknown` is the honest headline: a commit cage never saw looks exactly like
  one made before cage existed. Absence of evidence.
· not line-matchable: copilot: its stores record usage and prompts, not the text of an edit · kiro: its usage log records token counts only, with no tool-input payload
```

## 2. Reconciling UNKNOWN against real git history

| | |
|---|---|
| total commits in repo | 115 (2026-06-14 → 2026-08-03) |
| commits with a provenance row | 32 (28%) |
| provenance row `ts` values (all 79 rows) | clustered on 2026-08-02, 15:25–20:31 UTC — one day's capture runs |
| oldest matched commit | `d040b67`, 2026-06-30 |
| oldest Claude transcript still on disk for this project | 2026-07-06 (94 files total, back to that date) |
| commits older than the oldest transcript | ~13 (2026-06-14 → ~2026-07-05) — **structurally unrecoverable**, no transcript ever existed for them |

Capture (`transcript.parse_provenance` writing via the import sweep) was reintroduced
in the v0.46 line after the hookless rebuild had removed its `SessionEnd` trigger
(CHANGELOG: *"Capture was dead, and now it isn't"*) — so the 72% UNKNOWN figure is
mostly measuring **when the feature started working**, not how much of the repo the
agent wrote. Within the 32 commits it did capture, **100% of rows are `claude-code`**.

## 3. Backfill opportunity — a fresh pass beats the live cursor

Ran `authorcapture.capture()` directly (the same function `cage import` calls)
against a **throwaway, discarded ledger** with no prior cursor, over the same 94
on-disk transcripts the live ledger already had access to:

```python
from cage import authorcapture
authorcapture.capture(throwaway_root, all_94_transcript_files, repo=repo,
                       pol={"authorship": {"capture": True}})
```

| | live project ledger (`.cage/`) | fresh full pass (throwaway) | delta |
|---|---|---|---|
| commits recovered | 32 (28%) | 69 (60%) | **+41** |
| provenance rows | 79 | ~106 | +27 |
| suggested lines seen | 59,964 | 61,952 | — |

The 41 newly-recoverable commits date **2026-06-30 → 2026-08-02** — squarely inside
the window where transcripts exist but the live ledger's cursor never produced a row
for them. Even the full pass can't reach **46** commits (some dates overlap ones it
*did* match elsewhere in the repo) — those are either older than the oldest surviving
transcript (§2) or genuinely contain no agent-attributable landed lines (e.g. a commit
of generated output — see the related [P1 dogfood regression](../regression/2026-08-02-p1-authorship-dogfood.md)
§4 on why a non-match must never be read as "a human wrote it").

**Why the live ledger stopped at 32 when 69 are reachable:** `cage/authorcapture.py`'s
cursor skips a file once it's marked "covered" (no edits fall after the newest known
commit) — re-reading only happens if the file's bytes change. Once a run — even a
run that predates or otherwise fails to fully exploit today's matching/bucketing logic
— marks a file covered, that file is frozen: a later capture-path fix cannot re-benefit
from it without the file changing or the cursor being reset. That is consistent with
what's observed here: every file in `.cage/state/cursors.json`'s `_authorship` table
is marked covered, yet a cursor-free pass over the identical files finds more than
twice the commits.

## 4. What this suggests for the code (not yet filed as work — evidence only)

1. **Cursor has no version-awareness.** Consider stamping a `authorcapture` logic
   version alongside each cursor entry, so a matching/bucketing fix can invalidate
   just the affected entries instead of requiring a full manual cursor wipe.
2. **No visibility into what's frozen.** There's currently no way to see "N files are
   covered-and-skipped, here's how many commits they could still yield" without doing
   the throwaway-ledger experiment above by hand. A `cage authorship coverage` (or a
   `cage doctor` line) surfacing `files_read` / `uncovered` / `skipped` per source would
   make this discoverable instead of requiring code-level investigation.
3. **Retention risk is time-sensitive.** The 58 pre-2026-08-02 transcripts that still
   have unrecovered commits behind them are subject to Claude Code's own local
   transcript retention — if they age out and get pruned before a cursor reset happens,
   those 41 commits become permanently `UNKNOWN`, joining the ~13 pre-2026-07-06 ones
   that already are. Worth a `cage doctor` advisory naming the count while it's still
   recoverable, rather than discovering the loss after the fact.
4. **The two claims aren't in tension.** "This repo is 90–99% Claude-built" and
   cage's "72% UNKNOWN" both stand — cage's number is an evidence floor, not an
   estimate, and §3 shows more than half of that gap is closable *today* from data
   already on disk, not lost history.

## 5. Method note

§3's numbers come from calling `cage/authorcapture.capture()` directly against a
temporary, discarded ledger — **not** a `cage` CLI command, and nothing it wrote
touched any real ledger. Flagged here so this section is never mistaken for a
supported, repeatable `cage` view the way §1 is.
