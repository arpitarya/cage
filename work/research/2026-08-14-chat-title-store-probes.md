# 2026-08-14 — Does copilot-CLI or kiro-CLI carry a chat name?

**Take-away:** **Copilot CLI does — and not where cage looks.** The name is in a sibling
file, `workspace.yaml`, next to the `events.jsonl` cage already reads; 24 of 32 sessions
carry a non-empty one. **Kiro CLI does not** — `conversations_v2` has no title field of
any kind, and its one summary slot is `NULL` on every row. So P3b lifts a name for
copilot CLI and keeps the honest `""` for kiro, permanently.

Evidence for P0.2 of the ledger restructure. **Findings, not spec** — the phase that acts
on this cites it; where it disagrees with the code, the code wins.

Probed on the maintainer's macOS machine, 2026-08-14. Copilot CLI 1.0.75, kiro-cli 2.16.0.
Both stores read **read-only**; nothing was written.

---

## Why it was asked

Today only two surfaces yield a name: claude (transcript `summary` → cwd basename) and
copilot **VS Code** (`customTitle`/`generatedTitle`). Copilot CLI and kiro write `""`.
Whether that `""` is a *store limitation* or a *cage gap* was unknown, and the two lead
to opposite work — so it was probed rather than assumed.

---

## Copilot CLI — a name exists, in a file cage does not read

`~/.copilot/session-state/<session-id>/` holds seven entries. Cage reads exactly one of
them, `events.jsonl`.

**`events.jsonl` carries no conversation title.** 457 events across 24 session files, 269
distinct nested key paths, 12 event types. Every title-shaped key found is a property of a
*tool call* — `data.toolRequests[].name` (36), `data.toolRequests[].arguments.description`
(5), `data.toolName` (36), `data.predictedLabel` (13) — never of the conversation.
`session.start` carries `sessionId`, `startTime`, `copilotVersion` and a `context` block
(cwd, gitRoot, branch, headCommit) and no name; `session.shutdown` carries token and
model metrics and no name.

**`workspace.yaml`, the sibling, carries it.** Its top-level keys across 32 files:

| key | files carrying it |
|---|---|
| `id`, `cwd`, `user_named`, `summary_count`, `created_at`, `updated_at` | 32 / 32 |
| `git_root`, `branch`, `client_name` | 31 / 32 |
| **`name`** | **24 / 32** |
| `repository`, `host_type` | 8 / 32 |
| `remote_steerable`, `mc_task_id`, `mc_session_id`, `mc_last_event_id` | 1 / 32 |

- **Every `name:` slot that exists is non-empty** — 24 present, 24 non-empty. There is no
  written-but-blank case to handle.
- **8 sessions have no `name` key at all.** They are the honest-`""` case and stay `""`.
- **`user_named` is present on all 32 and is `false` on all 32** — the name is auto-derived
  from the first user turn, never user-authored. It is a real signal and should be
  recorded rather than flattened away: a generated label and a chosen one are different
  facts, and the field costs nothing to carry.
- Observed names are short prose derived from the opening prompt. **Not quoted here** —
  this repo is public and a chat name is user content.
- There are **32 `workspace.yaml` files but 24 `events.jsonl` files**, so the two are not
  in bijection; a name lookup must tolerate either side missing.

### Two constraints on using it

1. **It is YAML, and the stdlib has no YAML parser.** `dependencies = []` is law, so this
   cannot be `yaml.safe_load`. It is parseable without one: every file probed is **flat**
   — no nested blocks, no lists, one `key: value` per line. A minimal reader for
   `^name:\s*(.*)$` with quote-stripping is sufficient **and must be written to fail
   closed**: anything it does not understand yields `""`, never a guess. A general YAML
   subset parser is not needed and should not be written.
2. **It widens the read surface by one file per session directory.** Same PII posture as
   claude's `summary`: a name is user-derived prose, recorded **only** in the local audit
   file, never on a call/receipt/savings row, and excluded from anything that leaves the
   machine.

---

## Kiro CLI — no title, structurally

`~/Library/Application Support/kiro-cli/data.sqlite3`, table `conversations_v2`, 20 rows,
keyed by cwd. Seven tables total; `conversations` (the v1 table) and `history` are empty.

A conversation blob's top-level keys — all 20 rows carry all 16:

```
conversation_id · next_message · history · valid_history_range · transcript · tools
context_manager · context_message_length · latest_summary · model_info · file_line_tracker
mcp_enabled · mcp_last_checked · mcp_server_versions · mcp_disabled_due_to_api_failure
user_turn_metadata
```

**No title, name, label or subject at any depth.** Every title-shaped key path found
belongs to the embedded **tool schemas** — `tools.native___[].ToolSpecification.name`
(100), `.description` (100), and their `input_schema` property descriptions. Those are
static tool definitions serialised into every conversation; they describe kiro's tools,
not the user's chat. `model_info.description` describes the model.

**`latest_summary` is `NULL` on all 20 rows** — the one slot that could plausibly hold a
derived name is unpopulated in practice. This is the closest thing to a candidate and it
is empty, which is why it is named here rather than left for someone to rediscover.

`transcript` holds the raw turn text (e.g. a first turn plus a tool marker). **It must not
be used as a name.** A name synthesised from prompt text is a fabricated field wearing a
recorded field's clothes, and it would put arbitrary user prose on a path `""` currently
keeps clean.

---

## What P3b may and may not do

| surface | today | after P3b | why |
|---|---|---|---|
| claude | name | unchanged | transcript `summary` |
| copilot VS Code | name | unchanged | `customTitle` / `generatedTitle` |
| **copilot CLI** | `""` | **name, from `workspace.yaml`** | 24/32 sessions; flat file, stdlib-parseable |
| kiro CLI | `""` | **`""`, permanently** | no title field exists |
| kiro IDE | `""` | **`""`, permanently** | no per-chat identity at all |

**Never fabricate.** No session id dressed as a name, no first-prompt substring, no cwd
basename standing in for a title. An absent name renders as absent — the same rule that
makes every other refusal in cage readable.

**Upgrade watch.** `latest_summary` existing-but-`NULL` is exactly the shape of a slot a
vendor fills later (the same posture as kiro-CLI's still-null token slots). If it becomes
populated, kiro CLI gains a name and this table's last two rows are revisited. Nothing
should be built for that today.

---

## Reproduction

```bash
# copilot CLI — the name is NOT in events.jsonl
grep -h '^name:' ~/.copilot/session-state/*/workspace.yaml | wc -l
grep -h '^user_named:' ~/.copilot/session-state/*/workspace.yaml | sort | uniq -c

# kiro CLI — read-only, no title anywhere
sqlite3 "file:$HOME/Library/Application Support/kiro-cli/data.sqlite3?mode=ro" \
  "select count(*), count(json_extract(value,'\$.latest_summary')) from conversations_v2;"
```

**Sibling snapshot:** [regression/2026-08-14-calls-vs-metric-crosscheck.md](../regression/2026-08-14-calls-vs-metric-crosscheck.md)
— P0.1, the writer cross-check taken at the same cut.
