---
doc: handoff — surface-cut: delete `cage data *`, `cage report *`, and insights compare/estimate/calibration
status: PROPOSED — unbuilt
raised: 2026-08-14 (Arpit, after USAGE-ONLY / ADR 0011)
pair: [surface-cut.prompt.md](surface-cut.prompt.md)
---

# Handoff: SURFACE-CUT — remove the data group, the report command, and three insights views

**One-liner:** delete `cage data` (all six subcommands), `cage report`, and
`cage insights compare|estimate|calibration` — commands, modules, tests and goldens.

**Owner / executor:** Claude Code · **Model:** Opus (deletion with live entanglements)

**Status:** Ready to build. **P0 is a STOP check** (§2) — the repo may be mid-flight.

**Stress-tested:** the gate challenged the scope on three counts and Arpit chose maximal on
both open ones. (1) `cage data` is **six** subcommands, three of them capture/maintenance
rather than reporting — Arpit confirmed **all six**, so `watch`, `proxy`, `cleanup` and
`migrate-savings` go too. (2) `report.py` is a **library**, not a leaf — four modules import
from it; Arpit chose **delete it and its dependents**, so `mcpserver` and `serve` lose their
report surfaces and `chats`/`doctorcmd` reimplement inline. (3) `cage study report`
(goldens S3/S4) is a *different command* and **survives**. **Residual risks:** capture
becomes `cage import`-only; ledger retention loses its only pruning path; the kiro proxy —
ranked #1 in the kiro research doc as *"the ONLY path to all five values"* — is closed
permanently, not parked (§8).

---

## 1. Context & background

- USAGE-ONLY (ADR 0011) shipped: money is gone, fifteen modules deleted, zero `--usd` in
  `cli.py`, `tests/test_usage_only.py` is the regression pin.
- What remains of cage's output surface is disproportionate to a usage meter: a 894-line
  `report.py`, a six-command `data` group, a dashboard, a proxy, and three task-grain
  insights views that **return zero** for claude and copilot (TASK-GRAIN-SPINE).
- TASK-GRAIN-SPINE is the proximate trigger: metric rows carry no `task`, so
  `compare`/`estimate`/`calibration` see nothing for the agents whose spend now resolves
  from the metric ledger, and `report --by route` collapses to `chat`. Deleting those four
  surfaces removes every symptom — see §8 for what the defect leaves behind.

## 2. Definition of done

**P0 STOP check — before any deletion:**

- [ ] Confirm the working tree is not mid-build. **Observed 2026-08-14:** the golden set
      still contains fixtures for commands USAGE-ONLY removed — `P1–P6b` (`cage prices`),
      `O2` (`cage --usd`), `I7/I8a/I8b` (`matrix`), `I2/I3/I4` (`verdict`), `R2/R3/R4`
      (`--usd`). Either USAGE-ONLY's golden pass is unfinished or the set is stale. **Run
      the full suite first and report the result.** Do not stack this deletion on a red or
      half-finished tree.

Then:

- [ ] `cage data` and all six subcommands are gone from `cli.py`; no `cmd_export`,
      `cmd_cleanup`, `cmd_migrate_savings`, `cmd_watch`, `cmd_serve`, `cmd_proxy`.
- [ ] `cage report` is gone; `report.py` deleted; the four dependents (§4.5-C) work without it.
- [ ] `cage insights compare|estimate|calibration` gone; their modules deleted.
- [ ] `cage --help` and `docs/CLI.md` list no removed command; `test_cli_reference` green.
- [ ] MCP server exposes **four** tools (`cage_attrib`, `cage_adoption`, `cage_why`,
      `cage_task_outcome`) — `cage_report` and `cage_compare` removed from both the tool
      list and the dispatch.
- [ ] `--export` on surviving insights views **still works** (`viewexport.py` is NOT
      deleted — it is a different artifact path from `cage data export`).
- [ ] Goldens R1–R7, I5, I6a, I6b, O1, O2 deleted; no other golden moves.
- [ ] Full suite green after every phase.
- [ ] `work/OPEN-WORK.md` reconciled (§9.5): the three `*-METRICS-CSV` items are no longer
      parked — they are **unbuildable** and must be deleted, not carried.

## 3. Scope

**In scope:** the three command families, their modules, their tests, their goldens, their
MCP tools, and the dependents that break.

**Out of scope (explicit) — do NOT touch:**

- **`cage study`** — including `cage study report` (goldens S3/S4) and
  `study.export_bundle`, which is self-contained and does not use `exportcmd`.
- **`viewexport.py` / the `--export` flag** on surviving views. Different mechanism,
  different purpose; `cli._export_flags` stays for every view except the deleted ones.
- **`cage import`** and every capture path it drives.
- **`cage insights chats | graphify | commits | commit | adoption | attrib | why`**,
  `cage doctor`, `cage query`, `cage setup`, `cage task`, `cage authorship`, `cage policy`.
- Do not add a dependency; do not touch `tests/test_floor.py` or `tests/test_usage_only.py`.

## 4. Current state

| fact | value |
|---|---|
| `cage data` subcommands | `export` · `cleanup` · `migrate-savings` · `watch` · `serve` · `proxy` (group at `cli.py:544`) |
| `report.py` | 894 lines, imported by `chats.py`, `doctorcmd.py`, `mcpserver.py`, `serve.py` |
| MCP tools today | 6 (`cage_report`, `cage_attrib`, `cage_adoption`, `cage_why`, `cage_compare`, `cage_task_outcome`) |
| goldens | 43 total; 12 die here; several already stale from USAGE-ONLY (P0 check) |
| suite | run it in P0 — the tree state is unconfirmed |

**Read first:** `CLAUDE.md` · `work/OPEN-WORK.md` · `work/archive/` USAGE-ONLY pair (ADR
0011) · `cage/cli.py` (l. 544 the `data` group; l. 157–175 `report`) · `cage/clicmds.py`.

## 4.5 Change map

### A — Delete outright

| module | why |
|---|---|
| `cage/report.py` | `cage report` (894 lines) — rescue nothing, see C |
| `cage/exportcmd.py` | `cage data export` |
| `cage/otelout.py` | only consumer is `exportcmd.py:27,188` |
| `cage/cleanup.py` | `cage data cleanup` (`clicmds.py:374`) |
| `cage/migratecmd.py` | `cage data migrate-savings` (`clicmds.py:385`) |
| `cage/watchcmd.py` | `cage data watch` (`clicmds.py:837`) |
| `cage/serve.py` | `cage data serve` (`clicmds.py:193`) |
| `cage/proxy.py` | `cage data proxy` (`clicmds.py:441`) |
| `cage/compare.py` | `cage insights compare` |
| `cage/estimate.py` | `cage insights estimate` |
| `cage/calibration.py` | `cage insights calibration` |

**Verify before deleting:** `cage/csvout.py` — imported by `exportcmd.py:27`. If
`viewexport.py` also uses it, it **stays**. Check, do not assume.

### B — CLI + handler surface

- `cage/cli.py`: the whole `data` group from **l. 544** and its six subparsers ·
  `report` **l. 157–175** (including `_export_flags(rep, "report")` at **l. 166**) ·
  `compare` **l. 409–420** · `estimate` **l. 422–434** · `calibration` **l. 384–391** ·
  the `insights` group help text at **l. 35** and **l. 276** which names them ·
  the comment at **l. 403**.
- `cage/clicmds.py`: `cmd_report` **l. 59** · `cmd_serve` **l. 192** · `cmd_compare`
  **l. 322** · `cmd_estimate` **l. 333** · `cmd_calibration` **l. 353** · `cmd_cleanup`
  **l. 372** · `cmd_migrate_savings` **l. 381** · `cmd_proxy` **l. 441** · `cmd_export`
  **l. 810** · `cmd_watch` **l. 837**.

### C — Dependents that break (the risky part)

| consumer | uses | fix |
|---|---|---|
| `cage/chats.py:220` | `report._is_legacy_human(c)` | reimplement inline in `chats.py` |
| `cage/chats.py:436-437` | `report.kiro_routed_line` | reimplement inline in `chats.py` |
| `cage/doctorcmd.py:94` | `report.capture_warnings(health)` | reimplement inline in `doctorcmd.py` |
| `cage/mcpserver.py:46,124-127` | `cage_report` tool → `report.summarize/render_report/render_csv` | delete the tool + its dispatch branch |
| `cage/mcpserver.py:65,139` | `cage_compare` tool → `compare` | delete the tool + its dispatch branch |
| `cage/serve.py:38-40` | `report.render_report(report.summarize(...))` ×3 | module deleted entirely |

`chats.py` and `doctorcmd.py` are **surviving commands** — their behaviour must not change.
Move the three functions verbatim; do not "improve" them in transit.

### D — Tests

**Delete:** `test_csv.py` · `test_export_sweep.py` · `test_otel_export.py` ·
`test_compare.py` · `test_estimate.py` · `test_report_credits.py` · `test_report_savings.py`.
**Strip / re-scope:** `test_views.py` · `test_mcp_layer.py` (tool count 6 → 4) ·
`test_output_spec.py` · `test_cli_reference.py` · `test_universal_capture.py` (imports
`exportcmd`) · `test_adoption.py`, `test_canonical_ledger.py`, `test_capture_health.py`,
`test_capture_log.py`, `test_capture_on_read.py`, `test_debuglog.py`,
`test_graphify_usage.py`, `test_kiro_routing.py`, `test_legacy_ledger.py`,
`test_path_globs.py` (all import `report`) · `test_view_export.py` (**keep** — it covers
`viewexport`, which survives).

### E — Goldens to delete

`R1 R2 R3 R4 R5 R6 R7` (`cage report`) · `I5` (compare) · `I6a I6b` (estimate) ·
`O1 O2` (the top-line summary / `cage --usd`). **`S3`/`S4` are `cage study report` — keep.**
No other golden may move; one that does is a bug in the dependent rescue, not a re-bless.

## 5. Technical approach (decided)

- **Delete leaf-first**, suite green between each: `otelout` → `exportcmd` → the five other
  data modules → `compare`/`estimate`/`calibration` → the three C-rescues → `report.py` →
  the CLI/handler surface → tests → goldens.
- **`report.py` goes last** among the modules, because C's three rescues must land and go
  green *before* the file disappears.
- **MCP dispatch and tool list are edited together** — a tool listed but undispatched (or
  vice versa) is a silent protocol break.

## 6. Non-negotiables

- **stdlib only**; **append-only** ledger law; fail-open capture; counts-never-content.
- **Do not modify** `tests/test_floor.py`, `tests/test_usage_only.py`, or any surviving golden.
- **`CLAUDE.md` edits are PROPOSED, never applied.**
- **No concurrent session** — and see P0: do not stack on a half-finished USAGE-ONLY.

## 7. Dependencies & prerequisites

A green suite at P0. No services, env vars, or secrets. Manual CLI checks must use the
pytest sandbox env vars (`work/IMPLEMENTATION.md`, 2026-08-14 incident).

## 8. Edge cases & risks

| risk | handling |
|---|---|
| **Capture becomes `cage import`-only** — `watch` (poll loop) and `proxy` (reverse-proxy) both go | Accepted by Arpit. Record it in the ADR and in `docs/*-capture.md`: continuous capture is now the user's own scheduler. |
| **The kiro proxy path closes permanently** — the kiro research doc ranks it #1: *"the ONLY path to all five values"* for cache tokens and per-request credits | Not a parked idea any more. Amend the research doc's §4 ranking so a future reader doesn't plan against a deleted surface. |
| **Retention loses its only pruning path** (`data cleanup`) | `.cage/state/` grows unbounded. Pairs with the existing OUTPUT-GROWTH observation; file as a new queue item, do not leave silent. |
| **All machine-readable export ends** — jsonl, csv, json, otel | Mitigated: `--export` on surviving insights views (`viewexport.py`) still writes artifacts to `.cage/output/`. Say so in the release note, or it reads as total loss. |
| The three `*-METRICS-CSV` queue items | Become **unbuildable**, not parked. Delete from OPEN-WORK with the reason. |
| Deleting `report.py` before C's rescues | Ordering rule in §5. `chats` and `doctor` must stay byte-identical. |
| Stale goldens from USAGE-ONLY | P0 STOP check. |

## 9. Testing & validation

- After C's rescues and **before** deleting `report.py`: `cage insights chats` and
  `cage doctor` stdout **byte-identical** to before. That is the rescue's contract.
- MCP: tool list length 4, dispatch covers exactly those four, unknown-tool path unchanged.
- `test_cli_reference` proves no removed command survives in help or `docs/CLI.md`.
- Regression pins: `test_floor` · `test_usage_only` · `test_queue_honesty` ·
  `test_debug_coverage` · `test_output_spec` · `test_view_export`.

## 9.5 Documentation impact

- [ ] **ADR (required, new)** — why cage has no report, no export and no serving surface;
      what replaced them (`insights` + `--export`). The decision a future agent would reverse.
- [ ] **`docs/CLI.md`** — eleven entries removed.
- [ ] **`docs/PLAN.md`** — §3.9 (CSV), §7 (CLI/views), the OTel section, §3.6.3 team view.
- [ ] **`README.md`** — `cage report` is almost certainly in the quickstart.
- [ ] **`work/research/2026-08-13-kiro-per-chat-usage-fetch-spec.md`** — §4 ranks proxy
      capture #1; it is now impossible. Amend, don't leave it as advice.
- [ ] **`docs/kiro-capture.md`**, **`docs/copilot-capture.md`**, **`docs/claude-capture.md`**
      — any mention of `watch`, `proxy`, or export.
- [ ] **`CHANGELOG.md`** — major removal · **`docs/GLOSSARY.md`** · **`work/DOC-REGISTRY.md`**
      · **`docs/README.md`** · **`cage/explain_data.py`** (l. 1001 cites `otelout.py`).
- [ ] **`CLAUDE.md`** — command surface. **PROPOSE, do not apply.**
- [ ] **`work/OPEN-WORK.md`** — delete the three `*-METRICS-CSV` rows (unbuildable);
      re-scope TASK-GRAIN-SPINE (§10); add the retention gap.

## 10. Open questions

- **OPEN QUESTION:** TASK-GRAIN-SPINE loses all four of its symptoms with these deletions,
  but the underlying fact — **metric rows carry no `task`** — survives and will bite the
  next thing that needs task grain. Recommend **re-scoping, not closing**: keep the row,
  restate it as a capture-schema gap, and keep the `tests/test_compare.py` `_MODEL` comment's
  intent somewhere that isn't being deleted.
- **OPEN QUESTION:** with `watch` and `proxy` gone, does cage ship any guidance for
  continuous capture (cron, launchd, a hook)? Otherwise "import regularly" is advice with
  no mechanism — and Claude Code's 30-day transcript sweep makes missed imports permanent.
- **OPEN QUESTION:** `cage/csvout.py` — delete with `exportcmd`, or does `viewexport` use it?
  Verify in P1.
