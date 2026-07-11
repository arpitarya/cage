# Claude Code prompt: portable wiring — no absolute paths in committed files

You are fixing a sharing bug in `cage setup`: wired hook/MCP entries embed the
resolving machine's **absolute cage path**, and several wired files are
committed to git (`.mcp.json`, `.vscode/mcp.json`, `.kiro/hooks/*.hook`,
project hook configs) — so one developer's path ships to the whole team and
every clone gets broken wiring. Replace setup-time path resolution with a
**committed runtime-resolving shim**. Run AFTER the current tree is
reviewed/committed (ask if dirty). **No commits, tags, pushes, publishes.**

## Context to load first

- `CLAUDE.md`; all four wire modules — `claudewire.py`, `codexwire.py`,
  `copilotwire.py` (its docstring records WHY bare `cage` fails under the
  extension PATH — that constraint stays true), `kirowire.py`; `agents.py`
  (`_WIRE` dispatch); `setupcmd.py`; `gitcommithook.py`; `doctorcmd.py`;
  `paths.py`. Note which wired files are project-committed vs user-level —
  that split drives everything.

## The design (decided)

1. **The shim.** `cage setup` writes `.cage/bin/cage-run` (POSIX sh, minimal)
   — identical bytes on every machine, intended to be committed. At runtime it
   resolves cage in documented order: `command -v cage` → well-known installs
   (`~/.local/bin/cage`, pipx, an active `$VIRTUAL_ENV/bin/cage`) →
   `python3 -m cage` if importable → **exit 0 silently**. A clone without cage
   installed = working agents, no noise, no capture (fail-open extended to
   wiring). All args pass through (`cage-run import` ⇒ `cage import`).
   Windows twin `cage-run.cmd` mirrors the order (`where cage`, `Scripts\`,
   `py -m cage`) — coordinate with the windows-parity work if it has landed;
   if not, ship the .cmd anyway with an UNVERIFIED note.
2. **Committed wiring references the shim, never a binary path.**
   - `.vscode/mcp.json`: `${workspaceFolder}/.cage/bin/cage-run` (native VS
     Code substitution).
   - Claude project hooks + `.mcp.json`: relative `.cage/bin/cage-run` where
     the host guarantees repo-cwd; use the host's own variable (e.g.
     `$CLAUDE_PROJECT_DIR`-style) where one exists — verify per host, document
     per wire module which mechanism it relies on and why.
   - Kiro `.kiro/hooks/*.hook` and codex project config: same treatment,
     verified against how each host launches hook commands (cwd or variable).
     If a host provably launches with an unknowable cwd and no variable,
     document that ONE exception and keep it absolute + gitignore-advised —
     don't silently ship a broken relative path.
3. **User-level configs stay absolute** — `~/.copilot/hooks/cage.json`,
   `~/.codex/config.toml` MCP, `.git/hooks/*` (not cloned): per-machine by
   nature, absolute is the robust choice there. Unchanged behavior.
4. **Migration:** `cage setup` re-run detects legacy absolute entries in
   committed files and rewrites them to the shim (idempotent, prints what it
   migrated). Never touches entries the user hand-customized beyond the
   legacy pattern — list those and ask via the printed output.
5. **Doctor portability check:** flag any committed wired file containing a
   machine-specific absolute path (warn: teammates' clones will have broken
   wiring — re-run `cage setup`), flag a missing/execute-bit-less shim, and
   verify shim resolution succeeds on THIS machine (run `cage-run --version`).
6. **`cage query`:** concept entry `portable-wiring` — why the shim exists,
   the resolution order, the fail-open-when-absent behavior, which files are
   committed vs user-level, the one-exception host if any.

## Task

1. Explore the four wire modules; build the shim writer (one shared helper —
   don't quadruplicate it); switch each committed-file writer to shim
   references with the per-host cwd/variable mechanism verified and
   documented in that module's docstring.
2. Migration + idempotency in `setupcmd.py`/`agents.install` (setup twice ⇒
   byte-identical remains true).
3. Doctor checks (§5). Execute bit set on the shim at write time; handle
   `core.fileMode=false` repos gracefully.
4. Tests: shim resolution order (fake PATH layouts incl. cage-absent → exit
   0); each wire module's committed output contains no absolute path
   (regression test that greps the written files — this is the invariant that
   must never rot); migration rewrites legacy entries exactly once; setup
   idempotent; doctor flags a planted absolute path. Dummyrepo: extend the
   wiring scenario to clone-simulate (copy the testbed sans `.git` to a new
   path, run doctor there → portability clean, shim resolves).
5. Docs: **`docs/portable-wiring.md` is the design of record — read it first,
   implement to match, and update it wherever implementation reality diverges
   (e.g. the per-host cwd/variable mechanisms, any documented exception).**
   The README already links to it from the wiring section — verify the claim
   there matches shipped behavior; extend the setup section if needed.
   CHANGELOG in-tree, plan-doc note, CLAUDE.md edit proposed-not-applied,
   skillgen fragments if CLI text changed (regen + `--bless`).

## Constraints (hard)

- $0/stdlib; shim is plain `sh`/`cmd` — no bash-isms, no python launcher file.
- Fail-open is the shim's contract: cage absent ⇒ exit 0, never an error
  surfaced into an agent's hook run; resolution failure is silent by design
  (doctor is the place that diagnoses, not the hook path).
- Four agents; setup stays idempotent; user-level configs unchanged.
- Don't break existing installs: legacy absolute entries keep working until
  the user re-runs setup — the shim path is additive, migration opt-in by
  running setup.
- The `.cage/bin/` shim must not be swept by the cleanup allowlist (if that
  work has landed) — assert it.
- No commits; working tree only.

## Acceptance criteria (self-check)

- [ ] No committed wired file contains an absolute path (grep-tested per wire
      module); user-level files unchanged.
- [ ] Shim resolves per documented order on this machine; absent-cage clone
      simulation exits 0 silently; args pass through.
- [ ] Setup twice ⇒ byte-identical; migration from legacy absolute entries
      works and is printed.
- [ ] Doctor portability check catches a planted absolute path and a missing
      shim; passes clean after setup.
- [ ] Per-host cwd/variable mechanism documented in each wire module; any
      unavoidable exception explicitly documented, not silent.
- [ ] `cage query portable-wiring` answers; `just test` green; dummyrepo
      wiring scenario incl. clone-simulation green; skillgen clean; zero
      commits.
