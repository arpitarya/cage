# OPEN-WORK — the index of pending work

## Agent-closable

- **CHATS-CREDITS** — render kiro-CLI credit conversations as chat rows in
  `cage insights chats` (credits column filled, token cells `—`); kills the false
  "`cage report` counts it" refusal text. Spec + prompt:
  `docs/chats-credits.{handoff,prompt}.md` (filed 2026-08-12, picked up on paste).

## Arpit decides

- **REPORT-CREDITS?** — discovered 2026-08-12: `ledger.credits` is read by NO money
  view (grep: only `chats._credit_agents`), so once CHATS-CREDITS lands, chats is the
  only surface counting kiro-CLI usage. Decide whether `cage report` gains a credits
  count line. (filed 2026-08-12)

## How this file is maintained

Continuously. A new item is one line here, the moment it's known; detail goes inline
or into a handoff/prompt pair in `docs/` root. A completed item is **deleted, not
ticked** — legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records its outcome
and any evidence reaches [regression/](../docs/regression/), with residual limits
carried forward as their own lines. **Its own markers are never evidence** — reconcile
against git. The header's checkable claims are gated by `tests/test_queue_honesty.py`.
Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
