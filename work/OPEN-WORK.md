# OPEN-WORK — the index of pending work

## Agent-closable

- **GRAPHIFY-CHATS** — new `cage insights graphify`: per-chat graphify usage + gross
  saving (recorded tokens · without-graphify counterfactual · saved%), joined by the
  savings rows' `session` to the chat universe. Spec + prompt:
  `docs/graphify-chats.{handoff,prompt}.md` (filed 2026-08-13, picked up on paste).

## Arpit decides

**None.**

## How this file is maintained

Continuously. A new item is one line here, the moment it's known; detail goes inline
or into a handoff/prompt pair in `docs/` root. A completed item is **deleted, not
ticked** — legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records its outcome
and any evidence reaches [regression/](../docs/regression/), with residual limits
carried forward as their own lines. **Its own markers are never evidence** — reconcile
against git. The header's checkable claims are gated by `tests/test_queue_honesty.py`.
Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
