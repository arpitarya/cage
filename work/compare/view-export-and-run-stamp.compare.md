---
doc: compare — exportable views and where the generated-at stamp lives
status: DECIDED — verdict accepted by Arpit 2026-08-10; IMPLEMENTED v0.48 (unreleased) — living spec: `cage/runstamp.py` · `cage/viewexport.py` · ../CLI.md · `cage query view-export`
raised: 2026-08-10 (Arpit: "reports and insights: date/time optional in CLI, mandatory in exports; exportable by default into .cage/output")
---

# Compare — the artifact surface: `--export`, and where a clock is allowed to live

**Proposed verdict up front: an artifact-only metadata block, an additive `--export`
on every report and insight, all available formats per run, into
`<ledger>/.cage/output/<view>-<stamp>/`.** §Verdict has the precise rule.

## The fork

Two asks collided with two of cage's hard laws.

- *"date and time optional in CLI, mandatory in exports"* → **determinism**: no clocks
  in derived views; same ledger + same policy ⇒ same tables, pinned byte-for-byte by
  `tests/test_output_spec.py` and `tests/test_floor.py`.
- *"exportable by default, into `.cage/output`"* → the **CSV column contract**
  (`csvout.py`) that every BI consumer already reads, and the read/write split that
  keeps a read command from mutating disk.

Three questions had genuinely different answers, and each could have been settled the
wrong way cheaply.

## Q1 — where does the stamp live?

| option | for | against |
|---|---|---|
| **A · artifact-only block** | stdout stays clock-free; goldens keep meaning; one block, three renderings | a `--csv PATH` file has no stamp unless routed through `--export` |
| B · `generated_at` column on every CSV row | survives parsers that choke on preamble lines | widens every view's column contract; repeats one value down the file |
| C · filename + sidecar `.meta.json` | zero existing bytes touched | the stamp is not *in* the data file — the one place it needs to be |

**A.** The decisive argument is not convenience: it is that the determinism law is
about *derived numbers*, not about the absence of any clock anywhere. A stamp that can
never enter a cell, and never reaches the default surface, leaves the law exactly as
strong as it was — and the goldens keep testing something real. B and C both trade
that clarity for a lesser problem.

## Q2 — does a plain `cage report` now write a file?

Auto-export was declined. A read command that mutates disk on every invocation grows
`.cage/output/` without bound, and cage deletes nothing it wrote (`cleanup.py` is a
closed allowlist and this directory is not on it — deliberately, §Deliberately not
taken). "Exportable by default" is therefore read as *every report and insight
supports export, uniformly, with a default destination* — a capability, not a side
effect.

## Q3 — what does bare `--export` produce?

All available formats, into one per-run folder. The alternative — "the format follows
the flag you already passed" — is a smaller rule but makes the common case (`--export`,
no other flag) silently text-only, and a user who wanted the CSV finds out a day later.
Formats are **what the view actually has**, never a promised set: a view with no
`render_csv` exports text + JSON, and asking it for CSV is a typed refusal rather than
an empty file.

## Verdict

1. **`runstamp.py` owns the only clock call on a read surface.** One block, rendered as
   `# cage: k=v` for text and CSV and as a `cage` object for JSON — never re-worded per
   format. `CAGE_RUN_STAMP` pins it.
2. **Mandatory in an artifact, optional on a terminal.** Every `--export` file carries
   the block, with no flag to suppress it; stdout carries it only under `--stamp`.
   `tests/test_view_export.py::test_export_never_changes_stdout` is the binding gate.
3. **`--csv` / `--json` keep their existing byte contract**, on stdout *and* to a path.
   A `--csv PATH` is a stream redirected to a file; `--export` is an artifact. Only the
   artifact grows the block.
4. **Destination:** bare → `<ledger>/.cage/output/<view>-<stamp>/`; a path with a known
   suffix → that exact file, that format; any other path → a per-run folder under it.
   A directory destination *always* gets the per-run folder — two runs of one view must
   never clobber each other.
5. **Scope:** `cage report` + every `insights` leaf (17 views), gated by
   `test_every_report_and_insight_is_exportable`.

## Deliberately not taken

- **Bare `cage` (the overview) has no `--export`.** Not an oversight and not a
  half-build: a root-level optional-value flag would swallow the following subcommand
  (`cage --export report` exports to a file named `report`). The headline is a terminal
  surface; `cage report --export` is the artifact of the same ledger. *Revisit if* the
  overview ever becomes an addressable subcommand.
- **No cleanup class for `.cage/output/`.** An artifact cage deletes is an as-of record
  the user cannot get back, and the same reasoning that keeps `ledger/savings/` off the
  allowlist applies. *Revisit only with a named volume number* from a real machine —
  carried in `docs/OPEN-WORK.md`, not as a `# v2:` stub in the code.
- **`--html` stays matrix's own flag.** It renders a standalone dashboard page, a
  different artifact for a different purpose; folding it in would make one flag mean
  two things. *Revisit if* a second view ever grows an HTML renderer.

## Reopen trigger

This verdict is contingent on the split in (2)/(3) holding in practice. Reopen if
either fires:

- **A user's `--csv PATH` file is found in the wild being read as an as-of record** —
  i.e. the stream/artifact distinction is not one people actually make. Then the
  preamble moves onto `--csv` writes to a path, and the column contract takes the
  version bump that deserves.
- **`.cage/output/` on a real machine passes a named size** the user reports as a
  problem. Then the cleanup question in §Deliberately not taken is live, and it is
  answered with that number, not from first principles.

Not contingent, and changed only by reversing this doc: **the default surface has no
clock in it.** That is a determinism value, not a volume-gated trade.
