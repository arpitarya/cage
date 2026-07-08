# Claude Code prompt: Windows/mac parity + exportable path-probe diagnostics

You are making cage work first-class on **Windows and macOS**, and adding an
**exportable path-probe diagnostic** so a user on any OS can see exactly which
log paths cage looked at, which missed, and why — reviewable offline via the
existing bundle. Run this AFTER the current test-cycle tree is reviewed/committed
(ask me if the tree is still dirty). **Do not commit, tag, push, or publish.**

## Context to load first

- `CLAUDE.md`; `cage/paths.py` (all `*_home`/log-location helpers + env
  overrides); `cage/importcmd.py` + `cage/originrecord.py` (the `fcntl`
  try/except lock blocks); `cage/debuglog.py`; `cage/doctorcmd.py` +
  `cage/doctorbundle.py`; `cage/clicmds.py` (cron-line text);
  `cage/gitcommithook.py` and each `<agent>wire.py` (commands they write into
  hook files); `.github/workflows/python-package.yml`; `tools/dummyrepo/run.py`.

## Task

**Part 1 — Windows/mac parity (macOS is field-validated; Windows is the work):**

1. **CI matrix:** `python-package.yml` → `os: [ubuntu-latest, macos-latest,
   windows-latest]` × existing Python versions. Getting this green IS most of
   the deliverable — every red it surfaces is in-scope to fix.
2. **Per-OS paths** (`paths.py`): `vscode_user_dir()` gains
   `%APPDATA%/Code/User`; the Kiro globalStorage helper gains the Windows
   layout (`%APPDATA%/Kiro/User/globalStorage/...` — verify against Kiro docs,
   don't guess silently: if unverifiable, mark the candidate
   `UNVERIFIED-LAYOUT` in the docstring and probe report); env overrides keep
   winning everywhere. Audit every helper for hardcoded `~/Library` or
   `.config` without a Windows branch.
3. **File locking:** where `fcntl` is absent, use `msvcrt.locking` as the
   Windows analogue behind the same fail-open wrapper (one shared helper, e.g.
   in a small `cage/lockutil.py`, replacing both copied blocks). No lock
   available at all ⇒ today's behavior (proceed unlocked, debug-log it).
4. **Wiring portability:** commands written into hook files must work on
   Windows — resolved executable may be `cage.exe`/`Scripts\cage.exe`, paths
   with spaces need quoting, git hooks run under Git-for-Windows sh (keep
   `#!/bin/sh` wrappers POSIX-minimal or invoke `python -m cage` directly —
   choose whichever is provably portable and say why).
5. **Scheduler hint:** the printed automation line becomes OS-aware — cron
   example on POSIX, `schtasks /create ...` example on Windows. Still never
   installed, only printed.
6. **Interrupt + exit codes:** verify KeyboardInterrupt → exit 130 works on
   Windows (`cage watch` Ctrl-C included); document any unavoidable Windows
   deviation rather than faking it.
7. **Test portability:** chmod-based fail-open tests get a Windows-equivalent
   or a documented skip (`@skipif` with reason — a skip is a finding, not a
   free pass; keep a count); temp-file reopen patterns → `os.replace`-style
   portable idioms; no path-separator or `/tmp` assumptions in tests or
   `tools/dummyrepo` (the runner must pass on all three OSes in CI).
8. **Docs:** README gains a short platform note — macOS field-validated,
   Windows CI-tested (upgrade wording only after a real Windows manual run);
   add `docs/windows-manual-checklist.md` — the Part-C-style capture matrix
   distilled for a Windows fleet participant (per-agent Windows log paths,
   the per-cell checks, where to send the doctor bundle).

**Part 2 — path-probe diagnostic (extend debuglog + doctor, no new system):**

1. **Probe events in `debuglog`:** during import/capture, log per agent every
   candidate log location probed: path, exists?, files matched, rows parsed,
   rows appended vs deduped, cursor skip reason, and the resolved sink +
   precedence reason. Metadata only — counts-never-content holds.
2. **`cage doctor --paths`:** a read-only human-readable report, per agent ×
   this OS: each candidate location (env override noted if set), found/missing,
   parseable row count, cursor state, and one `why` line per miss ("dir absent",
   "no files match rollout-*.jsonl", "cursor: already imported", "parse: 0 rows
   — unknown format, see debug.log"). Ends with the active ledger sink and the
   precedence chain that chose it. This is a diagnostic, not a derived view —
   filesystem-dependent output is fine, but it must never write anything.
3. **Bundle it:** `doctor --bundle` includes the `--paths` report; keep the
   $HOME/username redaction rule (finding #12) applied to every member.
4. **Explain entry:** `cage query "why is nothing being captured"`-style
   concept entry pointing at `doctor --paths` + `CAGE_DEBUG=1` + the bundle as
   the export path.

## Required workflow

Explore → plan (files you'll change, pause for my confirmation) → implement
incrementally → docs per change (README platform note, CHANGELOG entry in-tree,
CLAUDE.md edits proposed not applied, skillgen fragments if the CLI surface
changed: `python -m tools.skillgen && python -m tools.skillgen --bless`) →
verify: `just test` locally, then push-less CI check is impossible — so run the
suite under any Windows access you have (none assumed); otherwise state plainly
that windows-latest CI on the eventual PR is the gate.

## Constraints (hard)

- $0/stdlib only (`msvcrt`/`fcntl` are stdlib — fine); determinism for derived
  views (the probe report is a diagnostic, exempt but read-only); fail-open
  write path; typed `CageError` read path; four agents; additive-only schema.
- Don't rename existing env overrides; don't change POSIX behavior that's
  field-validated — Windows branches are additive.
- Never mark Windows "verified" for a surface no one has manually run — the
  README wording and probe-report labels stay honest.
- No commits/pushes; working tree only.

## Acceptance criteria (self-check)

- [ ] CI workflow has the 3-OS matrix; every POSIX-only construct fixed or
      skip-documented with a count.
- [ ] Locking unified in one helper with fcntl/msvcrt/none branches, both call
      sites migrated, race test still green.
- [ ] All path helpers OS-aware with env overrides winning; unverifiable Kiro
      Windows layout explicitly labeled.
- [ ] `cage doctor --paths` answers "what didn't work and what's the correct
      path" for each agent in one screen; included in the bundle; redaction
      holds.
- [ ] Windows manual checklist doc exists; README platform note honest.
- [ ] `just test` green; skillgen `--check` clean; zero commits.
