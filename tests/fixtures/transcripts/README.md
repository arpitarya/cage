# Transcript fixture corpus — agent × surface (P0 validation harness)

Sanitized session-log samples pinning the **on-disk log format** `cage import`
parses for every agent × surface combination. Token counts are realistic; all
content is stripped (`[content stripped — counts only]` placeholders) — the
same counts-never-content PII discipline as the ledger itself.

Layout: `tests/fixtures/transcripts/<agent>/<surface>/` with
`agent ∈ {claude, codex, copilot, kiro}` and `surface ∈ {cli, vscode}` (the
four-agent invariant — never drop one). Each directory holds:

- the raw log file, named exactly as the agent writes it (the name matters:
  `importcmd`'s glob patterns are part of the pinned contract — codex must
  match `rollout-*.jsonl`, copilot must be `session-state/<id>/events.jsonl`
  (CLI) or `workspaceStorage/*/chatSessions/*.jsonl` (VS Code extension),
  kiro must be `dev_data/tokens_generated.jsonl`);
- `expected.json` — the exact call rows `transcript.py` + `importcmd.py`
  produce, plus plant metadata:
  - `env`: the path-override env var the test uses to plant the log
    (`CLAUDE_CONFIG_DIR` / `CODEX_HOME` / `COPILOT_HOME` / `KIRO_DATA_DIR`);
  - `plant`: where the log goes **relative to that env dir** (mirrors the real
    on-disk location, so the default — pathless — import scan finds it);
  - `volatile`: fields stamped at import time rather than carried by the log
    (`ts` for kiro — its token log carries no timestamps, so the row's `ts`
    is a write-time stamp; asserted present, not equal. Codex rows carry the
    `token_count` event's own timestamp since the 0.16.x shard fix);
  - `format_verified`: whether the format was pinned against a real client
    log (see per-format provenance below) or is a stand-in;
  - `rows`: the expected rows, in parse order, ids included (all ids are
    deterministic — uuid-derived, session+index-derived, or content-hashed —
    so re-import dedupe is assertable byte-for-byte).

`tests/test_fixture_corpus.py` parametrizes over every directory here, plants
the log into an isolated fake agent home, runs the real `cage import` path,
and asserts the ledger rows equal `rows` exactly (idempotency included). It
also fails if an agent × surface directory is ever missing.

## Format provenance

| Fixture | Status | Pinned against |
|---|---|---|
| claude/cli | verified | Claude Code CLI transcript (`~/.claude/projects/**/*.jsonl`), assistant turns with `uuid`/`timestamp`/`cwd`/`message.usage` — see `transcript.parse_calls` |
| claude/vscode | verified | Same store, same format: the Claude Code VS Code extension writes the identical `~/.claude/projects` transcript (plan §3.7 — only Claude's extension shares the CLI's on-disk log) |
| codex/cli | verified | Codex CLI 0.5x rollout (`session_meta` / `turn_context` / `token_count` with `payload.info.last_token_usage` and the sibling `payload.rate_limits`) — see `transcript.parse_codex_calls` / `_codex_rate_limits` |
| codex/vscode | verified | Real Codex VS Code-extension session (`openai.chatgpt` v26.623.x, 2026-07-07): the extension writes the **same** `~/.codex/sessions/**/rollout-*.jsonl` store and format as the CLI — sanitized sample captured on macOS, token counts + `rate_limits` verified against the live import. |
| copilot/cli | verified | Copilot CLI 1.0.65 `session-state/<id>/events.jsonl` — `session.shutdown.modelMetrics`, tokens under `usage`, `inputTokens` already total — see `transcript.parse_copilot_calls` |
| copilot/vscode | verified | Real Copilot Chat extension session (v0.54.0 / VS Code 1.126, 2026-07-08), pinned against **VS Code's chat-session store**: `<vscode-user>/workspaceStorage/<hash>/chatSessions/<session>.jsonl` (`kind:2, k:["requests"]` lines; per-request `requestId`/`timestamp`/`modelId`/`promptTokens`/`completionTokens`) — see `transcript.parse_copilot_vscode_calls`. The extension's own `GitHub.copilot-chat/transcripts/` event stream carries **no** usage event (no `session.shutdown`, even after quitting VS Code) — that's why the store differs from the CLI's `events.jsonl`. `CAGE_VSCODE_USER` overrides the user dir. |
| kiro/cli | verified | Kiro `dev_data/tokens_generated.jsonl` (`{model, provider, promptTokens, generatedTokens}`, coarse by design) — see `transcript.parse_kiro_calls` |
| kiro/vscode | verified | Real Kiro IDE token log (macOS, 2026-07-07): `~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/dev_data/tokens_generated.jsonl`, counts-only by construction (`{model, provider, promptTokens, generatedTokens}`, no timestamps — `ts` stays volatile). Pinned on this machine's layout; coarse fidelity (output tokens often 0) is the format, not a parse gap. |

Rule for the stand-ins: **do not invent formats.** When a real extension log
sample lands, sanitize it to counts, replace the stand-in, flip
`format_verified` to `true`, and update this table.

## `gap_ms` availability (derived human attention, plan §4.10)

Where a log carries per-turn timestamps for both the human turn and the
preceding assistant turn, the parser stamps an additive `gap_ms` on the call
row (previous assistant end → human turn that led to the call). Where it
doesn't, the field is **absent — never fabricated**:

| Agent | `gap_ms` | Why |
|---|---|---|
| claude | **yes** | every transcript record is timestamped; human turns are distinguishable from `tool_result` / meta records (the claude/cli fixture pins a 37 000 ms gap; its `tool_result` user record is correctly ignored) |
| codex | no | `token_count` events are timestamped but the pinned rollout carries no user-turn marker — an event-to-event gap would mix agent compute into human attention |
| copilot | no | CLI log aggregates once at `session.shutdown`; the VS Code store has one epoch-ms per request, no assistant-end timestamp to gap against |
| kiro | no | `tokens_generated.jsonl` carries no timestamps at all |

## Regenerating expected.json

`expected.json` is frozen output of the current parsers, reviewed by hand
(token math, id derivation) before committing. If a parser's contract changes
deliberately, re-derive the rows with the parser, re-review the numbers, and
update the fixture — never bless blindly.
