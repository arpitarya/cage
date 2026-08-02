# Handoff: CHATS-AUTHOR — the `agent%` authorship column on `cage insights chats`

**One-liner:** per chat, the share of landed matchable lines (in files that chat
proposed) that matched the agent's own proposals — v2 provenance counts joined by
`(agent, session)`, pure ledger derive, no git at render.
**Owner / executor:** Claude Code.
**Status:** Ready to build — **blocked on REV-TS** (see §7; Phase 0 verifies it and
STOPs if absent).
**Stress-tested (2026-08-02):** challenged: (a) *build now atop the skewed window
join* — resolved as a hard prerequisite, not a footnote: REV-TS
([proposal](archive/v0.45-rev-ts.proposal.md)) must land first and Phase 0
proves it landed; folding the fix in here was rejected (it is its own filed defect
with its own fixtures — double-pickup risk). (b) *always-written `residual_lines`
vs a schema version stamp* — presence-of-key survives as the minimal mechanism
(the credits `None` precedent); the debate pinned the implementation trap:
`schema.make_provenance` omits zero counts, so the deviation must be explicit and
tested. (c) **newly surfaced:** when two sessions propose the *same file* in one
commit, the per-chat rows double-count **both** sides (agent and residual) of that
file's lines — per-chat `agent%` stays ≤100% by construction (per-row residual is
floored at 0), but two chats' line counts are independent claims, not a partition;
the commit view remains the arbiter. Now a stated limit, footnoted. (d) *default-on
column bloat* — survives as one ≤6-char column; if the golden overflows 100 cols,
the recorded fallback is demoting it behind `--authorship` (one-line revert).
Residual risk: coverage is claude-code only — every other agent's cell is an
honest `—`, and that must never read as 0%.

## 1. Context & background

Design of record:
[proposals/chats-agent-authorship-column.proposal.md](proposals/chats-agent-authorship-column.proposal.md)
(metric scope, refusal shapes, and the three standing-guard answers are binding).
The chats view (`cage/chats.py`, FORMULAS §2.13) answers *which chat spent the
tokens*; the per-commit surfaces (`cage/commitview.py`, §2.14) answer *whose lines
landed per sha*. This joins them per conversation: provenance rows already carry
`(sha, agent, session_id)` + the five line-match counts, and for claude-code both
sides stamp the **same** session id (transcript stem — `importcmd` `_PARSERS`,
`authorcapture.capture`). Verified at HEAD 2026-08-02.

## 2. Definition of done

- [ ] **Phase 0 (gate):** `commitjoin` normalizes timestamps to one UTC normal form
      and the non-UTC (+05:30) goldenseed fixture exists and passes. If not, STOP —
      report, do not build.
- [ ] `schema.PROVENANCE_COUNT_FIELDS` gains `residual_lines`; on every **new**
      transcript-method row it is **always written, including 0** (the one
      deliberate deviation from omitted-at-0, documented in `make_provenance`'s
      docstring and pinned by a round-trip test asserting a zero survives).
- [ ] `authorcapture.capture` step 4 computes it: Σ matchable added lines across the
      row's landed files − `agent_lines`, floored at 0 — from the diff already in
      hand; no extra git call.
- [ ] `chats.summarize` joins `ledger.provenance(root)` by
      `(agents.row_surface(agent), session_id)` against each bucket's
      `(agent, session)`; sums `agent_lines` + `residual_lines` over rows carrying
      the residual key; counts rows lacking it (pre-upgrade) separately.
- [ ] Text: one `agent%` column after `credits`, default on. Three refusal shapes
      render `—`, each footnoted, never 0%: coverage (copilot/kiro,
      `authorcapture.coverage_note()`) · no provenance row joined ("no landed code
      evidence") · pre-upgrade rows only (`· N provenance row(s) predate residual
      counts — excluded`).
- [ ] CSV: `agent_lines` · `residual_lines` · `agent_pct` from the same rows —
      empty cells when refused, `—` never enters CSV.
- [ ] Money-independence extended and green: deleting `provenance.jsonl` leaves
      every **pre-existing** cell byte-identical; only the new authorship cells
      fall to `—`/empty.
- [ ] Guard test: no formula in `chats.py` combines an authorship count with a USD
      value (the v0.36 law — no rate, no minutes, no cost-split-by-author).
- [ ] `cage query chats-view` + `cage query agent-authorship` both gain the scope
      sentence ("of evidenced lines in files this chat touched — not a share of
      the chat's work"); FORMULAS §2.13 (column rows) + §2.14 (counts table row).
- [ ] Goldens re-blessed; `just test` full suite 0 fail (from 1401/0).
- [ ] Documentation updated per §9.5.

## 3. Scope

**In:** `schema.py` count field + docstring · `authorcapture.py` residual
computation · `chats.py` join/render/CSV · `linematch` helper reuse (matchable/
normalize — never a second matcher) · tests · docs · explain entries.
**Out (explicit):** the REV-TS fix itself (prerequisite, its own program) ·
**any backfill/migration of frozen provenance rows** (idempotency key — old rows
stay `—` forever, do not "helpfully" rewrite the append-only log) · acceptance
rate (`kept/suggested`) in any form · a chat-level cross-session clamp ·
conversation-share or tokens_in/out variants of the column · copilot/kiro edit
parsers · `--team` / anything leaving the machine · MCP tool changes ·
`commitview.py` (untouched — its per-commit math is the arbiter, not a consumer).

## 4. Current state

- Repo: `~/my_programs/cage`. Read first: `cage/chats.py` (bucket key, render,
  CSV, footer discipline), `cage/authorcapture.py` (step 4 — where the diff and
  landed paths are in hand; `COVERAGE_GAPS`), `cage/schema.py`
  (`PROVENANCE_COUNT_FIELDS`, `make_provenance`'s omit-at-0 loop — the thing you
  deviate from), `cage/originrecord.py` (`record`'s `**counts` filter — the closed
  boundary the new key must pass), `cage/commitview.py` `_buckets` (the per-commit
  math this must reconcile with, not re-implement), `cage/agents.py`
  (`row_surface`), `cage/linematch.py` (`matchable`/`normalize` — ONE function,
  both sides).
- Tests to mirror: `tests/test_chats.py` (money-independence, determinism),
  `tests/test_authorcapture.py`-class capture tests, goldenseed fixtures.

## 5. Technical approach (decided — do not re-litigate)

- **Metric scope:** denominator = matchable landed lines in files the chat
  proposed. `unattributed`/`unknown` are commit-scoped and structurally excluded —
  scope, not redistribution. Header/footnote wording must say so.
- **`residual_lines` always written** on new rows; presence of the key is the
  version gate. No schema version field, no migration.
- **Join normalization** through `agents.row_surface` on both sides — provenance
  stamps `claude-code`, chats buckets `claude`. Counts attach to every bucket
  sharing `(agent, session)`; a session split across surfaces is footnoted.
- **`agent%` is read, never re-derived** — sums of recorded counts only; no
  re-matching at render (the second-matcher mistake, §2.14).
- **Default on**, one column; demote to `--authorship` only if the 100-col golden
  forces it (record which in the build notes).

## 6. Non-negotiables / constraints

- **$0 / stdlib only**; derive-time only; the ledger is never rewritten.
- **Determinism law:** no clocks/random; same ledger+policy ⇒ same bytes.
- **v0.36 guard:** no rate, no minutes, no USD touches an authorship number.
- **Honesty rules:** `—` never means 0; every refusal shape footnoted with its
  reason; no acceptance percentage; counts-never-content (line bodies stay
  transient — ADR 0008; the plant-string test must stay green untouched).
- **Do not touch:** `commitview.py` · the ledger write path beyond the one count ·
  `verbmap` · wiring modules · frozen provenance rows.

## 7. Dependencies & prerequisites

**Hard:** REV-TS ([timestamp-utc-normal-form](archive/v0.45-rev-ts.proposal.md))
implemented and green — Phase 0 verifies, else STOP. Nothing else external; no new
config keys; no version bump (a release action).

## 8. Edge cases & risks

- kiro-IDE collapsed row → coverage `—` (doubly refused). · Chat with calls but
  commits in another repo/ledger root → no rows → "no landed evidence" `—`. ·
  Uncommitted live chat → `—` until the sweep covers it (by design). · Mixed
  pre/post-upgrade rows in one chat → % over carrying rows only + counted
  footnote. · Two sessions proposing the same file in one commit → both chats
  count that file's lines on both sides (stated limit (c), footnoted in the query
  entry). · `residual_lines` can never be negative (floored at capture). ·
  Hooked-method rows carry no counts → contribute nothing, exactly as in
  `commitview._buckets`.

## 9. Testing & validation

- `tests/test_chats.py` additions: join math vs a goldenseed session (chat sums ==
  Σ that session's per-commit §2.14 buckets) · refusal triad (no-provenance /
  copilot / pre-upgrade) · money-independence extension · no-USD-combination
  guard · CSV parity + empty-cell rule · determinism.
- Capture side: residual arithmetic on a fixture commit (incl. the zero case
  surviving the row round-trip); plant-string test untouched and green.
- Run: `just test` — full suite 0 fail; goldens blessed
  (`CAGE_BLESS_GOLDENS=1`, new fixtures only).

## 9.5 Documentation impact

- [ ] **FORMULAS.md** — §2.13 three column rows + scope sentence; §2.14 counts
      table gains `residual_lines` (with the always-written deviation stated).
- [ ] **explain_data.py** — both query entries updated (ships in the binary).
- [ ] **README** — one line under the chats view mention (user-facing column).
- [ ] **CHANGELOG** — entry under the next unreleased version.
- [ ] **PLAN.md** — plan entry (proposal graduates per lifecycle).
- [ ] **GLOSSARY** — `agent%` / `residual_lines` terms.
- [ ] **CLAUDE.md** — ⚠️ propose the edit (chats bullet + the second carve-out),
      surface for Arpit's review — never silently rewrite steering files.
- [ ] **DOC-REGISTRY** — bump touched rows. **OPEN-WORK** — delete CHATS-AUTHOR
      after IMPLEMENTATION.md records the build. **Archive** the pair + proposal
      on green (archive-on-implement), update `proposals/README.md`.
- N/A: ADR — the substrate deviation is one count field documented at the schema
  boundary; promote to an ADR only if a second always-written count appears.

## 10. Open questions

- OPEN QUESTION (naming only, non-blocking): CSV `agent_pct` as 0–1 float vs
  0–100 with 1dp — executor picks one, states it in FORMULAS §2.13, golden pins it.
