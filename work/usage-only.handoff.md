---
doc: handoff — usage-only: delete the money subsystem, retire the cutover, one basis everywhere
status: PROPOSED — unbuilt
raised: 2026-08-14 (Arpit, across the METRICS-PRIMARY field session)
pair: [usage-only.prompt.md](usage-only.prompt.md)
---

# Handoff: USAGE-ONLY — cage becomes a usage meter

**One-liner:** delete dollars entirely, retire `SPEND_CUTOVER`, and make the three
per-agent metric ledgers the only basis — tokens and credits, nothing derived.

**Owner / executor:** Claude Code · **Model:** Opus (large deletion with entanglements —
CLAUDE.md rubric: *"deleting code with entanglements"*)

**Status:** Ready to build. **P0 is destructive and gated** (§2).

**Stress-tested:** the money deletion was decided twice and is not re-litigated. What the
handoff newly surfaced and resolved: (1) a **literal** pre-cutover wipe deletes 100% of
copilot and kiro data — every row you hold is pre-cutover — and their stores would
re-import at pre-cutover stamps and be excluded again, forever; so the boundary is removed
by **retiring the cutover**, not by deleting rows behind it. (2) Killing dollars kills
`receiptprice`, which is the only thing that made the receipt→call id mismatch dangerous —
that risk dies with the subsystem rather than needing a fix. **Residual risk:** cage loses
its only cross-agent denominator (§10, unanswered).

---

## 1. Context & background

- Field session 2026-08-14 established, against real data: claude has tokens and **no
  credit unit exists on disk**; kiro CLI has credits and **no tokens**; kiro IDE has
  **no usable store at all**; copilot has both on both surfaces.
- CLAUDE-DEDUP measured at **2.00×** across a full matched window (43,973 calls rows vs
  21,955 request rows, both spanning 2026-07-12 → 2026-08-14). The metric ledgers are
  correct; `calls` is inflated.
- METRICS-PRIMARY (v0.50) made the metric ledgers the derive source *forward of a
  cutover*. The cutover existed to protect unrebuildable `calls` history. That history is
  no longer wanted — dev phase, no older data needed — so the cutover's only job is done.
- Dollars were the reason for `receiptprice`, `creditprice`, the `(provider, model)`
  price match, `cage.toml`'s 51 price rows, and five commands. None survive the decision.

## 2. Definition of done

**P0 STOP gate — destructive; do not proceed without an explicit go:**

- [ ] Full backup of `.cage/` and `~/.cage/` taken and its path reported **before** any
      deletion. This is the only irreversible phase.

Then:

- [ ] `constants.SPEND_CUTOVER` and the `calls` branch of `ledger.spend()` are **gone**.
      `spend()` reads the three metric ledgers unconditionally; `basis` is either removed
      or constant.
- [ ] `SPEND_SOURCES["kiro"]` no longer names `ide` (dead — no store exists); kiro's
      absence from the token spine is stated in code, like `CUMULATIVE_SOURCES`.
- [ ] **Zero `$` in any output.** No `--usd` flag, no `est_cost_usd` read path, no
      `cage prices`/`budget`/`forecast`/`roi`/`netsaved`/`matrix`, no `receiptprice`/
      `creditprice` module, no price rows in `cage.toml`.
- [ ] Per-agent unit policy renders with **distinct reasons**, never `0`:
      | agent | tokens | credits |
      |---|---|---|
      | claude | value | `—` *"Claude Code records no credit unit on disk"* |
      | copilot | value | value |
      | kiro | `—` *"no IDE token store on this install"* | value |
- [ ] kiro credits retagged `estimated` → `measured` (they are AWS's own recorded charge;
      the `estimated` tag existed only because they stood in for dollars).
- [ ] `cage doctor`'s kiro-ide line distinguishes **db absent** / **table missing** /
      **column drift** instead of one indistinguishable zero.
- [ ] Full suite green after every phase. Goldens re-blessed **only** where a deleted
      `$` column is the cause, and each re-bless named in the commit message.
- [ ] `work/OPEN-WORK.md` reconciled (§9.5) — it currently contradicts the archive.

## 3. Scope

**In scope:** the money subsystem's deletion, the cutover's retirement, the unit policy,
the honesty fixes, docs and queue reconciliation.

**Out of scope (explicit) — do NOT do these:**

- **Do not delete pre-cutover metric rows.** They are the *corrected* history (21,900
  request rows back to Jul 12). Retiring the cutover makes them readable again — that is
  the point, not a side effect.
- **Do not re-denominate** `budget`/`forecast`/`roi`/`netsaved`/`matrix` in tokens. They
  are deleted, not converted (Arpit's call, 2026-08-14).
- **Do not stop writing `calls`.** It remains the id namespace that savings receipts
  reference (`metering.record_call` writes `call=<c_ id>`); `adoption` and `commitjoin`
  still resolve against it. It is simply no longer a *derive* source.
- **Do not add a dependency.** `dependencies = []`.
- **Do not touch `tests/test_floor.py`.**
- Do not build the `*-READ` / `*-CSV` views (still parked).

## 4. Current state

| fact | value |
|---|---|
| `ledger.spend()` adopted in | report · chats · budget · forecast · adoption · commitview · compare · freshness · exportcmd |
| still on `ledger.calls()` | doctorcmd ×4 · exportcmd ×2 · clicmds · hookcmd · mcpserver · pricescmd · taskcorr · demo · importcmd (capture-side, correct) · ledgersync (union, correct) |
| money-bearing modules | ~20; six `--usd` sites; five commands |
| claude rows | 21,955 request (all with `provider`), span Jul 12 → Aug 14 |
| copilot rows | 57 chat · 27 cli · 26 cli-delta — **all pre-cutover** |
| kiro rows | 3 cli-conv · 5 cli-turn · 3 credits — **all pre-cutover**, zero `ide` |
| suite | 1842 passed / 11 skipped · 43 goldens |

**Read first:** `CLAUDE.md` · `work/OPEN-WORK.md` · `work/archive/v0.50-metrics-primary.handoff.md`
· `cage/ledger.py` (`spend`, `SPEND_SOURCES`, `CUMULATIVE_SOURCES`) · `cage/receiptprice.py`
· `cage/creditprice.py` · `cage/policy.py` · `docs/kiro-capture.md`.

**Field evidence (do not re-derive):** `work/research/2026-08-13-kiro-per-chat-usage-fetch-spec.md`
(§6 probes now answered — see §9.5).

## 5. Technical approach (decided)

### 5.1 Retire the cutover — do not wipe behind it

- Delete `SPEND_CUTOVER` and `spend()`'s `calls` branch. `spend()` = the three metric
  ledgers, filtered by `SPEND_SOURCES`.
- **Why not a literal pre-cutover wipe** (the phrasing of the decision): every copilot and
  kiro row in existence is pre-cutover, so a literal wipe zeroes both agents — and their
  stores (VS Code `chatSessions`, `kiro-cli/data.sqlite3`) persist, so re-import would land
  pre-cutover stamps and be excluded again. Retiring the cutover achieves the stated goal —
  **no boundary, one basis, nothing to footnote** — and keeps corrected history.
- The `calls` ledger's inflated rows simply stop being read. Optionally truncate them in
  P0; that is a storage decision, not a correctness one.

### 5.2 Delete money, don't convert it

- Remove: `receiptprice.py`, `creditprice.py`, `pricescmd.py`, `budget.py`, `forecast.py`,
  `roi.py`, `netsaved.py`, `matrix.py`; the `--usd` flags; `est_cost_usd` read paths;
  `policy.price_match` and the `[prices]` table.
- **Keep** `savings/` receipts and attribution — savings are token-denominated and survive
  the removal intact. Only their *pricing* dies.
- Keep `make_call`'s `est_cost_usd` **field** (append-only law; historical rows carry it)
  but read it nowhere.

### 5.3 Units are per-agent, never summed across agents

- `credits` is not one unit: copilot's is GitHub's tokens×rates computation, kiro's is an
  AWS credit. Rendering them in one column is fine; **summing or ranking across agents is
  forbidden** and must be prevented in code, not convention.
- Tokens are likewise not cross-comparable (different tokenizers, and copilot carries no
  `cached_in` on the vscode surface at all). State it; do not blend.

### 5.4 N/A carries a reason, never a zero

Reuse the existing idiom (`chats.py:422` — *"`—` is never 0%"*; `CUMULATIVE_SOURCES`).
Two absences, two different reason strings — one is a vendor law, the other a missing
store. Rendering them identically would invite a future agent to "fix" the wrong one.

## 6. Non-negotiables

- **stdlib only** — `dependencies = []`.
- **Append-only** — never rewrite or delete a ledger row outside P0's gated wipe.
- **Fail-open capture**; every new swallow site logs under `CAGE_DEBUG`.
- **Counts-never-content.**
- **None-sentinel credits preserved** — a recorded `0.0` and an absent value stay distinct.
- **Do not touch:** `tests/test_floor.py`, the golden fixtures except where a deleted `$`
  column forces it (name each).
- **`CLAUDE.md` edits are PROPOSED, never applied.**
- **No concurrent session** in this repo.

## 7. Dependencies & prerequisites

- A verified backup (P0 gate). No services, env vars, or secrets.
- Manual CLI verification must use the pytest sandbox env vars — a prior build polluted
  the real `~/.cage` by omitting them (`work/IMPLEMENTATION.md`, 2026-08-14).

## 8. Edge cases & risks

| risk | handling |
|---|---|
| Deleting `receiptprice` orphans `freshness`/`attribution` call-sites | Both are money paths; remove the call sites with the module. `adoption` + `commitjoin` id joins **survive** and must keep resolving against `ledger.calls()`. |
| Goldens carry `$` columns | Re-bless only those, name each in the commit. Any golden moving for another reason is a bug. |
| `cage.toml` price rows removed → `cage setup`/`doctor` schema drift | Migrate the policy file and pin with a test; a stale `[prices]` table must not fail a load. |
| copilot/kiro become readable again once the cutover dies | Expected and desired — their pre-cutover rows are valid, they were only excluded by the boundary. |
| A future Kiro version adds `devdata.sqlite` | Keep `parse_kiro_ide_metrics`; the doctor's three-way check announces the flip. |
| Orphaned zero-byte `.tmp` files in `~/.cage/ledger/` | Clean up on write; unrelated to this build but observed 2026-08-14. |

## 9. Testing & validation

- New: `spend()` with no cutover (one basis, no double-count); the three-way kiro-ide
  doctor check; the per-agent N/A reason strings; a guard that credits are never summed
  across agents.
- **A grep-gated test that `$`, `usd`, `est_cost_usd` and `price` appear in no output
  path** — the deletion's own regression pin.
- Regression: `test_floor` untouched · `test_debug_coverage` · `test_queue_honesty` ·
  `test_output_spec` · `test_cli_reference`.
- Suite green after **every** phase.

## 9.5 Documentation impact

- [ ] **ADR (required, new)** — why cage stopped measuring money, and why the cutover was
      retired rather than wiped behind. This is the decision a future agent would reverse.
- [ ] **`docs/PLAN.md`** — §3.1 calls the call record *"ground-truth spend"*; §3.3 the
      policy/prices file; §3.8, §4.5, §6 all money. Rewrite or mark superseded.
- [ ] **`README.md`** — the product is now a usage meter, not a cost meter. Positioning
      changes.
- [ ] **`docs/kiro-capture.md`** — still lists `devdata.sqlite` as a live source. It does
      not exist on a real install (field-probed 2026-08-14: `dev_data/` holds only
      `tokens_generated.jsonl`, 28 rows, 1,576 in / **0 out**, model `"agent"` on every
      row, with a byte-identical 6-row block repeated — not summable).
- [ ] **`work/research/2026-08-13-kiro-per-chat-usage-fetch-spec.md`** — close the
      `unverified:` header: probe 2 answered (no sqlite twin).
- [ ] **`work/MACHINE.md`** — split `| Kiro installed | yes |` into IDE and CLI rows; they
      are separate installs with separate stores, and conflating them is the exact premise
      error that file exists to prevent.
- [ ] **`CHANGELOG.md`** — major user-facing removal.
- [ ] **`CLAUDE.md`** — substrate/ledger description. **PROPOSE, do not apply.**
- [ ] **`work/OPEN-WORK.md`** — currently lists CLAUDE-DEDUP, CLAUDE-SUBAGENT-KEY, six
      `*-READ`/`*-CSV` items and METRICS-PRIMARY as pending while
      `work/archive/v0.50-metrics-primary.*` says implemented. Reconcile against git.
- [ ] **`docs/GLOSSARY.md`**, **`work/DOC-REGISTRY.md`**, **`docs/README.md`**.

## 10. Open questions

- **OPEN QUESTION (Arpit) — the one thing not yet decided.** Dollars were the only unit
  that made claude, copilot and kiro comparable. After this, "which agent used more" has
  no answer: claude has no credits, kiro has no tokens, and tokens aren't comparable across
  vendors. If cross-agent comparison is something cage should do, nothing in this build
  replaces it. Flagged twice in session, unanswered.
- **OPEN QUESTION:** truncate the inflated `calls` history in P0, or leave it unread?
  Recommend **leave it** — unread costs nothing, and it is the id namespace receipts point at.
- **OPEN QUESTION:** does `cage` keep the name/positioning of a spend tool? §9.5's README
  item depends on the answer.
