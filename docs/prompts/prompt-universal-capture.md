# Claude Code prompt: universal capture — explicit `import`/`export` over a global ledger

You are implementing universal token capture for cage so it works for **any agent, any
client (CLI or VS Code extension), and the no-project user** — led by explicit `cage import`
and `cage export`, not hooks, and **installing no background/OS job**. The full spec is in
`docs/prompts/handoff-universal-capture.md` — read it first and treat its **Definition of
Done** and **Non-negotiables** as binding.

## Context to load first
- Read: `cage/importcmd.py`, `cage/clicmds.py`, `cage/cli.py`, `cage/report.py`,
  `cage/doctorcmd.py`, `cage/paths.py`, `cage/policy.py`, `cage/schema.py`,
  `cage/transcript.py`, `cage/agents.py`, `CLAUDE.md`, `docs/cage-plan.md` (§3, §5, §10),
  `docs/debugging-capture.md`.
- Follow existing patterns: `importcmd.run` + `hooks.append_new` (idempotent by id),
  `paths.cage_bin()`, the `--scope` slice, `report.py`'s aggregation, `ledger.read`/
  `since_cutoff`, the v0.11.0 `debuglog` heartbeat. Drive every agent list from
  `agents.SURFACES`. Stdlib `csv`/`json` only.

## Task
1. **`cage import`** — bless the existing umbrella import as the canonical explicit capture
   verb (`--agent all` default; idempotent; per-agent count line; works with no hooks and no
   project `.cage/`). **Incremental: keep a per-file `(size,mtime)` cursor in `.cage/state/`
   and skip unchanged files; build the id-dedupe set once per run, not per `append_new`
   call.** `append_new` id-dedupe stays the correctness backstop. (Byte-offset partial-file
   parsing is a non-goal — too invasive to the parsers; revisit only if one growing file
   dominates.) The **global ledger is month-partitioned** (§3.6.1 shards), never one
   unbounded file.
2. **`cage export`** — import first (unless `--no-import`), print `↻ imported N new
   call(s)`, then emit the ledger: `--format jsonl|csv|json` (jsonl=raw rows, csv=flat,
   json=summary reusing `report.py` aggregation), `--since`/`--project`/`--agent` filters,
   `-o FILE` or stdout.
3. **Global ledger + resolution precedence** (`--ledger`/`CAGE_LEDGER` → nearest project
   `.cage/` from cwd → global `~/.cage`); add a `--ledger` flag to the import/export/report
   family; all read/emit surfaces honor it. Global = **plain `~/.cage` every platform, no XDG
   special-casing** (`CAGE_LEDGER` is the only relocation knob). `cage setup --global`
   initializes it.
4. **Project as a derived view via a NEW `project` field** — add an additive optional
   `project` field to the substrate (empty = legacy; **basename only, never a full path** —
   same PII guard as `scope`). Do NOT overload `scope` (§3.6.2 monorepo axis — leave it
   untouched). Populate `project` where the log exposes cwd: Claude = project dir basename
   now; Codex/Copilot = cwd basename only if their log carries it (verify `session_meta`/
   `turn_context` + Copilot session events — leave empty until confirmed); Kiro = always
   empty. Source the value from `basename(rec['cwd'])` (the confirmed transcript cwd field),
   NOT the lossy slug. `cage report --project <name>`/cwd-basename filters the global ledger.
5. **`cage watch`** — optional stdlib **foreground** poll loop (import-all; sleep), Ctrl-C
   clean. It must register nothing and stop with the terminal.
6. **NO OS job.** Do not write/register any launchd/systemd/cron/schtasks unit and do not add
   a `cage scheduler` command. cage installs nothing persistent. `cage doctor` may *mention*
   that a user can add their own cron calling `cage import`, but cage never creates it.
7. **Honest `cage doctor`** — infer each agent's capture state from the **debug heartbeat**
   (fired recently ⇒ real-time active; never ⇒ warn it likely won't, e.g. under a VS Code
   extension) — do NOT try to detect client type, cage can't. Stop labeling unfireable hooks
   "wired"; point at `cage import`/`cage export` as the universal path; show **"last import:
   N ago"**. No scheduler row.
8. **Build in phases (don't ship one mega-PR):** Phase 1 = global ledger + resolution +
   month partitions + `cage import` with the incremental cursor + the `project` field + honest
   doctor/staleness nudge (this alone fixes the Copilot-only user); Phase 2 = `cage export` +
   `cage watch`; Codex/Copilot `project` enrichment is a separate follow-up.
9. **Drop the cwd-`.cage` guard** — keep hook command strings byte-for-byte unchanged. The
   guard is obsolete: `resolve_root` sends a no-project cwd to global `~/.cage` (no stray local
   `.cage`, no scatter), so a hook firing anywhere captures into global (counts-only,
   `project`-tagged) — restoring passive capture for hook-firing clients. Explicit
   import/export resolve the same way. Wrap `policy.load` on the capture path so a malformed
   policy fails open instead of tracebacking.

## Required workflow
1. **Explore** the listed files before writing anything.
2. **Plan** — the export serializer + format set, the `project` field + ledger-resolution
   change, the `cage watch` loop, the doctor changes, and the test list; **pause for my
   confirmation before implementing.**
3. **Implement incrementally**, keeping `just test` green.
4. **Update docs to match** (handoff §9.5): README "Works with any agent", CHANGELOG +
   README "What's new", `docs/debugging-capture.md`, new-command docstrings, an ADR for
   "capture is global + explicit import/export; project is a derived view via a dedicated
   `project` field; cage installs no OS scheduler." For **CLAUDE.md**, PROPOSE the edits and
   flag for my review — do not silently rewrite it.
5. **Verify**: `just test`, `just demo` (§4.4). Fix what you break; don't report done until
   green and docs match.

## Constraints (hard)
- Use: stdlib only (`dependencies = []`); stdlib `csv`/`json`. Do NOT use: any non-stdlib
  dep, filesystem-watch libs, or network on the capture/read path.
- **No background/OS job**: no launchd/systemd/cron/schtasks unit, no `cage scheduler`
  command. The heaviest thing cage runs is a foreground loop the user starts/stops.
- All four agents first-class (`agents.SURFACES`); never assume Claude.
- Additive: do not remove/alter hooks, MCP, or the project-local `.cage/` ledger.
- Counts-never-content (no prompt bodies in any export); `project`/`scope` basename-only;
  deterministic byte-identical export for the same `--since` window; fail-open + idempotent.
- Substrate contract: only add the one additive optional `project` field (empty = legacy);
  update plan §3 + `schema.py`. Do not otherwise modify `make_call`/the enums, the
  attribution/matrix math, or the §4.4 demo numbers.

## Acceptance criteria (self-check before finishing)
- [ ] No hooks, no daemon, Copilot only → `cage import` then `cage export --format csv`
  produces Copilot rows; `cage report` shows the spend.
- [ ] No-project user captures into the global ledger; resolution precedence unit-tested.
- [ ] `cage export` emits valid jsonl/csv/json; json summary totals match `report`;
  `--no-import` leaves the ledger unchanged while default export imports first (count
  printed); `--since`/`--project`/`--agent` filters applied.
- [ ] `project` field stamped on Claude rows (basename), absent for Copilot/Kiro; `scope`
  untouched.
- [ ] Hook-triggered import in a dir with no project `.cage/` resolves to the global ledger
  (no stray local `.cage` created); `cage watch` Ctrl-C clean and registers nothing; **no
  launchd/systemd/schtasks/`cage scheduler` exists anywhere.**
- [ ] `cage report --project` filters the global ledger; doctor shows method matrix +
  VS-Code warning, no scheduler row.
- [ ] Tests added/updated and passing (`just test` green; no plan-number assertion changes).
- [ ] Docs updated (README/CHANGELOG/debugging-capture/docstrings/ADR); CLAUDE.md edits
  proposed for review.

## Tests
Cover: import with no project `.cage`; ledger-resolution precedence; `project` stamped for
Claude / absent for Copilot+Kiro; export jsonl/csv/json validity + summary-matches-report +
`--no-import` vs default-import + filters; hook in a no-project dir → global ledger (no stray
`.cage`); `cage watch` single-cycle +
clean exit; `--project` filtering; doctor method matrix + warning + no-scheduler;
malformed-policy fail-open on capture.

## Guardrails
- Ask before: deleting data, changing the substrate contract beyond the one additive
  `project` field, changing any public command's output shape, or any irreversible action.
- If a requirement is ambiguous or conflicts with the code, STOP and ask rather than guessing.
- Do NOT introduce any OS-level scheduling even if it seems convenient — it's explicitly out
  of scope.
