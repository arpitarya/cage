---
doc: prompt — surface-cut: delete `cage data *`, `cage report *`, and insights compare/estimate/calibration
status: PROPOSED — unbuilt
pair: [surface-cut.handoff.md](surface-cut.handoff.md)
---

# Claude Code prompt: SURFACE-CUT — remove the data group, report, and three insights views

**Model:** Opus — eleven modules deleted with live entanglements (`report.py` is imported by
four surviving modules; the MCP tool list and its dispatch must move together). CLAUDE.md's
rubric puts deletions-with-entanglements on Opus. Do not run this on Sonnet.

**Progress:** 0% — P0 not started.

You are deleting three command families from cage: `cage data` (**all six** subcommands),
`cage report`, and `cage insights compare|estimate|calibration` — commands, modules, tests
and goldens. The full spec is `work/surface-cut.handoff.md` — read it first; its
**Definition of done**, **Scope (out)** and **Non-negotiables** are binding. Where this
prompt and the handoff disagree, the handoff wins.

The handoff's **§4.5 change map** names every module, line anchor, dependent, test and
golden — measured against HEAD on 2026-08-14. Follow it. Re-verify a mapped fact only if
the code in front of you disagrees; then STOP and report.

## Before anything: P0 STOP check

1. **Concurrency.** If another session is working in this repo, STOP.
2. **Is the tree mid-build?** Run the full suite and report the result before touching
   anything. Observed 2026-08-14: the golden set still holds fixtures for commands
   USAGE-ONLY removed (`P1–P6b` for `cage prices`, `O2` for `cage --usd`, `I7/I8a/I8b` for
   `matrix`, `I2/I3/I4` for `verdict`, `R2/R3/R4` for `--usd`). Either USAGE-ONLY's golden
   pass is unfinished or the set is stale. **Do not stack this deletion on a red or
   half-finished tree** — report and wait.
3. **Sandbox.** Manual CLI verification must set the sandbox env vars the pytest suite sets
   (`work/IMPLEMENTATION.md`, 2026-08-14 incident).

## Context to load first

1. `CLAUDE.md`, then `work/OPEN-WORK.md`.
2. `work/surface-cut.handoff.md` — the spec.
3. The USAGE-ONLY pair in `work/archive/` + ADR 0011 — what just shipped.
4. `cage/cli.py` (**l. 544** the `data` group; **l. 157–175** report) · `cage/clicmds.py` ·
   `cage/report.py` · `cage/mcpserver.py`.
5. Contracts that pass untouched: `tests/test_floor.py` · `tests/test_usage_only.py` ·
   `tests/test_view_export.py` · `tests/test_queue_honesty.py`.

## Build order — suite green after EVERY step

- **P1 — leaf modules.** `otelout.py` → `exportcmd.py` → `cleanup.py` ·
  `migratecmd.py` · `watchcmd.py` · `serve.py` · `proxy.py` → `compare.py` ·
  `estimate.py` · `calibration.py`.
  **Verify `cage/csvout.py` first** — `exportcmd.py:27` imports it; if `viewexport.py` also
  uses it, it **stays**.
- **P2 — the three rescues, BEFORE `report.py` is deleted.** Move verbatim, do not improve:
  `report._is_legacy_human` → `chats.py` (used at **l. 220**) ·
  `report.kiro_routed_line` → `chats.py` (**l. 436–437**) ·
  `report.capture_warnings` → `doctorcmd.py` (**l. 94**).
  **Contract:** `cage insights chats` and `cage doctor` stdout **byte-identical** to before.
  Prove it before continuing.
- **P3 — delete `report.py`.** Only now.
- **P4 — MCP.** Remove `cage_report` (**l. 46**, dispatch **l. 124–127**) and `cage_compare`
  (**l. 65**, dispatch **l. 139**). Tool list and dispatch move **together** — a listed-but-
  undispatched tool is a silent protocol break. Result: four tools (`cage_attrib`,
  `cage_adoption`, `cage_why`, `cage_task_outcome`); update `test_mcp_layer.py`.
- **P5 — CLI + handlers**, per handoff §4.5-B (every line anchor is listed, including the
  `insights` help text at **l. 35** and **l. 276** that names the removed views).
- **P6 — tests + goldens**, per §4.5-D/E. Delete goldens `R1–R7`, `I5`, `I6a`, `I6b`, `O1`,
  `O2`. **`S3`/`S4` are `cage study report` — a different command. KEEP them.**
- **P7 — docs**, per §9.5. The ADR is required.

## Required workflow

1. **Explore** before writing. If the code disagrees with the change map, STOP and report.
2. **Plan** each phase with the files you'll change. **Pause for confirmation before P3**
   (deleting `report.py`) and **before P5** (removing user-facing commands).
3. **Implement incrementally.** Full suite after every step, not every phase.
4. **Update docs to match** (§9.5). `CLAUDE.md`: **propose the diff, do not apply it.**
5. **Verify:** suite green; only the twelve named goldens removed; no surviving golden moves.

## Constraints (hard)

- **Do NOT delete `cage study`** — including `cage study report` and `study.export_bundle`
  (self-contained, does not use `exportcmd`).
- **Do NOT delete `viewexport.py` or the `--export` flag** on surviving views. Different
  mechanism from `cage data export`; it is the only remaining path from a view to disk.
- **Do NOT touch** `cage import` or any capture path it drives.
- **Do not modify:** `tests/test_floor.py`, `tests/test_usage_only.py`, surviving goldens.
- stdlib only; append-only ledger law; fail-open capture; counts-never-content.

## Acceptance criteria (self-check before finishing)

- [ ] P0 suite result reported before any deletion
- [ ] All six `data` subcommands gone; `report` gone; the three insights views gone
- [ ] Eleven modules deleted; `csvout.py` decision made on evidence
- [ ] `chats` + `doctor` stdout byte-identical across the rescue (proven, not assumed)
- [ ] MCP exposes exactly four tools; list and dispatch agree
- [ ] `--export` still works on surviving views
- [ ] Exactly twelve goldens removed; `S3`/`S4` intact; no surviving golden moved
- [ ] `test_cli_reference` green — no removed command in help or `docs/CLI.md`
- [ ] ADR written; kiro research §4 amended (proxy capture is now impossible, not ranked);
      `CLAUDE.md` diff proposed not applied
- [ ] `work/OPEN-WORK.md`: three `*-METRICS-CSV` rows **deleted** (unbuildable, not parked);
      TASK-GRAIN-SPINE **re-scoped** not closed; the retention gap filed

## Guardrails

- Ask before: deleting anything outside §4.5-A, changing a surviving command's output, or
  touching `cage.toml`.
- If a handoff fact turns out stale, or a requirement conflicts with the code, **STOP and
  report** — that is diagnosis, not execution.
- Handoff §10 carries **three unanswered questions** (TASK-GRAIN-SPINE's re-scope wording;
  whether cage ships continuous-capture guidance now that `watch`/`proxy` are gone;
  `csvout.py`'s fate). Do not invent answers to the first two — the third is verifiable in
  P1 and you should settle it there.
