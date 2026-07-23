# Claude Code prompt: remove Codex support from cage completely

**Model: Sonnet.** Decisions locked in `docs/codex-removal.handoff.md` (an Opus investigate
pass already resolved the one real judgment call — see §2). This is mechanical execution
against a verified surface map, not diagnosis.

Read `docs/codex-removal.handoff.md` first — it is the design source for this change.

## Steps

1. **Core removal** — `agents.py` (`SURFACES`, `_WIRE`, docstrings), delete `codexwire.py`,
   strip codex from `importcmd.py`/`transcript.py`/`paths.py` (keep `codex_home()`),
   `setupcmd.py`'s shared skill-dir loop, `pathprobe.py`, verify + delete
   `clicmds.py`'s dead `cmd_import_codex`.
2. **Remove `cage data limits`** — `limits.py`, its CLI wiring, `credits.py` if
   limits-only, `Footprint.limits`, `test_limits.py`.
3. **Regenerate assets** — `tools/skillgen` (drop `[platform.codex]`) → `--bless`;
   `tools/docgen --target policy` (+ `spec` if a golden moved) → `--check` green.
4. **Fix tests + fixtures** — the ~18 files in the handoff's surface map; dummyrepo
   `AGENTS` tuple + rewrite S11/S15 seeders to `agent="copilot"`; delete
   `tests/fixtures/transcripts/codex/`.
5. **Docs + ship** — CLAUDE.md (the invariant + ~10 dependent lines), `docs/agents.md`,
   `docs/sources.md`, `README.md`, `docs/cage-plan.md` removal note, CHANGELOG + README
   "What's new" + version bump + test-count refresh, archive this pair to
   `docs/archive/vX.Y-codex-removal.{handoff,prompt}.md` linked from the CHANGELOG entry.

## Gate before calling it done

```
just test · python -m tools.dummyrepo · python -m tools.docgen --check ·
python -m tools.skillgen --check · just demo
```

## Out of scope (deferred, per handoff §2)

- The wiringscan orphan-ownership scanner (a new check class — its own design pass).
- Dropping the 7 `-codex`-named openai price rows (harmless, cosmetic only).

## Report back

Test count before/after, full gate output, `git diff --stat`, and the release version.

(Archive this file with its handoff pair on ship — throwaway once shipped.)
