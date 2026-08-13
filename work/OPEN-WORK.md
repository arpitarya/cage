# OPEN-WORK — the index of pending work

## Agent-closable

- **COPILOT-METRICS** — new ledger kind `.cage/ledger/copilot/chats-YYYY-MM.jsonl`:
  per-chat Copilot tokens in/out · cached · credits · session credits · nano-AIU,
  captured verbatim from all five stores (Arpit's scope call 2026-08-13). Spec + prompt:
  `docs/copilot-metrics-ledger.{handoff,prompt}.md` (filed 2026-08-13, picked up on
  paste). Grounding: `docs/research/2026-08-13-copilot-per-chat-usage-fetch-spec.md`.

- **CLAUDE-DEDUP** — defect: the claude transcript parser records every assistant
  row's usage, but one API response writes 1–5 rows (same `requestId` + `message.id`,
  distinct `uuid`, each with a full usage copy) — claude spend is inflated ~2–3×
  (3.17× measured live on 2.1.229). Fix: fold last-per-`(requestId, message.id)`,
  call id from `requestId`. Grounding:
  `docs/research/2026-08-13-claude-per-chat-usage-fetch-spec.md` (filed 2026-08-13).
- **CLAUDE-SUBAGENT-KEY** — defect: subagent transcripts
  (`<sessionId>/subagents/agent-*.jsonl`, current layout) are swept by the glob but
  session-keyed by filename stem, so their spend lands in a phantom chat; key
  `session` from each row's own `sessionId` (also covers legacy inline sidechains).
  Same grounding doc (filed 2026-08-13).

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
