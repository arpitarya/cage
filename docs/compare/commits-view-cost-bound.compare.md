---
doc: compare — how to bound `cage insights commits`' cost
status: OPEN — needs Arpit's verdict
raised: 2026-08-11 (agent-lane sweep P3, item 3.4)
---

# Compare — bounding `cage insights commits`

**The answer first:** the view's cost grows with the *whole* repo history while the
screen stays 20 rows. The obvious fix — a default `--since` — would put a **wall clock
in the default path**, which this repo has already ruled against once. I recommend
**Option B (cap the read at the row cap)**. Nothing is implemented; `--since` still has
no default.

## The measurement

- `cage insights commits` on cage's own repo: **6.4s** to print **20 rows** from **123
  commits**. With `--since 3d` (8 commits): **1.2s**.
- Cause: `commitview.summarize` builds a row for **every** commit, and each row costs one
  `linematch.commit_diff` → `git show --numstat` **subprocess**. The 20-row cap is applied
  later, in `render_commits`.
- `constants.COMMITS_DEFAULT_ROWS`' own comment claimed the cap "also bounds cost". It
  does not, and never did. **Corrected in this change** — that comment was the reason the
  problem stayed invisible.
- Landed already (uncontested, no decision needed): the O(n²) `w not in wanted` list scan
  is now a sha set, and a `--since` window that hides commits reports how many
  (`windowed_out`) instead of silently shrinking the history.

## The options

| # | option | cost bound | determinism | cuts |
|---|---|---|---|---|
| A | default `--since 90d` | by **time** | ❌ clock in the default path | by date |
| B | pass the row cap into `summarize` | by **rows** | ✅ pure function of the ledger + repo | by rank |
| C | leave it; document `--since` | none | ✅ | nothing |

### A — a default relative window · **do not take**

- Bounds cost by *time*, which is not the axis the screen is capped on, so it can cut
  everything or nothing. On cage's own repo a 90d default cut **zero** commits — the cost
  was unchanged — because the whole history is recent.
- It makes an untouched command's output change with the calendar: the golden fixture's
  commits are at a fixed `2026-07-01`, so the same ledger renders differently once they
  age past the window. Two green goldens broke on exactly this.
- INTERVIEW.md's DOGFOOD lesson already ruled on the shape: *"for any published window:
  make it **absolute, never relative** — a relative `--since` re-measures a different
  window each refresh."*

### B — bound the read by the row cap · **recommended**

- Cost becomes **O(rendered rows)**, not O(history): ~20 `git show` calls, flat forever.
  It bounds the thing that is actually expensive, on the axis the view is already paged on.
- Deterministic: same ledger + same repo ⇒ same table. No clock anywhere.
- `--all` lifts it, exactly as it lifts the render cap today — one flag, one meaning.

**The open sub-question, and it is the whole reason this is a compare doc:**
`summarize` is shared three ways, and they want different amounts of data.

| consumer | wants |
|---|---|
| text (`render_commits`) | 20 rows |
| `--csv` | **all** rows — "CSV is never truncated" is a standing rule |
| `--json` | all rows (agent-as-user) |
| `cage insights commit <sha>` | one specific row, at any age |

So B needs a `limit` parameter that `cmd_commits` sets **only** for the text path,
leaving CSV/JSON/detail uncapped — which means the slow case still exists for
`--csv`, and is then honest rather than accidental. That is a real trade to accept
explicitly, not a detail.

### C — leave it

Defensible: `--since` exists and works, and repos this hurts are large ones. But the
default path is the one everybody runs, and 6.4s at 123 commits is minutes at 5,000.

## Proposed verdict

**B**, with the sub-question resolved as: cap the **text** path only; `--csv`/`--json`
stay complete and pay full cost; `--all` lifts the cap on every path. Rejects A on the
determinism law and on the measurement (it did not bound cost here at all).

## Reopen trigger

Revisit **B's cap value** if a user reports the text view hiding work they expected, or
if `--csv` on a large history becomes a complaint with a **named commit count and wall
time** — not on an argument. Revisit **A** only if cage ever adopts an *absolute*
default window (a fixed date, not a relative one); a relative default is closed by the
determinism law and reopens only by reversing it.
