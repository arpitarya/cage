---
doc: regression — finding: Claude Code L1 hooks fired live inside a VS Code-extension session
date: 2026-08-02
severity: LOW — no data-loss/correctness risk; a documentation-accuracy finding
found: SELFWIRE task — first-ever field verification of `cage setup --claude --hooks`
status: OPEN — the "CLI-only" claim needs review, not yet corrected in code/docs
---

# The "hooks do not fire under a VS Code extension" claim did not hold for this session

**The claim, as written today** (`cage/attest.py` `LIMIT`, `cage/hookcmd.py` module
docstring, `CLAUDE.md`'s agent-surface bullets, `cage doctor`'s `metering` check): L1
hooks are **CLI-only** — a Claude Code session run through a VS Code extension is
supposed to produce **no** `SessionStart`/`SessionEnd`/`PreToolUse` firings, hence no
`state/attest.jsonl` rows, at all.

**What was actually observed** (this machine, this repo, 2026-08-02, first-ever field
run of `cage setup --claude --hooks` on cage's own repo — closing part of **L1-FIELD**):
the executing agent's own system prompt states *"You are running inside a VSCode native
extension environment."* After wiring L1 hooks (`.claude/settings.json` gained the
`PreToolUse`/`SessionStart`/`SessionEnd` entries shown below), two **unprompted**,
genuinely host-fired `PreToolUse` "tool" attestations appeared in
`.cage/state/attest.jsonl` immediately after two ordinary `Bash` tool calls that
happened to invoke `./bin/graphify`:

```
{"agent": "claude", "args_hash": "904cd809af922956", "kind": "tool", "tool": "graphify", ...}
{"agent": "claude", "args_hash": "0a90e7e3d734134a", "kind": "tool", "tool": "graphify", ...}
```

## Why this is solid evidence, not a fluke

`attest.record_tool` / `attest.record_session` are called from **exactly one** place in
the codebase — `cage/hookcmd.py`'s `_do_tool`/`_do_session`, invoked only by
`cage hook <event> --agent claude` (`grep -rn "record_tool(\|record_session(" cage/*.py`
confirms this). Nothing else writes `state/attest.jsonl`. The two rows above were never
produced by a manual `cage hook …` invocation — they appeared as a side effect of the
agent's own `Bash` tool calls, which is precisely what the wired
`.claude/settings.json` `PreToolUse` → `Bash` matcher entry is supposed to trigger:

```json
{"matcher": "Bash", "hooks": [
  {"type": "command", "command": "${CLAUDE_PROJECT_DIR:-.}/.cage/bin/cage-run hook tool --agent claude"},
  {"type": "command", "command": "${CLAUDE_PROJECT_DIR:-.}/.cage/bin/cage-run hook budget --agent claude"}
]}
```

A third, isolated manual invocation (`echo '{"session_id":...}' | cage-run hook tool
--agent claude`) was used earlier to prove the command itself works — that row was
deleted afterward to keep `state/attest.jsonl` free of synthetic test data; the two rows
above are the real, host-fired ones and were left in place.

## What this does and does not settle

- **Settles:** on this host (an agent whose own system prompt self-identifies as "a
  VSCode native extension environment"), the wired `PreToolUse`/`Bash` L1 hook *does*
  fire for real tool calls, end to end, with no manual step. This is genuine evidence
  toward **L1-FIELD** for the Claude leg specifically.
- **Does not settle:** whether "VS Code extension" in the existing claim meant this
  exact environment, a different (older/other) Claude Code VS Code integration, or was
  written by analogy from Copilot/Kiro's VS Code extensions (which *do* lack a verified
  hook surface, per `agents.HOOK_GAPS`) without being checked for Claude specifically.
  `SessionStart`/`SessionEnd` firing was **not** independently verified live (the
  session predates this task's `--hooks` wiring, so its own start/end boundaries were
  already past/not-yet-reached); only `PreToolUse` was confirmed live.
- Copilot and Kiro remain completely unverified — this finding is Claude-only.

## Suggested next step (not applied here)

Someone who knows which concrete Claude Code surfaces are meant by "VS Code extension"
in `attest.LIMIT` should either (a) narrow the claim to the surfaces where it's actually
true, citing this finding, or (b) if this environment is considered out of scope for
that claim (e.g. an SDK-embedded session rather than "the" VS Code extension), say so
explicitly so a future reader doesn't re-discover the same ambiguity. Left as **OPEN**
rather than edited in the same change, since correcting a stated invariant like
`attest.LIMIT` is a judgment call for whoever wrote it, not a mechanical doc sync.
