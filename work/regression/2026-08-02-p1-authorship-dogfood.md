---
doc: regression — P1 authorship dogfood gate (agent-vs-human v2)
date: 2026-08-02
repo: cage (its own checkout)
verdict: GATE PASSES — window join is sound; one design defect found and fixed in P3
---

# P1 dogfood — the commit-window join, measured on cage's own repo

**Verdict: the window join is sound.** Inside files a session actually proposed,
**68.7%** of matchable added lines are exact agent matches. That is the number the
gate exists to produce, and it is believable.

**One defect found, and it is not the join.** The three-bucket split the handoff
mocked (`agent / human / unknown`) would have printed **human~ 77%** for this repo —
because 89% of all added lines sit in files *no session ever proposed*, dominated by
one commit of generated JSON. Fixed by splitting the residual (§4).

`MIN_MATCH_CHARS` **frozen at 4**, with evidence (§3).

## 1. The run

| | |
|---|---|
| repo | cage's own checkout, 103 commits (2026-06-14 → 2026-08-02) |
| transcripts | 81 real Claude sessions, 123 MB |
| elapsed | 4.2 s (whole pass, cold cursor) |
| provenance rows written | **69** across 25 commits / 71 sessions |
| re-run | 0 new rows (idempotent on `(sha, agent, session, method)`) |
| edits with no commit yet | 0 uncovered |

Reproduce: `CAGE_AUTHORSHIP=1` + `authorcapture.capture(<throwaway ledger>, files,
repo=<repo>)`. Nothing is written outside the target ledger.

## 2. What the join actually produced

Suggestion accounting partitions exactly (`suggested == kept + kept_modified +
dropped`, asserted in the suite):

| bucket | lines | share |
|---|---|---|
| suggested (cleared the gate) | 53,159 | — |
| kept verbatim | 23,556 | 44.3% |
| landed-modified | 11,969 | 22.5% |
| dropped (file never landed) | 17,634 | 33.2% |

A 44% verbatim rate is the expected shape, not a miss: within one session an agent
edits a file repeatedly and only the **final** state is committed, so every superseded
intermediate `new_string` is correctly counted as modified-or-dropped rather than kept.

**The join test.** Restricting to files the session proposed *and* that landed in the
assigned commit — the only place the join can be wrong in the dangerous direction:

```
matchable added lines in files the session proposed :  34,264
matchable added lines in files NOBODY proposed      : 278,750
of the proposed-file lines, agent-matched           :  23,556  (68.7%)
```

Misassignment would show as a near-zero match rate there. It shows 68.7%. The join
is sound, and the pass proceeds to P2.

**Why the residual can only under-count.** When work is proposed in commit C's window
but lands in a later commit D, the file is absent from C, so its lines are counted
`dropped` — the agent share falls, it never rises. Inflation would require a human to
have typed a ≥4-char line byte-identical to one the agent proposed *in a file that
same session proposed in that same commit*. Undercount is the safe direction and it is
the one this rule fails in.

## 3. `MIN_MATCH_CHARS` — frozen at 4

Swept 1→12 over the same corpus:

| gate | suggested | kept | match rate |
|---|---|---|---|
| 1 | 58,072 | 23,887 | 41.1% |
| 2 | 57,858 | 23,810 | 41.2% |
| **4** | **57,214** | **23,556** | **41.2%** |
| 6 | 56,730 | 23,348 | 41.2% |
| 12 | 54,620 | 22,449 | 41.1% |

**The rate is flat — so the gate is not tuning the headline, which is exactly what it
should not do.** What moves is *which lines count*: raising 1→4 discards **331**
agent "matches" (1.4% of the total) that were pure punctuation — `}`, `)`, blanks —
lines that a human and an agent produce identically and that therefore evidence
nothing. Past 4 the returns are flat and real content starts being lost: `pass`,
`else:`, `break` are 4–5 characters.

4 is the boundary that keeps the shortest real statements and excludes the noise.
Unknown rate at 4: **14.3%** of added lines in proposed files (17.2% repo-wide).

## 4. The defect: a three-bucket split reads as a claim it cannot support

Repo-wide, the mocked buckets come out:

```
added lines  378,121
agent         23,556  ( 6.2%)
human~       289,458  (76.6%)   <- would be printed as "human"
unknown       65,107  (17.2%)
```

**That 76.6% is one commit.** `415775c` ("commit the knowledge graph") adds 312,131
lines, 257,359 of them in `graphify-out/graph.json` and its siblings — generated
artifacts. No agent proposed them line by line, so the rule labels them `human~`.
"Not the agent" is *literally* true and *reads* as "a person wrote 289k lines". This
is the v1 failure mode in new clothes: a residual presented as a finding.

**Fix (P3), and it costs nothing** — `NOT_PROPOSED` is already a computed verdict, so
the residual splits with no new inference:

| bucket | meaning | evidence |
|---|---|---|
| `agent` | matched an agent proposal | direct |
| `human~` | in a file this session **did** propose, matched nothing | residual, high signal — a real human tweak of agent work |
| `unattributed` | in a file **no** session proposed | cage has no evidence either way: a human file, a vendored file, or generated output — it does not guess |
| `unknown` | below the content gate, or binary | structural |

Nothing is redistributed; one bucket becomes two. For this repo it moves 278,750
lines out of a bucket labelled *human* and into one labelled *cage cannot say* —
which is the truth.

Deliberately **not** done: a generated-file classifier (`.gitignore`,
`linguist-generated`, a size heuristic). That would be a guess wearing a number, and
the honest bucket already exists.

## 5. Coverage, stated

- 25 of 103 commits carry a row (24%). The other 78 predate these transcripts or were
  made by sessions/agents cage cannot line-match — **unattributed, counted, never
  zeroed**.
- Per-agent: claude only. Copilot's stores record usage and prompts but not the text
  of an edit; Kiro's log records token counts with no tool-input payload
  (`authorcapture.COVERAGE_GAPS`). Both render `—` with the reason named, never 0%.
- 0 binary files in the sample, so the unreadable path is covered by unit tests only.

## 6. PII

The plant-string test (`tests/test_authorship_capture.py`) runs the pass with
`CAGE_DEBUG=1` — the most cage can possibly write — then greps every file under the
footprint for the sentinel line bodies **and** for their sha1/sha256/md5 digests,
full and truncated. Green. Proposed line text exists only in process memory for the
length of one match.
