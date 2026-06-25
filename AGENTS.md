# AGENTS.md — instructions for any agent working on Cage

Cage is itself a multi-agent tool, so its own repo is agent-agnostic. Whichever
agent you are (Claude Code, Codex, Copilot, Kiro, …), the full context lives in
[CLAUDE.md](CLAUDE.md) — read it first. The architecture, substrate contract, and
must-know rules there apply to every agent equally.

## Invariants every agent must remember

- **Four agents, always.** Cage supports **Claude Code · Codex · Copilot · Kiro**
  (`agents.SURFACES = ("claude", "codex", "copilot", "kiro")`). Never drop or
  silently break one. Every wiring/read surface — `agents.py`, `mcpserver.py`,
  `cage setup`, and the skill/steering data files — must keep all four
  first-class, and any new surface work fans out to all four. This is a product
  invariant, not a default you can trim.
- **Every release updates the README "What's new."** On each version: bump
  `cage/__init__.py` `__version__`, add a `What's new` entry for that version in
  `README.md` (never skip a version), and refresh the "N tests passing" count in
  the README `$0` section and `CLAUDE.md`'s `just test` comment. A shipped version
  with no changelog line is a release bug.
- **$0 / stdlib-only, deterministic, fail-open on the write path.** See
  [CLAUDE.md](CLAUDE.md) "Must-Know Rules" for the rest.

## Dev

```bash
just test          # python -m pytest -q
just demo          # seed §4.4 + print attrib/matrix
cage --version
```
