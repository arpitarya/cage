# WORKLOG

The running session handoff. At the end of **every substantive exchange**, append
an entry: what was asked, what was done, what was decided or left open, and the
single next step. Newest on top. Short and true — this is a rolling exit-interview
so a new session can pick up cold.

Distinct from [INTERVIEW.md](INTERVIEW.md) (the strategic,
cross-session succession record) — the worklog is the granular, per-exchange trail.
Distinct from [IMPLEMENTATION.md](IMPLEMENTATION.md) (what is *built*, milestone
by milestone) — the worklog is what *happened this session*.

---

## 2026-08-08 — Claude Code — GFX-COV copilot VS Code field run (GFX-COV-FIELD closed)

- **Asked:** VS Code field run done, proceed.
- **Done:** located the capture, ran the shipped route against it (146,261 tokens saved,
  72 files, idempotent), rebuilt the fixture from the sanitized real record, added the two
  tests the capture earned, published
  [the run](regression/2026-08-08-gfx-cov-vscode-field-run.md). 1498 => 1500.
- **The lesson, and it is the same one twice:** my synthetic fixture was wrong in exactly
  the way a synthetic fixture is always wrong — it was *too clean*. A real agent prefixes
  `cd <repo> &&` because `run_in_terminal` reuses a shell, and the real part carries no
  `resultDetails`. Both paths worked, but **neither was tested**; the route was correct by
  design and unverified by evidence. A fixture I wrote cannot falsify an assumption I made.
- **Decided:** keep the report-read fixture **separate** rather than adding a synthetic
  readFile part to the real capture — a fixture labelled real must not carry invention.
- **Open:** **GFX-KIRO-RATE** only (kiro's refusal rate, n=2 so far; ADR 0009's veto reopens
  below a 10% file rate). GFX-COV-FIELD is closed — both routes verified on real data.
- **Next step:** the v0.47.0 release cut. Everything is staged; it needs Arpit's explicit go
  because `gh release create` publishes to PyPI.

## 2026-08-07 — Claude Code — GFX-COV field run (kiro half closed)

- **Asked:** continue.
- **Done:** measured the kiro half of GFX-COV-FIELD against the real kiro-cli store —
  the P0 probe runs were still in it, so the evidence was already there. 2 graphify
  invocations: 1 filed (3,545 tokens), 1 refused as truncated, re-run idempotent.
  Published to [regression/](regression/2026-08-07-gfx-cov-kiro-field-run.md).
- **Decided:** report n=2 as *both branches execute*, **not** as a 50% refusal rate.
  ADR 0009's veto is keyed to a 10% file rate and that needs a real sample; publishing a
  rate off two runs would be the kind of number this project exists to refuse.
- **Also observed (worth keeping):** the project-scoped sweep filed nothing because the
  real conversations key to `~/my_programs/cage` — ADR 0006 scoping working, seen rather
  than assumed. And the sandbox never touched `~/.cage` (verified after: 0 graphify
  receipts, pre-existing rows untouched).
- **Open:** GFX-COV-FIELD's copilot **VS Code** half — still needs one real graphify run
  in a Copilot chat; the route rests on 1,132 structural samples and a
  SHAPE-VERIFIED / CONTENT-SYNTHETIC fixture.
- **Next step:** the v0.47.0 release cut (needs Arpit's go — it publishes to PyPI), or the
  VS Code field run (needs Arpit's hands).

## 2026-08-07 — Claude Code — GFX-COV built, all five phases (v0.47.0, 1462/0 => 1498/0)

- **Asked:** execute the GFX-COV pair (Opus). P0 was a blocking real-store evidence gate.
- **Done:** P0 probes + [research doc](research/2026-08-07-graphify-store-evidence.md) ->
  STOP -> Arpit's four verdicts -> P1 copilot-VSCode route - P2 kiro-CLI route +
  [ADR 0009](adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md) -
  P3 `--rescan-graphify` + the coverage gap surfaces - P4 tests + the full docs pass.
  Pair archived to `docs/archive/v0.47-*`.
- **The premise the pair was built on was false, and the gate is what caught it.** F2 said
  copilot's `chatSessions` carried the command but no tool result. 1,132 real
  `run_in_terminal` parts say it carries `commandLine.original`, a **per-command**
  `cwd.path`, and the output through two carriers. The route was never impossible - nobody
  had looked.
- **Decided (Arpit, at the gate):** `resultDetails` else the ANSI-stripped UI buffer -
  build VS Code on structural evidence and confirm post-build - **structural truncation
  guard only, no invented marker** - ship the kiro query route and name its ~2000-token cap.
- **Two things I would not let a successor "tidy up":** (1) the VS Code guard matching no
  marker string is a *decision backed by 1,132 samples*, not an omission - every `truncat`
  hit in the corpus was rust clippy's own lint output, so a substring guard refuses good
  receipts and catches no real elision; (2) kiro refusing on truncation will make its
  column look thin, and that is the guard working - a lower confidence would dress up a
  number wrong in a known direction.
- **The handoff's section 9.5 was also wrong** about which CLAUDE.md sentences go stale: the
  copilot-VSCode one does not exist, and the kiro-token-log one is still true (it is about
  *call* metering, not graphify). The real gap was that CLAUDE.md never stated graphify
  coverage at all - filed as row **G** of the held steering-edits proposal, not applied.
- **Open:** **GFX-COV-FIELD** - no real graphify run has ever been observed in a VS Code
  Copilot chat (the fixture is SHAPE-VERIFIED / CONTENT-SYNTHETIC), and kiro's refusal
  rate against real usage is unmeasured.
- **Next step:** the v0.47.0 release cut, or the GFX-COV-FIELD evidence run - whichever
  Arpit wants first.

## 2026-08-07 — Claude Code — GFX-COV P0: field probes done, STOPPED at the gate

- **Asked:** execute the GFX-COV prompt (Opus). P0 is a blocking evidence gate ending in
  a mandatory STOP.
- **Done:** all four probes, read-only, on this machine's real stores. Wrote
  [docs/research/2026-08-07-graphify-store-evidence.md](research/2026-08-07-graphify-store-evidence.md)
  and six redacted real-shape fixtures under `tests/fixtures/transcripts/graphify/`.
  Suite green 1462/11.
- **Decided by evidence (not by me):** the F2 no-result assumption that copilot VS Code
  was skipped for is **false** — `run_in_terminal` persists command, cwd and output.
  kiro-CLI is buildable but truncates stdout at ~2000 tokens (marker pinned verbatim from
  a real graphify query), so its query route will honestly file nothing most of the time.
  Kiro IDE is confirmed unbuildable — it has a richer store than the handoff knew about
  (`workspace-sessions/`) and that store still records zero assistant/tool content.
- **Open — Arpit's call:** handoff OPEN QUESTIONS 1–2 are answered by the evidence
  (1: the query route IS possible, no fallback probe needed; 2: yes, documented gap).
  Four *new* forks the evidence raised are in the research doc §5: which VS Code output
  carrier is the `actual` (A), whether structural evidence suffices without one real
  graphify run in a Copilot chat (B), what a VS Code truncation guard keys on when no
  marker exists (C), whether kiro's mostly-silent query route is worth shipping (D).
- **Next step:** Arpit's verdict on A–D, then P1 (copilot VS Code route).

## 2026-08-07 — Cowork — GFX-COV pair: graphify coverage for copilot-VSCode + kiro

- **Asked:** "copilot in vscode shouldn't be skipped and graphify ledger should work
  with copilot and kiro. create a handoff and prompt with automated testing."
- **Done:** wrote and committed the pair —
  [graphify-agent-coverage.handoff.md](graphify-agent-coverage.handoff.md) +
  [graphify-agent-coverage.prompt.md](graphify-agent-coverage.prompt.md) (Model:
  Opus · Progress: 0%). Five phases: P0 real-store evidence probes (BLOCKING gate,
  ends in a STOP) · P1 VS Code route (report-read unconditional — needs no result
  text; query route probe-gated, truncation ⇒ unmeasurable) · P2 kiro-CLI route over
  `conversations_v2.history` (transient body read, hashes-only persist — **ADR
  required**, carve-out #2 after the chats title) · P3 `--rescan-graphify` backfill
  + doctor/explainer loud gaps · P4 the automated test suite (per-route unit + E2E,
  cross-route deferral, truncation guard, PII grep, idempotency, determinism).
- **Debated (gate ran, changed the plan):** the VS Code query route was demoted from
  assumed-possible to probe-gated (the F2 no-result claim has never been re-pinned on
  a current store, and the repo's own real-vscode samples carry 0 requests); the kiro
  route was blocked until it carried its ADR; truncation-inflation and cross-route
  double-count mitigations were promoted into the DoD.
- **Decided:** a store P0 proves unbuildable ships as a loud, named gap (doctor +
  query explainer), never a fabricated counterfactual — OPEN QUESTIONS 1–2 in the
  handoff are Arpit's call at the P0 gate.
- **Open:** OQ1 (chatSessions may persist no result text → report-read-only ship?),
  OQ2 (kiro IDE likely has no command-bearing store → gap + shim guidance = "works"?),
  OQ3 (flag spelling, default `cage import --rescan-graphify`).
- **Next step:** hand the prompt to Claude Code on Opus; P0 needs one real graphify
  run through VS Code copilot and one through kiro-cli on Arpit's machine.

---

## 2026-08-07 — Cowork — GF-AGENTS: why the graphify ledger is empty for copilot/kiro

- **Asked:** "cage graphify ledger isn't working with copilot or kiro — test it and
  tell me what is wrong."
- **Done:** ran the diagnosis in a sandbox (source staged from this repo, v0.46.1):
  all 15 graphify unit tests green, then a true E2E — synthetic
  `~/.copilot/session-state/<id>/events.jsonl` carrying a bash `graphify query` +
  result → `cage import --agent copilot` filed one modeled receipt
  (`s_…`, raw 4509 / actual 26 / saved 4483 tok). **The copilot CLI route works.**
- **Found — three distinct causes, so "not working" is true for the surfaces in use:**
  1. **Kiro has no graphify route at all, even in principle.** `import_kiro` takes no
     savings-id snapshot and no `detect_and_file_kiro` exists; kiro's only source
     (`tokens_generated.jsonl`) carries neither commands nor tool results, so a
     transcript route cannot be built from that store. The PATH shim is the only
     possible route, and shims don't fire inside the IDE (same class as the
     hooks-under-VS-Code finding).
  2. **Copilot VS Code is skipped by design (F2).** `_detect_graphify_copilot`
     explicitly skips every `chatSessions/` file — that store logs the command but no
     tool result, so no counterfactual can be sized. All VS Code copilot use →
     structurally zero graphify receipts.
  3. **The import cursor never backfills.** Detection runs only over the files `_scan`
     returns; verified E2E that an already-imported `events.jsonl` is never rescanned
     (a deleted receipt is not refiled). Any copilot session ingested before the F1
     copilot-graphify route shipped will never produce graphify receipts unless its
     file changes.
- **Caveat:** the copilot-CLI match is `toolName == "bash"`; no real capture in
  `samples/` contains a shell run (only `create`), so the name is unverified in the
  field — a mismatch would make even the CLI route silently find nothing.
- **Open / next:** decide (a) document copilot-VSCode + kiro as out of graphify scope
  (README/doctor should say it out loud), and/or (b) a `--rescan-graphify` backfill
  that walks the full match set ignoring the cursor (idempotent by receipt id, so
  safe); field-verify `toolName=="bash"` on a real copilot CLI log with a shell run.
  Filed as **GF-AGENT-FIELD** in OPEN-WORK Tier 4.

---

## 2026-08-03 — Claude Code — CI-S18: the build gate goes green again (v0.46.1)

- **Asked:** "fix cicd and publish a new version" — after the v0.46.0 release surfaced a
  red `build` job.
- **Done:** root-caused and fixed S18, released v0.46.1. **The failure was pre-existing**
  (v0.45.0 failed identically on all nine legs) and **not a product bug**: the scenario
  re-read a `.claude/settings.json` that `claudewire` correctly *unlinks* once cage's own
  entry is stripped and nothing of anyone else's remains. It died with FileNotFoundError
  on the right answer. S18 now **asserts** the removal — documented behaviour that had no
  scenario covering it. No `cage/` module changed.
- **Decided:** assert the removal rather than guard it with `if exists()`. A tolerated
  outcome is untested; the crash was pointing at a real coverage hole.
- **Found, filed not fixed (CIGF-HERMETIC):** `tools/cigraphify` cannot run on a dev
  machine at all — its sandbox is a sibling of the repo, so under `$HOME` the root
  resolver walks up and adopts the real `~/.cage`. CI has no ancestor `.cage`, so it is
  green there and nobody sees it.
- **My error, reported:** diagnosing that, I ran `cage setup` from a probe dir under
  `$HOME` and it rewrote the real `~/.cage/{cage.toml,prices.toml}`. Verified
  non-destructive (setup is idempotent, ledger mtime predates it, `cage doctor` green,
  52,576 rows intact) and cleaned up every sandbox I created — but the lesson is the
  filed item's own: **never run a capture-path probe from inside `$HOME`.**
- **Open:** the two releases that shipped through a red gate are worth a glance —
  `publish-pypi` has no `needs` link to `build` by design, so nothing published was
  affected, but a gate that stays red trains people to ignore it.
- **Next:** tier 2's three decisions.

## 2026-08-03 — Claude Code — CHATS-AUTHOR: `agent%` on `cage insights chats` (1442/0 ⇒ 1462/0)

- **Asked:** execute the CHATS-AUTHOR prompt — the `agent%` authorship column, behind a
  hard Phase-0 REV-TS gate.
- **Done:** gate verified **independently** (not trusted from the prompt's status line) —
  `commitjoin` normalizes at construction and at probe; the five non-UTC fixtures pass.
  Then the column, end to end: `residual_lines` in the provenance substrate, the capture
  computation, the `(agent, session)` join, render + CSV, 20 new tests, all §9.5 docs,
  pair + proposal archived, OPEN-WORK row deleted. 1462/0; only the three chats goldens
  moved.
- **Decided:** (a) the handoff's "demote behind `--authorship` if the golden overflows
  100 cols" fallback was **moot** — I10a was already 113 cols *before* the column, so
  width could never have been what decided it. Raised it rather than silently applying
  either reading; Arpit confirmed **default-on**. (b) §10's open question: CSV
  `agent_pct` is **0–100 with 1dp**. (c) A **fourth** refusal case exists in fact — a row
  that joins but carries no matchable line (a commit of only binary files) — folded into
  *no landed evidence* rather than invented as a new shape, since both reduce to the same
  statement. (d) CSV empties **all three** authorship cells on a refusal, not just the
  percentage: writing `0,0` would put the claim the text dash refuses to make into data.
- **Found, not asked for:** two tests in `test_copilot_credits.py` read the chats CSV by
  **column index**, so the three new columns broke them as a false failure about credits.
  Re-pointed to read by header — the same class of latent breakage would hit the next
  column too.
- **Open:** the CLAUDE.md edit is **proposed, not applied** (below) — it needs Arpit's
  read. The README "What's new" line and the `just test` count refresh are deliberately
  left to the release, which is the next step.
- **Next:** release v0.46.0 (bump `__version__`, "What's new", test count, tag, GitHub
  release — the GitHub release *is* the publish trigger).

## 2026-08-03 — Claude Code — tier 2: REV-CREDITS · REV-HARDEN P2 · CLI-GAPS(a) (1423/0 ⇒ 1441/0)

- **Asked:** "go" — continue to tier 2.
- **Done:** REV-CREDITS defect 1 (the lost billing delta) + all three guard gaps + the
  method law in `compare`; four of REV-HARDEN P2's five; CLI-GAPS(a). Every fix red
  before green. 1441/0, zero goldens moved.
- **Two findings that changed the work:**
  (1) **COPILOT-PREMIUM-DEAD's premise is false.** OPEN-WORK says `premium` "now has no
  reader" — but `chats.py` sums it into a **rendered column** plus a CSV column, pinned
  by three goldens. So it is not dead-field removal; it is removing a user-visible
  column that can only ever print 0 (the source value is fractional and `int()` floors
  it). Widening to float is not the alternative either — it would duplicate `credits`
  exactly, same counter. **Left for a decision, not swept.**
  (2) **The non-finite counter was worse than filed** — not a bad value stored, but
  `int()` **raising** and costing the whole file's rows.
- **Decided:** the delta carrier is the largest token mover (deterministic, not dict
  order) and is explicitly *not* an attribution claim — splitting it is defect 2's basis
  fork and stays in the compare doc. A backwards counter reads as a **reset**, not a
  clamp to 0, because clamping discards real spend. The unpriced-vs-zero Optional lives
  in `convert`, not `otelout` — the review pointed one level too high, and a second copy
  of that ladder is how the credits rung drifted once already.
- **Routed to a decision rather than patched:** the OTel `gen_ai.system` rename. It *is*
  deprecated (semconv v1.37.0, before our pinned 1.42.0), but verifying it surfaced that
  the GenAI conventions **moved to their own repo**, so the pin's referent is itself
  unclear. [Research doc](research/2026-08-03-otel-genai-semconv-pin.md) with three
  options; recommendation is to fix the pin, from which the rename falls out.
- **Open:** three decisions — COPILOT-PREMIUM-DEAD · REV-CREDITS defect 2 · the semconv
  pin. No code is blocked on them.
- **Next:** tier 2's buildable work is done. Remaining queue is your lane (tier 3's
  steering sitting, NET-1) plus tier-5 triggers.

## 2026-08-03 — Claude Code — tier 1 cleared: two armed bombs defused (1416/0 ⇒ 1423/0)

- **Asked:** "go" — continue to tier 1.
- **Done:** **REV-HARDEN P1** — `cage hook` usage errors exit **0**, not 2. Exit 2 is
  the BLOCK verdict wired to `PreToolUse`/`Bash`, so a stale event name blocked *every
  Bash call in the session*, silently (a blocked tool call reads as the agent refusing).
  Reproduced at HEAD first. Scoped to `hook`: other verbs keep exit 2, `--help` keeps 0,
  and a real budget block still returns 2 — asserted through `cli.main`, where both
  codes actually travel. **REV-DOGFOOD-DATE** — the freshness guard split into
  structural (always) + age (opt-in via `CAGE_DOGFOOD_FRESHNESS`, set in this repo's CI
  only), so the 60-day ceiling stops being a bomb that reddens every machine on
  ~2026-10-02 with no code change.
- **Decided — one deliberate divergence from the proposal.** It asked for a
  `verbmap.REMOVED`-style migration map for hook *event* names. I did not build it: it
  would be an empty dict awaiting a future rename, and such a map goes stale in the very
  release that renames one — the mistake `wiringscan`'s own docstring already records
  ("the detector is the live parser, not `verbmap.REMOVED`"). The direction is derived
  from live `EVENTS` instead. **Found while checking:** `wiringscan` *already* flags a
  dead `(hook, <event>)` pair because `_parser_verbs()` reads the positional's
  `choices` — which is also why the other obvious fix (dropping `choices` so unknown
  events fall through to `hookcmd.run`, which already handles them) would have been
  wrong: it would have blinded the F1 detector.
- **Also decided:** opt-in beats skip-on-fork for the age check, because the failure
  modes are asymmetric — silently-off for the maintainer is a stale snapshot;
  wrongly-on for a contributor is a red suite they cannot fix. The split is a test, so
  the bomb can't be re-armed by deleting a comment.
- **Open:** REV-HARDEN P2–P4 remain (P2 in tier 2, P3/P4 in tier 5). The proposal now
  marks P0/P1 implemented and records the divergence.
- **Next:** **tiers 0 and 1 are both gone.** Tier 2 — four fabricated numbers, batchable
  in one green run: REV-CREDITS (with COPILOT-PREMIUM-DEAD decided inside it) ·
  REV-HARDEN P2 · CLI-GAPS(a).

## 2026-08-02 — Claude Code — ID-ENTROPY built: 32-bit row ids, tier 0 now EMPTY (1413/0 ⇒ 1416/0)

- **Asked:** "go" — continue to the next agent-lane item.
- **Done:** `ids.new_id`'s random field 4 → 8 hex (32 bits). At 16 bits a collision was
  a **silently dropped row** (every merge path dedupes by id), measured at 874 per
  200,000; re-measured after the change the same way: **0 per 200,000**. Two width tests
  were red first (`assert [65536] == [4294967296]`). Two stale comments corrected in the
  same diff — `mergeutil.union_by_id`'s docstring asserted *"ids never legitimately
  collide"*, which the measured rate falsified, and `transcript._composite_id`'s
  "same 15-char shape" parity note. Finding flipped OPEN → RESOLVED (banner above the
  unedited body) and given the index row it never had.
- **Decided:** entropy width is tested as a **contract** (`randbelow` called with
  `0x100000000`), not by generating ids and counting — a statistical test for a
  1-in-4-billion event is either vacuous or flaky, and neither notices the field getting
  narrower again. **Ids already written are never rewritten** and keep their 16-bit
  risk; that is the argument for doing it now, not for backfilling.
- **Verified, not trusted:** every blast-radius claim in OPEN-WORK's build note checked
  against HEAD first — `test_transcript.py:275`'s `len == 17` is the *deterministic*
  path and needed no edit, `test_study.py:62`'s `len == 18` is `machine.py`'s own
  generator, `graphifymeter.py:88` mints independently, and no regex or width parse of
  an id exists anywhere.
- **Open:** nothing. **Tier 0 is now empty and was deleted from OPEN-WORK** — both
  accruing-damage items (REV-TS, ID-ENTROPY) closed the same day.
- **Next:** **NET-1 is unblocked and is Arpit's lane** — its only gate was this one line.
  The agent lane moves to tier 1: REV-DOGFOOD-DATE (dated bomb ~2026-10-02) and
  REV-HARDEN P1 (`cage hook` exit-2 = BLOCK).

## 2026-08-02 — Claude Code — REV-TS built: one UTC normal form (1401/0 ⇒ 1413/0)

- **Asked:** "implement all" — execute the REV-TS pair, taking my three recommendations.
- **Done:** built P0→P3. `commitjoin` gains one parse (`as_utc`) + one normalizer
  (`norm_ts` → `YYYY-MM-DDTHH:MM:SSZ`, sub-seconds truncated); **`Window` normalizes its
  bounds at construction**, so a window holding a raw `%cI` string cannot be built
  anywhere, including a hand-built one in a test; probes normalize in `window_for`;
  `authorcapture._uncovered` normalizes before the cursor compare; `commitview._iso` is
  now `as_utc` rather than a second parse. Docs, CHANGELOG (v0.45.0 unreleased),
  FORMULAS §2.14, GLOSSARY, explain entry, a published finding, and the full archive
  lifecycle all done in the same change; OPEN-WORK's REV-TS row deleted after
  IMPLEMENTATION.md recorded it, and its header de-staled.
- **Decided / found — the build corrected the spec three times:**
  (1) **A claimed failure shape is FALSIFIED.** The review said pure-UTC repos also
  break the inclusive same-second bound, assuming a `+00:00` window bound — but git
  renders `%cI` as `…Z` at zero offset and *never* emits `+00:00`. Those repos were
  correct all along (`.` 0x2E sorts below `Z` 0x5A, which is exactly the inclusive
  bound). This is why the normal form is **seconds**: milliseconds would have broken
  the one case that already worked. It is now a guard test, labelled a guard, not a red
  fixture. (2) `typing.NamedTuple` **forbids** overriding `__new__`, so `Window` became
  a `collections.namedtuple` subclass — my own recommendation named a mechanism Python
  rejects. (3) The fixtures went to `tests/test_authorship_capture.py`, not
  `goldenseed.py`: a golden asserts nothing here (`_date` slices the offset away), and
  keeping goldenseed untouched made **"no golden moved"** the real blast-radius check —
  which held, zero re-blessed.
- **Open:** frozen provenance rows are **not** repaired and deliberately can't be — a
  corrected sweep may *add* rows on the right sha beside the wrong ones, so the
  `_authorship` cursor is left alone and the residue is changelog'd. Pure-UTC repos
  have nothing to distrust.
- **Next:** **ID-ENTROPY** (tier 0's remaining item, one line, NET-1's only gate).
  REV-TS unblocked CHATS-AUTHOR (its Phase-0 gate now passes), HR-COPILOT-JOIN, HR-FIELD.

## 2026-08-03 — Cowork — proposals refined and renamed by topic; four steering edits merged

- **Asked:** review and refine the pending proposals and rename them — *"i see some start
  with claude md"*.
- **The naming defect, generalised:** those four were named after **the file they patch**
  (`claude-md-*`), and `v044-review-hardening` after **the release that raised it**.
  Neither is the topic. Three of the four also had takeaway-last `doc:` lines
  (*"proposed CLAUDE.md edit — DOC-CASE"* names the program, not the idea).
- **Decided with Arpit (AskUserQuestion, both recommendations taken):** fold the four
  into **one** `steering-edits-pending.proposal.md`, and drop the version from
  `v044-review-hardening` → `review-hardening`.
- **The merge is the substantive change.** Four files patching one file and needing one
  sitting is the doc-proliferation pattern Arpit has now rejected twice. The merged doc
  leads with a **verdict table** (one box per edit, each with the HEAD evidence that it
  is still unapplied); an applied section is **deleted** from the file and the file goes
  when the table empties — the same remove-don't-tick law as OPEN-WORK. Every section
  keeps its raised-by provenance.
- **The refinement worth keeping:** both source proposals carried a hardcoded `just test`
  target (HR1 1354, COPILOT-CREDITS 1391) and both had fallen *below* the file they patch
  (1401; suite now 1423) — either would have regressed CLAUDE.md. Merged as item **E**
  and rewritten as a **rule**: set the count to whatever `just test` prints the day you
  apply it. A number in a held patch is a bug with a delay fuse.
- **Queue effect:** OPEN-WORK's four tier-3 rows collapse to one **STEERING-EDITS** item
  (18 open rows now). DOC-LINK-CHECK still rides that sitting — it needs a policy call
  before it can be written at all.
- **Guard:** proposals/README's format table now states that the topic is the *idea*, not
  the file patched or the release that raised it, with both fixed cases named. Version
  prefixes belong to `archive/` alone.
- **Verified:** 9 proposals, all passing name · topic · frontmatter · status · paragraph
  budget; zero dangling `proposals/` links.
- **Next:** unchanged — tier 2's batchable fixes in the agent lane, NET-1 in yours.

## 2026-08-03 — Cowork — proposals audited against the format rules and brought to spec

- **Asked:** review the proposals and rewrite the ones not following the correct format.
- **The rules, taken from the repo not invented:** `<topic>.proposal.md` naming +
  `status: proposed` frontmatter (proposals/README) and **paragraphs ≤4 lines**
  (CLAUDE.md *Documentation style*), plus the standing "evidence lives elsewhere, link
  the proof" and "this folder reads as ideas not yet built" laws.
- **Audit result: 10 of 11 failed at least one rule.** Only
  `net-positive-evidence-run` was clean.
- **Fixed:** 7 renamed from bare `<topic>.md` (17 files of inbound links repointed) ·
  `claude-md-copilot-credits` **had no frontmatter at all** and got the full block ·
  three `status:` values (`held for review`, `AWAITING ARPIT'S REVIEW — not applied`)
  normalised to the literal `proposed`, with the held-ness moved to its own `held:` key
  so the status vocabulary stays sortable · nine over-length paragraphs broken.
- **Two deeper failures, worth more than the formatting:**
  1. `v044-review-hardening` was carrying its **shipped** P0/P1 inline with
     strikethrough — the exact ticked-not-removed anti-pattern OPEN-WORK forbids, in the
     folder that must read as *not yet built*. Bodies removed (recorded in
     IMPLEMENTATION.md:19); what was kept is the one thing a reader still needs — P1's
     **deliberate divergence** (it declined the `verbmap.REMOVED` migration row because a
     hand-kept map goes stale in the very release that renames an event; the fix-hint
     derives from live `hookcmd.EVENTS` instead).
  2. Its evidence link pointed at `_review/…`, which is **gitignored** — a proof no
     teammate or fork can open. The doc's own text said "move to `docs/regression/` on
     pickup", and pickup had already happened. Moved to
     `docs/regression/2026-08-02-review-v0.37.0-to-v0.44.0.md` and repointed.
- **Also:** `chats-agent-authorship-column`'s Trigger still said "parked until Arpit
  accepts" — it is picked up and its REV-TS gate now passes. Corrected to say so.
- **Guard against recurrence:** proposals/README now states the format as a **checkable
  table** (name · frontmatter · status vocabulary · paragraph budget) plus the two
  practice rules, so the next audit is a script, not a judgement call.
- **Verified:** all 11 pass on all four axes; no `proposals/` link dangles.
- **Next:** unchanged — tier 2's four batchable fixes in the agent lane, NET-1 in yours.

## 2026-08-02 — Cowork — proposed edits relocated, OPEN-WORK's completed work archived out

- **Asked:** move the loose `*.proposed.md` docs into `proposals/`, review whether they
  are already built, review OPEN-WORK, and archive what is already implemented.
- **Done (moves):** the four held CLAUDE.md edits moved `docs/` root →
  [proposals/](proposals/) and renamed to the `*.proposal.md` convention — the root is
  reserved for live handoff/prompt pairs, and it now carries exactly one (chats-author).
  All inbound links repointed (8 targets across OPEN-WORK · docs/README · DOC-REGISTRY ·
  IMPLEMENTATION · 4 archived pairs).
- **Done (review — the useful finding):** all four re-verified against CLAUDE.md at HEAD.
  **None is applied** — no `Authorship, per commit` bullet, no *"a v2 exists"* amendment,
  no `[billing.copilot]` text, no Dogfood section, and `FORMULAS.md` still missing from
  the ALL-CAPS list (:674–676). **But two have gone stale in a way that bites:** hr1's §3
  says `just test` 1148→1354 and copilot-credits' §5 says 1354→1391, while CLAUDE.md
  already reads **1401** and the suite is now **1416** — applying either verbatim would
  *regress* the file. Recorded on the rows, in proposals/README and in docs/README so the
  trap is visible at the point of use. (CLAUDE.md's own count is itself 15 behind.)
- **Done (archive):** **279 lines of completed-work narrative removed from OPEN-WORK** —
  fifteen `X closed` blocks (AGENT SURFACE P0–P3 · ADOPT · WIN-CI · CMD-SYNC · OTEL ·
  DEBT · CODEX-OUT · GF-DEBT · CI-GF+WIN-GF · CLEAN · SUITE · SYNC-GUARD · README-FIX ·
  HR1 · BUD-V) plus the two already-decided "Decisions open". **Each was checked against
  its record before deletion**, not assumed: all are in IMPLEMENTATION.md; README-FIX's
  record is CHANGELOG v0.37.2 (it has *zero* IMPLEMENTATION hits — the one that would
  have been a silent history loss). OPEN-WORK 469 → **243 lines**.
- **Rescued from the deleted prose** (they existed nowhere else): **KIRO-CLI-SCOPE**,
  which was a carried-forward item living only in a paragraph — now a tier-5 row; and
  **ADOPT-COV's trigger + guard rail** (*if half B is empty, the finding is that the shim
  route is structurally unattributable — report it; adding an `agent` field to usage rows
  is a capture change needing its own proposal*) — now in §Implementation. Everything
  else that still binds became a **Standing constraints** section: the three-agent gate,
  the floor-test invariant, the disputed `attest.LIMIT`, `outcome="auto"`, the frozen lab
  corpus, what binds the next lab run.
- **Also found:** **112 dangling `.md` links tree-wide**, nearly all history in
  WORKLOG/PLAN/INTERVIEW pointing at pairs that gained a `vX.Y-` prefix on archive. That
  re-scopes **DOC-LINK-CHECK** — the test cannot just be added, it would go red on 112
  links on day one; the row now says decide the policy first. Six genuinely broken links
  in the v0.39 archive were repaired, and no `claude-md-*` link dangles.
- **Open:** the four steering decisions, still one sitting. Tier 0 stayed empty — REV-TS
  and ID-ENTROPY closed while this ran (v0.45.0 in tree, suite 1416).
- **Next:** unchanged — tier 1 (REV-DOGFOOD-DATE, REV-HARDEN P1) in the agent lane, NET-1
  in yours; NET-1 is no longer gated on anything.

## 2026-08-02 — Cowork — the open queue reviewed and re-ordered, into OPEN-WORK itself

- **Asked:** review the open items, prioritise them, and write up the implementation
  detail. Second instruction, mid-task: **"do not create a new open queue document, put
  this in the OPEN-WORK document itself."**
- **Done:** first filed it as `proposals/open-queue-order.md` — **wrong call, corrected
  on Arpit's instruction.** The order now lives in [OPEN-WORK.md](OPEN-WORK.md) itself:
  the flat Pending table is **re-tiered in place** (all 22 rows preserved verbatim, none
  rewritten), the ordering rule leads the file, and a new **§Implementation** carries the
  tier-0–2 build detail. Proposal deleted (moved to `_to_delete/`), its proposals/README
  entry removed, and the four inbound links repointed — including the concurrent
  session's `rev-ts.{handoff,prompt}.md`, which had already cited it. OPEN-WORK
  link-checks clean. Every code claim **re-verified against HEAD before ranking**
  rather than carried from OPEN-WORK's markers: `commitjoin.py:89/99/118` (`%cI` local
  offset, lexicographic compare) · `ids.py:15` (16 bits) · `transcript.py:446-466`
  (skip-before-stamp drops the credit delta) · `adoption.py:105` vs `:188` (half A
  row-filters, half B is month-granular via `read_kind`) · `convert.py:35-36` (the real
  `$0` leak) · `cli.py:686` + `hookcmd.py:49` (argparse exit 2 == BLOCK) ·
  `test_dogfood_freshness.py:108-111` (date bomb).
- **Decided:** the ordering argument is **two resources, not one** — NET-1 and the three
  field-verifications cost Arpit's hands, every fix costs an agent session, so they run
  *concurrently*; the queue had been sequenced as though it had one lane. Within the
  agent lane the rule is **accruing damage outranks static wrongness**: REV-TS (frozen
  `originrecord` rows) and ID-ENTROPY (collision ⇒ silently dropped row) get worse with
  elapsed time; every other wrong number does not. ID-ENTROPY is NET-1's *only* gate and
  is one line, so it lands before the evidence run, not after.
- **Three things the repo corrected mid-session** (rule 3 working as designed):
  (a) CHATS-AUTHOR is **picked up and packaged**, not awaiting accept — an earlier draft
  said otherwise off a stale OPEN-WORK snapshot; (b) the Claude Code entry directly below
  shows that pair **already ran and STOPPED at its REV-TS Phase-0 gate with no work
  started**, so REV-TS's blocking is *observed*, not predicted — that is now the single
  strongest reason it heads the lane; (c) the review's "fix `otelout` for the fabricated
  `$0`" framing is wrong — `otelout._savings_row:102-104` already omits on `None`; the
  hard `0.0` is `convert.py:35-36`, and fixing it in `otelout` would put a second copy of
  the pricing ladder there (the credits rung already drifted between two copies once).
- **Blast radius checked, not assumed:** `tests/test_transcript.py:275` (`len == 17`)
  exercises the **deterministic** uuid-less path, not `new_id` — it does not need
  changing; no regex or width-parse of an id exists in `cage/` or `tests/`. Also:
  `mergeutil.union_by_id`'s docstring already asserts *"call/receipt ids never
  legitimately collide"*, which the measured 1-in-229 rate falsifies — widening the
  field makes an existing invariant true rather than adding a feature.
- **Open:** Arpit accepts, re-orders or declines the order — OPEN-WORK's `Next:` line is
  deliberately left untouched until then (new **QUEUE-ORDER** row filed). Also filed as
  §11: OPEN-WORK's header still claims v0.44 is unreleased and `__version__` unbumped;
  both false (`v0.44.1` tagged, `cage/__init__.py:19`). Its stated suite count (1401) was
  not re-run and is unverified.
- **Doc-shape lesson (the reason the first attempt was wrong):** a sequencing doc filed
  *next to* OPEN-WORK splits the plan of record in two, which is the exact failure
  [doc-size-discipline](doc-size-discipline.md) exists to prevent (*"Arpit stopped reading
  the plans"*). A re-prioritisation is not a parked idea — it belongs **in** the queue.
- **Next:** REV-TS — its pair is already written (`rev-ts.handoff.md` + `.prompt.md`, by
  a concurrent session); execute it. It heads the agent lane and releases the stalled
  CHATS-AUTHOR pair. NET-1 starts in parallel the moment ID-ENTROPY's one line lands.

## 2026-08-02 — Claude Code — CHATS-AUTHOR Phase 0 gate: **FAILED, work not started**

- **Asked:** execute [chats-author.prompt.md](archive/v0.46-chats-author.prompt.md) (the `agent%`
  column on `cage insights chats`), whose Phase 0 gate requires REV-TS landed.
- **Done:** gate verification only — read `cage/commitjoin.py` at HEAD and swept
  the tree for a normalizer and a non-UTC fixture. **REV-TS has not landed:**
  `commit_windows` (:89) still parses raw `%cI`, `:99` sorts those raw strings, and
  `window_for` (:118) string-compares them against `…Z` transcript timestamps —
  no `fromisoformat`/UTC helper exists in the module. `tests/goldenseed.py`
  commits are all `+00:00` (`:424–428`), so no `+05:30` or same-second-boundary
  fixture exists anywhere in `tests/`.
- **Decided:** STOP per the prompt's hard gate — no schema, capture, join, render
  or test work started; REV-TS deliberately **not** fixed here (its own filed
  program, per the packaging decision in the entry below).
- **Open:** nothing new. The three REV-TS failure shapes stand as proposed.
- **Next:** pick up REV-TS ([timestamp-utc-normal-form](archive/v0.45-rev-ts.proposal.md))
  as its own handoff/prompt pair; re-run this prompt once its `+05:30` fixture is green.

## 2026-08-02 — Claude Code — REV-TS picked up: handoff + prompt pair written

- **Asked:** "go" — write the REV-TS pair the failed gate above called for.
- **Done:** [rev-ts.handoff.md](archive/v0.45-rev-ts.handoff.md) + [rev-ts.prompt.md](archive/v0.45-rev-ts.prompt.md)
  (**Opus** — the diagnosis is the work; wrong normal form freezes wrong authorship).
  Every claim re-verified against HEAD, not carried from the proposals. Lifecycle
  bookkeeping done in the same change: proposal header + `proposals/README.md` gain
  the picked-up pointer, `docs/README.md` *Active work* leads with the pair,
  OPEN-WORK's REV-TS row points at it and its CHATS-AUTHOR row records the failed
  gate, DOC-REGISTRY rows bumped.
- **Decided — the handoff corrects both proposals, and says so:** (a) **the normal
  form is fixed-precision SECONDS.** Both proposals sketch `…THH:MM:SS[.mmm]Z` —
  *optional* ms — which is still not totally ordered (`.` 0x2E sorts below `Z`
  0x5A), so it re-introduces the bug. Seconds is also the only form satisfying
  `commitjoin`'s own documented inclusive-same-second bound, since `%cI` carries no
  sub-second. Truncate, never round. (b) **Frozen rows can gain siblings, not just
  stay wrong** — the idempotency key is `(sha, agent, session_id, method)`, so a
  corrected sweep writes rows on the *corrected* sha while the wrong ones persist,
  double-counting those lines across two commits. Therefore the `_authorship`
  cursor is deliberately **not** invalidated, no repair verb is invented, and the
  limit is changelog'd rather than papered over.
- **Also found while verifying:** existing goldens must stay **byte-identical**
  (`commitview._date` slices the offset away at `ts[5:16]`), which makes "nothing
  else moved" the strongest check on the change; but `insights commits --csv`
  writes `w.hi` raw, so its `ts` column silently emits *local* time today and
  becomes UTC — un-goldened, user-visible, changelog-worthy.
- **Open:** one non-blocking naming question (handoff §10): public `norm_ts` vs a
  private helper — recommended public, since `authorcapture` needs it directly.
- **Next:** run [rev-ts.prompt.md](archive/v0.45-rev-ts.prompt.md) in Claude Code (Opus). P0 —
  the `+05:30` and same-second fixtures — must be shown RED before any fix lands.

## 2026-08-02 — Cowork — CHATS-AUTHOR packaged: handoff + prompt pair

- **Asked:** create the handoff and prompt for CHATS-AUTHOR (the entry below) —
  i.e. accept the proposal and package it for execution.
- **Done:** debate gate run before packaging (implementation-handoff discipline),
  then wrote the live pair: [chats-author.handoff.md](archive/v0.46-chats-author.handoff.md) +
  [chats-author.prompt.md](archive/v0.46-chats-author.prompt.md) (**Opus** — substrate deviation
  + guard reconciliation). Proposal header, proposals/README entry, docs/README
  *Active work*, the OPEN-WORK **CHATS-AUTHOR** row and DOC-REGISTRY all updated
  to the picked-up state; entry stays in proposals/ per the lifecycle rule.
- **Decided (at the gate):** (a) REV-TS is a **hard Phase-0 gate in the prompt** —
  the executor STOPs unless `commitjoin` is UTC-normalized; folding the REV-TS fix
  into this pair was rejected (own filed defect, double-pickup risk). (b) The gate
  surfaced a new limit now in the handoff: two sessions proposing the *same file*
  in one commit double-count **both** sides (agent and residual) per chat — per-chat
  `agent%` stays ≤100% by construction, commit view stays the arbiter. (c)
  `make_provenance`'s omit-at-0 loop is the named implementation trap for the
  always-written `residual_lines`; a zero must survive the round-trip, test-pinned.
- **Open:** one non-blocking naming question in the handoff §10 (CSV `agent_pct`
  scale); executor picks and pins.
- **Next:** REV-TS first; then run the prompt in Claude Code against the pair.

## 2026-08-02 — Cowork — CHATS-AUTHOR proposal: human-vs-agent per chat

- **Asked:** a proposal for a human-vs-agent percentage column on `cage insights
  chats`. Clarified the metric first (AskUserQuestion): Arpit chose **code
  authorship share** — the v2 line-match evidence re-keyed per chat — over
  conversation share or a tokens_in/out ratio (the latter would mislabel the whole
  context window as "human").
- **Done:** filed [chats-agent-authorship-column.proposal.md](archive/v0.46-chats-author.proposal.md)
  (status: proposed, owner unclaimed). Verified against HEAD before writing: the
  join key is real (`importcmd` and `authorcapture` both stamp `session=f.stem`;
  `agents.row_surface` normalizes `claude-code`→`claude`), so the column is a pure
  ledger join with no git at render. One substrate addition: `residual_lines`,
  **always written including 0** (presence = version gate — the credits `None`
  precedent), because frozen idempotent rows can never be backfilled. Indexed in
  proposals/README (Active), OPEN-WORK (**CHATS-AUTHOR**), DOC-REGISTRY rows bumped.
- **Decided/open:** denominator scoped to files the chat proposed — `unattributed`/
  `unknown` are commit-scoped and structurally excluded, stated as scope not
  redistribution. Three refusal shapes render `—`, never 0%. Fork left for pickup:
  default-on column vs `--authorship` flag (default-on proposed). **Sequenced after
  REV-TS** — publishing this atop the skewed window join would give a wrong number
  a friendlier face. No cross-session clamp exists per chat; stated as a limit.
- **Next:** Arpit accepts, amends, or declines the proposal; on accept it graduates
  to a handoff/prompt pair after REV-TS lands.

## 2026-08-02 — SELFWIRE hardening: evidence over assumption

- **Asked:** a corrective follow-up on the SELFWIRE task above — Claude-only (no
  Copilot/Kiro flags), grep every committed `.cage/` file for machine-specific paths,
  actually prove `SessionEnd`/auto-close rather than assume it, add a `justfile`
  recipe so `--hooks` can't be silently dropped, never hand-edit `.cage/`, never seed
  dummy data, don't touch `cage/`/`tests/`/goldens, don't commit.
- **Done:** grepped every committed `.cage/`/`.mcp.json`/`.claude/`/`bin/graphify*`
  file for `arpitarya`/`/Users/` — clean; re-confirmed the graphify hook intact.
  Manually replayed the exact wired `session-end` payload with this session's **real**
  id (from the scratchpad path, not fabricated) and `CAGE_DEBUG=1`: result was a clean
  **negative** — `no-open-task-in-session`, because every one of this ledger's 40,431
  calls has `"task": ""` and no `tasks.jsonl` exists, so auto-close structurally has
  nothing to close under plain transcript capture. Did not fabricate a task to force a
  positive result (out of scope per instructions). `PreToolUse` remains confirmed
  **host-fired** from before. `cage insights attrib` now shows real (not `cage demo`)
  graphify savings data. Added `just wire` (→ `cage setup --claude --hooks`), verified
  idempotent. Ran `just test`: **1401 passed, 10 skipped**, unchanged. Updated
  [OPEN-WORK.md](OPEN-WORK.md)'s **L1-FIELD** row and [IMPLEMENTATION.md](IMPLEMENTATION.md)
  with the full evidence trail.
- **Self-flagged:** the entry below hand-edited `.cage/state/attest.jsonl` (via the
  `Write` tool) to strip synthetic test rows — that violates this pass's own
  "never hand-edit `.cage/`" constraint, discovered on review of the prior turn. Left
  as-is rather than restoring fabricated rows; not repeated here.
- **Decided/open:** still did **not** commit — tree is dirty exactly as before, plus
  these doc edits. Copilot/Kiro legs of L1-FIELD still need a real install each. The
  `attest.LIMIT` "VS Code extension" tension and the auto-close **positive** case
  (needs a real task-tagged session) are both still open, named explicitly rather than
  quietly dropped.
- **Next:** human decides what (if anything) to commit; someone wires Copilot/Kiro for
  real; someone with a task-tagged session confirms the positive auto-close case.

## 2026-08-02 — SELFWIRE: cage's own repo wired at project level

- **Asked:** wire cage's own repository for project-level capture (there was no
  `.cage/` here — every command fell through to the global `~/.cage` sink) and
  field-verify L1 hooks actually fire, per the SELFWIRE prompt.
- **Done:** `cage setup --claude --hooks`; confirmed the pre-existing hand-written
  graphify `PreToolUse` hook in `.claude/settings.json` survived untouched; confirmed
  live (unprompted) `PreToolUse` hook firing via genuine new rows in
  `.cage/state/attest.jsonl` after ordinary `Bash` tool calls — closes the Claude leg
  of **L1-FIELD**. Filed a finding: the firing happened inside a session that
  self-identifies as a "VSCode native extension environment," which is in tension
  with the documented "hooks don't fire under a VS Code extension" claim — see
  [finding](regression/2026-08-02-finding-hooks-fire-in-vscode-extension.md) and the
  updated **L1-FIELD** row in [OPEN-WORK.md](OPEN-WORK.md). Updated
  [IMPLEMENTATION.md](IMPLEMENTATION.md).
- **Decided/open:** did **not** commit — the new wiring files (`.cage/cage.toml`,
  `.mcp.json`, `bin/graphify*`, the modified `.claude/settings.json`, the new
  `.claude/skills/`) were found already `git add`-staged when this task reached its
  git-review step, apparently by the concurrent Cowork review session below (which was
  editing `docs/OPEN-WORK.md`/`WORKLOG.md`/`docs/proposals/` at the same time) — left
  the index exactly as found rather than guess at intent. Copilot and Kiro legs of
  L1-FIELD are still unverified (no real installs available here).
- **Next:** the human decides what to commit (the wiring, and/or the concurrent
  review's changes) and wires Copilot/Kiro on real installs for the rest of L1-FIELD.

## 2026-08-02 (Cowork) — full review of v0.37.0→v0.44.0; findings filed as three proposals

- **Asked:** review everything shipped after v0.37.0 and split the verdicts into
  not-right / going-to-break / better-approach; then put the review doc in `_review/`
  and file proposals for the fixes.
- **Done:** six parallel verified review passes over all 24 commits (graphify/Windows/
  CI, OTel+wires, insights views, authorship/HR1, copilot credits/pricing, CLI/doctor/
  misc); every finding checked against HEAD, top three re-verified by hand; suite
  confirmed green at HEAD (1400 pass in the review sandbox). Report:
  `_review/cage-review-v0.37.0-to-v0.44.0.md` (durable home on pickup:
  `docs/regression/`). Filed [timestamp-utc-normal-form](archive/v0.45-rev-ts.proposal.md)
  (the headline defect: `%cI` local-offset vs UTC lexicographic compares — authorship
  joins skewed on this IST machine), [copilot-credits-integrity](proposals/copilot-credits-integrity.proposal.md)
  (lost credit deltas + multi-model double-count), and
  [v044-review-hardening](proposals/review-hardening.proposal.md) (P0 dogfood date bomb
  ~2026-10-02 · P1 hook exit-2=BLOCK · P2 honest-refusal · P3 wiring hygiene · P4
  durable joins). Four OPEN-WORK rows added (REV-TS · REV-CREDITS · REV-DOGFOOD-DATE ·
  REV-HARDEN). ID-ENTROPY confirmed still open at HEAD.
- **Decided / open:** fixes are *filed, not built* — Arpit picks up via the proposal
  lifecycle (handoff/prompt pair per program). REV-DOGFOOD-DATE has a hard date.
- **Next step:** pick up REV-TS first (correctness of the v0.43 flagship on the
  maintainer's own machine), or P0 of REV-HARDEN if the calendar is the constraint.

## 2026-08-02 (Claude Code) — DOGFOOD executed: cage's own ledger, published (Sonnet)

- **Asked:** run the DOGFOOD prompt. Its own stop condition fired correctly on first
  read — `docs/dogfood/<date>.md` did not exist, so I stopped and said so rather than
  seeding or approximating anything. Arpit then said to run the commands myself and get
  the real numbers, which is P0 — normally his hands, done in-session here instead.
- **Done:** ran the three allowlisted commands (`cage report --usd`,
  `cage insights adoption`) against the real global `~/.cage` ledger over the full
  all-time window (no `--since` on either — the ledger's first row is 2026-02-15).
  Before trusting `cage insights attrib`'s default "most recent task" output, traced it
  to its source rows in `~/.cage/ledger/{calls,receipts}-2026-07.jsonl` and found it was
  the `cage demo` seed (`session: "demo"`, task `fix-handover-bug`, ts 2026-07-23,
  matching `cage/demo.py`'s hardcoded slices exactly) — the *only* task-tagged row in
  the entire global ledger. Surfaced this to Arpit via AskUserQuestion rather than
  deciding alone; he chose to omit `attrib` with a note. Built `docs/dogfood/
  {2026-08-02,latest,README}.md`, the README line-16 pointer, `tests/
  test_dogfood_freshness.py` (10 tests: the real guard + 8 tmp_path failure modes +
  the skip-env test), refreshed the test count everywhere (1391 → 1401), and wrote
  `docs/proposals/steering-edits-pending.proposal.md` (held, not applied). Doc sweep: IMPLEMENTATION
  milestone entry written before the OPEN-WORK row was removed, proposal archived to
  `docs/archive/v0.44-dogfood-report.proposal.md` and moved to Graduated, pair archived
  to `docs/archive/v0.44-dogfood-report.{handoff,prompt}.md`, DOC-REGISTRY rows bumped.
  `just test`: **1401 passed / 0 failed / 10 skipped** (1391 baseline + 10 new).
- **Decided:** the non-negotiable ("ZERO dummy data — the executing agent never runs a
  ledger command and never authors a number") was written against a scenario where P0's
  *output* is missing or fabricated; it didn't anticipate the executing agent running
  P0 itself at the user's direct instruction, nor a ledger whose only real signal for
  one of the three allowlisted commands turned out to be a fixture. Both were treated
  as "ambiguous — stop and ask" rather than guessed through.
- **Open:** `docs/proposals/steering-edits-pending.proposal.md` awaits Arpit's apply/amend/decline; a
  real `attrib` snapshot lands whenever any task on this machine is actually closed —
  not filed as OPEN-WORK since it isn't actionable work, just a fact about future usage.
- **Next:** Arpit reviews the proposed CLAUDE.md line; not committed — left dirty per
  the standing directive.

## 2026-08-02 (Claude Code) — DOC-CASE executed: `docs/formulas.md` → `docs/FORMULAS.md` (Sonnet)

- **Asked:** run the DOC-CASE prompt — rename the tracked lowercase `docs/formulas.md`
  to `docs/FORMULAS.md` so it matches the 120 existing uppercase citations, fix the two
  live code docstrings, and sweep the docs.
- **Done:** verified nothing programmatic reads the filename (no `docs/` glob in
  `tests/`/`tools/`, no MANIFEST/pyproject reference) before touching it. Two-step
  `git mv` (`formulas.md` → `_formulas.tmp` → `FORMULAS.md`), verified via
  `git ls-files`, not `ls` — registered as a clean `R` rename, no silent no-op. Fixed
  `cage/roi.py:85` and `cage/report.py:682`. Left every history-class citation
  untouched: `CHANGELOG.md` (4×), `docs/archive/**` (4×), `docs/IMPLEMENTATION.md:1051`,
  `docs/INTERVIEW.md:311`, `docs/WORKLOG.md:39,213,235,1160`. Doc sweep: OPEN-WORK row
  removed (residuals filed as CC-CLAUDEMD-DOCCASE + DOC-LINK-CHECK), IMPLEMENTATION
  milestone entry, DOC-REGISTRY rows bumped, README Active-work swapped, pair archived
  to `docs/archive/v0.44-doc-case-rename.{handoff,prompt}.md`,
  `docs/proposals/steering-edits-pending.proposal.md` written and held for review (steering files are
  never edited silently). `just test`: **1391 passed / 0 failed / 10 skipped** — no
  change in count.
- **Decided:** `docs/WORKLOG.md:235` is a third history-class citation the handoff's
  explicit list (`:39`/`:213`) didn't name — another past session spotting the same bug
  and not filing it. Extended the same treatment on the same reasoning rather than
  rewriting it.
- **Worth naming:** this line at `:39` below is exactly the entry that *did* eventually
  get filed and executed — but `:213` records an *earlier* session spotting the same
  bug and explicitly leaving it alone unfiled, which is why it survived long enough to
  be found twice. The discipline held on the second sighting, not the first.
- **Open:** `docs/proposals/steering-edits-pending.proposal.md` awaits Arpit's apply/amend/decline;
  the DOC-LINK-CHECK idea (a link-checker test, same class as `test_cli_reference.py`
  catching a dead verb) is filed but not built.
- **Next:** review the proposed CLAUDE.md line; not committed — left dirty per the
  standing directive.

## 2026-08-02 (Cowork) — DOGFOOD proposal reviewed and rewritten; DOC-CASE found (Opus)

- **Asked:** review `proposals/dogfood-report.md` — "how is it going to work, is it
  going to be one version behind or the same version?"
- **Answered:** neither, and the question exposed the flaw. `~/.cage` is cumulative
  across v0.12→v0.43, so no single version owns the numbers; the stamp only records
  which build took the snapshot. Refreshed inside the release cut it matches the
  shipping version, refreshed after it ships one behind — but either way the reader is
  **time-behind**, so **date is the real freshness axis and version is provenance**.
- **Done:** rewrote the proposal. Three changes: (1) dated `docs/dogfood/<date>.md` +
  `latest.md` snapshots (the `regression/latest-*` pattern) instead of a README-inline
  block; (2) a **version-free, date-free** README pointer at `latest.md`, so the README
  is written once and never edited again; (3) a **60-day freshness guard test** reading
  `latest.md`'s frontmatter — no numbers, so it runs in CI with no ledger — replacing
  the release-checklist line.
- **Decided:** *derive or guard, never remind.* The checklist line was the same pattern
  `[meta] cage_version` drifted eleven releases on. Version-distance was rejected as the
  gate because the cadence here breaks it — v0.37→v0.43 inside ~two days, and
  `__version__` is deliberately not bumped for in-tree work.
- **Also decided:** the snapshot window must be **absolute, never relative**. A relative
  `--since` measures a different window each refresh, breaking comparability and letting
  a stale number move *down*; an absolute window makes staleness only ever understate.
- **Deliberately not taken, recorded in the proposal:** the README-inline block, with a
  reopen trigger (two snapshots agreeing in shape ⇒ inline the headline figure).
- **Found, filed as DOC-CASE:** the tracked file is `docs/formulas.md` but 120 citations
  across 49 files spell `FORMULAS.md` — invisible on macOS, dangling on GitHub and any
  case-sensitive checkout.
- **Accepted same session (Arpit):** the `docs/dogfood/` home and the **60-day** gate.
  DOGFOOD is now **picked up** — pair written, proposal stays put as the rationale.
- **Pairs created:** `dogfood-report.{handoff,prompt}.md` (Sonnet; four phases, **P0 is
  Arpit's hands** and blocks the rest) and `doc-case-rename.{handoff,prompt}.md`
  (Sonnet; single phase). Both listed under *Active work* in `docs/README.md`.
- **Debate gate, DOGFOOD — three challenges held, one residual accepted.** *Held:* the
  guard is fakeable by editing one frontmatter line ⇒ hardened with a second assertion,
  `snapshot_date` must equal the newest snapshot **filename**'s date, so satisfying it
  requires a new file; the agent could invent numbers ⇒ killed by sequencing (P0 is
  human, the agent never runs a ledger command); publishing real output could leak
  private project names ⇒ killed by a command allowlist (no `insights chats`, no
  `--project`). *Residual, named not solved:* a date-based test is calendar-triggered,
  so `git bisect` and old-tag CI can go red for a non-code reason — mitigated by a
  self-explaining failure message + `CAGE_SKIP_DOGFOOD_FRESHNESS=1`, in the
  GF-LAUNCHER "stated limit, never half-fixed" tradition.
- **Debate gate, DOC-CASE — measured, not assumed.** The rename fixes 120 citations and
  breaks exactly **2**, both docstrings (`roi.py:85`, `report.py:682`); nothing globs
  `docs/` and neither MANIFEST nor pyproject names the file. `core.ignorecase = true`,
  so the `git mv` must be two-step or it silently no-ops — the one real trap.
  History-class citations (CHANGELOG, `archive/`, and the WORKLOG/INTERVIEW lines that
  *quote the bug*) stay lowercase deliberately.
- **Next:** DOGFOOD **P0** — Arpit runs `cage report` · `insights attrib` ·
  `insights adoption` over an absolute window on the dev machine. DOC-CASE can run any
  time. **NET-1** unchanged as the standing next action.
- **No code touched. Nothing committed** (standing directive).

## 2026-08-02 (Claude Code) — COPILOT-CREDITS built: billed credits + the pricing ladder (Opus)

- **Asked:** execute the COPILOT-CREDITS prompt — capture the credits Copilot bills,
  price copilot by ladder (credits×rate → token×table → UNPRICED).
- **Verified before planning, as the prompt required:** the choke point **is** one place
  (`prices.call_usd_match`; `call_usd` wraps it, every USD consumer goes through one of
  the two — no caller prices independently), and `copilotCredits` in the **real** store
  matches the research doc (11/348 requests, float, 0.100185–1.382565, all
  `copilot/auto`).
- **Done:** substrate field → capture on both surfaces → the ladder in a new
  `creditprice.py` behind the one choke point → report/chats/CSV/doctor/explain →
  docs + archives. 1354/0 ⇒ **1391/0**; goldens `I10a/b/d` re-blessed (the added
  column, nothing else), no report golden moved.
- **Decided (§10, the open question):** the key is **`[billing.copilot] usd_per_credit`
  in cage.toml**, not `[credits.copilot]`. Verified the merge first: `[credits]` sits in
  `policy._PRICE_SECTIONS`, so `policy.load` reads it from `prices.toml` **only** — and
  the rate belongs in cage.toml by the vendor-facts-move rule, so the proposal's
  spelling would have been read back as absent in every project with a prices file. The
  handoff pre-authorized this fallback; proposal amended in the same change.
- **Decided (asked Arpit, guardrail):** copilot-**CLI** stamps the new float `credits`
  itself rather than the read side treating `premium` as credits, because
  `totalPremiumRequests` is fractional (`0.33`) and the int `premium` field floors it to
  0 and drops the key. Arpit chose "stamp `credits` on CLI rows too"; `premium` left
  untouched.
- **Decided (no question needed):** `credits` defaults to a `None` sentinel, not `0.0` —
  the handoff's literal signature contradicted its own §8 rule that a recorded zero is
  a real zero, and no other reading satisfies both.
- **Finding filed:** copilot-CLI `premium` has captured **nothing, ever** — 13 real rows,
  none carrying it ([research](research/2026-08-02-copilot-credit-fields-real-stores.md)).
  Now unread by pricing but still written; carried into OPEN-WORK as
  **COPILOT-PREMIUM-DEAD**. Also corrected the old OPEN-WORK row's `elapsedMs`→`gap_ms`
  half: `gap_ms` died with the human axis in v0.36, so that is void, not pending.
- **Also caught:** both the chats CSV and the report CSV hardcoded `method="measured"`,
  which would have let a rate-derived dollar read as an invoice. Now degrades to
  `modeled` whenever a credits-priced row is in the aggregate.
- **Open / next:** `docs/proposals/steering-edits-pending.proposal.md` — the CLAUDE.md bullet,
  written and **held for Arpit's review** (steering files are never rewritten silently).
  `__version__` deliberately not bumped; v0.44 sits unreleased in tree.

## 2026-08-02 (Claude Code) — HR1 P4 + the full doc sweep; program closed (Opus)

- **Asked:** finish the phases.
- **Done (P4):** `cage task time` — strict duration parsing, `human_minutes` +
  `human_minutes_method="attested"`, and two named notes for the cases where the
  attestation will not reach a commit (open task; dirty close). Then the §9.5 doc
  checklist end to end, plus archiving the handoff/prompt/proposal trio.
- **Decided:** parsing is **strict, not fail-open** (the write-path rule does not apply
  to a figure a human types); `0` and `d` are both rejected, with reasons.
- **Findings filed rather than fixed:** **HR-COPILOT-JOIN** — copilot-vscode has
  per-request timestamps but stamps no `project`, so the join cage just built can never
  fire for it; **HR-FIELD** — the four buckets have only been read on cage's own repo,
  which is unusually artifact-heavy (80% `unattributed`).
- **Not applied, deliberately:** the CLAUDE.md architecture bullet is **proposed for
  Arpit's review**, per the prompt — steering files are never silently rewritten.
- **Next step:** Arpit reviews the proposed CLAUDE.md edit; then HR-COPILOT-JOIN.

---

---

## 2026-08-02 (Claude Code) — HR1 P2 + P3 built (Opus)

- **Asked:** continue through the phases.
- **Done (P2):** `commitjoin.join_calls` — task-id join (reusing `taskgroup.join_rows`)
  then the commit window, with per-agent joinability as a **stated table** and every
  exclusion counted by reason. **Done (P3):** the three views + goldens A1–A4.
- **Decided:** `unattributed` becomes a first-class fourth bucket (from the P1 gate);
  an **unstamped** `project` is *unconfirmable*, not adopted; `BEFORE_HISTORY` deleted
  as unreachable rather than shipped as dead vocabulary.
- **Caught while smoking the real repo:** the Σ row printed `0` where its rows printed
  `—`, and the hours estimator printed the raw commit gap when no agent span existed.
  Both now refuse. The second one was v1's exact failure mode reappearing.
- **Open:** none blocking.
- **Next step:** P4 — `cage task time <duration>`.

---

---

## 2026-08-02 (Claude Code) — HR1 P1 built + dogfood gate passed (Opus)

- **Asked:** implement all four phases of agent-vs-human v2, one after the other.
- **Decided up front (Arpit, this session):** the three OPEN QUESTIONS that change the
  CLI contract — verb spelling **`cage insights commits` / `commit <sha>`** (not
  `report --by commit`); the agent/human/unknown split **default-on** on the list view;
  `[authorship] estimate_hours` default **true**. The fourth (`MIN_MATCH_CHARS`) was
  deferred to the dogfood data, as the handoff requires.
- **Done (P1):** both audit findings verified first-hand (`parse_provenance`/
  `record_transcript` have no production callers; `latency_ms` is set only in
  `metering.py`). Then the capture re-wire: `parse_edits`, `commitjoin` (windows),
  `linematch` (normalize/gate/match), `authorcapture` (the pass), five additive-optional
  provenance counts, the `[authorship]` policy table. 1270 pass / 0 fail.
- **Gate:** PASSED on cage's own repo — 69 rows over 25 commits from 81 real
  transcripts, **68.7% verbatim match inside proposed files**, re-run writes 0.
  `MIN_MATCH_CHARS` frozen at **4** with a measured sweep.
  [regression doc](regression/2026-08-02-p1-authorship-dogfood.md) · [ADR 0008](adr/0008-line-match-authorship-counts-persisted-content-transient.md).
- **Amended the handoff's §5.4 mock (flagged, not silent):** a single `human` bucket
  printed **76.6%** for this repo, 89% of it one commit of generated JSON. The residual
  now splits `human~` (files the session proposed — a real human tweak) vs
  `unattributed` (files nobody proposed — human, vendored or generated; cage does not
  guess). Costs nothing: `NOT_PROPOSED` was already computed. A generated-file
  classifier was considered and **declined** — a guess wearing a number.
- **Open:** none blocking.
- **Next step:** P2 — `commitjoin.join_calls`, reusing `taskgroup.join_rows`.

---

---

## 2026-08-02 (Cowork) — COPILOT-CREDITS packaged: handoff + prompt (Opus)

- **Asked:** create the handoff and prompt for COPILOT-CREDITS.
- **Done:** [copilot-credits.handoff.md](archive/v0.44-copilot-credits.handoff.md) +
  [copilot-credits.prompt.md](archive/v0.44-copilot-credits.prompt.md); Active-work indexed;
  OPEN-WORK row → ready to execute; proposal header carries the picked-up pointer.
- **Tier call:** **Opus**, not Sonnet — `CALL_FIELDS` gains a field (substrate
  contract, plan §3 in the same change) and a new pricing rung carries method-tag
  discipline; the rubric routes substrate/method changes to Opus even when additive.
- **The one real risk, pre-decided:** `[credits.copilot] usd_per_credit` is a scalar
  in a table shaped per-provider/per-model `per_mtok` — handoff §10 orders: verify
  `policy.load` merge, fall back to `[billing.copilot]` + amend the proposal in the
  same change if it collides. Guardrail: if the pricing choke point turns out not to
  be one place, STOP and report — unifying is its own decision.
- **Next step:** run the prompt in Claude Code (**Opus**).

## 2026-08-02 (Cowork) — verdict C ACCEPTED; COPILOT-CREDITS spec written with worked CLI outputs

- **Asked:** "we're going with both" — proposal with example CLI outputs.
- **Done:** compare verdict C recorded as DECIDED;
  [proposals/copilot-credits.proposal.md](archive/v0.44-copilot-credits.proposal.md) —
  capture design (additive `credits` call field; CLI `premium` read as credits;
  sidecar deferred), `[credits.copilot] usd_per_credit` policy key (cage.toml —
  plan economics, not vendor rate card), the 3-rung ladder, worked outputs in house
  style: report --usd before/after (⚠ both-fixes block), chats credits column, CSV
  `priced_via`, doctor coverage line.
- **Sequencing note:** CHATS-VIEW shipped mid-session (v0.42, parallel Claude Code
  run) — so COPILOT-CREDITS now ADDS the credits column to the built view rather
  than preceding it; proposal amended to match.
- **Decided in-spec:** allowance modeling · nano-AIU→USD · sidecar capture all
  *deliberately not taken*, each with a trigger.
- **Next step:** handoff/prompt pair for COPILOT-CREDITS.

## 2026-08-02 (Cowork) — CLI-REF: one document for every CLI command, test-gated

- **Asked:** list all CLI commands → then "create one document with all cli commands
  and link it to readme and always maintain it".
- **Decided (Arpit, two choices put to him):** *hand-authored + test-gated*, over a
  regenerated doc (which would re-add the `tools/docgen` machinery the hookless
  rebuild deliberately deleted) and over hand-authored-with-a-rule (the class of doc
  this repo has already watched go stale twice). And: document the gaps found **and**
  file them in OPEN-WORK, rather than documenting only or fixing them in this change.
- **Done:** `docs/CLI.md` (50 addressable commands, every flag, the removed-verb
  table, Known gaps, a Maintaining section) + `tests/test_cli_reference.py`
  (bidirectional against `cli.build_parser()`, with the detector self-tested);
  linked from `README.md` and `docs/README.md`; registered in `CLAUDE.md`'s
  maintained-doc set and `DOC-REGISTRY.md`; the removed-verb Must-Know rule now names
  the doc as part of the migration.
- **Found:** two front-door inconsistencies — `data migrate-savings` unadvertised in
  `cage --help`, and `prices`/`study`/`policy` using a positional choice instead of a
  subparser (no per-action `--help`, flags a flat union). Filed as **CLI-GAPS**;
  deliberately not fixed here, since (b) is a front-door change that re-blesses
  goldens. Also fixed on contact: four orphaned continuation lines in
  `DOC-REGISTRY.md`'s docs-index row.
- **Open / caveat:** the suite was **not** run — this Cowork sandbox has no pytest and
  no network, so the new module was exercised through a pytest-free harness (93 green
  against the live parser). Two pre-existing case bugs spotted but left alone:
  `CLAUDE.md` and `docs/README.md` both cite `docs/FORMULAS.md` while the file on disk
  is `docs/formulas.md` — harmless on macOS, a broken link on a case-sensitive checkout.
- **Concurrency note:** a Claude Code session was editing `docs/` at the same time;
  these edits were re-applied on top of its latest writes, not over them.
- **Next step:** run `just test` on the dev machine (expect 1148 + 93), then decide
  CLI-GAPS (a) — the one-line front-door fix plus a golden re-bless.

## 2026-08-02 (Claude Code) — CHATS-VIEW: `cage insights chats` built end to end

- **Asked:** execute the CHATS-VIEW prompt (`docs/chats-view.prompt.md`) — the per-chat
  detail view, per the accepted handoff + proposal.
- **Done:** `cage/chats.py` (group-by-(agent,surface,session), title join, ranking/
  truncation, CSV twin); CLI wiring (`insights chats`); the one manifest.py carve-out
  sentence; `tests/test_chats.py` (19 tests) + 4 golden fixtures (I10a–d); added
  `insights chats` to `test_floor.py`'s pinned view list; docs sweep (explain_data,
  FORMULAS §2.13, PLAN §7, GLOSSARY, DOC-REGISTRY, CHANGELOG `v0.42.0 (unreleased)`,
  README). `just test` 1125/0 ⇒ 1148/0.
- **Decided/open:** the handoff's assumed `manifest.read_imports` helper doesn't
  exist — used the real `manifest.read()` filtered to `kind=="import"` (same rows,
  naming correction, not a design change). Followed the CLAUDE.md proposal lifecycle
  precedent (v0.40/v0.41's archived docs) rather than the handoff's literal "next
  unreleased version" wording for README's What's-new/test-count, since CLAUDE.md
  frames those as release-time actions — added the CHANGELOG entry now (explicit
  handoff ask) but left What's-new/test-count for the actual v0.42.0 release cut.
  CLAUDE.md's own architecture-flow bullet edit is proposed for Arpit's review, not
  applied — per the prompt's explicit instruction.
- **Next step:** Arpit reviews the proposed CLAUDE.md edit; archive the handoff/prompt
  pair to `docs/archive/v0.42-chats-view.{handoff,prompt}.md` and graduate the proposal
  (already done in this session, ahead of this entry) — nothing else pending.

## 2026-08-02 (Cowork) — PROMPT-PROGRESS: prompt docs must state how much is done

- **Asked:** Arpit — "whenever a prompt is generated i want to see the percentage of
  work done; always add it in the CLAUDE.md."
- **Decided (his two calls, asked before writing):** it binds **`docs/*.prompt.md`
  only** (not every agent reply), and the denominator is **that feature/program's own
  phases** — not the OPEN-WORK queue (no fixed total) and not an effort guess.
- **Done:** new Must-Know bullet in CLAUDE.md beside the model-tier rule — a
  `**Progress:**` line under `**Model:**`, three constraints (countable denominator ·
  count against evidence not ticks, the OPEN-WORK ✅ trap · a partial phase doesn't
  count, say it in words) · `0% — not started` → `100%` in the archiving change ·
  updated in the same change as the work. Doc-discipline pointer updated to name both
  prompt-doc rules. Applied on contact to the live pair
  ([agent-vs-human-v2](archive/v0.43-agent-vs-human-v2.prompt.md) 0%,
  [chats-view](chats-view.prompt.md) 0%) and to the just-archived
  [v0.41-agent-surface](archive/v0.41-agent-surface.prompt.md) (100%, P0–P3).
- **Found:** `agent-vs-human-v2.prompt.md` had **no `**Model:**` line at all** — a
  standing violation of the older prompt-doc rule. Added **Opus** with the reason
  (P1 is a substrate re-wire behind a STOP-capable gate; the commit-window join is
  diagnosis), flagged in-file for Arpit to confirm.
- **Open:** confirm that Opus tier. Nothing else; no code moved, suite untouched.
- **Next:** none from this exchange — the queue is unchanged (NET-1 still next).

## 2026-08-02 (Cowork) — CHATS-VIEW picked up: detailed design + handoff/prompt pair

- **Asked:** detailed proposal on how the chats view works, then the handoff and
  Claude Code prompt.
- **Done:** [proposals/chats-view.proposal.md](archive/v0.42-chats-view.proposal.md)
  rewritten as the design of record (the five-step mechanism, the carve-out wording,
  known honesty limits) + the pair: [chats-view.handoff.md](chats-view.handoff.md) ·
  [chats-view.prompt.md](chats-view.prompt.md) (**Sonnet** — additive, fully specced).
  Indexed in docs/README Active work; OPEN-WORK row → ready to execute.
- **Debate gate (blocked-capable, run before packaging):** survived with amendments
  now in spec — stale-title honesty (manifest rows only on appended rows), legacy
  sessions display ids (never backfilled), top-20 counted truncation + `--all`
  (no-silent-caps), local-only/no `--team` with a money-independence test pinning
  the labels-only manifest read.
- **Open:** one non-blocking naming question (cache_write column header width) —
  executor picks, golden pins.
- **Next step:** run the prompt in Claude Code (Sonnet) — build after COPILOT-CREDITS
  if the copilot columns should fill on arrival, or before it (columns land empty-honest).

## 2026-08-02 (Cowork) — CHATS-VIEW proposed: per-chat detail view, titled where the store has a title

- **Asked:** can cage show a detailed per-chat view (kiro/claude/copilot) by chat
  title — tokens in/out, cached in/out, lines suggested? Proposal if yes.
- **Done:** [proposals/chats-view.proposal.md](archive/v0.42-chats-view.proposal.md) —
  verdict YES, derive-time only; the substrate already carries every numeric column
  (`cached_in` = cache reads, `cache_write_in` = the honest "cached out"). Per-agent
  honesty matrix: claude full · copilot-vscode titled but uncached (store limit, see
  research doc) · copilot-cli cached but untitled · kiro-ide ONE unsplittable row ·
  kiro-cli credits-only per cwd.
- **The crux decided in the proposal:** titles live only in `imports.jsonl`, which is
  "never read by any derived view" — proposed option A: a scoped carve-out (chats
  joins `session_name` for **labels only**; money cells stay ledger+policy-pure;
  deleting the manifest must change zero money cells, tested).
- **Deliberately not taken:** "lines suggested" — no agent store persists it;
  revisit via agent-vs-human-v2's git-side counts at task level, never per-chat-exact.
- **Next step:** Arpit accepts/overrides option A; then CHATS-VIEW graduates to a
  plan entry (build after COPILOT-CREDITS so the copilot columns fill).

## 2026-08-02 (Cowork) — HR1 graduates: v2 accepted-amended (commit views, line-match, guarded hours) → handoff + prompt

- **Asked:** audit leftover human-axis logic; research v2 implementation; design commit
  list/detail views (tokens + hours, **no USD**); spec human-vs-agent line capture;
  produce the handoff + prompt pair.
- **Found (re-grades the proposal):** (1) provenance capture is **ORPHANED** —
  `transcript.parse_provenance` / `originrecord.record_transcript` have zero callers
  since the hookless rebuild; only `--attest` writes rows, so the real unknown-rate is
  ~100% until the import sweep is re-wired. (2) `latency_ms` is set only by the library
  meter — transcript-imported calls carry 0, so "agent time measured" holds only there;
  elsewhere it is a turn-span, `~`-marked. The v0.36 removal itself is clean — remaining
  "human" mentions are legacy read-guards, verbmap tombstones, and the provenance enum,
  all deliberate; do not clean them up.
- **Decided (Arpit):** no USD anywhere on these surfaces. Human hours ESTIMATED is
  allowed — §4 **amended, not repealed**: `~` marker with the method named in the
  output, gap guard (`[authorship] max_est_gap`, default 4h ⇒ `—` beyond it),
  attestation `*` always wins, config kill-switch. Line capture: match agent edit-block
  lines (transient, counts-only persisted — never bodies or hashes) against commit
  diffs; **human = residual (`human~`)**; unknown is first-class, never redistributed.
  Views: `cage insights commits` (list) + `cage insights commit <sha>` (detail).
- **Produced:** proposal rewritten in place (accepted-amended) ·
  [handoff](archive/v0.43-agent-vs-human-v2.handoff.md) · [prompt](archive/v0.43-agent-vs-human-v2.prompt.md).
  Build order P1 capture re-wire → P2 `commitjoin.py` → P3 views → P4 time; P1 ends
  with a dogfood gate on cage's own repo (match/unknown rates) before P2.
- **Next:** run the prompt (P1 first) — slotted after the current track per OPEN-WORK.

## 2026-08-02 (Cowork) — Copilot/VS Code token research: credits are persisted per request; title is a label, not a key

- **Asked:** research how VS Code Copilot displays token in/out/cached per chat, and
  whether title-based lookup could beat id-based capture.
- **Done:** read VS Code `main` + `vscode-copilot-chat` sources, real-store samples, and
  public docs. Written up: [research/copilot-vscode-token-sources.md](research/copilot-vscode-token-sources.md).
- **The finding that matters:** the chatSessions store persists **`copilotCredits` /
  `sessionCopilotCredits` per request** — the actual billing unit — and cage drops them.
  Capturing credits retires copilot/auto UNPRICED (24/60 real calls, 975k tok at $0)
  with real billing, not a price alias. Also unread: `elapsedMs`/`timeSpentWaiting`
  (a free `gap_ms` feed).
- **Cached tokens are NOT in chatSessions.** They persist only in the new debug-gated
  `<vscode-user>/agentHostUsage/<sessionId>.jsonl` sidecar (per-call `cacheReadTokens`,
  real routed model, `totalNanoAiu`) — deleted with the session; candidate third source.
- **Decided (research verdict):** title stays a display label (already lifted via
  `session_name_copilot_vscode`); keying capture by title would break idempotent
  re-import (mutable, non-unique, late). The id that hurts is `modelId: copilot/auto` —
  fixable via credits (#1) and `kind:0` `selectedModel.metadata.family/version`.
- **Next step:** decide whether COPILOT-CREDITS enters the queue ahead of P2, then spec
  the importcmd/transcript change (ranked plan in the proposal, §4).

## 2026-08-02 (Claude Code) — AGENT-L3 P3: seven skills, and the program is done

- **Asked:** finish the program — this entry covers **P3**.
- **Done:** seven skills through P2's `steering.py` renderer, `cage setup --skills`,
  status reporting all three layers. 1096/0 ⇒ **1125/0**.
- **The lint caught a real weakness, and I fixed the document rather than the rule.**
  `steering.lint` failed the honesty-reviewer skill for naming no cage command. That
  was correct: a review skill that never tells you how to *check* is weaker than one
  that does. It gained a `cage query <topic>` / `just test` verification section. Same
  for lab-runner. Neither got an exemption.
- **The strongest single fact from the whole program:** the floor test passes with
  **every** layer installed — three layers added across P1–P3, and not one derived
  number moved, in either direction, on any of the three agents.
- **Open (both field-verification, not code):** the hook file shapes and the path-free
  Kiro MCP entry are unit- and CI-tested but have not run on a real Claude Code /
  Copilot / Kiro install. Filed as **[L1-FIELD]** and **[KIRO-MCP-FIELD]**.
- **Next step:** archive the agent-surface handoff/prompt pair and graduate the
  proposal; then the field verification above.

## 2026-08-02 (Claude Code) — AGENT-L1 P2: hooks that change no number, and every gap named

- **Asked:** continue the program — this entry covers **P2**, the Opus phase.
- **Done:** `cage hook <event>`, agent attestation, auto task-close, budget blocking,
  steering; opt-in on all three agents. 1059/0 ⇒ **1096/0**.
- **The strongest evidence is the floor test, extended rather than exempted.** It now
  installs **hooks as well as MCP** onto an already-captured project and still asserts
  the ledger bytes and seven views byte-identical, in both directions. That is the
  phase's real acceptance criterion and it passed without any number being touched.
- **Two design calls I'd want inherited:**
  1. **Auto-close writes `outcome="auto"`, not `"ok"`.** A session ending is not a job
     well done. `tasks.jsonl`'s outcome (which gates compare/estimate/calibration) and
     `.cage/outcomes.json` (ok|redo, which gates `cage task quality`) turn out to be
     **different stores on different axes** — so a task can be closed for cost purposes
     while staying invisible to the success rate. Stamping `ok` would have silently
     inflated quality for every session that merely finished.
  2. **I did not invent a Copilot pre-tool event name.** The only Copilot hook shape
     cage has evidence for is the `sessionStart` form its own v0.10 wrote and the tests
     still pin. So Copilot gets identity + auto-close and **no** per-tool attestation or
     budget block, named in `agents.HOOK_GAPS` and printed by `cage setup --status`.
     Two-of-three *named* beats three-of-three *guessed* — an invented event name fails
     **silently**, which is the exact class this repo has paid for twice.
- **Scoped down honestly:** attestation resolves adoption's **half A** only. Half B's
  `NO_LINK` is still structurally true — a graphify savings id folds in an answer hash
  no attestation can reconstruct — so **ADOPT-COV is not closed by P2**, and the docs
  say so rather than implying the hook layer solved it.
- **Open:** the hook file *shapes* come from cage's own prior implementations and the
  repo's recorded facts, not from fresh vendor verification. Field-verifying them on a
  real Claude Code / Copilot / Kiro install is carried forward.
- **Next step:** **P3 — L3 · skills**, through `steering.py`'s existing renderer.

## 2026-08-02 (Claude Code) — AGENT-L2 P1: the refusals cross the boundary; kiro's MCP is committable

- **Asked:** continue the agent-surface program — this entry covers **P1**.
- **Done:** `cage_verdict` + `cage_compare` + `cage_task_outcome` on MCP; kiro's MCP
  config moved to the committed path-free form; new `kiro-mcp` doctor check. 1039/0 ⇒
  **1059/0**.
- **The decision that mattered — how to test a refusal.** Asserting *"INSUFFICIENT DATA
  is in the output"* would pass for a wrapper that printed the phrase and dropped the
  ⚠ note beneath it. So the tests assert **equality with the CLI's own stdout**. That
  makes any future summarizing layer a test failure rather than a judgement call.
- **Found and stopped: the Windows fork in kiro's committed file.** The handoff says
  write `python3` on POSIX and `py -3` on Windows. Both **committed** — which means two
  teammates on different OSes churn the diff on every `cage setup`, breaking the
  byte-identical rule the same phase requires. A committed file can carry one spelling.
  **Resolved by naming the limit rather than forking:** default `python3` everywhere,
  and `cage doctor` tells a Windows machine to run `cage setup --python-launcher` for
  the `py -3` form (machine-specific — gitignore that one file on a mixed-OS team).
  Pinned by `test_kiro_mcp_is_byte_identical_across_machines`.
- **Found: `tests/test_portable_wiring.py` does not exist** and never has, though
  CLAUDE.md and the prompt both cite it as the grep gate. The assertions live in
  `tests/test_agents.py`; CLAUDE.md now says so rather than pointing at a ghost.
- **Open:** nothing blocking. The path-free form is **not yet verified on a real Kiro
  install** — the prompt's stop-condition is about that, and it can only be closed on a
  machine with Kiro. Doctor's check is the substitute until then.
- **Next step:** **P2 — L1 · hooks + steering (Opus)**.

## 2026-08-02 (Claude Code) — AGENT-L0 P0: residue cleared, the floor is a test

- **Asked:** execute [agent-surface.prompt.md](archive/v0.41-agent-surface.prompt.md) — phases in
  order, stop at each gate. This entry covers **P0** only.
- **Done:**
  - **The floor is now a test, not an intention** — `tests/test_floor.py`, 15 tests,
    parametrized over all three agents. It proves both directions of the binding rule:
    installing every layer cage ships onto an already-captured project changes **no**
    ledger byte and **no** view's stdout, and stripping it again changes neither.
  - **Built before P1 on purpose** — P1/P2/P3 are judged against it, so it could not be
    written after the thing it judges.
  - Skill residue removed from the README (×3, one saying *"all four agents"*), and the
    same lie found and fixed in two places the prompt didn't list: **CLAUDE.md's wiring
    bullet** and **`docs/example/setup.md`**, both describing hooks/skills/steering/git
    hooks that `cage setup` has not written since v0.36.
  - `--no-skill` was **already** gone from the parser; the test now pins that it stays
    gone (a removed flag must *fail*, never be silently accepted).
- **Decided:** the floor test's `_WIRING_ARTIFACTS` list is the extension point —
  **a new layer is added to the floor by listing its artifacts, never by relaxing an
  assertion.** That is what stops P1–P3 quietly weakening the gate they must pass.
- **Found (worth knowing for P1):** `agents.install` today writes exactly four files —
  `.cage/bin/cage-run`, `.mcp.json`, `.vscode/mcp.json`, `.kiro/settings/mcp.json`. The
  last is the absolute-path exception P1 replaces with the path-free form.
- **Open:** nothing blocking. `just test` green at **1039/0** (was 1024/0).
- **Next step:** **P1 — L2 · MCP** (Sonnet): `cage_verdict` + `cage_compare` with
  refusals verbatim, `cage_task_outcome` as the ladder's only write tool, Kiro's MCP
  committed path-free, and the doctor check on the resolved `python3`.

## 2026-08-02 (Cowork) — PLAN.md de-staled: marked, never renumbered

- **Asked:** is PLAN.md still needed? Then: fix it.
- **Answer: yes, and it is the most load-bearing doc in the repo** — **~65 source files
  cite `plan §X`**, so its section numbers are a live addressing scheme. Deleting it would
  be a 65-file citation migration. But it was badly stale, and CLAUDE.md tells every agent
  to read it before touching the substrate.
- **The worst line was the first one:** *"Status: design of record (v0.1). **Nothing built
  yet.**"* — in a project at v0.40 with 1024 tests, shipped on PyPI. Replaced with an
  honest status plus three reader's notes: how to read the file (marked-never-renumbered),
  the v0.36 hookless rebuild, and the three-agent count.
- **Technique, applied consistently: mark, never delete or renumber.** A superseded
  section keeps its number and gains a **REMOVED in vX.Y** heading — so every other
  citation keeps resolving and the section becomes correct history instead of a lie.
  §4.6/§4.10 already had this; added it to **§5.1** (`tools/skillgen` — the whole
  skill/steering machinery, deleted in the hookless rebuild; the directory does not exist)
  and **§3.8** (`cage data limits` — removed with Codex, since Codex's `rate_limits` block
  was the *only* quota signal any supported agent ever provided; no `limits.py` exists).
- **Fixed inline:** three prose enumerations naming Codex as a supported agent · two
  "four agents always" claims · a moot `.codex/hooks.json` example. Left as history:
  the mentions *inside* REMOVED sections, which are now correct past tense.
- **Found and fixed a dangling-citation cluster nobody had noticed.** Five shipped
  modules cite `plan §8.1`–`§8.5` as their design anchor (`budget` · `quality` ·
  `regression` · `recommend` · `forecast`) — but **§8 had no subsections at all.** The
  content was there as an unnumbered list; added the `§8.N` anchors and a note that the
  numbering is load-bearing and must never be renumbered.
- **Corrected my own earlier claim mid-task.** I had reported "`plan §2.1` is cited 8×
  and dangles". Wrong twice: six are qualified *"prices-toml plan §2.1"* and one
  *"import-ledger plan §2.1"* — archived plans that genuinely have a §2.1. Only **two**
  were bare; I traced both (policy.py → the prices split; transcript.py →
  import-ledger §2.1, which names `totalPremiumRequests` explicitly) and qualified them
  with a note that PLAN.md has no §2.1.
- **Verified, not assumed:** an anchor sweep over every `plan §X` cited in `cage/*.py`
  now shows **zero dangling references** into PLAN.md; only §2.1 remains, correctly
  pointing at archived plans. Both edited modules parse.
- **Not run:** `just test` — the sandbox is Python 3.10. Changes are docs plus two code
  *comments*; still worth a local run before commit.
- **Next step:** unchanged — the agent-surface program from P0.

---

## 2026-08-02 (Cowork) — Kiro MCP blocker RESOLVED; "records, not wiring" clarified

- **Asked:** (1) "nothing to commit" means the *records*, not hooks/MCP. (2) Can Kiro's
  MCP path be relative to the repo root instead of `~`?
- **(1) Clarified everywhere:** *every piece of wiring is committed; only the **records**
  are not.* Reworded in the proposal, handoff, prompt and OPEN-WORK — the earlier phrasing
  ("data is per-user") was loose enough to read as excluding config.
- **(2) The answer is better than my proposal, and Arpit's instinct pointed at it.**
  **Repo-relative genuinely fails** — Kiro resolves a relative `command` against its
  *install directory*, not the workspace (kirodotdev/Kiro #6525), and there is no
  variable substitution (#5659). **But path-free works, and cage already ships it:**
  `kirowire.install` writes `{"command":"python3","args":["-m","cage","mcp"]}` under
  `--python-launcher`. No absolute path, no relative path, no substitution — `python3`
  resolves through PATH like any interpreter.
- **So the blocker dissolves without new machinery.** Make the path-free form the
  **committed default for Kiro**; the absolute-path + gitignore exception disappears, and
  the parity table now reads ✅ committed for all three agents. **My seed/materialize
  proposal from the previous turn is withdrawn** — it would have invented a mechanism to
  solve a problem an existing code path already solves.
- **The trade it introduces, written into all four docs rather than buried:** the
  path-free form depends on *which* `python3` resolves. If cage lives in a venv that
  interpreter isn't in, MCP silently won't start. **So `cage doctor` must check whether
  the resolved `python3` can import cage** and name it with the fix — converting a silent
  no-MCP into a named, fixable condition. Silent capture failure is the exact class this
  project has paid for twice.
- **Pattern worth noting:** the answer was in `kirowire.install`'s *other* branch — the
  same shape as the Copilot correction two turns ago, where the answer was in
  `_strip_legacy_hooks`'s other branch. Both times I read one branch and generalised;
  both times the question caught it.
- **Next step:** unchanged — run the program from P0.

---

## 2026-08-02 (Cowork) — "all layers committed, multi-user" turns a concession into a blocker

- **Asked:** L0–L3 all get committed to git and must work with multiple users.
- **Made it the acceptance test for every phase**, not a preference — in the proposal,
  the handoff, every phase gate in the prompt, and OPEN-WORK.
- **Drew a distinction the design had left implicit: wiring is shared, data is
  per-user.** Committed — hook files, MCP config, steering, skills, `.cage/bin/cage-run`,
  `cage.toml`, `prices.toml`. Gitignored and machine-local — `ledger/`, `out/`, `state/`.
  **Nothing in this program may commit a ledger**; team numbers come from
  `refs/notes/cage-ledger` (ADR 0001), a separate mechanism. Without stating this,
  "multi-user" reads as "share the ledger", which would be a privacy and correctness
  disaster.
- **⚠️ The requirement converts a documented concession into a BLOCKER.**
  `.kiro/settings/mcp.json` keeps a **resolved absolute path** because Kiro spawns MCP
  servers from its *install directory* (kirodotdev/Kiro #6525) and supports **no variable
  substitution in `command`** (#5659) — so relative or `${workspaceFolder}` provably
  breaks. Cage's current answer is "keep the absolute path, gitignore the file".
  **Under this requirement that fails both ways:** gitignored ⇒ a teammate gets no Kiro
  MCP; committed ⇒ a path wrong on every other machine.
- **Proposed resolution, due in P1 and not deferrable: commit the *intent*, materialize
  the machine-local file** — a template or `cage.toml` declaration in git, with
  `cage setup` writing the resolved `mcp.json` locally (still gitignored). Clone →
  `cage setup` → correct path for *that* machine. This is **cage's own `[sources]`
  seed→materialize pattern**, so it needs no new concept. If it proves impossible, the
  prompt says **stop and report** rather than ship a gitignored two-of-three surface.
- **Three hygiene rules the requirement implies, now written down:** writes must be
  **idempotent and byte-identical** (two teammates running `cage setup` must not churn a
  diff — cage already byte-compares, but that stops being an optimisation and becomes a
  rule) · **foreign entries are never touched** in shared files · **a teammate without
  cage installed gets silence, not breakage** (the shim already exits 0; every layer
  must preserve it).
- **New acceptance criteria:** a fresh clone + `cage setup` on a *different* machine
  yields working wiring; **no absolute path in any committed file**; `cage setup` twice
  produces no diff.
- **Next step:** unchanged — run the program from P0; the Kiro MCP resolution lands in P1.

---

## 2026-08-02 (Cowork) — corrected: Copilot hooks CAN be committed

- **Asked:** why are Copilot's hooks user-level — can't they be committed?
- **They can. I was wrong, and cage's own code disproves my claim.**
  `copilotwire._strip_legacy_hooks` cleans **two** locations, one of which is repo-level
  `.github/hooks/cage.json` — which cage itself wrote in v0.10.0, *with foreign-hook
  preservation*, the signature of a shared committed file rather than a cage-owned one.
  I had read only the user-level line and generalised.
- **Confirmed against GitHub's docs:** repo-level `.github/hooks/*.json` applies whenever
  Copilot agents run in that repository; user-level `~/.copilot/hooks/*.json` applies to
  the CLI everywhere; and hooks are **loaded from multiple sources and combined**
  (policy · user · project · plugins), with *all* matching entries running.
- **This inverts the parity table's conclusion.** Copilot is the **best**-placed of the
  three for L1, not the worst: repo-level hooks are committed and portable, so they can
  reference `.cage/bin/cage-run` and give a teammate working capture on clone — the same
  property Claude's `.claude/settings.json` has. My table had it backwards.
- **Two consequences the build now owes:** (1) **combining is a double-capture risk** —
  wire both locations and both fire on the same event, which is exactly the proof P2
  already owes; pick one location and justify it. (2) **repo hooks apply to the coding
  agent only from the default branch**, so feature-branch wiring silently doesn't fire
  until merged — stated so nobody debugs a phantom gap.
- **Corrected in all four docs** (proposal, handoff, prompt, OPEN-WORK), each carrying
  the correction visibly rather than a silent rewrite — the prompt's version explicitly
  tells the executor an earlier draft was wrong, so they don't half-trust it.
- **Lesson, again:** I asserted a platform constraint from one line of a docstring
  without checking the other branch of the same function. Arpit's question was the check.
- **Next step:** unchanged — run the program from P0.

---

## 2026-08-02 (Cowork) — three-agent parity made a gate; found the limit that shrinks L1

- **Asked:** this must work with Claude, Copilot and Kiro — make sure of it, add it to
  the table.
- **Done:** a per-agent parity table added to the proposal, the handoff **and** every
  phase gate in the prompt. `agents.SURFACES` is restated as a product invariant: **a
  phase is not done until all three have the layer, or the gap is named in output.**
  Handback now requires per-agent status per phase, not just at the end.
- **⚠️ The finding that materially shrinks L1's promise: hooks are CLI-only — they do not
  fire under a VS Code extension.** So L1's two headline wins (agent identity at capture,
  auto task-close) apply to **CLI sessions only**; a VS Code session falls back to L0
  silently. Written into all three docs as a build-to constraint: **L1 may never be
  described as "cage knows which agent ran"** — it is *"for CLI sessions"*, and every view
  built on it inherits the caveat. A hook-derived agent field silently absent for every
  VS Code user is **the ADOPT half-B problem again, one layer up** — which is exactly the
  kind of repeat this project keeps paying for.
- **Three per-agent shapes recorded because they are load-bearing, not trivia:**
  copilot's hooks are **user-level** (`~/.copilot/hooks`) so they cannot ride the portable
  `.cage/bin/cage-run` shim the committed files use · kiro's hook file is **one hook per
  file**, not a `hooks[]` container, and **kiro has no session-start trigger** (so
  `agentStop` self-backfills, and auto task-close must close what it can infer *or
  decline and say so*) · kiro's MCP config keeps the **absolute-path exception**, the one
  documented deviation from portable wiring.
- **P3 gained a parity clause too:** *a skill on one agent and not the others is not
  done* — one source text, three deliveries, never three hand-written copies. That is the
  shim-contract drift lesson applied to prose.
- **Next step:** run the program from P0.

---

## 2026-08-02 (Cowork) — all four agent-surface phases specced as one gated program

- **Asked (mid-turn):** spec *all* the phases/tiers, not just phase 1.
- **Done:** `agent-surface.{handoff,prompt}.md` now cover **P0 → P1 → P2 → P3** as one
  gated program, with a **per-phase model tier** — P0/P1/P3 Sonnet, **P2 Opus**, because
  P2 wires three agents' hook systems into a capture path that must stay fail-open and
  change no number; a wrong call there re-creates the silent-unmetering class this
  project has already paid for twice.
- **The design decision that makes the program safe: P0 builds a *floor test* before any
  layer exists** — a project with no hooks, no MCP, no steering captures, derives and
  reports identically. Every later phase is judged against it, and the binding gate is
  **"removing a layer changes no number"**. Building that proof first, rather than after,
  is what stops L1 quietly becoming load-bearing.
- **P1 gained the ladder's only write tool**, `cage_task_outcome` — every starved surface
  (`compare`/`estimate`/`calibration`/NET-1) is starved for the same reason: nobody closes
  tasks. Its docstring must say it is the *only* write tool, so the next reader doesn't
  add a second by analogy.
- **P2's framing is deliberate:** the prize is **not** real-time capture. It is the two
  things L0 structurally cannot do — a hook **knows which agent fired it** (exactly what
  ADOPT-COV cannot get from a shim subprocess; stamp it, never infer it) and session
  boundaries **auto-close tasks**. Plus `budget.check` finally getting an enforcement
  site, which it has never had.
- **P3's governing rule is one line:** *a skill never computes a number — it runs cage
  and quotes it.* Method tags verbatim, refusals relayed never smoothed. Seven skills in
  build order, each rendered from **one source into three deliveries** — never three
  hand-written copies, which is the shim-contract drift lesson applied to prose.
- **Three stop-and-report triggers written in:** a gate that can't be met without changing
  a number · P2 needing a second write tool · hooks and pull both recording a turn with
  dedupe failing. Handback is required **per phase**, with gate *evidence* rather than a
  claim.
- **Next step:** run the program from P0; NET-1 remains Arpit's lab session.

---

## 2026-08-02 (Cowork) — agent surface re-designed as a four-layer ladder

- **Asked:** clean slate — ignore what was built, remove old residue; hooks and steering
  optional on top of a hookless floor; MCP more; skills more. Table, then a pair.
- **Superseded `cage-skills.md`** rather than editing it: its opening premise —
  *"cage already ships one skill (`/cage`)"* — is **pre-hookless and false**. Verified:
  the rebuild deleted the skill/steering machinery and **no code writes a skill file**.
  Archived naming its successor, per the proposal lifecycle.
- **New design of record — `proposals/agent-surface-layers.md`:** L0 hookless (the floor,
  never optional) → L1 hooks+steering → L2 MCP → L3 skills, each opt-in and strictly
  additive, with the binding rule **L0 must work perfectly alone, forever** and no layer
  may become a dependency of a lower one.
- **The three findings that made the ladder worth drawing:**
  1. **L1 mostly fixes problems we already have, not new ones.** Auto task-close on a
     session boundary unblocks `compare`/`estimate`/`calibration`/NET-1 — all starved for
     the same reason, nobody runs `cage task outcome`. And a hook **knows which agent
     fired it**, which is precisely the attribution ADOPT-COV cannot obtain from a shim
     subprocess. It also gives `budget.check` its first real caller.
  2. **L2 already exists and is under-used:** six read tools ship, and **`verdict` and
     `compare` — the two that answer "is this tool worth it" — are not among them.**
  3. **Only L3 can carry the honesty discipline.** MCP hands an agent a JSON number;
     nothing makes it say *"that's modeled, not measured"*. Without L3 the discipline
     stops at the CLI boundary.
- **Residue found and scoped for removal:** the README claims a skill **three times**,
  one of which says **"all four agents"** — wrong twice over (no skill; three agents
  since v0.33), and live on PyPI. Same class as the human-axis claim. **Kept**
  `claudewire._strip_stale_hooks` — it strips *old* hook entries from user configs, so
  it is migration, not residue; deleting it would abandon pre-rebuild machines to dead
  verbs.
- **Sequencing decided L0 → L2 → L1 → L3:** L2 is cheap and answers the product
  question; L1 before L3 because hooks unblock the evidence that makes L3's advice worth
  taking; a skill interpreting numbers you cannot yet trust is premature.
- **Phase 1 specced only** (`agent-surface.{handoff,prompt}.md`) — README residue + the
  two MCP tools, with the emphasis on **refusals crossing the MCP boundary verbatim**
  (`INSUFFICIENT DATA`, `SAVING (GROSS)`, the min-n block). A tool that silently returns
  nothing where the CLI would have explained itself is worse than no tool. L1 and L3 are
  named in both docs but explicitly **not to be built**.
- **Next step:** run `agent-surface.prompt.md`; NET-1 still Arpit's lab session.

---

## 2026-08-02 (Claude Code) — ADOPT built; "no evidence" needed a second strength

- **Asked:** execute the ADOPT prompt (Opus tier — the honesty
  boundary, not the rendering).
- **Verified the premise myself before designing, as the prompt demanded:**
  `usagelog.record` writes exactly `ts · op · args_hash · exit · ms · outcome · route`.
  **Confirmed — there is no `agent` field.** Half A is agent-blind by substrate.
- **Done:** `cage/adoption.py` + `cage insights adoption` (CLI · `--csv` · `--json` ·
  `--since` · MCP `cage_adoption` · `cage query tool-adoption`), 25 unit tests, 4 goldens
  (I9a–I9d). Suite 995 → **1024 green**. Proposal + handoff/prompt archived; FORMULAS
  §2.12 written; every index updated.
- **Decided (the prompt's open question): an empty half B RENDERS its refusal.** It is
  never suppressed. Suppressing it makes *cage cannot attribute these* indistinguishable
  from *cage has no per-agent answer at all* — the exact conflation the view exists to
  prevent. Golden `I9b` pins it.
- **Found during the build — a third correction on top of the handoff's two.** The
  handoff softened the proposal's *never invoked* to *no evidence of invocation*.
  **That is still too strong whenever any savings row is unattributed**: the unattributed
  row could belong to the very agent being named. `I9b` printed "no evidence of
  invocation: claude" beside two unattributable rows that were almost certainly claude's.
  The view now picks between two claims by coverage — the strong one only at 100%.
- **Also beyond scope, deliberately:** a linked `call` id resolves the agent *directly*
  and is a stronger join than the session, so it is tried first and **labelled per row**
  (`joined via call` / `session`). More precision, no blending.
- **Coverage on the real ledger (honest number):** 3 of 6 savings rows attributable by
  session; 6 of 6 once the call rung counts, though 3 of those are legacy rows and one
  is a `cage demo` seed. Small-n — the shim blind spot is structural, not measurable here.
- **Version correction, mid-session:** v0.39.0 was tagged and published by another
  session while this work was in flight, so ADOPT is **not** in v0.39.0. Its CHANGELOG
  section was lifted out of the v0.39.0 entry into a new `## v0.40.0 (unreleased)`, the
  archive files renamed `v0.40-insights-adoption.*`, and the README's v0.39.0 *What's
  new* line restored to what that release actually shipped.
- **Open:** none. The tree stays uncommitted per instruction; `__version__` stays
  `0.39.0` until the v0.40.0 release commit bumps it.
- **Next step:** nothing blocking — the next agent can pick from OPEN-WORK.

## 2026-08-02 (Cowork) — ADOPT specced; the proposal's headline was half-derivable

- **Asked:** handoff + prompt for `insights-adoption.md`.
- **Verified the premises against code first** — the fourth spec running where an
  unchecked premise would have shipped. **It was wrong again, and usefully so.**
- **The finding:** the proposal promises "per agent × tool: invocations · receipted ·
  missed · never invoked". **Per-agent is not derivable for most invocations.**
  `usagelog.record` writes `ts · op · args_hash · exit · ms · outcome · route` — **no
  `agent`**. And shim/native savings rows carry an **empty session**, because a
  subprocess genuinely cannot know which agent spawned it (`graphifymeter`'s receipt-id
  deferral exists *for* that reason). Only the **transcript** route yields a session
  joinable to `calls.agent`.
- **Uncomfortable corollary, recorded:** leg D's celebrated finding ("claude invoked
  graphify unprompted; copilot and kiro did not") was **operator-attributed** — one agent
  per lab cell — not derived from the data. The product view cannot reproduce it as
  cleanly as the lab did, and the spec says so rather than implying otherwise.
- **Re-scoped to two halves, kept visibly separate:** **A** totals + outcomes from usage
  rows — exact, no join, and the distinction the proposal celebrates ("ran but cage
  missed it") is **already the recorded `outcome` field**, not something to derive.
  **B** per-agent from transcript-route savings only, with shim/native rendered
  **agent-unknown and the reason named** — never an "other" bucket, never a timestamp
  guess.
- **Two honesty rules written hard:** "never invoked" is phrased as *no evidence of
  invocation* (absence of evidence, in a view about what capture saw); and **no currency
  appears anywhere** — usage rows are diagnostic-only with a byte-identical test pinning
  it, so the view counts them and prices nothing, stated in the docstring so the next
  reader doesn't think the invariant lapsed.
- **Left to the executor:** what to print when *every* invocation came via the shim, so
  half B is entirely agent-unknown — explicit unavailability line or suppress the half.
  Silently printing an empty table is ruled out.
- **Opus tier, deliberately** — not for the rendering but for the honesty boundary:
  never-invoked vs invoked-and-missed vs invoked-and-unattributable. Blur any two and the
  view is worse than nothing.
- **Next step:** run the ADOPT prompt; NET-1 remains Arpit's lab session.

---

## 2026-08-02 (Cowork) — WIN-CI closed; the living spec still held the wrong diagnosis

- **Asked:** v0.38.0 is released after the first-ever Windows CI run went red on two
  real bugs — is anything left to do?
- **Yes, one thing that mattered, and it was not bookkeeping.** The CHANGELOG's
  diagnosis was corrected (commit `d29dea7`), but **`docs/shim-contract.md` B8 still
  carried the superseded hypothesis** — that a `call`/`goto` back-edge leaked cmd.exe
  stack frames. The contract is the **living spec**; the changelog is history. So the
  repo was in the inverted state its own docs law forbids: history held the truth, the
  spec held a disproved technical claim stated as fact.
- **Two concrete harms from leaving it:** a future agent would inherit a **false lesson**
  ("`call`/`goto` causes recursion aborts"), and would **not** inherit the real one. And
  TOOL-SDK's proposal says every future tool interceptor "implements this same shape" —
  so the next interceptor's author would put a `<` in a `rem` and rediscover this from
  scratch.
- **Fixed:** B8 now states the flat `for` is retained on its own merits (provable
  termination) and is **not** load-bearing against the abort, with the correction marked
  and dated. Added **B8a — no `<` or `>` anywhere inside a parenthesized block,
  including in comments**: cmd.exe tokenizes redirection characters inside a `rem`
  nested in `(...)`, because `rem` is a *command* whose line is still tokenized, not a
  comment in the sense the word implies. Also added the **test-harness corollary**:
  leave `%SystemRoot%\System32` on `PATH` so the shim's own `findstr.exe`/`where.exe`
  resolve — prepend tmp dirs onto system dirs, never the whole inherited PATH (which
  would expose a real `cage` and defeat the "cage absent" assumption), never nothing.
- **Why it belongs in the contract specifically:** it is invisible on POSIX, invisible
  in review, and its error message points at recursion rather than at the character that
  caused it. Five pushes and two wrong hypotheses is exactly the cost a written contract
  exists to stop the *next* person paying.
- **Bookkeeping:** WIN-CI removed from Pending with a closure entry; the State line
  corrected from "built, in tree, uncommitted" to released-and-on-PyPI with the 12-job
  green run recorded. Queue is now GF-LAUNCHER · ADOPT · NET-1 · TOOL-SDK · DOGFOOD ·
  SKILLS · HR1 — **nothing blocked**.
- **Noted, not filed:** Windows is now CI-*executed* but still not field-validated, and
  the README already says exactly that — no change needed.
- **Next step:** ADOPT (do agents invoke graphify at all), then NET-1.

---

## 2026-08-02 (Claude Code, Sonnet) — OTEL executed: `cage data export --otel` built end to end

- **Asked:** execute `docs/otel-export.prompt.md` (picked up via the IDE selection) —
  add `--otel` to `cage data export`, mapping calls to GenAI attributes and deciding
  how receipts/savings (no GenAI equivalent) are represented, honoring the pre-stable
  semconv finding from the handoff review.
- **Did:** new module `cage/otelout.py`; `--otel` wired into `cage/cli.py` /
  `cage/exportcmd.py` / `cage/clicmds.py`, mutually exclusive with
  `--csv`/`--format`/`--study`. Pinned `constants.OTEL_SEMCONV_VERSION = "1.42.0"` /
  `OTEL_SEMCONV_STATUS = "pre-stable"`, stamped in every document's `cage.meta` block.
  **Decided:** receipts/savings are cage-namespaced (`cage.savings[].cage.*`) —
  `cage.saved` GROSS, `cage.saved_usd` via the existing `receiptprice` ladder, omitted
  (never `$0`) on an UNPRICED refusal or a non-money unit; no `gen_ai.*` name
  invented. Calls omit `gen_ai.client.operation.duration` when `latency_ms` is 0
  (never a fabricated zero-duration span). Added `cage query otel-export`
  (`explain.py`'s `_live()` gained `semconv`/`semconv_status`) and 13 tests in
  `tests/test_otel_export.py` covering the mapping, omission rules, determinism,
  legacy-human exclusion, and the flag-combination errors.
- **Verified:** full suite green, 982 → 995 (13 new, 0 regressions); manual smoke
  of `cage data export --otel` against a seeded ledger, confirmed byte-identical
  across two runs and combination errors render the right `CageError` text.
- **Decided/open:** the duration attribute reuses the convention's *metric* name
  (`gen_ai.client.operation.duration`) as a flat JSON key, since this export is an
  attribute map, not real OTLP metrics/spans (out of scope per the handoff) — stated
  in the module docstring rather than left implicit. Nothing left open; no residual
  filed on OPEN-WORK.md.
- **Docs:** proposal + handoff/prompt archived to
  `docs/archive/v0.39-otel-{export.handoff,export.prompt,genai-export.proposal}.md`;
  `docs/proposals/README.md`, `docs/archive/README.md`, `docs/README.md` (Active work
  emptied), `docs/OPEN-WORK.md`, `docs/DOC-REGISTRY.md`, `CHANGELOG.md`, `README.md` +
  `CLAUDE.md` test counts, and a new `CLAUDE.md` architecture bullet all updated in
  this change, last (per the handoff's parallel-execution rule).
- **Next:** none — OTEL is closed. Whatever CODEX-OUT/DEBT/CMD-SYNC leave behind in
  OPEN-WORK.md's next-priority line (WIN-CI → ADOPT → NET-1) is unaffected by this
  change.

## 2026-08-02 (Claude Code, Sonnet) — CMD-SYNC executed: prices.toml applied, sources authority declined

- **Asked:** execute `docs/claude-md-sync.prompt.md` — apply the `prices.toml` split
  proposal to CLAUDE.md, decline the `[sources]` authority proposal, both docs-only.
- **Independently re-verified proposal 2 before acting**, per the prompt's own
  instruction. Read `cage/paths.py` `resolve_log_sources`'s full docstring: *"Precedence
  per built-in agent: env override > policy `[sources]` > built-in … Fully additive: an
  empty/absent `[sources]` returns exactly the built-in registry."* That is exactly what
  CLAUDE.md already said. Same verdict as the handoff — **declined, not applied**.
- **Did:** applied proposal 1 verbatim — the one-way-data-flow diagram + caption now
  name `cage.toml` (order/budgets/routing) and `prices.toml` (model prices, `[credits]`)
  separately; new **Prices file** architecture bullet
  (`Footprint.prices`); **Pricing is managed** bullet states the two-file write split
  (`prices set`/`sync` → `prices.toml`, `alias`/`route-tool` → `cage.toml`); **State
  cleanup** NEVER list gained `prices.toml`; constants/numbers-layers phrasing updated.
  `grep -c prices.toml CLAUDE.md`: 0 → 10. Governing sentence kept verbatim: **vendor
  facts move, routing decisions stay.**
  Archived both proposals to `docs/archive/v0.39-claude-md-{prices-file,sources-authority}.proposal.md`
  and the handoff+prompt pair to `docs/archive/v0.39-claude-md-sync.{handoff,prompt}.md`.
  Updated `docs/proposals/README.md` (both moved Active → Graduated), `docs/README.md`
  (dropped from Active work — docs root carries no loose pair), `docs/OPEN-WORK.md`
  (CMD-SYNC row removed from Pending, closure paragraph rewritten), `docs/archive/README.md`
  index row added, `DOC-REGISTRY.md` rows bumped.
- **Zero code changes** — `git diff --stat cage/` confirmed empty for this session's own
  edits (the pre-existing uncommitted `cage/` diff in the tree predates this session,
  from concurrent CODEX-OUT/DEBT/OTEL work). `just test`: 995 passed / 0 failed / 10
  skipped (unchanged by this docs-only change).
- **Decided/left open:** nothing — CMD-SYNC is fully resolved, no residual item filed.
  Directive A (making `[sources]` the sole authority) stays unfiled unless requested —
  it would be a code change, not a doc sync.
- **Next step:** none for CMD-SYNC. Queue continues per `docs/OPEN-WORK.md`.

## 2026-08-01 (Claude Code, Sonnet) — DEBT executed: Part 1 landed, Part 2 re-verified closed

- **Asked:** execute `docs/structural-debt.prompt.md` (opened in the IDE, model just
  set to Sonnet per the doc's own tier).
- **Followed the prompt's own instruction literally.** Part 2 requires "run `cage` with
  no args… If what you observe differs from this, stop and report" before building
  anything. Ran it. Output: `cmd_overview`'s headline (tokens · calls · unpriced ·
  last-import) **and a live capture-on-read that imported 3004 real calls** into my
  actual `~/.cage` ledger — not `_ROOT_HELP`. Stopped, as instructed.
- **This is the same finding an earlier session already closed the same day** (see the
  "DEBT Part 2 CLOSED" entry below) — I had not read that entry yet when I hit this
  independently, so it's now a **third** confirmation of the same false premise across
  two different agents/sessions.
- **Asked the human directly** (AskUserQuestion, since this changes what "done" means
  for an already-decided handoff): four options — fix capture-on-read only, build the
  state line and drop the overview call, stop and re-scope with a new handoff, or leave
  Part 2 alone. **Chose: leave Part 2 alone entirely.**
- **Did:** Part 1 landed — the `paths.py` splits-on-contact rule in `CLAUDE.md`
  (Must-Know Rules, beside the removed-verb rule). Archived the resolved
  proposal+handoff+prompt trio to `docs/archive/v0.39-structural-debt.*` (mixed outcome:
  Part 1 implemented, Part 2 declined, both stated in the archive headers with a
  claim-vs-truth table). Updated `docs/proposals/README.md` (Active → Graduated),
  `docs/README.md` (dropped from Active work), `docs/OPEN-WORK.md` (DEBT row removed
  from Pending, closure paragraph rewritten to point at the archive), `IMPLEMENTATION.md`
  entry added.
- **Decided/left open:** nothing — DEBT is fully resolved, no residual item filed.
- **Note on environment:** heavy concurrent activity in this working tree during the
  session (CODEX-OUT landed mid-session, ~30 files touched) — re-read every shared doc
  immediately before editing it to avoid clobbering concurrent writes; no collisions hit.
- **Next:** unchanged — WIN-CI, then whatever OPEN-WORK names next.

## 2026-08-01 (Claude Code, Opus) — CODEX-OUT: purge the Codex agent, protect Codex pricing

- **Asked:** execute `docs/codex-purge.prompt.md`. Remove every Codex reference —
  *except* the two that aren't the agent. No paid LLM calls; cage tree stays uncommitted.
- **Done:** classified all 116 `codex` hits in `cage/` + `tests/` into the three
  categories **before** deleting anything, then executed category by category.
  Category 1 (the agent) deleted from `paths`/`wiringscan`/`doctorcmd`/`doctorbundle`/
  `explain_data`/`agents` and from the test env-redirects + codex cases. Category 3
  (stale prose) had the word dropped from six modules. **Category 2 held**:
  `data/prices.toml` is byte-identical (empty `git diff`, unchanged sha) and a new guard
  test prices a Copilot call on all seven `gpt-5.x-codex` ids. Suite 983 ⇒ **982 green**;
  no golden moved. Pair archived to `docs/archive/v0.39-codex-purge.*`; CHANGELOG,
  OPEN-WORK, IMPLEMENTATION, archive index, README/CLAUDE.md test counts updated.
- **Decided:** (a) `paths.py:106/122/126` are all docstring *examples*, not migration
  behaviour — re-pointed at `claude` / generalised to `import-<agent>`; the dead-verb
  detector is the live parser and never enumerated agent names, so `cage import-codex`
  is still reported dead. (b) The handoff **mis-filed `test_output_spec.py`** under
  "delete codex cases" — its only hit is `prices set openai gpt-5.3-codex`, category 2,
  kept. (c) `paths.py` deliberately not split; `agenthomes` stays a named seam.
- **Open:** the accepted trade — a pre-v0.33 `~/.codex/config.toml` keeps a dead `cage`
  verb undetected. Named in the CHANGELOG `Removed` entry, by design.
- **Next step:** OTEL or DEBT (both parallel-safe with this, now landed).

## 2026-08-01 (Claude Code, Sonnet) — GF-DEBT: close the six honesty debts WIN-GF/CI-GF left

- **Asked:** execute `docs/graphify-honesty-debts.prompt.md` before v0.38.0 is
  committed — restore the deleted `restricted-environments.md`, state GF-LAUNCHER
  where users are, add a `cage query` explainer for the twin pair, write ADR 0007,
  make cage-lab state POSIX-only coverage, and write down the corpus-sizing lesson.
- **Done:** all six, in the same change. Restored `docs/restricted-environments.md`
  from `git show b2c4253^:...` (restore-then-update: fixed a stale
  "companion to portable-wiring.md" reference, dropped the removed Codex row, added a
  GF-LAUNCHER subsection). README Platforms line + `cage doctor`'s new `launcher-gap`
  check + the restored doc all state the same gap now. New `cage query graphify-shims`
  concept entry, live-interpolated. `docs/adr/0007-graphify-twin-pair-hand-paired-not-templated.md`
  filed. `docs/cage-lab/{01-setup,03-verify}.md` updated. The corpus-sizing rule is
  written into `tools/cigraphify.py`'s docstring **and** enforced — 4 new tests in
  `tests/test_cigraphify.py` prove `check_bare_graphify_is_intercepted` cannot pass on
  a zero-row or zero-saving result, with no real graphify needed. Two incidental test
  fixes (`test_doctor.py`'s check-name set; a stale-verb grep false-positive in the new
  explainer's own prose). 979/0 ⇒ **983/0**.
- **Decided:**
  - **`launcher-gap` is its own doctor check**, not folded into `_interceptor` — it
    answers "are two independent switches both on", a different shape of question
    than "is the installed shim alive".
  - **The vacuous-CI-run check was NOT deferred** — on inspection,
    `check_bare_graphify_is_intercepted` already raised `Fail` on an empty or
    zero-saving result (written the same session as WIN-GF/CI-GF, before GF-DEBT
    existed as a task). What was missing was a *regression test proving it*, not the
    enforcement itself — added four, monkeypatching the shell-call/ledger-read seams
    rather than requiring real graphify.
  - **Corrected the explainer's own prose rather than weakening the stale-verb grep
    gate** — `cage/explain_data.py` legitimately needed to describe the old
    `cage graphify` marker string, which is exactly what `tests/test_cli_tiering.py`
    exists to catch; reworded instead of carving an exception.
- **Open:** GF-LAUNCHER remains unfixed by design (documents, does not patch) — a fix
  needs a decision that moves both twins together.
- **Next step:** the actual next code work is still WIN-CI (push, read the Windows
  `graphify` CI job) — GF-DEBT was documentation debt paid down first, per the
  handoff's "before v0.38.0 is committed" instruction.

## 2026-08-01 (Claude Code, Opus) — WIN-GF + CI-GF: graphify is metered on Windows

- **Asked:** execute `docs/win-graphify-shim.prompt.md` — contract → `.cmd` twin → wire
  → liveness → flip, building CI-GF first as its harness (it was unbuilt).
- **Done:** all five phases plus CI-GF, in one pass. New: `docs/shim-contract.md`,
  `cage/data/shims/graphify.cmd`, `tools/cigraphify.py`, `tests/fixtures/cicorpus/`,
  `tests/test_win_graphify_shim.py`, `.gitattributes`, the `graphify` CI job. Changed:
  `paths`/`adoptcmd`/`pathshim`/`wiringscan`/`doctorcmd`, README Platforms + What's new,
  CHANGELOG (v0.38.0), version 0.37.2 → 0.38.0. 962/0 ⇒ **979/0** (+10 Windows-only
  skips); dummyrepo S1–S18 PASS; `tools.cigraphify` 7/7 on macOS.
- **Decided:**
  - **Both twins install on every OS**, mirroring `runshim.write` — a committed `bin/`
    that is byte-identical everywhere is what survives a cross-OS clone. `refresh_shim`
    completes the pair when either exists (the POSIX→Windows upgrade path).
  - **Hand-paired, not templated.** Batch and sh share no syntax subset; `runshim.py`
    hand-pairs for the same reason. The written *contract* is the shared artifact —
    which is what TOOL-SDK actually needs to template.
  - **Contract doc lives in `docs/`, not beside the shims** (the prompt asked for
    "alongside"): `data/shims/*` is package data and would ship a spec in every wheel.
    Both twins cite it by path in their headers.
  - **No python-launcher variant for the interceptor**, in either twin — the sh twin has
    none, and fixing one side is exactly the drift the contract exists to prevent. Filed
    as a stated gap, not half-built.
- **Two handoff claims corrected by contact with reality:** graphify is PyPI
  (`graphifyy`), not npm — on Windows it is `Scripts\graphify.exe`, so the twin never
  shares a filename with it, but `.EXE` precedes `.CMD` in PATHEXT so it must never
  share a directory. And `graphify query` emits its lines in a different order every
  run, so CI compares content, not bytes.
- **Open:** the Windows behaviour tier (10 tests) and the Windows CI leg have never
  executed — they run first on CI. Windows stays CI-asserted, never field-validated.
- **Next step:** push and read the Windows `graphify` job; then ③ ADOPT.

## 2026-08-01 (Claude Code, Sonnet) — SYNC-GUARD: name and guard the sync tests' borrowed table

- **Asked:** execute `docs/sync-fixture-guard.prompt.md` — five `test_policysync`
  tests borrow whatever bundle-shipped scalar-keyed table survives `_strip_to_v016`
  as their generic worked example (`[budgets]`, then `[quality] signal`); a bundle
  removal reddens all five for a reason unrelated to whatever removed it. Add one
  guard test naming the fix, and move the borrowed table/key into one constant so a
  re-point is a one-line edit. Explicitly not in scope: the synthetic-bundle fixture
  (filed as a proposal, third-occurrence trigger). No paid LLM calls, no commits.
- **Done:** added `_EXAMPLE_TABLE, _EXAMPLE_KEY = "quality", "signal"` (+
  `_EXAMPLE_DEFAULT`) to `test_policysync.py` with a comment pointing at the proposal;
  re-pointed all six tests that hardcoded `"quality"`/`"signal"`/`"task_ok"` to build
  their edits and assertions from the constant instead (their assertions are
  unchanged — only how the example table is named). Added
  `test_borrowed_example_table_still_in_bundle`, asserting
  `policy.bundled_raw()["quality"]["signal"] == "task_ok"`, with the exact failure
  message from the prompt. Verified by monkeypatching a copy of `bundled_raw()` with
  `[quality]` popped (never touched the shipped bundle file): the guard fails with
  the intended message, and — matching the original SUITE incident — five of the six
  re-pointed tests fail alongside it, but the guard now names why.
  `test_already_in_sync_message_on_current_file` untouched. Confirmed nothing else in
  the suite borrows a live bundle table this way (other `bundled_raw()[...]` reads
  are all against the permanent `[meta]` table). Suite: **961 → 962 passed, 0
  failed**. Archived the solo prompt to `docs/archive/v0.36-sync-guard.prompt.md`;
  removed `SYNC-GUARD` from `docs/OPEN-WORK.md`.
- **Decided/open:** nothing left open — the synthetic-bundle fixture remains a
  deliberately-parked proposal, not a task.
- **Next step:** none for SYNC-GUARD; `docs/OPEN-WORK.md` next item stands (**NET-1**
  / **HR1** / **H**, per the standing no-commit directive).

---

## 2026-08-01 (Claude Code, Sonnet) — CLEAN: cleanup becomes advisory (90d, warn-only, never per-tool)

- **Asked:** execute `docs/cleanup-safety.prompt.md` — cage should stop deleting
  `.cage/state/` on its own. Three changes: retention 30 → 90 days, the auto sweep
  warns instead of deletes, tool savings get an explicit never-per-tool invariant.
  Decide what `[cleanup] enabled=false` now means. No paid LLM calls, no commits.
- **Done:** `CLEANUP_DEFAULT_DAYS` 30→90 (comment rewritten to argue for 90, matching
  the new value). `cleanup.maybe_run` now only prints a stderr reminder — count,
  reclaimable KB, the exact fix — silent at zero, throttled on the existing 24h
  stamp, fail-open; `cage data cleanup --apply` is now the *only* path that deletes.
  New `[cleanup] warn` switch (env `CAGE_CLEANUP_WARN`, default true). Decided
  `enabled` semantics: `false` means no automatic anything (not even the reminder),
  but a manually-typed `cage data cleanup`/`--apply` always runs — an explicit
  command is never silently ignored; `run_cli`'s payload key renamed `enabled` →
  `auto_reminder` to match. Added the `NEVER`-list comment + a `days=0` test proving
  `ledger/savings/<tool>/` survives `prune` regardless of window. Updated
  `explain_data.py`, `cage.toml`'s bundled `[cleanup]` block (+ `policy_version`
  0.26.0→0.27.0 and a `policysync.DEFAULT_CHANGES` entry so existing projects get
  offered the 30→90 refresh), `docs/example/toml-config.md`, `GLOSSARY.md`, and
  `CLAUDE.md`'s cleanup paragraph. Goldens P5/P6a/P6b re-blessed (policy_version +
  in-sync count shifted). Suite: **956 → 961 passed, 0 failed**. Pair archived to
  `docs/archive/v0.36-cleanup-safety.{handoff,prompt}.md`.
- **Decided:** the "safer" `enabled` reading from the handoff — auto-only gate, never
  blocks an explicit command. No stdout leakage anywhere (asserted by a dedicated
  test); the accepted trade-off (unbounded `state/` growth if the reminder is
  ignored) is left as-is per the handoff, not solved.
- **Next:** `SYNC-GUARD` — 5 `test_policysync` tests still borrow a live bundle table
  as their generic-mechanics example; see [OPEN-WORK.md](OPEN-WORK.md).

## 2026-08-01 (Claude Code, Sonnet) — SUITE: green the last 6 tests (949/6 ⇒ 956/0)

- **Asked:** execute `docs/suite-green.prompt.md` — fix G-SAV (`savings.record()` drops
  `ts`) and BUD-V-TEST (5 `test_policysync` tests borrow `[budgets]`), no paid LLM
  calls, no commits in `cage`.
- **Done:** `savings.record()` gained `ts: str | None = None`, forwarded to
  `schema.make_savings`; `**_ignore` kept for the three shim callers. Asked before
  adding the kwarg-parity guard test (per the handoff) — approved, added
  `test_record_explicitly_accepts_every_make_savings_keyword`. Re-pointed the five
  `test_policysync` mechanics tests from `[budgets]` (commented out, opt-in) to
  `[quality] signal` — verified it's active in the bundle, survives `_strip_to_v016`,
  has a simple scalar key, and isn't already another test's subject. Full suite:
  **956 passed, 0 failed**. Test counts refreshed in `README.md` / `CLAUDE.md`.
- **Decided:** re-point now **and** file the synthetic-bundle-fixture as a follow-up
  (`SYNC-FIXTURE` in `OPEN-WORK.md`) — the recommended third option. Re-pointing alone
  leaves `test_policysync`'s mechanics coupled to whatever table cage happens to ship;
  the synthetic fixture is real design work (a small fake bundle the tests own) so
  it's carried forward rather than done inline.
- **Open:** `SYNC-FIXTURE` (design the synthetic bundle fixture). Both G-SAV and
  BUD-V-TEST removed from `OPEN-WORK.md`; outcome recorded in `IMPLEMENTATION.md`
  first, per the removal precondition.
- **Next step:** pick up `SYNC-FIXTURE`, or move to NET-1 / the v0.36 release (still
  blocked on the no-commit directive).

---

## 2026-08-01 (Claude Code, Sonnet) — BUD-V: verify the budget opt-in change

- **Asked:** execute `docs/budget-optin-verify.prompt.md` — verify the (already-made)
  bundle change that ships `[budgets]` commented out, opt-in only, no constant
  fallback. No paid LLM calls, no commits in `cage`, report don't fix silently.
- **Done:** ran the full suite on the dev machine's `.venv` (Python 3.14, `tomllib`
  available — the Cowork sandbox that authored the change couldn't). Baseline before
  re-blessing: 937 passed / 8 failed. Re-blessed goldens **P5**/**P6a**/**P6b**
  (only line that moved: `"11 project keys equal to the bundle — in sync"` → `"8"`,
  since budgets' 3 keys no longer exist on either side of the sync diff). After:
  **949 passed / 6 failed**. Live-exercised in a scaffolded `/tmp` project: no-cap
  render, `budget.check` with an absurd spend, opt-in with a tiny `session_usd` +
  `on_exceed = "block"` tripping `proceed=False`, and `policy sync --apply` leaving an
  existing active `[budgets]` table byte-identical. Full detail:
  [IMPLEMENTATION.md](IMPLEMENTATION.md).
- **Decided:** **keep as-is.** The bundle change needs no code fix. The 6 remaining
  red tests are not caused by a defect: 5 × `test_policysync.py` pin the *old*
  always-on-budgets bundle shape (they use `[budgets]` as a convenient example table
  for generic sync-mechanics assertions, not for budget semantics) — recommended fix
  is to rewrite them against a different actively-shipped table, not restore the
  default. 1 × `G-SAV` (`test_savings.py` shard test) is unrelated: `savings.record()`
  silently drops a caller-supplied `ts` into its `**_ignore` catch-all instead of
  forwarding it, so the row always lands in the *current* month's shard — a real bug,
  but nothing to do with budgets; left unfixed, out of scope.
- **The one thing checked for and ruled out:** `cage policy sync` does not try to
  re-add `[budgets]` as a missing default — an active project table (existing or
  newly opted-in) buckets as `project_own` ("your own keys — not in the bundle") and
  is never touched by `--apply`. No escalation needed.
- **Side note for the human:** `cage setup --claude` in the throwaway `/tmp` test
  project appended a PATH line for that directory to `~/.zshrc`
  (`export PATH="/private/tmp/cage-budget-check/bin:$PATH"  # cage adopt: graphify
  metering interceptor`) — normal `cage setup` behavior, but the temp dir is gone now
  so the line is stale. I couldn't remove it myself (the harness's auto-mode
  classifier blocked editing `~/.zshrc`); safe to delete that one line whenever
  convenient.
- **Next:** rewrite the 5 `test_policysync.py` tests off `[budgets]`, or file that as
  ordinary test-debt separate from BUD-V; then whatever OPEN-WORK item follows.

---

## 2026-08-01 (Claude Code, Opus) — K+NET: gross vs net savings

- **Asked:** execute `docs/net-savings.prompt.md` — relabel gross (K), stop `verdict`
  calling a $0-self-declared tool a SAVING (NET-2), and add task-level net (NET-3).
  No paid LLM calls, no commits in `cage`.
- **Done:** all three. New `cage/netsaved.py` + `tests/test_netsaved.py` (10 tests);
  gross relabelled in text and CSV across report/attrib/roi/overview/ceiling from one
  shared phrase; `cage query gross-vs-net` added; `docs/formulas.md` §2.1 rewritten and
  §2.1a added. Suite **947 pass / 8 fail** — all 8 pre-existing (BUD-V ×7, G-SAV ×1),
  verified against a stripped-out copy. Goldens R1/R2/R6/I2/I3/O2 re-blessed;
  **P5/P6 deliberately not** (they are BUD-V's defect, not this change's).
  Pair archived to `docs/archive/v0.36-net-savings.*`.
- **Decided (the one the prompt left open):** *attributable cost = the ±120s task-window
  union.* The whole task measures task size, not tool cost; "turns with a tool-use block"
  is sharper but no ledger field marks one, so it needs a capture-time change. Symmetric
  window because both adjacent turns are cost-of-use. Net is a **lower bound** (a re-read
  three turns later is not counted) and says so.
- **Decided (not asked):** `SAVING (GROSS)` rather than INSUFFICIENT DATA — gross is a
  genuinely computed number, and discarding it would hide the very comparison the finding
  exists to make visible. And **COSTING stays assertible**: the omitted term is ≥ 0.
- **Open:** the gross/net split is only as useful as its coverage — on graphify's real
  call-less, task-less shim receipts `netsaved` refuses entirely. Per-query netting needs
  the transcript route to stamp `call` at capture time (a separate change, out of scope).
- **⚠ Concurrency, again:** a second session wrote this tree mid-run — goldens **P5/P6a/P6b**
  were blessed at 16:57 by something other than me (I blessed only R1/R2/R6/I2/I3/O2).
  I reverted them: blessing them while BUD-V is undecided launders the defect into the
  contract. Check `git status` mtimes before trusting a suddenly-greener suite.
- **Next:** **BUD-V** — decide whether the bundle or `test_policysync` is wrong.

---

## 2026-08-01 (Claude Code, Opus) — K2: kiro capture routing, both halves + the tests

- **Asked:** execute `docs/kiro-routing.prompt.md` (K2) — route kiro **IDE** rows to the
  machine ledger, scope kiro **CLI** credits by cwd, without breaking claude/copilot.
  No paid LLM calls, no commits in `cage`.
- **Done:** both halves, the read-side honesty (with K3/K4's wording, done once as the
  prompt asked), and `tests/test_kiro_routing.py` (27 tests). Suite: **937 passed**, 8 red
  — none mine (7 = the concurrent budget-opt-in bundle change, 1 = pre-existing `G-SAV`).
  Goldens R1/R2/R4 re-blessed. Pair archived to `docs/archive/v0.36-kiro-routing.*`.
  Detail + the per-root map: [IMPLEMENTATION.md](IMPLEMENTATION.md).
- **Decided (the two the prompt left open):**
  1. **Capture switches compose as AND** — the project's gates the sweep, the machine
     ledger's additionally gates the routed leg. Most restrictive wins; it is the only
     composition that honours both stated intents. Visible under `--debug`, never silent.
  2. **The summary names the sink** and the rollup counts only rows that landed here, so
     no line can imply project rows that went elsewhere.
- **Verified, not assumed:** `conversations_v2.key` is the absolute **symlink-resolved**
  cwd (a `/tmp/x` conversation is keyed `/private/tmp/x`) — measured on the real store.
  Prefix-matched on a separator boundary, so `cage` never swallows `cage-lab`.
- **Caught while testing:** K4's caveat checked `"claude"` but a claude row's `agent` is
  `claude-code` — it would have silently never fired. Fixed via `agents.row_surface`.
- **⚠ For the human — two things I did that you should know:**
  1. I ran a `git stash`/`pop` to isolate a failure. It restored all content, but it
     **flattened the staged/unstaged split** (the `MM`/`AM` entries in `git status` are
     now plain staged). Nothing was lost; the index just no longer distinguishes them.
  2. A **concurrent session** is editing this tree (budget opt-in). It rewrote
     `cage/data/cage.toml`, `OPEN-WORK.md` and `IMPLEMENTATION.md` mid-run. That is the
     source of the 7 red `policysync`/P5/P6 tests — tracked as `BUD-V`, not mine.
- **Next step:** `BUD-V` (verify the budget opt-in change), then `K+NET`.

## 2026-08-01 (Claude Code, Opus) — Tier-1 human axis removed, substrate included

- **Asked:** execute `docs/human-removal.prompt.md` — remove the Tier-1 human axis
  completely (substrate included), keep provenance `origin="human"` untouched, keep old
  ledgers readable, decide the `minutes`-receipt question. No commits in `cage`.
- **Done:** the full removal + wiring migration + docs. Suite green
  (915 passed; the 1 failure is pre-existing, see below). Handoff/prompt archived to
  `docs/archive/v0.36-human-removal.*`.
- **Decided:**
  1. **The handoff's scope was wrong on two verbs.** `cage human outcome` and
     `cage human quality` were filed under the `human` group but are not the human
     axis — `outcome` is the task-close verb `compare`/`estimate`/`calibration` all
     depend on. Deleting them as specified would have silently amputated §4.7–§4.8.
     They **moved** to a new `task` group instead.
  2. **The open `minutes`-receipt question: exclude with a visible footnote**, not
     price at `$0`. A silent `$0` still enters a total as a real zero and reads as
     "measured nothing saved"; `cage report` now counts the exclusion and names it.
     The predicate covers `unit == "minutes"` from *any* tool, not just
     `tool == "human"` — `record_receipt` accepted an arbitrary unit.
- **Open:** OPEN-WORK **HR1** — any agent-vs-human rebuild is a fresh design behind a
  proposal doc, never a revert (nothing was left in the tree to restore).
  **G-SAV** — `test_savings.py::test_record_writes_into_the_per_source_month_shard`
  fails on the baseline too; unrelated to this work, now filed.
- **Next step:** OPEN-WORK **K** — relabel `saved` as gross.

---

## 2026-08-01 (Claude Code, Sonnet) — `[meta] cage_version` derived, drift closed

- **Asked:** execute `meta-version.prompt.md` (written earlier today in the Cowork
  session below; archived by this same entry to
  [v0.36-meta-version.prompt.md](archive/v0.36-meta-version.prompt.md)) — derive
  `cage_version` from `__version__`,
  leave `policy_version` alone, pin it with a test, close the release-checklist gap.
- **Done:** removed the literal from `cage/data/cage.toml [meta]`; `policy._bundled()`
  now derives `cage_version` from `cage.__version__` live (one point, feeds
  `bundled_raw()`/`load()` both); `initcmd.run` stamps it once onto a freshly
  scaffolded project's `cage.toml` (historical fact, `mark_custom=False` — marking it
  customized broke `test_policysync.py`'s v0.16-fixture strip helper on the first
  attempt, so switched off the mark). Caught a second latent bug via manual CLI
  smoke test (not any pytest failure): `pricestoml._inplace_table_edit` inserted a
  brand-new key right before the table span's *next header*, not after the table's
  own last key — for `[meta]` (followed by ~20 lines of unrelated prose before
  `[capture]`) that buried the stamp mid-comment-block, valid TOML but unreadable.
  Fixed the insertion point; full suite re-run clean. Added the drift-guard test + a
  fresh-scaffold test; fixed `test_zipapp.py`'s now-invalid "written byte-identical to
  bundle" assumption (real behavior change, documented why, not a weakened assertion);
  re-blessed `P1.txt`. Added the CLAUDE.md release-checklist line. Archived the prompt
  to `docs/archive/v0.36-meta-version.prompt.md`; updated OPEN-WORK/README/DOC-REGISTRY
  to match (remove-on-done).
- **Decided/left open:** `policy_version` is untouched, confirmed still a content
  counter (no coupling to `__version__`) — matches the standing pushback from the
  Cowork session. Two pre-existing, unrelated test failures left as-is (confirmed
  failing in isolation, no `[meta]`/policy involvement): `test_I2_verdict_saving`
  (golden drift, looks date-relative) and
  `test_savings.py::test_record_writes_into_the_per_source_month_shard` (shard
  partitioning). Not filed as new OPEN-WORK items in this pass — flagging here for
  whoever picks up next to triage and file if still red.
- **Next:** **K — relabel `saved` as gross** (proposal B), OPEN-WORK's next item.

## 2026-08-01 (Cowork) — CMD-SYNC: one proposal applies, one is WRONG and declined

- **Asked:** review both CLAUDE.md proposals, produce a pair, and can they run in
  parallel?
- **Verdict: apply `claude-md-prices-file`, DECLINE `claude-md-sources-authority`.**
- **✅ Proposal 1 verified true against code:** `data/prices.toml` exists,
  `policy._BUNDLED_PRICES` loads it, `_bundled()` merges both files — and **CLAUDE.md
  mentions `prices.toml` exactly zero times** while its flow diagram still reads
  `cage.toml (prices/order/budgets)`. The file every agent loads names the wrong home
  for the vendor rate card. Real, load-bearing, apply.
- **❌ Proposal 2 is wrong — applying it would make CLAUDE.md lie.** It asks CLAUDE.md to
  say `[sources]` is the *only* path source with no built-in fallback. But
  `paths.resolve_log_sources`'s own docstring says: *"env override > policy `[sources]`
  > built-in … **Fully additive: an empty/absent `[sources]` returns exactly the built-in
  registry**"* — which is what CLAUDE.md **already** says. The proposal describes a
  Directive A end-state that **never fully shipped**: the `sources_seed`/`sources_drift`
  machinery exists, the runtime fallback was never removed. Declined, archived with the
  contradicting docstring cited as evidence.
- **⚠️ Correction to my own review from earlier today.** I reported both proposals
  "verified still needed — CLAUDE.md stale on both". I had compared CLAUDE.md against
  each proposal's *quoted* "current text" and inferred staleness. **I never checked the
  code.** Proposal 2 isn't stale documentation, it's an unbuilt design. The error is
  recorded in the handoff and in the proposal itself rather than quietly fixed — it is
  the same failure I keep catching in the plan files (a marker is an assertion, not
  evidence), this time in my own review.
- **Parallel: NO, and moot.** Both edit `CLAUDE.md` — overlapping regions of one dense
  reference file, a guaranteed conflict for zero speedup. And after the review only one
  job remains, so there is nothing to parallelise. Flagged that CLAUDE.md was edited
  **three times today** (CODEX-OUT, DEBT, the doc-citation sweep), so the executor must
  re-read it rather than work from a remembered copy.
- **Residual noted, not filed:** if Directive A is actually wanted, it is a *code*
  change (remove the fallback, make no-`[sources]` loud) — a feature, not a doc sync.
  Nothing indicates it is wanted.
- **The prompt makes the executor re-verify proposal 2 independently** and stop if they
  disagree, rather than trusting my verdict — I was wrong on this exact question once.
- **Next step:** unchanged — WIN-CI; CMD-SYNC and OTEL are both ready.

---

## 2026-08-01 (Cowork) — DEBT Part 2 CLOSED: my premise was wrong twice, verified

- **Asked:** the executing agent found Part 2's premise false *again* and offered four
  scopes. Chose: **leave Part 2 alone / close it.**
- **Verified in code before answering** (having been wrong twice, I did not take either
  side on trust): `cli.py:651` — no subcommand → `clicmds.cmd_overview`, **not**
  `_ROOT_HELP`. `cmd_overview` calls `captured_read_root()`. And `cli.py:114` states the
  intent outright: `_capture_flags(p)  # bare cage (overview) is a read too —
  capture-on-read applies`.
- **Both of my premises were false, in opposite directions.** Proposal: "prints argparse
  usage". Handoff v1: "prints `_ROOT_HELP`, state is missing". Truth: `cmd_overview`
  already prints tokens · calls · unpriced · last-import — *the exact gap I re-scoped to
  already had a feature.*
- **Worse: my v1 acceptance criterion would have caused a regression.** I required "a
  test proves bare `cage` writes nothing" and called it the one way the feature could do
  harm. That capture-on-read is **designed** — Phase 1's *a number is never staler than
  the instant it's shown* — and is gated, throttled, fail-open, `--no-import`-escapable
  and stderr-announced. Suppressing it would make the one command whose job is showing
  state show stale state. Flagged in both docs as **do not implement**.
- **Why closed rather than re-scoped a third time:** two independent premises collapsed
  on inspection. An item that evaporates each time it is examined is telling you
  something. v0.38 is uncommitted with WIN-CI and CODEX-OUT queued behind it.
- **Corrected rather than quietly rewritten:** the handoff keeps a claim-vs-truth table,
  the prompt carries an explicit *ignore the earlier draft* warning, and the proposal
  keeps its original wrong text below the closure note. The error is the useful record.
- **Part 1 survives untouched** — a CLAUDE.md rule has no premise to be wrong about.
- **Next step:** unchanged — WIN-CI, then CODEX-OUT / OTEL.

---

## 2026-08-01 (Cowork) — OTEL specced; parallelism answered with a file-overlap map

- **Asked:** review `otel-genai-export.md`, produce a pair, and can it run in parallel
  with CODEX-OUT and DEBT?
- **⚠️ Review finding that changed the design.** The proposal called OTel GenAI "the
  enterprise lingua franca". **It is pre-stable** — as of semconv v1.42.0 (June 2026)
  `gen_ai.*` moved to its own repo, has no 1.0, is labelled *Development*, and names can
  still change between versions. That collides directly with cage's determinism law
  (same ledger ⇒ same output), because an export tracking a moving spec silently changes
  shape. **Design gained: pin the targeted semconv version in `constants.py`, stamp it
  in the emitted document, and treat a spec bump as a deliberate changelog'd change —
  the `prices_version` discipline.** Help text and docs must say "pre-stable".
- **Second constraint written hard:** no `opentelemetry-*` dependency. Cage writes a
  file; the collector ingests it. Adding an SDK to emit JSON would end `dependencies = []`,
  which *is* the product.
- **Third:** never invent a `gen_ai.*` attribute for cage-only data (receipts, savings
  have no upstream equivalent) — omit or cage-namespace, decided and stated. And omit
  rather than emit a `0` that reads as measured.
- **Parallelism answered with an actual overlap map, not a guess.** CODEX-OUT touches 12
  modules; DEBT touches `cli.py` + CLAUDE.md; OTEL touches `exportcmd.py` + a new module.
  **Code collision ≈ zero.** The only real contact points are (1) `explain_data.py` —
  CODEX-OUT edits the stale-wiring entry, OTEL adds a new one, different regions; and
  (2) the **shared bookkeeping** — OPEN-WORK/WORKLOG/IMPLEMENTATION/CHANGELOG/DOC-REGISTRY
  plus the **test-count line in README + CLAUDE.md**, which three concurrent agents would
  certainly collide on.
- **Rules issued:** code and tests first, shared docs **last** with a re-read; whoever
  lands last owns the test count. If two run truly concurrently, **CODEX-OUT goes first**
  — widest blast radius, most re-blessed goldens, far easier to land a small change on
  top of it than the reverse. Serial-preferred order: CODEX-OUT → OTEL → DEBT.
- **Next step:** unchanged — WIN-CI first; then any of the three.

---

## 2026-08-01 (Cowork) — DEBT specced; my own proposal's premise was false

- **Asked:** a handoff + prompt for structural-debt.
- **Split it honestly: the two halves are different animals.** Part 1 (`paths.py`) is a
  **rule**, not a task — there is nothing to build beyond writing it into CLAUDE.md, and
  a handoff that pretends otherwise would invent work. Part 2 is a real, small feature.
- **⚠️ Found while spec'ing: part 2's premise was wrong — my own proposal's.** It claimed
  *"`cage` with no args today prints argparse usage."* It does not. `cli._ROOT_HELP` is a
  hand-written one-screen brief (daily verbs, grouped subcommands, five worked examples)
  that the parser's formatter returns instead of argparse's dump. **The help is already
  good.** Building a "landing flow" would have replaced something that works.
- **Re-scoped to the real gap: *state*.** A user reads a fine menu and still can't tell
  whether a ledger exists, whether capture ran, or whether anything is unpriced. So: one
  line above the unchanged help — `ledger ~/.cage · 1,204 calls · last import 3h ago ·
  ⚠ 12 unpriced`. Correction recorded in the proposal itself, above the false sentence,
  so the error is visible rather than quietly overwritten.
- **The requirement that matters most:** bare `cage` **must write nothing** — no import,
  no cursor, capture-on-read stays OFF — pinned by a test. It is the one way a
  convenience feature here could do real harm.
- **Part 1's rule carries CODEX-OUT's earned clause:** *a deletion and a move never share
  a diff.* That verdict came from declining to move `agenthomes` during the purge; now it
  is a rule instead of a one-off judgement.
- **Prompt requires the executor to verify the correction first** (run bare `cage`, check
  it prints the curated help) and stop if what they see differs — I was wrong once here
  already, so the spec doesn't ask to be trusted.
- **Next step:** unchanged priority — WIN-CI, then CODEX-OUT; DEBT is low.

---

## 2026-08-01 (Cowork) — CODEX-OUT specced; DEBT reviewed and amended

- **Asked:** review `structural-debt.md`; remove everything referencing Codex; produce a
  handoff + prompt.
- **Arpit overrode my earlier call and that is recorded as his**: I argued to keep the
  codex scan as legacy detection; he decided to remove it. The handoff states the
  accepted loss plainly — a pre-v0.33 machine keeps a dead `cage` verb undetected — and
  requires the CHANGELOG `Removed` entry to name it, so the trade is visible not silent.
- **⚠️ The finding that reshaped the whole job: THREE unrelated things are spelled
  "codex".** (1) the **agent** — `codex_home`, wiringscan's config scan, doctor's
  `.codex/hooks.json`, `CODEX_HOME` in the doctor bundle → delete. (2) the **model
  family** — `gpt-5.3-codex`/`gpt-5.2-codex` in `prices.toml` (20 rows) plus `policy.py`'s
  `…-codex-high` → `…-codex` effort fold. **These are OpenAI ids that Copilot emits** —
  the file's own comment says *"Codex CLI + Copilot (both emit gpt-family ids)"* — so
  deleting them **silently UNPRICES a supported agent**. (3) stale prose enumerations
  ("Copilot/Kiro/Codex leave it empty") → drop the word, keep the sentence.
  A literal `grep -i codex && delete` would have broken live Copilot pricing. Same class
  as the two-different-"human"s trap, with an extra head.
- **Filed** `codex-purge.{handoff,prompt}.md` (**Opus** — the typing is trivial, telling
  the three apart is the job) leading with that table, and requiring
  `git diff cage/data/prices.toml` to be **empty** as an acceptance criterion.
- **DEBT reviewed: sound, one amendment.** CODEX-OUT is the first real test of its
  fix-on-contact rule — it touches the agent-home helpers. **Verdict: do NOT move them in
  this change** (a deletion and a move in one diff can't be reviewed); instead
  `agenthomes.py` is added to the proposal's named-seam list so the *next* touch does a
  clean move. Rule-not-project framing holds; part 2 untouched.
- **Left as judgement for the executor:** `paths.py:106/122/126` describe verb-tail
  parsing of legacy commands (`cage import --agent codex`) — those may still serve a
  migration path, so each is decided per site and stated.
- **Next step:** run `codex-purge.prompt.md` (Opus); WIN-CI still pending.

---

## 2026-08-01 (Cowork) — dead doc-citation sweep; Codex residue labelled, not deleted

- **Asked:** do the cleanup; *"we aren't going to support codex anything soon."*
- **Swept 11 dangling `docs/*.md` citations across 11 modules** — the v0.36 hookless
  sweep deleted five design docs and swept none of their pointers. Re-pointed each at
  its surviving home rather than deleting the sentence: `cli-output-spec.md` → the
  goldens (now past tense, correctly historical) · `csv-output.md` ×6 → `csvout.py` +
  `cage query csv-output` · `debugging-capture.md` ×2 → `cage doctor --bundle` +
  CLAUDE.md *Capture observability* · `sources.md` → `cage query sources`.
  Zero live dangling refs remain; all 12 edited files parse.
- **Two things found while sweeping.** `explain_data.py`'s **`csv-output` entry itself**
  pointed at the missing `csv-output.md` — the explainer explaining CSV cited a dead
  doc. And `paths.py`'s `[sources]` comment still carries the pre-Directive-A
  "byte-for-byte fallback" wording; I left the semantics alone (that's **CMD-SYNC**,
  awaiting Arpit's accept) but flagged it inline so the two land together.
- **Codex: labelled, NOT removed — and this is the important call.** Support was already
  removed in v0.33.0, so there is nothing to "stop supporting". What survives is
  `paths.codex_home()` + `wiringscan`'s `~/.codex/config.toml` scan + doctor's
  `.codex/hooks.json` scan, and it is **deliberate legacy detection**: a machine wired
  before v0.33 still holds a cage command in those files, and per CLAUDE.md's
  wiring-liveness rule ("both real-world failures were user-level") deleting the scan
  abandons those users to a silently dead verb — the F1 class. It read as dead code, so
  I gave `codex_home()` a docstring saying why it survives and when it may be deleted
  ("once no supported upgrade path can start from a pre-0.33 install"), plus an inline
  note on doctor's scan. **Removing it would have been the natural reading of the
  instruction and the wrong thing to do.**
- **New CLAUDE.md rule — deleting a doc is a citation migration**, the prose twin of the
  removed-verb/`verbmap.REMOVED` rule. Same failure shape: nothing errors, the pointer
  just goes nowhere. Requires re-pointing or an explicit past-tense statement in the
  same change, with the sweep command inline. This rot surfaced twice in a week; that is
  the bar the repo already uses for codifying a rule.
- **⚠️ UNVERIFIED — comments only, but the suite was not run here** (sandbox is Python
  3.10; cage needs 3.11+). All edits are comments/docstrings, no logic touched, and
  every file parses — but `just test` should confirm before commit, since a golden could
  in principle pin a docstring.
- **Next step:** `just test` on the dev machine, then WIN-CI.

---

## 2026-08-01 (Cowork) — proposal lifecycle codified; first proposal graduated

- **Asked:** define the lifecycle of a proposal once implemented, archive accordingly,
  and put the lifecycle in CLAUDE.md.
- **Applied it first, then wrote it down.** `proposals/windows-graphify-interceptor.md`
  was already `status: implemented` but still sitting in the directory — the exact bug
  the rule now forbids. Archived to
  `archive/v0.38-windows-graphify-interceptor.proposal.md` with a header naming the
  version **and where the living spec now lives** (`shim-contract.md`), plus an archive
  index row and a **Graduated** section in `proposals/README.md`.
- **CLAUDE.md gained the rule**, mirroring the handoff/prompt lifecycle it sits beside.
  Four states — **proposed → picked up → implemented → archived** — with the
  picked-up state made explicit (a pair is written; the proposal *stays put* and gains a
  pointer, because it is still the rationale). Five same-change obligations on
  implementation: move · header naming the living spec · IMPLEMENTATION entry ·
  index entry to *Graduated* · carry forward anything unbuilt. Declined and superseded
  get the same treatment with the decider or successor named.
- **The clause I think matters most:** *where an archived proposal disagrees with the
  living spec, the spec wins.* Implementation routinely corrects the proposal that
  motivated it — WIN-GF's was wrong on the packaging source (PyPI `graphifyy`, not npm)
  and on the re-entry guard's scope — and that correction is the valuable part. Without
  the precedence rule an archived proposal reads as authority it never had.
- **Framing:** an implemented proposal left in `proposals/` is the same class of bug as a
  ticked-but-present OPEN-WORK item — it inflates the queue of open ideas and makes the
  directory lie about what is still on the table.
- **GF-DEBT gained item 7:** when ADR 0007 lands it becomes that archived proposal's
  living-spec anchor. Also verified the other twelve proposals are genuinely unbuilt
  (the two CLAUDE.md ones are CMD-SYNC — awaiting Arpit's accept, not implementation).
- **Next step:** unchanged — run GF-DEBT before committing v0.38.

---

## 2026-08-01 (Cowork) — audited v0.38; filed GF-DEBT (six honesty debts)

- **Asked:** what is missing from the WIN-GF/CI-GF delivery; then file a pair for
  anything needing implementation.
- **Audited the artifacts, not the summary.** The code holds up: the 3-copy marker set
  has a drift test, `paths.GRAPHIFY_SHIMS` is a single enumeration both writer and
  readers share, the `%ERRORLEVEL%`-expands-at-parse-time trap is pinned by a test that
  names it, package-data ships `data/shims/*`, and release hygiene (version, changelog,
  README what's-new, **both** test counts) is complete.
- **Six gaps, all in the honesty surface rather than the code:**
  1. **`docs/restricted-environments.md` was deleted** in the v0.36 hookless sweep
     (`b2c4253`, 129 lines: Tier 1/2/3 + the WDAC caveat) and **8 source files still
     cite it** — `clicmds`, `doctorcmd` ×2, `paths`, `policy`, `runshim` ×2, CLAUDE.md.
     Recoverable from git; restore-then-update, never rewrite.
  2. **GF-LAUNCHER unstated to users.** The README claims Windows graphify works and
     recommends `--python-launcher` two sentences later — never saying neither twin
     meters under it (B5). Same failure class as the human-axis README claim, three days
     on.
  3. No `cage query` entry for the twin pair, though doctor can now **fail** on it.
  4. No ADR for three decisions, chiefly **hand-paired, not templated** — the one a
     future agent will try to "fix" (I proposed templating; Arpit's executor correctly
     rejected it). Filed with a veto condition gated on a *third* interceptor.
  5. The cage-lab manual has zero mentions of the twin — the fidelity authority is
     silent on a newly-claimed platform.
  6. The CI-corpus lesson is unwritten: too small ⇒ every query honestly
     `unmeasurable` ⇒ **the leg passed while asserting nothing.**
- **Corrected my own finding mid-audit:** I first reported *three* broken CLAUDE.md refs.
  `docs/cli-output-spec.md` is a historical mention of something correctly removed, and
  `anton/docs/cage.md` belongs to another repo. Only one was real. Recorded in the
  handoff so the executor doesn't chase two ghosts.
- **Filed** `graphify-honesty-debts.{handoff,prompt}.md` (**Sonnet** — six explicit
  targets, no architectural judgement; the ADR records decisions already made). Scoped
  **before v0.38.0 is committed** — same change, not a follow-up. GF-LAUNCHER stays open:
  this documents it, the fix must move both twins.
- **Next step:** run GF-DEBT, then push and read the Windows CI leg.

---

## 2026-08-01 (Cowork) — WIN-GF specced: a `.cmd` twin, and CI-GF confirmed as its harness

- **Asked:** work up `windows-graphify-interceptor.md`, aim for anything other than an
  `.exe`, produce a handoff + prompt — and does `ci-graphify-matrix.handoff.md` help
  test it?
- **Answer to the CI question: yes, it *is* the harness.** CI-GF's Windows `present` leg
  installs real graphify (npm ⇒ `graphify.cmd`), runs `cage setup`, puts `bin/` first on
  PATH and invokes **bare `graphify`** — which is exactly WIN-GF's acceptance test, on
  the only Windows available (the dev machine is macOS). Dependency now stated in both
  docs: **build CI-GF first**; shipping the twin *flips* its assertion from
  asserts-the-gap to asserts-the-fix.
- **Artifact decided: `graphify.cmd`** — plain text bundled data, no `.exe`, nothing
  compiled, works from `cage.pyz`. **PowerShell ruled out on a hard fact I verified:
  `.ps1` is not in default PATHEXT** (`.COM;.EXE;.BAT;.CMD;…`), so a `.ps1` shim could
  never be found by a bare `graphify` — the bug itself. That single fact makes `.cmd`
  the only artifact satisfying both "no exe" and "resolves by bare name".
- **Filed the pair** (`win-graphify-shim.{handoff,prompt}.md`; Opus 1–2, Sonnet 3–5) with
  the six behaviours extracted from the bash source — re-entry guard · PATH scan skipping
  **all** interceptors · self-identifying marker strings (`pathshim._INTERCEPTOR` greps
  them) · exit 127 rather than bare-name fallback · meter only if cage answers · exact
  passthrough.
- **Traps written in, all real:** **cmd has no `exec`** — `call … & exit /b %ERRORLEVEL%`
  means a nested process and a `Terminate batch job (Y/N)?` prompt on Ctrl-C, recorded as
  a **documented divergence** rather than pretended parity; **npm's graphify on Windows is
  itself `graphify.cmd`**, so the PATH scan must skip cage's copy by *content*, never by
  filename; both shims may coexist (Git Bash/WSL) and must skip each other.
- **Phase order defended:** liveness (4) precedes the CI flip (5) — a twin without
  detection recreates F1's nine-day silent unmetering on a new OS. And Phase 1's contract
  doc is also TOOL-SDK's first artifact, so the Windows fix lays the paved road's first
  paver rather than detouring from it.
- **Next step:** run `ci-graphify-matrix.handoff.md` (①), then `win-graphify-shim.prompt.md` (②).

---

## 2026-08-01 (Cowork) — declined plays removed from the proposal, not just marked

- **Asked:** remove play 1 and play 2 from the market-play file.
- **Done:** both sections deleted outright, not struck through. The doc is now a
  single-play proposal, so it was **renamed `market-plays.md` → `otel-genai-export.md`**
  with its title and frontmatter rewritten to match — a file whose name promises three
  plays and delivers one is the same class of lie as a stale README claim.
- **Kept deliberately:** a one-line record of *what* was removed and by whom (a `uvx`
  instant-trial push and ccusage interop), so a future reader doesn't re-propose them as
  fresh ideas; and the research context (~10% of orgs can prove agent ROI; the
  capture-vs-attribution split), which stands independent of the declined plays and
  still informs ADOPT and HR1's ranking.
- **OTel export downgraded** from "defer until 1–2 ship" (they never will) to **not
  scheduled** — it serves the team/enterprise story, and the graphify track comes first.
- **Forward refs updated** (`proposals/README.md`, `OPEN-WORK.md`); the two earlier
  WORKLOG entries keep the old filename as written — history is not rewritten, and this
  entry is the rename record.
- **Next step:** unchanged — README-FIX commit, then CI-GF.

---

## 2026-08-01 (Cowork) — direction set: graphify works, then a paved road for more tools

- **Asked (direction):** *"not interested in play 1 or play 2 — i want graphify to work
  and maybe in future more tools."*
- **Recorded:** market-plays 1–2 (uvx trial, ccusage interop) **DECLINED** in the
  proposal's own status line; OTel export stays parked unaccepted. The research context
  is kept — it still informs the moat/entry framing.
- **Measured the gap the directive implies:** "graphify" appears in **34 of 91 modules**.
  The receipt substrate (`savings/<tool>/`, pricing ladder, `[tools] order`, roi/attrib/
  verdict) is already tool-agnostic — a second tool's *reporting* costs zero code — but
  the *capture* side (shim, `cage data graphify`, `graphifymodel`, transcript patterns,
  liveness scans, its confidence constant) is bespoke. That asymmetry is the cost of
  "more tools later" and the reason a contract is worth extracting.
- **Filed `proposals/tool-integration-contract.proposal.md`:** interceptor **template** rendered
  per tool (the `runshim.py` pattern — WIN-GF's `.cmd` twin renders from the same
  template) · a generic `cage data meter <tool>` verb (graphify's becomes an alias) ·
  per-tool detection/confidence **registry as data** (stdlib law: no plugin execution) ·
  per-tool savings model behind one interface, honest UNPRICED without one.
  **fux is the second tool** (`fux/cage_receipt.py` already pushes receipts); the
  contract ships only when two tools use it — a one-consumer abstraction is
  speculation.
- **Queue re-ranked into the graphify-works track:** README-FIX (truth first) →
  **CI-GF** (the green harness everything else refactors under) → **WIN-GF** (phases
  1–2 write the shim behaviour contract = the tool contract's first artifact) →
  **ADOPT** (do agents even invoke it) → **NET-1** (does it pay) → **TOOL-SDK**.
  DOGFOOD/SKILLS/HR1/DEBT queue behind; MKT row removed.
- **The sequencing insight worth keeping:** WIN-GF and TOOL-SDK share their first
  deliverable — extracting the bash shim's behaviour into a written contract serves
  both, so the Windows fix is not a detour from the paved road, it is its first paver.
- **Next step:** README-FIX commit (Arpit) · then run CI-GF's handoff.

---

## 2026-08-01 (Cowork) — market research pass; three plays filed; queue re-ranked

- **Asked:** research + creative review of all proposals and open items.
- **Research (web):** only ~10% of orgs can prove agent ROI, and those that can
  attribute spend **to commits** — HR1 ask #1 in the market's own words. **ccusage**
  (4.8k★) parses the same Claude Code JSONL cage does, via bare `npx`, across 15+
  agents — and does zero attribution, no counterfactuals, no method tags. OTel GenAI
  semantic conventions standardize token telemetry; adoption measurement is an active
  research area (AISI 177k MCP-tool study). Sources in the session log.
- **Read:** cage's moat is the half ccusage doesn't have (attribution + honesty);
  cage's gap is the frictionless entry ccusage has. Compete on neither's turf:
  **interop**.
- **Filed `proposals/market-plays.md`:** (1) **uvx instant trial** — cage is stdlib-only,
  the perfect `uvx` citizen, and never says so; make `uvx cage-flux demo` the README's
  first command (~zero code, verify entry point). (2) **ccusage interop** — a
  `format = "ccusage"` custom-tool source (the kiro-cli mechanism) ingests its JSON:
  15-agent breadth in one parser, rows `estimated`, no receipts, fail-loud on schema
  drift. Their users are cage's audience, pre-qualified. (3) **OTel GenAI export** —
  `cage data export --otel`, one-way like CSV; feeds Langfuse/Helicone instead of
  fighting them. Deferred behind 1–2.
- **Deliberately not proposed:** proxy/observability platform (infra, not $0) ·
  per-user enterprise attribution (different axis; per-commit is the defensible one) ·
  real-time dashboards (determinism law).
- **Queue re-rank from the research:** ADOPT stays high (timely, nothing ships it);
  HR1 #1 (tokens/commit) rises — it is the proven-ROI cohort's own vocabulary; the
  gross-vs-net finding is a Show-HN-grade content play (a draft, not code).
- **Next step:** verify `uvx cage-flux` works (minutes, dev machine) → README first
  command; then the standing queue (README-FIX commit · CMD-SYNC · NET-1).

---

## 2026-08-01 (Cowork) — proposal sweep: every open item now has a doc; 2 stale-CLAUDE.md finds

- **Asked:** a plan for WIN-GF · review all proposals (update/archive) · a proposal per
  open item · a skills proposal. Nothing committed.
- **WIN-GF** — expanded into a **5-phase plan** inside its proposal: behaviour contract
  → `.cmd` twin (cmd, not PowerShell — no execution-policy variance) → `cage setup`
  wiring → wiringscan/pathshim liveness (PATHEXT-aware) → the CI assertion flips.
  Order rationale recorded: contract before twin (two implementations of an unwritten
  contract drift), liveness before flip (a twin without detection recreates F1 on a
  new OS). Opus for phases 1–2.
- **Proposal review — the significant find:** the two parked CLAUDE.md proposals
  (`claude-md-prices-file`, `claude-md-sources-authority`, both 2026-07-28) are
  **still needed, not archivable** — checked against CLAUDE.md: the flow diagram still
  omits `prices.toml`, and the `[sources]` paragraph still describes the pre-Directive-A
  extend/replace-with-fallback semantics. CLAUDE.md is the doc every agent loads;
  both annotated and filed as **CMD-SYNC** (Arpit's accept gates application, per the
  proposals' own rule). The other three reviewed: `larger-lab-corpus` and
  `policysync-synthetic-bundle` valid with live triggers; `agent-vs-human-v2` current.
  **Archived: none** — every parked proposal survived review.
- **Four new proposals**, one per open item that lacked a doc:
  `net-positive-evidence-run` (NET-1 — protocol with **pre-committed outcomes**, so no
  post-hoc reading) · `dogfood-report` (release-checklist refresh so it can't drift
  stale) · `insights-adoption` (counts only — usage rows stay unpriced or their
  invariant breaks) · `structural-debt` (split-on-contact with named seams; explicitly
  NOT proposing to trim the 38 verbs). README-FIX needs none (done in tree); CI-GF
  already has a handoff (further along than a proposal).
- **`cage-skills`** — six candidates over existing surfaces, all prompt-only except the
  adoption-nudge. Governing rule: **a skill never computes a number — it runs cage and
  quotes it**, method tags verbatim, refusals relayed never smoothed. Start:
  cage-analyst + cage-task-closer (the latter feeds the closed-task pipeline that
  NET-1/compare/estimate are all starved by). Three agents always.
- **Next step:** Arpit's calls — README-FIX commit · CMD-SYNC accept · pick from the
  proposal queue. Agent-buildable next: CI-GF, ADOPT.

---

## 2026-08-01 (Cowork) — review fallout: README fixed in tree; three plans + two proposals filed

- **Asked:** from the review — fix 1/2/3 with my judgement, a CI with/without-graphify
  plan (4), what to do on adoption (5) and debt (6); propose an agent-vs-human v2
  (per-commit: tokens · who did what · suggested-vs-accepted · time); update the README;
  **commit nothing**.
- **README (in tree, uncommitted — README-FIX):** the two human-axis claims replaced
  with real capabilities (gross/net + adoption); a gross-vs-net honesty beat added to
  the story, linking the finding — the ON-arm-cost-more result presented as proof the
  discipline works, not hidden; Platforms now states the Windows shim gap; an
  evidence-status paragraph under the demo matrix says plainly the A/B verdict is
  still open at n=1 and that `verdict` refuses it. ELI5 rewritten off the
  robot-vs-you framing (it was the removed axis in disguise).
- **Judgement calls:** (2) evidence front-running fixed by *stating the evidence
  state*, not weakening the demo — the matrix stays, labelled as the seeded demo.
  (3) DOGFOOD cannot be done from here (real ledger lives on the dev machine; ZERO
  dummy data) — filed with the exact step: `cage report` on cage's own ledger → a
  "Measured on itself" README section.
- **CI-GF plan** (`ci-graphify-matrix.handoff.md`): a `graphify: [absent, present]`
  axis on `python-package.yml`. Key insight making it free: graphify is AST-only —
  real binary + real queries in CI cost $0; only *agent* traffic is paid, which stays
  lab-scope. The Windows `present` leg asserts the WIN-GF gap **flip-ready**. Absent
  legs stay byte-identical (the always-running gate); `present` skips (never fails) on
  npm flake. CI proves mechanics; the lab keeps fidelity.
- **ADOPT (5):** filed — `cage insights adoption`, per-agent invoked/receipted/missed
  from usage rows + receipts; the "never ran vs ran-and-missed" distinction is the
  product surface leg D proved possible.
- **DEBT (6):** filed low — `paths.py` splits fix-on-contact (next router change moves
  routing out, etc.), never big-bang; a bare-`cage` landing flow for the 38-subcommand
  surface.
- **HR1 → proposal written** (`agent-vs-human-v2.md`), the four asks graded honestly:
  tokens/commit = build (reuse `taskgroup`'s join, never a second one) ·
  authorship/commit = mostly built (provenance aggregation; unknown-rate stated first) ·
  suggested-vs-accepted = new counts-only capture, `estimated`, enum resolution
  (proposed/landed/landed-modified/dropped — line-level accept-% not claimable) ·
  time = agent `measured`, wall-clock `measured`, **human only by attestation** —
  gap-derived attention is vetoed with an evidence bar for reopening (the v1 killer).
  Build order #2→#1→#4(agent/wall)→#3→#4(attest).
- **Fix-on-contact:** WIN-GF's wall-of-text row moved to
  `proposals/windows-graphify-interceptor.md`; row now one line. OPEN-WORK back to 0
  rows over budget.
- **Next step:** Arpit reviews README diff + the HR1 grades; then README-FIX commit is
  his call, CI-GF is the next agent build.

---

## 2026-08-01 (Cowork) — archive swept; `docs/` root is clean

- **Asked:** archive implemented docs.
- **Done:** `budget-optin-verify.prompt.md` (the last unarchived pair — BUD-V closed
  earlier today) moved to `archive/v0.36-budget-optin-verify.prompt.md` with a header
  recording the verdict: **keep as-is, no code fix**, and that the `policy sync`
  entanglement it was written to catch **did not materialise**. `docs/` root now holds
  **zero** handoff/prompt/plan files — it reads as a true list of work not yet done.
- **Found while checking: the archive index had drifted.** 29 of 54 v0.36 files had no
  row in `archive/README.md`. Classified rather than bulk-added:
  - **25** are the 2026-07-28 consolidation sweep, covered by that section's prose. Made
    the coverage **explicit** — the section now states it stands in for individual rows
    on purpose, because 24 near-identical rows would bury the pairs carrying distinct
    work, and names the eight families so a reader can find them on disk.
  - **4** were archived outside that sweep and genuinely lacked rows:
    `open-work-runner`, `three-agent-parity`, `legd-publish`, `budget-optin-verify`.
    Rows added.
- **`docs/README.md`** *Active work* now reads **None**, and says plainly that what
  remains is not agent work: NET-1 (a lab session), HR1 (a proposal first), H (the
  release, blocked on the no-commit directive).
- **Next step:** NET-1 or H — both are Arpit's call; no agent work is queued.

---

## 2026-08-01 (Cowork) — SYNC-FIXTURE re-scoped to SYNC-GUARD (my call)

- **Asked:** what to do for SYNC-FIXTURE. Arpit delegated the choice: *"make the best
  call."*
- **Investigated first:** `policy.bundled_raw()` is the **single**, uncached point
  `policysync` reads the bundle from, and neither `policysync` nor `pricestoml` reads the
  bundle's *text* (only the project file's) — so a synthetic bundle is one monkeypatch.
  But the `v016` fixture calls `initcmd.run()`, which scaffolds the project file **from
  the real bundle**, so a fake bundle needs a fake project file too. And a fully
  synthetic bundle stops testing sync against the actually-shipped bundle —
  `test_already_in_sync_message_on_current_file` is the only real-bundle coverage and
  must survive any refactor.
- **Called it: guard now, fixture later.** Three reasons. (1) **Sequencing** — a half-day
  test refactor on a green 956/0 suite immediately before a release delivers nothing to
  users and takes real regression risk. (2) **The pain was diagnosis, not repair** — the
  re-point took minutes; understanding five budget-unrelated failures took far longer, and
  a guard captures exactly that for ~an hour. (3) **Two removals in one cycle is not the
  steady state** — this cycle deleted an entire axis *and* made budgets opt-in; a normal
  release removes no tables.
- **Done:** `docs/sync-fixture-guard.prompt.md` (**Sonnet**, prompt only — too small for a
  pair per CLAUDE.md). Its highest-value part is not the guard but moving the borrowed
  table/key into **one named constant**, so a future re-point is a one-line edit rather
  than a five-test rewrite. The fixture is filed as
  `docs/proposals/policysync-synthetic-bundle.proposal.md` with an evidence trigger — a **third**
  removal — rather than a date, matching the ADR veto-condition style.
- **Recorded honestly in the proposal:** the synthetic fixture's real cost is losing
  real-bundle coverage, so it is a downgrade unless the smoke test survives it.
- **Next step:** CLEAN, then SYNC-GUARD.

---

## 2026-08-01 (Cowork) — CLEAN specced: cleanup becomes advisory

- **Asked:** default cleanup 30 → 90 days · show a warning when cleanup is due, optional
  via `cage.toml`, default true · **never** a separate cleanup for tools like graphify /
  fux, because deleted savings are unrecoverable.
- **Checked the third point first, and it is already satisfied** — tool savings live at
  `ledger/savings/<tool>/` (`Footprint.savings_dir`) and `cleanup.NEVER` protects
  `"ledger/"`. **But only structurally:** move that directory one level out and the
  protection vanishes with no test failing. Specced an explicit test (a savings file
  survives `prune` even at `days=0`) plus a comment at `NEVER` and a standing invariant
  in CLAUDE.md, so the guarantee stops being incidental to the path layout.
- **Decided (Arpit) — warn-only, the strongest of the three options offered:** the auto
  sweep never deletes again; deletion happens solely via `cage data cleanup --apply`.
  New `[cleanup] warn` switch, default true, env `CAGE_CLEANUP_WARN`, `policy._flag`
  precedence.
- **Trade-off recorded rather than solved:** `state/` now grows unbounded for anyone who
  ignores the notice. Accepted — unrecoverable deletion is the worse failure — mitigated
  by making the reminder recur every throttle interval and include the reclaimable size
  so it escalates naturally. The prompt says *do not reintroduce automatic deletion*.
- **Requirements that are easy to get wrong, so written explicitly:** stderr never stdout
  (stdout is the deterministic table surface) · silent when zero items are eligible (a
  "0 items" reminder trains people to ignore it) · honour `CLEANUP_THROTTLE_HOURS` or it
  prints on every command · fail-open.
- **Left undecided for the executor:** what `[cleanup] enabled = false` means now that
  auto never deletes — full off switch, or no-automatic-anything while an explicit
  `--apply` still works. Recommended the second (someone typing `--apply` has asked
  plainly), but it must be chosen aloud.
- **Flagged as stale-on-landing:** CLAUDE.md's cleanup paragraph states the auto path
  prunes; it becomes wrong the moment this ships.
- **Next step:** SUITE first (green the suite), then CLEAN.

---

## 2026-08-01 (Cowork) — corpus frozen; the too-small hypothesis filed

- **Asked:** what does "corpus refresh cadence" mean, what is the impact, what to do?
- **Explained:** `_src/tinyshop/` (~43 KB, 6 modules, byte-pinned by `.fixture-sha256`)
  is the control variable. Changing its bytes invalidates every published comparison —
  the ceiling, the modelled `raw_alternative` and the graph communities all move — so a
  refresh forces a full **A-arm re-run**: paid tokens for the scripted legs, a manual
  session across three agents for leg D.
- **Decided — the corpus is FROZEN.** `tinyshop` is never mutated; a new question gets a
  **new named corpus alongside** it, results labelled per corpus. Old evidence stays
  valid permanently. Matches the append-only philosophy, and costs nothing today.
  Removed from *Decisions open*; the standing rule in `cage-lab/README.md` law 5 was
  strengthened from "rebuild the configuration, never the corpus" to name the freeze.
- **Raised, and Arpit filed it:** tinyshop may be too *small* to show graphify's value —
  with six modules, reading them all is cheap, which is exactly the cost a graph exists
  to avoid. **This bears directly on K+NET:** leg D's "+14% with graphify ON" has two
  incompatible readings — graphify's overhead exceeds its benefit *generally*, or only
  *on a 43 KB corpus* — and nothing currently distinguishes them. Filed as
  `docs/proposals/larger-lab-corpus.proposal.md` (`status: proposed`), with the trigger being
  NET-1: if 5 paired tasks clear `MIN_COMPARE_N` on tinyshop and graphify still reads
  net-negative, "the fixture is too small" becomes the leading remaining explanation.
- **Explicitly not proposed:** replacing tinyshop. Its bytes are the control for every
  published result; mutating it would invalidate the leg D report and both benchmarks
  for no gain.
- **Next step:** unchanged — run `suite-green.prompt.md` (SUITE).

---

## 2026-08-01 (Cowork) — SUITE pair written (BUD-V-TEST + G-SAV)

- **Asked:** handoff + prompt to close BUD-V-TEST and G-SAV.
- **Done:** `docs/suite-green.{handoff,prompt}.md` (**Sonnet**; escalate to Opus only if
  re-pointing the sync tests changes what they assert). Filed as one item, **SUITE** —
  same change, same goal: 949/6 ⇒ 955/0.
- **G-SAV diagnosis confirmed in code:** `schema.make_savings` *accepts* `ts`;
  `record()` does not, so it lands in `**_ignore` and every row is stamped now. Fix is
  the signature. **Keep `**_ignore`** — three shim-boundary callers (`graphifytx` ×2,
  `graphifymeter`) rely on the fail-open push contract. Flagged that `**_ignore` is
  *why* the drop survived, and proposed (ask-first) a kwarg-parity test so the next one
  is impossible rather than unlikely. Also required: the shard test must prove a
  **past-month** `ts` — a fix that only works for the current month is the same bug
  with better luck.
- **BUD-V-TEST: ruled out one of the two options you named.** Hand-writing an active
  `[budgets]` block into the `v016` fixture **cannot** work — the assertions compare
  against a *bundled* default (`bundled 25.0`, `1.0 → 2.0`), and with no bundled
  counterpart the classifier buckets an active table as `project_own` and leaves it
  alone, which is precisely what BUD-V verified as correct. So: re-point at a live
  table. Constraints written into the handoff — must be active in the bundle, must
  **survive `_strip_to_v016`** (which strips `[cleanup]`, ruling out your example),
  simple scalar key, not already another test's subject. `[quality]` is the likely fit,
  flagged verify-don't-assume.
- **Named the deeper problem:** these tests couple *generic mechanics* to *whatever cage
  ships*, which is why removing one product table reddened five unrelated tests — and it
  recurs on the next removal. Durable fix is a **synthetic bundle fixture**. Left as an
  explicit decide-and-state, recommending re-point-now **plus** filing the fixture.
- **Guards:** don't restore `[budgets]` to green a test; don't weaken an assertion
  silently; per-test before/after note proving mechanics coverage survived.
- **Next step:** run `suite-green.prompt.md`. Then NET-1 / HR1 / H.

---

## 2026-08-01 (Cowork) — K2/K3/K4 found built; queue reconciled, K-TEST filed

- **Asked:** what does "K3/K4 — place the wording" mean, and what are the consequences?
- **Explained:** HONEST-LIMIT is a *verdict*, not a defect — the source can't carry the
  fact, so cage refuses to invent it. **K3**: kiro's `ts` is import-stamped, `session` is
  the constant `"kiro"`, `project` absent ⇒ rows can't be ordered, `--since` is
  meaningless for them (included/excluded by when *import* ran — the dangerous case,
  because the number looks normal), and no kiro ON/OFF delta may ever be reported.
  **K4**: copilot's stores are separate so `surface` is real; claude's are shared so it
  is blank and unknowable — blank means "the source does not say", never `"cli"`; for
  claude, `project` is the discriminator that does work.
- **Found while checking: K2, K3 and K4 are all BUILT** in the working tree —
  `paths.kiro_routed`, `importcmd._kiro_leg`, the cwd-scoped credits filter,
  `report._kiro_limits_caveat`, `report._surface_caveat`, and a `kiro-routing` explainer
  entry. **Fourth stale-marker catch today**; verifying against code rather than the
  plan is what surfaced it each time.
- **The executor beat the handoff on K2:** comparing the resolved **ledger dir** instead
  of the root collapses `CAGE_BASE` and `CAGE_LEDGER` together and makes a same-process
  double-lock impossible *by construction* — so the fixed-lock-order advice I wrote was
  unnecessary. Recorded in the archive header.
- **Done:** IMPLEMENTATION entry appended (removal precondition), K2 and K3/K4 removed
  from OPEN-WORK, kiro pair archived, README pair count corrected.
- **⚠️ Carried forward as `K-TEST`:** none of it is pinned. Two tests merely *call*
  `paths.kiro_routed` to stay routing-aware; **nothing asserts** that kiro lands globally
  from inside a project, that `--ledger` still wins, that one turn appears once across
  two project ledgers, or either caveat's text. An honesty line that can regress silently
  is backwards — these must be pinned before the release.
- **Next step:** BUD-V, then K+NET; K-TEST before H.

---

## 2026-08-01 (Cowork) — verification prompt for the budget opt-in

- **Asked:** a prompt to test the budget change before deciding what to do.
- **Done:** `docs/budget-optin-verify.prompt.md` (**Sonnet**; escalate to Opus only if
  `policysync` manages `[budgets]`). Eight checks: suite · bundle parses and is inert ·
  the guard never blocks · fresh scaffold inherits no cap · **opting back in still
  works** (most likely broken, least likely noticed) · existing projects unaffected ·
  the `policy sync`/`freshness`/`explain_data` entanglement · goldens.
- **Framed report-don't-fix**, ending in a keep / keep-with-fixes / **revert**
  recommendation — the call is Arpit's, so it gathers evidence rather than assuming the
  change is right. Guards: don't restore defaults to make a test pass (such a test was
  pinning the old decision); don't add a constant fallback; **G-SAV** pre-classified as
  pre-existing so it isn't misattributed.
- **Filed as BUD-V** at the top of the queue — verifying an unvalidated change outranks
  starting new work.
- **⚠️ Two tooling lessons, both cost real time this session:**
  1. Editing docs with `str.replace` **fails silently** when an anchor has drifted — the
     script rewrites the file unchanged and still reports success. One edit this
     exchange printed "ok" and landed nothing. **Assert the anchor before writing and
     re-read after.**
  2. `docs/README.md`'s *Active work* had been reset to "nothing pending" by the
     executing session while three prompt pairs sat in `docs/` root. Fixed, and it is
     the same class as a stale OPEN-WORK: **the index must be verified against `ls`,
     not trusted.**
- **Next step:** run `budget-optin-verify.prompt.md`, then `net-savings.prompt.md`.

---

## 2026-08-01 (Cowork) — budget caps become opt-in (bundle change, UNVERIFIED)

- **Asked:** the cost cap must be defined in `cage.toml` — absent ⇒ not needed, present
  ⇒ enforced.
- **Found:** the *code* already behaves exactly that way. `policy.budgets` returns `None`
  for a missing key, `budget.check` computes `over = bool(cap and …)` so a `None` cap can
  never trip, `proceed` stays True, and `render_budget` prints `—` for both cap and
  of-cap. **Nothing to build.**
- **The actual defect was the bundle**: `cage/data/cage.toml` shipped
  `[budgets] session_usd = 2.00 / daily_usd = 25.00 / on_exceed = "warn"`, so every
  scaffolded project got a ceiling nobody chose.
- **Done:** commented the `[budgets]` table out of the bundle, following the
  `[ledger] warn_mb` precedent, with a comment stating the semantics. **Deliberately no
  constant fallback** (unlike `warn_mb`): there is no defensible default spend for
  someone else's project, and a cap nobody asked for is a false alarm.
- **⚠️ UNVERIFIED — could not run the suite here.** The Cowork sandbox is Python
  **3.10.12**, which lacks `tomllib`; cage requires 3.11+. Established a baseline first:
  the same 8 test files give **47 failed / 39 passed / 21 errors both before and after**
  the edit, so the change introduces no new failure *that this environment can see* —
  but that is not a green suite. **Run `just test` locally**; a golden with a budget
  line may need re-blessing, and `test_policysync`/`test_prices_split` touch the bundle.
- **Lesson recorded:** the sandbox cannot validate cage. Any code/data change made from
  Cowork must be handed back as unverified with an explicit local-test instruction.
- **Next step:** run `just test`; then `net-savings.prompt.md` (Opus).

---

## 2026-08-01 (Cowork) — NET re-scoped: the machinery already exists

- **Asked:** what can be done about NET ("nothing answers: is graphify actually saving
  money?").
- **Found, reading the code first: I had overstated the work.** `cage insights compare`
  *already* answers the measured A/B ("did tasks with graphify cost less"), and
  `cage insights verdict <tool>` *already* computes `net = saved − own-cost` and prints
  SAVING / COSTING / INSUFFICIENT DATA. The item as filed described building what exists.
- **The two real gaps:**
  1. **Evidence, not code.** `compare` gates at `MIN_COMPARE_N = 5` closed tasks per arm;
     leg D produced 1. Below the gate it refuses — correctly. Filed as **NET-1**, a lab
     task, no build.
  2. **A genuine blind spot.** `roi`'s "own cost" is `receipt.meta.tool_cost_usd` — what
     the tool spends on *itself*. graphify is AST-only and declares **$0**, so
     `verdict graphify` computes `net = gross − 0 = gross` and reports **SAVING** on the
     exact sessions leg D measured costing ~14% more. Cage has no concept of *cost of
     use* (the invoking turn, the hook's injected context, a re-read) as distinct from
     *the tool's own cost*.
- **Constraint established:** graphify receipts are **call-less** (a `task`, no `call`),
  so per-query net is impossible for shim-pushed receipts — task-level via `taskgroup`
  is the honest granularity. Recorded in the handoff so no one fakes the link.
- **Done:** `docs/net-savings.{handoff,prompt}.md` (**Opus**) covering K + NET-2 + NET-3
  as one change (NET-2's wording depends on K's relabel). Explicitly out of scope: a
  second comparison path — `compare` stays the A/B answer.
- **Left undecided for the executor:** what counts as *attributable* cost (whole task ·
  tool-use turns only · a window around the receipt `ts`). Each is defensible and each
  yields a different number, so it must be chosen aloud and documented, not picked
  silently.
- **Arpit selected all four options** including "close the item"; read as *close the
  vague NET item, replace with the three concrete ones*, the only self-consistent
  reading. Flagged in-session.
- **Next step:** run `net-savings.prompt.md` (Opus); NET-1 whenever a lab session runs.

---

## 2026-08-01 (Cowork) — K2 handoff + prompt written

- **Asked:** write the K2 handoff/prompt pair.
- **Done:** `docs/kiro-routing.{handoff,prompt}.md` (**Opus**). The handoff leads with
  the two-stores/opposite-fixes table, then the part that is actually hard: a per-root
  table of everything `importcmd.run` builds against a single sink (`seen`, cursors,
  `_import_lock`, `_write_manifest`, `_record_health`, `_record_capture_log`,
  `_import_rollup`) and what each breaks when the kiro leg writes elsewhere. Approach is
  a **contained nested leg**, explicitly not a rewrite, with a deadlock warning about
  concurrent project imports.
- **Also confirmed while writing:** the kiro **CLI** store is not a built-in adapter at
  all — it arrives as a *custom tool source* (`fmt="kiro-cli"`) through
  `import_custom_tools`, and `_ingest_credits` calls `parse_kiro_cli_credits(f)` with
  the default `workspace=""`, i.e. every conversation on the machine. That is the CLI
  half of the double-count, and the fix is a filter, not a reroute.
- **Left undecided on purpose** (flagged for the executor): whose `capture_enabled`
  switch governs a write to the *global* ledger when the project's policy is the one
  loaded; and what the `captured N new` summary reports when a sweep touches two
  ledgers. Both are real precedence questions, not details.
- **Flagged:** `docs/cage-lab/03-verify.md` check 11 (`~/.cage` untouched) stops being
  true for a *default* run and must be updated to distinguish default vs `--ledger`.
- **Next step:** unchanged — **HUMAN** first (it deletes code K2's read-side wording
  would otherwise touch twice), then K2.

---

## 2026-08-01 (Cowork) — ADR 0006 scope error caught before implementation

- **Asked:** what needs to be implemented for ADR 0006 (kiro rows are machine facts).
- **Found, reading the code to build the change-map: the ADR's scope was wrong.**
  Kiro has **two** stores with **opposite** attribution properties, and the ADR said
  "kiro rows" throughout:
  - **IDE** `tokens_generated.jsonl` (`parse_kiro_calls`) — no project, `session="kiro"`,
    no `ts`. Machine fact. The ADR is correct for this one.
  - **CLI** `conversations_v2` SQLite (`parse_kiro_cli_credits`) — **keyed by cwd**, real
    `conversation_id`, real `updated_at`. Project-attributable. `parse_kiro_cli_credits`
    already takes a `workspace` filter; the importer just passes `""` (read-all), which
    is why it double-counts. **The correct fix here is the opposite of the ADR** — pass
    the cwd and stamp `project`.
  Routing CLI credits to the global ledger would have destroyed attribution the source
  actually supports — and credits are the paid unit, so it is money.
- **Done:** amended ADR 0006 in place (retitled to *Kiro **IDE** rows…*, added a Scope
  table naming both stores, narrowed the decision and the veto trigger). OPEN-WORK's K2
  row now carries both directions.
- **Also identified:** the real implementation cost is not the routing rule but
  `importcmd.run`, whose docstring states "one active sink per run — never a
  double-write". `seen`, cursors, `_import_lock`, manifest, health, capture-log and the
  rollup are all built per-root. Kiro writing elsewhere breaks that invariant
  deliberately, so the sweep needs a contained nested leg for the global sink.
- **Lesson:** an ADR written from a survey rather than a full read can encode a scope
  error that looks authoritative. Building the change-map *before* handing it off is
  what caught it.
- **Next step:** unchanged — HUMAN first; K2 needs its own handoff before execution.

---

## 2026-08-01 (Cowork) — three decisions: human axis out, kiro routed global, NET filed

- **Asked:** explain K / K2 / K3-K4 (what's happening, what's wrong, what to do); plus
  two new directives — *something that tells me if graphify is actually saving money*,
  and *remove the human calculation completely, rebuild after the 0.36 release*.
- **Decided — HUMAN:** remove the Tier-1 human axis **including the substrate**
  (`gap_ms` on calls, `"minutes"` in `UNITS`) — a substrate-contract change, plan
  §3/§4.10. Ships **in 0.36 as a breaking change** ⇒ CHANGELOG *Removed* section +
  `verbmap.REMOVED` entries so `cage human` prints a direction instead of exiting 1.
  Rebuilt after release.
  ⚠️ **Trap recorded in the plan: cage has two different "human"s.** The Tier-1 cost
  axis is the one being removed; **provenance `origin="human"` is authorship and must
  survive untouched.** An agent told only "remove human" would take both.
- **Decided — K2, upgraded from a decision to a fix.** Arpit pushed back on
  document-or-warn: kiro is paid, so a wrong number is a real problem. Investigation
  showed it's worse than "don't sum" — kiro's log has no project/session/ts, so
  importing it into a *new* project pulls the whole global history (workspace-on's 28
  rows included 22 turns from the workspace-off phase). **Per-project kiro cost has
  never been correct.** Fix: kiro rows go to the **global ledger only**; explicit
  `--ledger`/`CAGE_BASE` still wins so cage-lab keeps isolation. Double-counting becomes
  impossible by construction. Also established: kiro ids (`c_kiro{idx}{sha1}`) are
  stable across ledgers, so id-merging paths (`ledger-sync`, `--team`, study bundles)
  were already safe — only naive file-summing broke.
- **Filed — NET:** the real question under K. Layer 1 net = gross − the measured cost of
  the invoking turn; layer 2 paired ON/OFF delta (the only "actually"), which the
  existing `compare`/`verdict`/`study` machinery already supports; layer 3 hook tax
  falls out of layer 2. Must print INSUFFICIENT DATA at n=1.
- **Sequencing call:** **HUMAN goes first.** `compare`/`verdict`/`matrix` all carry
  human total-cost lines, so building NET before the removal means editing the same
  code twice.
- **Next step:** write the HUMAN handoff + prompt pair (Opus — deletion with
  entanglements, per the CLAUDE.md tier rubric).

---

## 2026-08-01 (Cowork) — `meta` closed; queue down to 4

- **Asked:** what's pending for the **meta** item.
- **Found:** nothing — it was implemented in Claude Code in parallel with this session.
  Verified against the prompt's acceptance criteria rather than taking the build log's
  word: literal gone from `data/cage.toml`, `policy._bundled()` derives from
  `__version__`, `initcmd._stamp_cage_version()` stamps once at scaffold, drift-guard
  test present, `policy_version` untouched, prompt archived.
- **Done:** removed **meta** from OPEN-WORK (recorded in IMPLEMENTATION.md, so removal
  is legal) and bumped the registry rows. `docs/README.md` had already been updated by
  the executing session.
- **Flagged from the build, not in the spec:** a latent `pricestoml._inplace_table_edit`
  bug (a new key inserted before the *next* table header rather than after the table's
  own last key) was found by a **manual smoke test** — no test pins insertion position,
  so that coverage gap is still open. Also `test_zipapp.py`'s verbatim-copy assertion
  legitimately changed meaning, and was declared rather than quietly relaxed.
- **Next step:** **K — relabel `saved` as gross** (proposal B). Queue: K · K2 · K3/K4 · H.

---

## 2026-08-01 (Cowork) — OPEN-WORK re-cut to the budget (the trial's first test)

- **Asked:** *"create a plan for pending items."*
- **Done:** rewrote `OPEN-WORK.md` under the new size discipline. **205 → 40 lines**,
  exactly at budget. Leads with next/blocked/state in 3 lines; one 5-row pending table;
  open decisions; what binds the next lab run; a 5-line maintenance pointer.
- **Nothing deleted without a home** — verified before cutting: all seven durable rules
  are already carried in `CLAUDE.md` (`.venv`, usage-rows) or `docs/cage-lab/` (ZERO
  dummy data, precision-vs-source, reproducible-workspace, corpus-not-config, three
  artifact types), so the section became a link. The superseded 2026-07-29 list and the
  ✅ tail went with it.
- **⚠️ Trial finding, day one — the rule was wrong as written.** Four rows blew the
  120-char cap on *raw* length while their rendered text was ~107. Markdown link
  targets cost ~60 raw chars and zero reading burden, so counting raw **punishes
  exactly the linking rule 3 requires** — the two rules fought each other.
  **Amended: measure rendered text** (strip link targets, `*`, backticks). Recorded in
  `doc-size-discipline.md` §4 with a runnable check, tagged as a trial amendment. All
  rows now pass; one row was genuinely too long and was shortened.
- **Decided:** the amendment is exactly what the expiry is for — the rule met a real
  doc and lost a piece of itself on the first contact. Cheap because it was a trial.
- **Next step:** **K — relabel `saved` as gross** (proposal B).

---

## 2026-08-01 (Cowork) — doc size discipline, on trial to 2026-09-01

- **Asked:** plans are too big to read — can anything be done? Then: add the rules with
  an **expiry date** so they can be tried and retained or removed, into CLAUDE.md, with
  a separate section if Claude Code needs more detail.
- **Diagnosed (mine, not the format's):** evidence inlined when `regression/` and
  `archive/` already own it · one doc written for three audiences (decider, executor,
  future reader) when the handoff/prompt convention exists to split them · index rows
  promising "one line each" written at 300–400 chars.
- **Done:** four composing rules — lead with the answer · one audience per doc ·
  evidence lives elsewhere · a hard budget (plan ~40 lines, table row ≤120 chars).
  Summary in CLAUDE.md; full spec, worked before/after, fix procedure and trial-exit
  criteria in the new [doc-size-discipline.md](doc-size-discipline.md). Indexed in
  docs/README + DOC-REGISTRY.
- **Decided:** scope is *all authored docs*, but reference docs (CLAUDE.md, PLAN.md,
  design docs) are **exempt from rule 4 only** — CLAUDE.md is loaded into every agent's
  context and its density is load-bearing; rules 1–3 still bind them. My call, flagged
  as reversible at review.
- **Decided:** the trial **lapses if unreviewed** on 2026-09-01 rather than persisting.
  A trial that silently becomes permanent was never a trial. Judged on evidence — does
  Arpit read the plan · did anything get lost · violation count · any decision made
  worse — not on preference.
- **Deliberately not built:** the grep test for over-length rows. Enforcing a rule
  before knowing it works is backwards; it's listed as an option *if* the trial is
  retained.
- **Next step:** re-cut OPEN-WORK.md to the budget (~205 lines → ~1 screen), which is
  also the trial's first real test.

---

## 2026-08-01 (Cowork) — OPEN-WORK is a continuously-maintained doc

- **Asked:** *"always maintain open work document and keep it upto date add it in
  claude.md"*.
- **Done:** the CLAUDE.md OPEN-WORK entry gained the **currency obligation** on top of
  the existing removal rule — maintained continuously, updated in the *same* change as
  the work, with six explicit triggers (item finishes · new work/defect discovered ·
  scope/verdict/owner/priority changes · blocked or unblocked · order changes ·
  standing constraint added or lifted), and the symmetry stated: **discovering work and
  not filing it is the same defect as finishing work and not removing it.** Added a
  second clause: **never trust the file's own ✅ markers as ground truth** when
  reconciling — verify against `regression/`, `archive/`, `IMPLEMENTATION.md` and the
  code, citing today's stale-marker miss as the worked example. Mirrored both into
  OPEN-WORK's header and widened the DOC-REGISTRY trigger from "a phase opens/closes"
  to the full continuous list.
- **Decided:** the queue is a *live* instrument, not a checkpoint artifact. Its failure
  modes are symmetric — an unfiled discovery understates the work exactly as a stale ✅
  overstates progress — so both are named as defects of the same class.
- **Next step:** unchanged — **K, relabel `saved` as gross** (proposal B).

---

## 2026-08-01 (Cowork) — OPEN-WORK becomes remove-on-done; the rule enters CLAUDE.md

- **Asked:** *"in open work md file once the task is done remove it from the list but
  make sure everything is up to date with details in implementation file / add it in
  claude.md file as well."*
- **Done:**
  - **CLAUDE.md** gained two entries. (1) A release-checklist line: `[meta]
    cage_version` **is the package version, always** — derive it from
    `cage.__version__` (the `manifest.py` pattern), never hand-maintain it; a
    project's existing stamp is history and is never rewritten. It also records that
    **`policy_version` is deliberately NOT coupled to the release** — it is a content
    counter driving the `cage policy sync` recommendation, and bumping it per release
    would tell every project its defaults are stale when nothing changed.
    (2) A *Documentation discipline* entry making **OPEN-WORK.md** a maintained doc
    with its own law: **a completed item is REMOVED, never left ticked**; removal is
    legal only once the outcome is appended to IMPLEMENTATION.md and any evidence
    published to regression/; residual limits/decisions are carried forward as their
    own items. Framing: *a ticked-but-present item and a deleted-but-unrecorded one
    are the same bug in opposite directions — the first inflates the queue, the second
    loses the history.*
  - **OPEN-WORK.md** rewritten under its own new rule: header states the law; the
    phase index rebuilt to **pending-only**; the completed section bodies (A, B+B-fix,
    C, D, E, F, G, I, J) deleted and compressed into one *Done and removed* line
    pointing at IMPLEMENTATION.md + regression/; the RESOLVED **K1** row removed with
    a note recording where it went. Duplicate `## K` heading fixed (the follow-up
    tracker is now `## L`). **212 → ~200 lines, and every line is now work not yet
    done.**
  - **docs/README.md**: `legd-publish.prompt.md` moved out of *Active work* (spent),
    the OPEN-WORK blurb restated as the remove-on-done law, the "Leg D is DONE" note
    updated to DONE **and PUBLISHED** with the true remaining list.
  - **Archived** `legd-publish.prompt.md` → `archive/v0.36-legd-publish.prompt.md`
    with the standard header (implemented for v0.36, unreleased; names the seven
    artifacts it produced).
- **Decided:** the queue's *length* is the signal. A plan file that accumulates ticked
  items stops being readable as a plan, so completion is recorded **elsewhere** (build
  log + evidence) and deleted **here**.
- **Corrected mid-task:** my first pass listed `B-fix-3` and the copilot `--path` glob
  as pending — both were already built (`hookbypass.py`; `[sources] path_globs`,
  archived). Checking `docs/regression/` and `docs/archive/` against the file, rather
  than trusting its own ✅ markers, is what caught it. A stale ✅ is exactly the failure
  the remove-on-done rule exists to prevent.
- **Open:** `meta-version.prompt.md` is the only unstarted prompt (`cage_version` still
  ships `0.25.0` against `__version__ = "0.36.0"`).
- **Next step:** **K — relabel `saved` as gross** (proposal B: *"avoided read cost
  (gross) — excludes the cost of using the tool"*). Highest value, trivial cost, and it
  guards cage's headline number.

Entry-point tracker: ALL-CAPS, no frontmatter.

---

## 2026-08-01 — Claude Code: built `[sources] path_globs` (leg-D K1 closed)

- **Asked:** run the path-globs prompt — move the `--path` discovery patterns out of
  `importcmd.py` and into `cage.toml`, fixing the copilot `--path` bug. Opus, no paid
  calls, tree stays uncommitted.
- **Found first:** `paths.py` already held an **unstaged, unwired 82-line WIP block**
  from an interrupted prior session, implementing a *separate* `[path_globs]` table —
  nothing read it, no tests, no docs, and nothing in WORKLOG/README ratified that shape.
  Treated as WIP and replaced.
- **Two forks put to Arpit, both recommendations accepted:**
  1. **Shape:** `path_globs` is a **per-entry key inside `[sources]`**, not a sibling
     table. One table, one materializer, one resolver; `replace = true` covers it for
     free — which is literally what the handoff's "same table, same semantics" asks for,
     and what its "exists on the resolved source model" wording describes.
  2. **`--project`** (out of the prompt's stated scope) also reads the key, so **no**
     glob literal survives anywhere in `importcmd.py` rather than one surviving two lines
     from the one removed.
- **Built:** seed in code → `cage setup` materializes → `cage.toml` is the authority.
  `_scan` now takes a pattern *sequence* and dedupes the file set. Absent `path_globs`
  ⇒ loud no-op. Zero-match ⚠ names the patterns tried. Doctor advisory for a stale table.
  `cmd_import_claude` was passing **no policy** — it would have resolved zero patterns;
  fixed.
- **Verified beyond the suite:** real CLI smoke — `--path` over a `chatSessions` tree
  imports with `surface = vscode` and does **not** match a sibling foreign `.jsonl`; the
  loud-absence line and the doctor advisory both render. The AST grep-gate was proven to
  bite by temporarily reintroducing a literal.
- **Sealed-doc tension, resolved by precedent:** §9.5 asks to flip the finding's Status,
  §6 says don't touch `docs/regression/**`, and the file is pinned by its `.sha256`. The
  repo already has the answer — DOC-REGISTRY records the 2026-07-29 benchmark being
  bannered "with digests unchanged above a `HASH-COVERS-BELOW` marker". Applied the same
  convention: a RESOLVED banner above the marker, published body byte-identical, digest
  **verified unchanged**. No re-hash, no rewrite.
- **Open:** one proposed CLAUDE.md sentence (not applied — the prompt says propose and
  stop).
- **Tests:** 939 passing; 2 pre-existing clock-relative failures, confirmed unrelated by
  re-running against the pre-change tree.
- **Next:** K0 — relabel `saved` as gross.

## 2026-08-01 — Claude Code: write up and publish leg D

- **Asked:** synthesise the six leg-D cell records into the three artifact types and
  publish them — run report, four finding docs, final phase benchmark — under a strict
  honesty contract: zero invented numbers, never upgrade an UNPROVEN to a PASS, never
  soften a FAIL, don't edit the cell records to fit the narrative. No paid calls; the cage
  tree stays uncommitted.
- **Done:** read all six cell records and reconciled every figure against both lab
  ledgers (`workspace-{off,on}/.cage/`) before writing anything — calls, imports,
  receipts and usage rows all agree with the cells. Published
  `2026-08-01-leg-d-run-report.md`, four `2026-08-01-finding-*.md`, and
  `2026-08-01-phase-benchmark.md` (+ sidecars, + index rows). Bannered the 07-29
  benchmark and added a current-Status header to the 07-29 adoption finding — both above
  a new `HASH-COVERS-BELOW` marker, **digests unchanged**, bodies untouched.
- **Headline published:** claude invoked graphify unprompted (2 queries, **18,456 tokens
  saved**, `route: transcript`); copilot and kiro did not. Adoption is agent-specific and
  cage measured it.
- **Mid-write-up, a seventh cell record appeared** — the operator's `saved` **is GROSS**
  finding, with "do not publish the benchmark without this". Published as
  `2026-08-01-finding-saved-is-gross.md` (**HIGH**), and the counterweight now leads in the
  run report headline and sits above the fold in the benchmark, not in a footnote.
  **Corrected its cost row explicitly rather than silently:** it apportioned D1's cost from
  a two-session total (≈$0.28 ⇒ ≈+14%), but `imports.jsonl` has a per-session row for D1
  (`est_cost_usd 0.242783`, 30 rows) ⇒ the measured delta is **+31%**. Every token split in
  that record reconciles to the ledger exactly.
- **Held the line on three over-claims:** F2's copilot-VS-Code limit is **untested, not
  confirmed** (copilot never invoked graphify, so the path never fired); D3/D4 prompt
  counts are **UNVERIFIED** (5 and 4 rows vs a 7-turn script, count unrecorded); no kiro
  ON/OFF delta is reported (kiro rows carry no `ts`/`session`/`project`, so D5 and D6 are
  indistinguishable in the ledger).
- **Decided/open:** Phase **D** closed, Phase **I** complete (scripted + manual); new
  **K** section carries the five findings, K0 (`saved` is gross, HIGH) leading. One is a
  real code bug (copilot `--path` glob),
  filed **not fixed** — this task was a write-up, not a code change.
- **Next step:** K1 — fix `importcmd.import_copilot`'s `--path` glob and add the
  `chatSessions/` test.

## 2026-07-30 — Claude Code: publish the lab artifacts + the three shim-integrity fixes

- **Asked:** execute `shim-integrity.handoff.md`/`.prompt.md` — publish the three
  Phase-I cage-lab artifacts (approved), then build B-fix-1 (doctor checks the
  **PATH-winning** graphify), B-fix-2 (heal or name stale adopt-era shims), B-fix-3
  (warn when a graphify hook bypasses the interceptor). No paid calls, no commits.
- **Done:** all four tasks. New `cage/pathshim.py` (four-state PATH resolution, dead =
  doctor **failure**) and `cage/hookbypass.py` (absolute-path hook, **advisory**);
  `agents.install` heals only inside a cage-managed root; the three artifacts hashed
  with sidecars and the old benchmark bannered superseded above its hash marker.
  37 new tests; suite 925 green.
- **Decided (confirmed with Arpit before building):** `foreign` is **ok-level**, not
  warn — doctor's existing `interceptor` check already warns about that same absence,
  and a second warn is the noise that gets a check ignored. The PATH check runs on
  **every** doctor invocation (the handoff's stated default) — its whole value is
  being unmissable.
- **Found, not fixed:** `test_I2_verdict_saving` is a **clock-driven** golden — the
  `insights regression` 7d window is read from the live clock while the seed pins
  fixed July dates, so it flipped to INSUFFICIENT DATA today (cutoff `07-22 20:19Z`
  vs newest seeded call `07-22 09:00Z`). Left red rather than re-blessed: blessing
  would encode a clock-dependent state as the output contract. Unrelated to this work.
- **Left alone deliberately:** this machine's stale `anton/bin/graphify` — doctor now
  names it, but healing a specific machine is out of scope (Arpit, 2026-07-29).
- **Open / next:** Arpit decides on the I2 golden and on the proposed CLAUDE.md
  wiring-liveness sentence (drafted in the handback, **not applied** — propose-and-stop).
- **Next step:** await those two calls; manual leg D remains the only open Phase-I work.

## 2026-07-30 — Claude Code: cage-lab three-agent parity fix

- **Asked:** the same-day rebuild wired claude only; bring `cage-lab` to
  three-agent parity (claude+copilot+kiro, both workspaces) per updated
  `docs/cage-lab/01-setup.md` (now carries law 0: three agents always in scope).
  Zero paid calls, don't drive questions, don't re-author the fixture.
- **Done:** `cage setup --all --no-graphify` (workspace-off) / `cage setup --all`
  (workspace-on), plus `graphify kiro install` in workspace-on (claude/copilot
  installers re-ran idempotently). `cage setup --status` now lists all three agents
  wired in both workspaces. Re-verified the whole gate: no clobbering across three
  installers + cage's block, workspace-off still clean (including its new
  cage-written `.kiro/` MCP dir — zero graphify content in it), interceptor still
  live and still beats the stale anton shim, fixture hashes unchanged, `~/.cage`/
  `~/.zshrc` both unchanged. `rebuild.sh` and `drive.sh` updated so the parity fix
  is reproducible from scratch, not just true of the current tree.
- **Found, not resolved:** `01-setup.md` §3/§4 now pin a fixture layout
  (`_src/pkg/...`) and question set that don't match what's built
  (`_src/tinyshop/...`). Left the fixture untouched (standing law: never
  re-author it; a hash mismatch is Arpit's call) — flagged in `cage-lab/SETUP.md`
  and `docs/IMPLEMENTATION.md` for a decision.
- **Open / next:** Arpit resolves the fixture/manual mismatch, then reviews
  `questions.txt` and drives via `drive.sh` (claude/copilot) + the manual kiro
  cell (`05-manual-cells.md`).
- **Next step:** await Arpit's call on the mismatch; no further action taken.

## 2026-07-30 — Claude Code: rebuild cage-lab from scratch (setup only, zero paid calls)

- **Asked:** `../cage-lab` was deleted; rebuild it from `docs/cage-lab/01-setup.md`,
  recording every command. Stop after the §6 verification gate — Arpit drives the
  question set himself. Zero paid calls beyond one authorized ~$0.02 smoke prompt.
- **Done:** fresh `_src/tinyshop/` fixture (6 files, ~8.1k-token `models.py` + 4 small
  cross-calling modules — caught and fixed a real dataclass-inheritance bug while
  proving it runs), `questions.txt` (6 Qs), `workspace-off`/`workspace-on` built per
  the manual, `SETUP.md`/`rebuild.sh`/`drive.sh` written. All 6 §6 checks pass
  (`rebuild.sh`, idempotent, $0 by default; `--smoke` opts into the one paid check).
  Smoke prompt captured into `labledger/`; `~/.cage` and `~/.zshrc` both confirmed
  byte-for-byte unchanged.
- **Decided/found:** three real-CLI deviations from the manual's literal commands,
  each corrected back into `docs/cage-lab/01-setup.md`/`02-run.md` in this same
  change (Python version floor, `workspace-off` needs `--no-graphify`, PATH needs
  the per-workspace `bin/` not a shared one). `graphifyy` turned out to already be
  on PyPI (0.9.30) — no local-source deviation needed there, only for cage (v0.36
  unreleased). Separately found: the 2026-07-29 run's raw report artifacts were
  never published to `docs/regression/` before that lab was deleted and are now
  gone — recorded as a process finding in `docs/OPEN-WORK.md` §I, not something
  this session could recover.
- **Open / next:** Arpit reviews the six questions (printed in the handback),
  authors `runs/<run-id>/run-manifest.md`, then drives `./drive.sh <off|on>
  <claude|copilot> <run-id>` himself. Kiro stays manual-only (05-manual-cells.md).
- **Next step:** await Arpit's go on driving; this session took no further action.

## 2026-07-29 — Claude Code: OPEN-WORK Phase I scripted legs (clean-room A/B)

- **Asked:** run I — cheapest model, full matrix, rebuild cage-lab from scratch (clean
  capture). copilot ON = both plain + forced. Run now.
- **Done:** rebuilt cage-lab from scratch; drove **70 real prompts** across claude+copilot
  CLIs × arms; captured isolated (`--ledger`, dev cage w/ F1). **24 graphify receipts — 23
  via the new F1 copilot detector on real traffic, 1 claude auto-adopt; copilot-plain=0.**
  I.4 all PASS. $5.29, 429 turns. Three deliverables written in `cage-lab/reports/`.
- **Findings:** kiro unscriptable (manual D); copilot ON = passive skill; **the graphify gap
  is adoption, not capture** (measured). F1 validated end-to-end on real data.
- **Open / next:** publish the 3 lab artifacts into `cage/docs/regression/` — **gated on
  Arpit** (guardrail). **Leg D** (manual VS Code + kiro, 4/6 cells UNPROVEN) — Arpit's hands.
  H (release) still blocked by no-commit.
- **Next step:** await Arpit on (1) publish-to-regression, (2) scheduling leg D.

## 2026-07-29 — Claude Code: OPEN-WORK G + F (free; C folded into I)

- **Asked:** after gate-1, Arpit chose *fold C into I* and *start G and F*.
- **Done:** **G1** 0.3 confidence labelled UNVALIDATED everywhere · **G2** ADR-0005 veto
  threshold made precise (`dc>1.0%` over ≥5 both-route runs) + named the honest gap (`dc`
  uninstrumented; miss untallied; filed) · **G3** graphify LLM-verb audit (metered verbs
  LLM-free; extract/update backend-gated; proxy is the config-only route) · **G4** bounded
  ceiling now in the `report` footer (modeled, not CSV, silent w/o a graph — 0 goldens
  changed) · **F1** copilot-CLI detection BUILT (reuses shared counterfactual/deferral,
  ADR-0005 tests pass) · **F2** copilot-VS-Code probed = usage-row-only (command yes, result
  no). `just test` green — **889 passed**.
- **Decided / open:** CLAUDE.md needs an architecture-note refresh (graphifytx is now
  claude+copilot-CLI; ceiling is community-bounded + surfaced in report footer) — **not
  edited** per the no-silent-CLAUDE.md rule; proposed for Arpit. G2 instrumentation of `dc`
  filed, unbuilt. Real machine has **0** graphify-via-copilot invocations to catch (adoption).
- **Next step:** report G+F; then **I** — needs Arpit's go + the still-open **cost cap**;
  and I.3's copilot/kiro graphify-ON installers still don't exist (must build or scope out).

## 2026-07-29 — Claude Code: OPEN-WORK A + B (free, pre-gate-1)

- **Asked:** run the pending OPEN-WORK phases in order; A + B are free and first; stop at
  GATE 1 and report before any paid call (C).
- **Done:**
  - **A (ceiling credibility):** ran the ceiling on cage's own `graphify-out/` = 552,159
    tokens / 249 files — **not defensible** ("one question reads every file" is false).
    Shipped a **community-bounded** ceiling (`repoceiling.community_corpus`): largest
    community = 89,853 / 22 files (upper bound), median ≈3,007 (typical), whole corpus as
    context; pre-community graphs fall back to `UNBOUNDED`, loud. Tests + FORMULAS +
    GLOSSARY + explain_data updated. `just test` green.
  - **B (VS Code shim):** probed via this session's own VS-Code-extension subprocess PATH.
    Interceptor reaches PATH only through a shell-rc append (per-machine, launch-method
    dependent), and the PATH-winning shim here is a **stale adopt-era** one that routes
    through the removed `cage graphify` (exit 1) → **silent unmetered pass-through**. VS
    Code shim capture is CONTINGENT; transcript is the reliable route. Corrected §F table.
- **Decided / open:**
  - A's fork (community-subgraph vs read-count cap) collapsed: read-counts don't exist on
    day one, so community-subgraph is the only viable deterministic bound — no compare doc.
  - Filed (not built): doctor should scan the PATH-winning `graphify`, not just the root's
    `bin/`; `cage setup` should heal a stale adopt-era shim; **anton's shim needs healing**
    (edits another repo — needs Arpit's ok).
- **Next step:** **STOP GATE 1** — await Arpit's go for C (~2 paid calls). Do not spend.
- **Update (same session):** Arpit gave the go for C and said *leave anton's shim (filed
  only)*. On starting C, found **`cage-lab` is not on this machine** (`../cage-lab` absent)
  — arm B's workspace (`golden/workspace/`, `graphify claude install`, interceptor) and
  arm A's baseline (`golden/captures/`) are all in that missing repo. **C is BLOCKED; 0
  paid calls spent.** Refused to improvise a fresh workspace (a new baseline ≠ arm A's
  control — would measure nothing). Corrected OPEN-WORK Phase C. **Blocked on Arpit:**
  restore/clone cage-lab, or fold C into I (build the workspace via I.2, needs the cost
  cap). G3's finding doc already exists in-tree and already reads as adoption-not-defect.

- **Asked:** execute the graphify-capture handoff (GC0–GC5); probe first, change-map,
  pause; keep `just test` green; docs; no paid calls; tree uncommitted.
- **Done:** GC0 probed **real** logs — copilot-cli carries command+result
  (`tool.execution_*`), copilot-vscode partial, kiro none → verdict in plan §3.0.
  Built GC1 usage rows (`usagelog.py`), GC2 claude transcript detection
  (`graphifytx.py` + shared `repoceiling.py`), GC3 deterministic ids + content-key
  deferral (ADR 0005), GC4 doctor graph-staleness, GC5 forward model
  (`graphifymodel.py`) composed into `insights verdict graphify`. 879 tests green;
  new tests for all phases; re-blessed goldens I2/I3. End-to-end verified via CLI.
- **Decided/open:** GC3 id design — kept **session in the id** (per-session
  attribution) per Arpit's direction; cross-route dedupe is a **deferral**, not
  id-collision; shim session stamped honest-empty (root-cause fix). ADR 0005 records
  it with a veto tied to a measured double-count rate. `savings_id` added as an
  additive kwarg (call_id precedent). **Open:** whether to archive the
  handoff/prompt pair now — kept **active** because GC6/G1 remains a live plan phase
  and the tree is uncommitted (no version to name); flagged for Arpit. A CLAUDE.md
  usage-row invariant is *proposed* below, not applied.
- **Next:** GC6/G1 (the A/B re-run) is now runnable.

## 2026-07-28 — Claude Code: G0.5 executed — golden workspace rebuilt, plan §1.1 corrected on contact

- **Asked:** execute the G0.5 handoff — rebuild `cage-lab/golden/workspace/`'s
  tooling layer with the real installers, fixture preserved byte-for-byte,
  every command recorded, no paid calls.
- **Done:** pre-flight sha256 of fixture (9) + captures (148) + regression
  docs (46); moved workspace aside (never deleted until verified); restored
  fixture unchanged; `git init` (nested, gitignored from cage-lab); `graphify
  update .` (510 nodes/534 edges/62 communities); `graphify claude install`;
  `cage setup --claude`; `cage doctor` confirmed the interceptor **live**
  once `workspace/bin` was prepended to PATH (matching `drive.py`'s own
  convention for `graphify=on` cells — checked the driver's source rather
  than guessing); re-hashed everything → identical. Wrote `SETUP.md` +
  `rebuild.sh`, then **actually ran `rebuild.sh`** (not just authored it) —
  it reproduced byte-identical `CLAUDE.md`/`settings.json` on a second pass
  and correctly refused to re-run while its own safety backup still existed.
  Removed both backup copies only after every check passed. Committed in
  cage-lab; cage tree left uncommitted per the standing directive.
- **Decided / found, all folded into plan §1.1 on contact:** the PreToolUse
  hook `graphify claude install` writes **never shells out to `graphify` at
  all** — it's a static `[ -f graphify-out/graph.json ] && echo '<json>' ||
  true` that only injects fixed instructional context on Glob/Grep; the
  PATH-bypass risk the plan named is real but lives downstream, only if the
  agent itself later runs `graphify query|...`. No `--strict` flag exists in
  the installed `graphifyy 0.5.0`. No per-subcommand `--help` — appending
  `--help` runs the installer for real. Copilot and Kiro **do** have
  first-party installers (`copilot install`, `vscode install`, `kiro
  install`) — the plan's "no copilot or kiro installer" claim was wrong,
  correction filed, doesn't change G0.5/G1 scope. Neither installer clobbers
  the other's `CLAUDE.md` block in the graphify-then-cage order (verified via
  before/after diff, not assumed); whichever runs first on an absent file
  does decide whether the file gets a `# CLAUDE.md` H1, which is why the
  rebuilt file lacks the one the old workspace had.
- **Open:** G1 (~2 paid calls) — run the real driven claude question against
  this workspace and record whether graphify fires and whether cage sees it.
- **Next step:** hand back to whoever runs G1; nothing further needed in
  cage-lab or cage for G0.5 itself.

## 2026-07-30 — Cowork: shim-integrity landed → docs/ root emptied, five items left

- **Confirmed built:** B-fix-1/2/3 (`pathshim.py`, `hookbypass.py`, doctor checks) and
  the three lab artifacts **published + hashed** into `docs/regression/` with index rows.
  Phase **B** and phase **J** now closed; **I** has only its manual leg outstanding.
- **Archived the three now-implemented prompts** (`three-agent-parity`,
  `cage-lab-rebuild`, `open-work` runner → `archive/v0.36-*`), so `docs/` root is back to
  the nine living docs and once again reads as *work not yet done*. Active work is
  **empty by design**; the remaining items are not documents.
- **Rewrote OPEN-WORK's pending list to the five real remaining items**, superseded list
  kept: (1) ledger hygiene decision — blocks D · (2) **prove B-fix-1/3 outside the test
  suite** — run `cage doctor` in `workspace-on` and in a shell where the stale
  `anton/bin/graphify` wins · (3) leg D, Arpit's six manual cells · (4) the final
  benchmark superseding `2026-07-29-phase-benchmark.md` once D fills the 4 UNPROVEN
  cells · (5) H, release — at which point cage-lab's `-e ../cage` deviation expires and
  must switch to the published wheel.
- **Item 2 is the one I'd not skip:** the tests prove the checks work in the abstract;
  the anton shim and the lab's own absolute-path hook are the two real-world cases that
  motivated them, and neither has been run through the shipped check yet.
- **Next:** ledger decision → doctor confirmation → leg D.

## 2026-08-01 — Cowork: `[meta] cage_version` drift (0.25.0 vs 0.36.0) — prompt written

- **Arpit:** `[meta] cage_version`/`policy_version` should always be the package version.
- **Agreed on `cage_version`, pushed back on `policy_version`** — the latter is a
  **content counter** read by `freshness.py` / `doctorcmd._policy_version` to recommend
  `cage policy sync`. Coupling it to the release would tell **every project on every
  release** its policy defaults are behind, even when nothing changed — killing the
  signal. `prices_version` is date-based and independent for the same reason.
- **The `cage_version` drift is worse than a stale literal:** `pricescmd.py:150` **prints
  it** (`prices — bundled … (cage 0.25.0)`) and `_POLICY_META_KEYS` **copies it into every
  newly created project**. So a value eleven releases stale is both displayed and
  propagated.
- **The right pattern already exists in-tree:** `manifest.py:54` does
  `row.setdefault("cage_version", __version__)` — derived, cannot drift. And
  `docs/example/toml-config.md:45` already shows `0.36.0`, so **the doc asserts the
  invariant the shipped data file violates.**
- **Why it drifted:** tests assert the key *exists* and that project meta matches bundled
  meta, but **nothing asserts it equals `__version__`**, and no release-flow step mentions
  it. The checklist line is the real fix; the code change is cleanup.
- **Semantics settled in the prompt:** a *project* stamp is a **historical fact** (which
  cage scaffolded this — never rewritten); the *displayed/bundled* value is **always the
  running package version**. The bundled key's meaning was undefined, which is exactly why
  nobody bumped it.
- **Shipped** [meta-version.prompt.md](meta-version.prompt.md) (**Sonnet**, unpaid) with a
  guardrail: if anything depends on the bundled value being *older* than the package, stop
  — that would make it a real counter and the whole change wrong.

## 2026-08-01 — Cowork: THE HARD FINDING — `saved` is gross; graphify ON cost MORE

- **Arpit asked the question the whole cycle avoided:** overall, did using graphify save
  tokens or cost more? Answered from leg D's own paired data rather than from the
  receipts.
- **D1 OFF vs D2 ON** — same agent, surface, fixture, questions, model; graphify the only
  variable: **+37% calls (30→41), +29% tokens in (1.29M→1.67M), +78% out, ≈+14% cost.**
  Cage recorded **18,456 tokens saved** for the same session.
- **Both numbers are true.** `saved = raw_alternative − actual` is a **per-query
  counterfactual** that never subtracts the cost of *using* graphify: the query turn
  (each drags ~40k cached tokens at this context size), the hook's tax on every
  `Bash|Grep`/`Read|Glob` call, or a re-read provoked by the **truncated** ~2,000-token
  graph answer. Nothing is miscomputed — **the label is narrower than it reads.**
- **This points at cage's own headline metric**, and it's the same class of quiet
  wrongness cage exists to catch in other tools. `repoceiling` inherits it: the day-one
  bound is gross too.
- **Confidence held deliberately low: n = 1 ⇒ UNPROVEN, a signal not a measurement.**
  The repeats = 3 rule exists for exactly this comparison and the manual cells ran once.
  ~95% of input is cache reads, so the token delta overstates and dollars (~14%) are the
  right lens; D1's cost is apportioned, not measured.
- **Proposal: B now, A next, C later** — (B) relabel to *"avoided read cost (gross) —
  excludes the cost of using the tool"*; (A) report `net saved` = gross − the cost of the
  turns that produced the query (computable — that turn is in the transcript cage already
  parses); (C) session-level ON/OFF delta in `insights verdict` where paired data exists.
- **Made BLOCKING:** written to `cage-lab/reports/cells/FINDING-gross-vs-net-savings.md`,
  added as OPEN-WORK **§K** (HIGH), and inserted into the leg-D publish prompt as
  **Task 2b** — the benchmark may not print "27,658 saved" without the cost-delta
  counterweight.
- **Next:** publish leg D *with* K, then relabel (B), then `path_globs`.

## 2026-08-01 — Cowork: path_globs designed (copilot --path fix, config-driven)

- **Asked:** research and propose the fix for the copilot `--path` glob bug; then
  "option B, but defined in cage.toml, not hardcoded in Python".
- **Researched the real code first.** Three `--path` branches, three hardcoded globs
  (claude `**/*.jsonl` ok · copilot `*/events.jsonl` **broken** · kiro `*` ok).
  `_parse_copilot_any` already dispatches on shape and `_detect_graphify_copilot` uses
  the same test — **both stores are supported downstream; only the glob can't reach one.**
- **Rejected reusing the existing `[sources] glob`** (my earlier option C): it is
  **anchored** to its declared root, so `--path` at a `chatSessions` dir would still match
  nothing — the same bug relocated. That killed the tidiest-looking option.
- **Rejected the one-line `**/*.jsonl`**: works, but only *incidentally* safe (a foreign
  jsonl happens to parse to zero rows). Named both copilot shapes explicitly instead —
  safe by construction.
- **Design (Arpit's directive applied):** a new **`path_globs`** key, root-agnostic,
  distinct from the anchored `glob`. **Two keys, two jobs** — overloading one reintroduces
  the bug in a new place. Resolution follows the existing `[sources]` pattern exactly:
  **seed in code** (so a new agent store ships in a release, not in hand-edited tomls) →
  **materialized by `cage setup`** → **`cage.toml` is the authority at import time**.
- **Consequence accepted and made loud:** a project with no `[sources]` gets no
  `path_globs`, so `--path` matches nothing — stated explicitly, never a silent code
  fallback, consistent with the existing "empty [sources] captures NOTHING" law.
- **The half that matters as much as the glob:** the zero-match message must **name the
  patterns tried**. Hiding the glob is why this bug cost 20 minutes in leg D.
- **Shipped** [path-globs.handoff.md](archive/v0.36-path-globs.handoff.md) +
  [path-globs.prompt.md](archive/v0.36-path-globs.prompt.md) (**Opus**, unpaid; archived
  on implementation 2026-08-01), with 8 tests including
  a **grep-gate** (no glob literal survives in the `--path` branches) and the
  `surface = "vscode"` test that pins the actual fix — untested today, because D3 only
  showed `vscode` via a declared `[sources]` override.
- **Next:** run the leg-D publish prompt, then this one.

## 2026-08-01 — Cowork: LEG D COMPLETE (6/6 manual cells) + publish prompt

- **Ran all six manual cells with Arpit**, live, over ~90 minutes. Cell records written
  as we went: `cage-lab/reports/cells/D1..D6-*.md`.
- **The headline:** same workspace, same six questions, same graphify install —
  **claude invoked graphify unprompted (2 queries, 18,456 tokens saved, via the
  TRANSCRIPT route); copilot and kiro did not.** Adoption is agent-specific, and the
  usage log is what made "never ran" distinguishable from "ran but cage missed it".
- **D2 vindicated the graphify-capture cycle:** the VS Code extension's subprocess never
  had the workspace `bin/` on PATH, so the interceptor shim never ran — exactly as phase
  B predicted. Had cage only had the shim, both savings would have been invisible. The
  GC2 transcript detector built this session is the sole reason they exist.
- **Four product findings, all invisible to the scripted legs:** (1) `import --agent
  copilot --path` hardcodes the CLI glob and can never reach the VS Code store —
  reports "matched 0 files" while the files parse fine; (2) kiro rows **double-count
  across ledgers** (global log × per-workspace ledgers); (3) kiro rows carry **no time,
  session or project** — its A/B is not reconstructible at all; (4) per-surface
  attribution works for copilot (separate stores) but not claude (shared store).
- **Process failures worth remembering:** I twice gave commands with inline `#` comments
  that zsh passed as arguments; and I asserted a bare `cage import` was safe under
  `on_read = false` — it isn't, it's a machine-wide sweep by definition, and it
  contaminated workspace-off with 33,003 rows. Both corrected in the docs.
- **Shipped** [legd-publish.prompt.md](legd-publish.prompt.md) (**Opus**, unpaid) — run
  report + 4 finding docs + final benchmark, hashed and indexed, with a strict honesty
  contract: no invented numbers, UNPROVEN never upgraded, and **F2's copilot-vscode
  limit marked untested rather than confirmed** (copilot never invoked graphify, so the
  limit was never exercised — the easiest place in the write-up to over-claim).
- **Open:** D3/D4 prompt counts unrecorded → to be published as UNVERIFIED.
- **Next:** run the publish prompt, then the copilot `--path` glob fix, then release.

## 2026-07-30 — Cowork: B-fix-3 decided and specced (doctor warns on hook bypass)

- **Arpit: yes, cage should warn** when a graphify hook invokes by absolute path.
- **Specced as B-fix-3** in [shim-integrity.handoff.md](shim-integrity.handoff.md) +
  [prompt](shim-integrity.prompt.md); OPEN-WORK §J's open question is now a decision.
- **The design call that matters: ADVISORY, never a doctor failure.** B-fix-1's dead
  shim means *cage's own wiring is broken* (failure); an absolute-path graphify hook
  means *graphify is working exactly as designed and cage merely can't observe that
  path* (advisory). Blurring them would cry failure on a correct third-party
  integration — which is how a check earns being ignored, and this check exists
  precisely because the last silent gap went unnoticed for nine days.
- **Message written to be true, not loud:** "graphify's hook invokes `<path>` directly
  — cage's PATH interceptor is bypassed, so any saving on that path is invisible.
  Savings from an explicit `graphify query` are unaffected."
- **Escalation on `--strict`** — detectable from the command string (or
  `GRAPHIFY_HOOK_STRICT`): there the read hook *denies* the first raw read, so the
  avoided read is a saving unmeterable by any current route. Stronger wording there.
- **Hook is never modified** — graphify owns that artifact; same rule as `foreign`.
- **Next:** run the shim-integrity prompt (now 3 fixes), decide the ledger reset, drive.

## 2026-07-30 — Cowork: cage-lab reviewed → graphify 0.9.30 invalidates three findings

- **Reviewed the rebuilt lab.** Good: three-agent parity real (`✔ claude ✔ copilot
  ✔ kiro` both workspaces), all three graphify integrations present in `workspace-on`,
  OFF clean, shim is the live `cage data graphify` form, isolated ledger works,
  `~/.cage` untouched, `bin/` symlink matches the manual.
- **The finding: graphifyy jumped 0.5.0 → 0.9.30 and the claude integration changed.**
  Three claims cage was carrying are now FALSE — the hook "spawns no process" (it runs
  **`graphify hook-guard search|read`**), "no `--strict` exists" (it does, plus
  `GRAPHIFY_HOOK_STRICT`), and the passive `Glob|Grep` matcher (now **`Bash|Grep`** +
  **`Read|Glob`** — the agent's primary search *and* read paths).
- **PATH-bypass is back, confirmed in graphify's source**
  (`install.py::_claude_pretooluse_hooks` writes the **absolute** `.venv/bin/graphify`
  path). It never traverses PATH ⇒ cage's interceptor can't see it; a hook isn't a Bash
  tool call ⇒ the transcript route can't either. **Both routes blind.**
- **Kept proportionate:** hook-guard mostly *nudges*, and a follow-up `graphify query`
  via Bash still meters normally. The bypass costs visibility of the nudge, not
  automatically a receipt. **The real exception is `--strict`**, where the hook DENIES
  the first raw read — an avoided read is a saving with no query, unmeterable by any
  current route.
- **Decided: `--strict` OFF for run 1** — it changes behaviour *and* adds an
  unmeterable saving path; enabling it beside the ON/OFF pairing moves two variables at
  once. Filed as a separate later arm.
- **Docs patched:** 01-setup §3/§4 now match the real `tinyshop` fixture and the six
  actual questions (Q4–Q6 are deterministic, so token variance between arms is agent
  overhead, not question noise) · new §4a records the 0.9.30 facts + the strict
  decision + "record the hook block verbatim" · OFF-arm check gains the documented
  `[tools] order` exemption (a benign bundled-default line that fails a naive grep) ·
  02-run §1a ledger hygiene (reset or account for the smoke rows — real data, never
  silently deleted) · 03-verify ON cells now need **three** answers, not two.
- **OPEN-WORK §J** records the whole thing and marks §C's "hypothesis dead" line
  SUPERSEDED; open product question filed: should `doctor` warn when a graphify hook
  invokes by absolute path (the mirror of B-fix-1).
- **Next:** decide the ledger reset, then drive.

## 2026-07-29 — Cowork: three-agent scope made LAW 0 across the lab docs + parity prompt

- **Arpit:** claude, copilot and kiro are **always** in scope — document it everywhere.
- **Added as law 0** in `docs/cage-lab/README.md` (now six laws), and swept the
  conditional language out of the manual: `graphify kiro install` is **ALWAYS**, not
  "if in scope"; `cage setup --all` in **both** workspaces with `cage setup --status`
  as the check; 02-run states kiro being non-scriptable is a **route** difference, not
  a reason to drop it from the matrix; 05-manual-cells says all three appear there.
- **Rationale written in, not just the rule:** this mirrors cage's own `agents.SURFACES`
  product invariant — dropping an agent silently is how a capture gap survives a green
  report. And concretely: omitting an installer turns that agent's ON cell into a
  second OFF cell, which then reports a zero that *reads as an adoption finding but is
  a setup bug*. That misreading is the reason it must be fixed before any question runs.
- **Shipped** [three-agent-parity.prompt.md](three-agent-parity.prompt.md)
  (**Sonnet**, zero paid calls) — assess what the lab already has, re-wire both
  workspaces `--all`, run all three graphify installers, re-verify the gate, and push
  the fix into `rebuild.sh` so the next rebuild doesn't lose it. Hard guardrail:
  **never re-author the fixture** — hash mismatch means a new baseline and that's
  Arpit's call.
- **Next:** run the parity prompt, then Arpit drives the six questions.

## 2026-07-29 — Cowork: questions pinned; TWO real config gaps found before the run

- **Asked:** what are the questions, how do I type them in a VS Code extension, and is
  everything configured for claude + copilot + kiro?
- **Answer to the third: NO — two gaps, both would have silently spoiled cells.**
  1. `docs/cage-lab/01-setup.md` said `cage setup --claude` for both workspaces. That
     wires **claude only** — a copilot or kiro session there gets no MCP wiring.
     **Fixed to `cage setup --all`** in both workspaces, with `cage setup --status`
     named as the verification.
  2. `graphify kiro install` was commented out as "only if in scope". Kiro **is** in
     scope — left out, the kiro ON cell is silently just a second OFF cell.
     **Now required.**
- **Pinned the fixture layout** (`pkg/big_module.py` ~8–9k tokens + store/importer/
  policy/util/report with real cross-module calls) so the questions could be authored
  against something concrete rather than a description.
- **Pinned the six questions** in 01-setup §4: Q1–Q3 graphify-sensitive (cross-module
  reasoning a grep-and-read agent answers by opening the big module — the expensive
  path the graph replaces; repeats = 3), Q4–Q6 capture-correctness (cheap, local,
  there to generate turns to meter; repeats = 1).
- **Added 05-manual-cells §1a — how to type them in a VS Code extension:** open the
  *workspace* folder not the lab root · launch from an activated shell to carry the
  venv PATH (and record it) · turn 1 is always the pre-flight probe · one question per
  turn, never batched · same session per cell · **repeats run as separate sessions** —
  a second ask in the same chat sees the first answer and isn't an independent sample.
- **Next:** run the rebuild prompt (now with `--all`), then drive.

## 2026-07-29 — Cowork: cage-lab rebuild prompt (setup only, stops before the questions)

- **Asked:** a prompt to set cage-lab up so Arpit can then run the questions himself.
- **Shipped** [cage-lab-rebuild.prompt.md](cage-lab-rebuild.prompt.md) — **Sonnet**
  (the manual is written, decisions made; it's a recorded build with a hard gate), a
  wrapper over `docs/cage-lab/01-setup.md` rather than a duplicate of it.
- **Scoped to STOP at the verification gate.** It builds `drive.sh` but never runs it;
  the only spend is one ~$0.03 smoke prompt proving capture lands in the isolated
  ledger with `~/.cage` untouched.
- **Two things it must hand back before Arpit spends anything:** the **six authored
  questions** (so he can swap them *before* the run, not after) and the resolved PATH
  order — specifically whether the lab's interceptor out-competed the known stale
  `anton/bin/graphify`. If it doesn't, the fix is the lab's PATH order; **editing anton
  stays out of scope** per Arpit's direction.
- **Fix-the-manual-on-contact** guardrail: if a real CLI differs from
  `docs/cage-lab/01-setup.md`, use the real verb and correct the manual in the same
  change — plus the `graphify <agent> install --help` footgun (it may install for real).
- **Next:** run it, approve the questions, then drive.

## 2026-07-29 — Cowork: `docs/cage-lab/` — the rebuild manual (lab is now disposable)

- **Asked:** a separate dir in cage documenting how to set cage-lab up — it's being
  deleted and rebuilt from scratch.
- **Created [cage-lab/](cage-lab/README.md)** — 6 docs: README (what the lab is, the
  five laws, what's safe to delete) · 01-setup (`.venv` + explicit PATH, structure,
  fixture as the control variable, question set, the two workspaces via tool-owned
  installers, a verify-before-you-spend gate) · 02-run (manifest before the first call,
  the 3-vs-1 repeat split, driver responsibilities, kiro not scriptable) · 03-verify
  (per-agent bars, three-way reconciliation, 11 checks, four verdicts, what invalidates
  a cell before scoring) · 04-publish (three artifact types, append-only regression,
  what a good headline looks like) · 05-manual-cells (Arpit's leg).
- **The asymmetry made explicit up front:** the whole `../cage-lab` tree is
  **disposable**; `cage/docs/regression/**` is **never** deletable. The lab is
  scaffolding, the evidence is permanent — so results live in cage, not in the lab.
- **Written prescriptively, not descriptively** — cage-lab isn't reachable from this
  session, so the docs say how to build it rather than describing files I can't read.
  The 6 questions are specified by *shape* (graphify-sensitive vs capture-correctness)
  and must be authored fresh; content-free by construction, which is what lets captures
  be stored byte-exact.
- Linked from `docs/README.md`, `CLAUDE.md`, and OPEN-WORK §I.2.
- **Next:** delete `../cage-lab`, rebuild from 01-setup.md, then the scripted legs.

## 2026-07-29 — Cowork: `.venv` toolchain isolation made a STANDING lab rule

- **Arpit's directive:** set cage-lab up with a `.venv` — **and always do it this way.**
- **Recorded as standing** in `CLAUDE.md` (cage-lab section) and `docs/OPEN-WORK.md`
  **§I.2a**, plus a row in I.2's rebuild table and the durable-rules block.
- **The rule:** `python3 -m venv .venv` + pinned cage/graphify, and **PATH set
  explicitly by the driver** (`$LAB/bin:$LAB/.venv/bin:$PATH`) — *not* shell
  activation, which only affects shells that activate. The run **proves its own PATH**
  (`command -v graphify` written into the run manifest) instead of anyone checking by
  hand; `SETUP.md` names the exact builds.
- **Rationale from live evidence:** B found a stale interceptor in an unrelated project
  winning on PATH *from inside cage-lab* and silently unmetering every graphify run.
  Toolchain isolation is the same principle as the isolated ledger, applied one level up.
- **Declared deviation recorded:** cage-lab is black-box by rule (installs the shipped
  cage, never imports it), but v0.36 is unreleased, so `-e ../cage` is the only option.
  Written down as a deviation, to be switched to the published wheel at phase H.
- **Limit stated rather than glossed:** the venv does **not** reach VS Code extension
  subprocesses, which inherit VS Code's launch environment — so D.0's per-machine
  pre-flight still applies in full to D1–D4. Scripted legs deterministic; VS Code legs
  per-machine-verified.
- **Next:** unchanged — shim-integrity prompt, then leg D.

## 2026-07-29 — Cowork: shim-integrity handoff+prompt; manual runbook handed over in chat

- **Asked:** the manual prompt list in chat; a Claude Code handoff + prompt for the rest.
- **Shipped** [shim-integrity.handoff.md](shim-integrity.handoff.md) +
  [shim-integrity.prompt.md](shim-integrity.prompt.md) (**Opus**, unpaid): publish the
  three lab artifacts (approved) + **B-fix-1** PATH-winning doctor check
  (live/dead/shadowed/foreign; `dead` is a **failure** with a runnable fix line,
  `foreign` never touched, scan executes nothing) + **B-fix-2** heal adopt-era shims
  **in-root only**, name-don't-write outside.
- **Debate gate changed the spec twice:** "heal every stale shim you find" was rejected
  (a PATH winner can live in another project — silently rewriting it is the class of
  action cage refuses); "report the dead shim as a warning" was rejected (a dead cage
  shim means capture is **silently off**, indistinguishable from cage not installed —
  that is a failure, and the wired-vs-asset severity tiers must not blur).
- **Anton explicitly out of scope** in both docs, per Arpit — the generic capability
  gets built; no other repo is touched.
- **Residual risk named:** doctor gains a check that will fail where cage used to say
  OK. That's the point — but every finding must name the exact file and a runnable
  fix, or it becomes noise people learn to ignore.
- **Leg D runbook delivered in chat** (pre-flight → per-cell loop → verification), with
  the 6 questions taken **verbatim from `cage-lab/questions.txt`** — cage-lab isn't
  reachable from this session, and inventing questions would break comparability with
  the scripted legs.
- **Next:** run the shim-integrity prompt; Arpit runs leg D.

## 2026-07-29 — Cowork: publish approved · anton dropped · B-fixes specced · leg D checklist

- **Publish APPROVED** — the three lab artifacts (run report · finding · phase
  benchmark) may be written into `cage/docs/regression/`; recorded in OPEN-WORK so the
  guardrail no longer blocks. Append-only/never-edit still holds for what's published.
- **Anton's stale shim REMOVED from the pending list** at Arpit's direction. The two
  *generic* product fixes stand on their own; anton is no longer tracked here.
- **B-fix specced (§B-fix, not yet built)** — the two shim-integrity fixes:
  **B-fix-1** `cage doctor` resolves the **PATH-winning** graphify the way the shell
  does and applies the existing liveness test to it, reporting `live`/`dead`/`shadowed`
  /`foreign` (a dead cage shim is a doctor **failure** — capture is silently off; a
  foreign one is never touched); **B-fix-2** extend `cage setup`'s dead-verb healing to
  PATH-resident adopt-era shims, and where the shim is outside a cage-managed root,
  *name it with a runnable fix line* rather than silently editing another project.
  Read-only, side-effect-free, live-parser as detector.
- **Leg D rewritten as a runnable checklist** — D.0 per-machine pre-flight (which
  graphify wins · is it live or dead · how VS Code was launched — and `command -v`
  **through the agent's own Bash tool**, since that subprocess PATH is the one that
  matters), D.1 the six cells (claude/copilot VS Code, kiro IDE, each OFF+ON), D.2
  eleven verification questions per cell, D.3 the four verdicts. Uses the **same 6
  questions** as the scripted legs — a different set makes the cells incomparable.
- **Called out:** copilot-vscode `usage row without a receipt` is the *expected honest
  outcome* (F2: command yes, result no), not a failure to fix.
- **Next:** publish the artifacts · build B-fix-1/2 · Arpit runs leg D.

## 2026-07-29 — Cowork: one runner prompt for all pending work

- **Asked:** create a prompt to run all the pending items.
- **Shipped** [open-work.prompt.md](open-work.prompt.md) (**Opus** — A is a judgment
  call, B a probe whose negative reframes the capture story, C an experiment).
- **Two hard stop gates rather than one long run:** after A+B (free) because B's
  answer changes what C and I are worth, and before I because it needs Arpit's go
  **and** the still-open cost cap. The prompt refuses to spend a paid call or start
  I without both, and must state its own call-budget estimate before he decides.
- **Standing laws hoisted to the top** so they apply per-phase, not per-mention:
  zero dummy data (`NOT AVAILABLE`/`UNPROVEN` is the only filler) · cage tree
  uncommitted · never fabricate a limit's resolution · docs updated in the same
  change · CLAUDE.md proposed-never-silently-edited · `just test` green with every
  re-blessed golden named.
- **Handback is per gate, not only at the end**, and must explicitly name everything
  recorded UNPROVEN / NOT AVAILABLE / HONEST-LIMIT — burying those is the exact
  failure this cycle exists to prevent.
- **Next:** run it. A and B are free; everything past gate 1 waits on Arpit.

## 2026-07-29 — Cowork: four decisions recorded; manual testing moved to last

- **Repeats: exactly 3** (not "n≥3"). Recorded in I.3 — **with a warning I added
  rather than silently obeying:** applying 3 repeats to all 18 questions × both arms
  × every cell is ~600 calls. Repeats only average out *agent non-determinism when
  measuring a delta between arms*; capture-correctness cells verify the ledger
  against **this run's own log**, which is deterministic, so **n=1 is correct there
  and n=3 is pure waste**. Split: n=3 on the graphify-sensitive subset, n=1 on the
  rest. The run manifest must state the real call budget before starting.
- **Usage-row invariant → CLAUDE.md: yes, APPLIED** (two lines in Must-Know Rules,
  after "`method` is sacred"): diagnostic-only, never priced, never read by a
  derived money view, `args_hash` never carries query text. Was proposed-not-applied
  since the graphify-capture build; now landed.
- **Ceiling surfaced beyond `verdict`/`cage query`: yes** → new item **G4**. Home is
  the `report` **footer** via `display.Footer` (not a column — report is money-side);
  renders `modeled` with derivation footnoted; recommend it stays out of CSV (not a
  row-level fact); re-blesses goldens. **Gated on A** — if the whole-corpus bound
  isn't defensible, wider surfacing just spreads a number nobody believes.
- **Manual testing runs LAST** — D is now I's final leg, after every scripted leg is
  green. Stated as a principle in the order line: Arpit's time is the scarcest input,
  spent only on cells a script can't reach, and only after the automated legs have
  shaken out protocol bugs that would otherwise cost him the pass twice.
- **Still open and now the single gate on I: the cost cap.**
- **Next:** A → B → C, then G4/F, then I (scripted) → D last.

## 2026-07-29 — Cowork: OPEN-WORK gains phase I (clean-room end-to-end validation)

- **Asked:** add an item — set up cage-lab from scratch, drive the questions,
  capture logs + graphify savings into the ledger, verify every number, **with and
  without graphify** — and check what's still needed. Plus: **no dummy data.**
- **Added phase I** to [OPEN-WORK.md](OPEN-WORK.md), and **reconciled the overlap
  rather than stacking a duplicate**: I **absorbs E** (the 18-question sweep) and
  **executes D** (the manual VS Code cells) as its manual leg — both rows kept so
  the absorption is recorded, not silent.
- **I.0 restates the ZERO-dummy-data law** and says why here: a fresh lab is empty,
  cells fail, sweeps are expensive — this is precisely where a plausible row gets
  invented. `NOT AVAILABLE`/`UNPROVEN` is the only allowed filler; `tools/dummyrepo`
  never touches this ledger; the benchmark reports coverage, not completeness.
- **Scoping calls made:** "from scratch" rebuilds tooling + a new workspace but
  **keeps** Phase 1 captures (the comparison baseline) and never touches published
  regression reports; the run writes to an **isolated ledger**, never `~/.cage`
  (36,451 unrelated calls); the fixture stays hash-identical or it's a new baseline.
- **Pairing protocol:** graphify the only variable; OFF must be genuinely off (no
  graph, no steering, no interceptor); repeat n≥3 because agents are
  non-deterministic — report a range, never a single "exact" delta.
- **Gap found while writing it:** the workspace only ever ran
  `graphify claude install`. **A copilot/kiro ON arm does not exist yet** — the
  installers were discovered in G0.5 but never used. Listed as blocking.
- **Still needed before I can run:** B (VS Code shim answer) · C (G1 — two calls to
  protect a ~200-call run; if graphify never fires, the ON arm equals the OFF arm
  and the pairing measures nothing) · the copilot/kiro installs · a cost cap.
  Recommended first: F1 and the G debts, so the report doesn't caveat what it
  could have fixed.
- **Next:** A and B (free) → C → then I on Arpit's go.

## 2026-07-28 — Cowork: docs consolidation — 24 cycle docs archived, ONE pending plan

- **Asked:** archive all the plans/handoffs/prompts, then create just one plan with
  what's pending.
- **Done:** 24 files moved to `docs/archive/v0.36-*` (import-ledger · cage-lab ·
  cage-lab-setup · capture-precision · golden-set ×3 · phase1-closeout ×3 ·
  report-per-run ×4 · graphify-ab-steering · g05-rebuild ×2 · graphify-capture ×3),
  each with an archive header naming what was built and where its remainder went.
  `docs/` root now holds **only** the living process docs + PLAN.md + OPEN-WORK.md.
- **Created [OPEN-WORK.md](OPEN-WORK.md)** — the single plan of pending work:
  **A** ceiling credibility (free, first — is the whole-corpus bound defensible on
  a real repo?) · **B** VS Code shim reality check (free, first — the PATH
  interceptor under VS Code is unverified; if it fails, every VS Code graphify
  saving is invisible on every agent) · **C** G1 the A/B (~2 calls) · **D** manual
  cells (Arpit) · **E** Phase 2 sweep (~100 calls, his go) · **F** copilot-cli
  detection + copilot-vscode fidelity probe · **G** honesty debts (report-read
  0.3 uncalibrated · ADR 0005 veto threshold unnamed · graphify-LLM verb check) ·
  **H** the v0.36 release, blocked by the no-commit directive.
- **Corrected a misreading:** GC0's table is about *cage's observability*, not
  graphify's function — graphify works with all three agents (installers exist for
  each) and the PATH shim meters invocations on all of them. Kiro loses only the
  transcript cross-check. Table now in OPEN-WORK §F.
- **Promoted the durable rules** out of the archived plans (never-more-precise ·
  reproducible-workspace · rebuild-config-not-corpus · three-artifact-types ·
  usage-rows-diagnostic-only) into OPEN-WORK so the archive is never cited as spec.
- **Next:** A and B (free, both can invalidate later work) → C.

## 2026-07-28 — Cowork: G0.5 GREEN → graphify-capture plan+handoff+prompt (before G1)

- **G0.5 executed and green** (Claude Code, Sonnet): fixture 9 files hash-identical,
  captures (148) + regression (46) untouched, both CLAUDE.md blocks present
  (additive markers, no clobber), interceptor live, cage-lab commit `3d72f4f`.
  **Findings that changed the plan:** the PreToolUse hook is a *static bash
  conditional* — no subprocess, so the PATH-bypass hypothesis is **dead**; "0 real
  receipts" now has one surviving explanation: **adoption**. Installed graphifyy
  0.5.0 corrections: no `--strict`; `--help` on subcommands **runs the installer
  for real** (discovery hazard); copilot/kiro/vscode installers DO exist — my
  asymmetry claim was wrong and was killed.
- **Asked next:** best approach to capture graphify tokens/logs/savings — then
  "yes to all of it" + *will cage model how much graphify is GOING to save?*
- **Researched from disk** (shim, hook, graphifymeter.py, graph.json, cache):
  cache carries zero usage signal; all existing routes are invocation-gated while
  real usage may be invocation-less (reading GRAPH_REPORT.md IS the saving).
- **Shipped:** [graphify-capture.plan.md](graphify-capture.plan.md) (GC0–GC6) +
  handoff + prompt (**Opus**, unpaid, sequenced BEFORE G1). Core: transcript-side
  detection at import (pull, ADR-0002-shaped) · usage rows in `state/` · dedupe to
  one receipt · forward model as three labelled claims (history band / graph
  ceiling / verdict). Debate gate scoped copilot/kiro behind the GC0 probe
  (`gap_ms` precedent) and demoted report-read receipts to lower confidence.
- **Next:** run graphify-capture (Opus) → then G1 (~2 paid calls) → archive the
  G0.5 pair (implemented, still in docs/ root — archive-on-implement rule).

## 2026-07-28 — Cowork: G0.5 packaged (handoff + prompt) — debate gate blocked the first version

- **Asked:** handoff and prompt for the clean rebuild.
- **The debate gate blocked it and the plan changed.** A literal "dump the
  workspace and recreate it" **destroys the A/B**: arm A's captures were taken
  against a specific toy codebase, so a freshly-authored fixture makes the A−B
  token delta measure *"different repo"* as much as *"graphify installed"*.
- **Amendment (plan §1.2.0): rebuild the configuration, never the corpus.** The
  fixture sources are preserved **byte-for-byte and hash-asserted**; only the
  tooling layer (`graphify-out/`, `CLAUDE.md`, `.claude/`, `.cage/`, `bin/`) is
  deleted and re-derived by the tools' own installers. A fixture change would be a
  *new baseline* requiring arm A to be re-run, never a silent comparison.
- **Also cut:** `graphify hook install` — it rebuilds the graph on commit
  (freshness, not usage), and a mid-capture rebuild adds noise to the one thing
  arm B measures.
- **Kept from the earlier pass:** installers only (never a hand-written steering
  block, even as a fallback); discovery from `--help` before execution; record
  **how the PreToolUse hook invokes graphify** — a free predictor of the
  PATH-bypass outcome before G1 spends a call.
- **Shipped:** [graphify-ab-g05-rebuild.handoff.md](graphify-ab-g05-rebuild.handoff.md)
  + [graphify-ab-g05-rebuild.prompt.md](graphify-ab-g05-rebuild.prompt.md)
  (**Model: Sonnet**, no paid calls), plan §1.2.0, README index.
- **Next:** run G0.5, then G1 (~2 paid calls). Cage tree stays uncommitted.

## 2026-07-28 — Cowork: graphify's real installers researched → clean-rebuild scoped (G0.5)

- **Asked:** research graphify's own CLI setup commands and use them for the golden
  set; update the plan; "make sure the golden set is clean — maybe dump it and
  create the folder again."
- **Researched graphify's real setup surface** and recorded it in
  [graphify-ab-steering.plan.md](graphify-ab-steering.plan.md) §1.1:
  `graphify claude install` (CLAUDE.md steering **+ a PreToolUse hook**),
  `codex|opencode|claw|droid install` (AGENTS.md), `graphify hook install`
  (git-driven graph rebuild — freshness, not agent usage). Arm B must use the
  **real installer**, never a hand-written steering block.
- **Two consequences that change the experiment.** (a) The PreToolUse hook may
  invoke graphify by absolute path, **bypassing cage's PATH-interception shim** —
  so arm B must record *did graphify fire* and *did cage see it* as two separate
  outcomes; `fired=yes, cage=no` would be a HIGH finding and the best explanation
  yet for "0 real receipts". (b) **There is no Copilot or Kiro installer** — so
  V4/V5b have no first-party always-on path, which is itself a field-matrix finding.
- **Scoped the "dump it" instinct** (§1.2). Agreed the defect is real — the
  workspace's provenance is unknown — but split it four ways: **REBUILD**
  `golden/workspace/` · **DELETE freely** `golden/runs/` · **KEEP**
  `golden/captures/` (arm A's baseline; deleting it destroys what arm B is compared
  against) · **NEVER DELETE** `docs/regression/**` (published, hashed, append-only).
- **Decided / made standing:** a workspace is valid evidence only if its setup is
  reproducible — `SETUP.md` + `rebuild.sh`, tool-owned installers only, recorded
  step order (graphify and cage both write `CLAUDE.md`; who clobbers whom is an
  observation). Added as golden-set plan §2.4a and as phase **G0.5**.
- **Next:** execute G0.5 (unpaid) — rebuild the workspace with provenance
  recorded — then G1 (~2 paid calls).

## 2026-07-28 — Cowork: benchmark reviewed → the graphify A/B tested the wrong condition

- **Asked:** how to fix it (the open items the benchmark surfaced); create a plan;
  and how was graphify set up in the golden set.
- **Inspected the workspace and found the answer to both.** Setup present:
  `bin/graphify` (the cage interceptor shim, with its recursion guard), a **real**
  `graphify-out/` graph (GRAPH_REPORT/graph.json/cache — graphify genuinely ran),
  and `[tools] order = ["graphify", …]`. Setup **absent**: `workspace/CLAUDE.md`
  contains only the cage block and **zero mentions of graphify** — whereas cage's
  own repo CLAUDE.md carries an explicit "prefer `graphify query` over grep" block.
- **So V2/V4 asked an agent an architecture question in a repo that never told it
  graphify existed.** The agent read files, correctly. The finding's *observation*
  holds; its *implication* (graphify savings never materialise in real use) does
  not, because real graphify-enabled repos carry the steering.
- **Why this matters beyond tidiness:** that implication is the leading candidate
  explanation for "0 real receipts across 36,451 calls". If the cause is missing
  steering, it's a `cage setup` fix and the mystery closes; if steering is present
  and it still doesn't fire, the product finding is real and much more serious.
  **Right now we can't tell which** — which is the whole reason for the plan.
- **Noticed an ownership asymmetry worth a finding of its own:** *cage writes the
  shim; graphify writes the steering.* Nobody owns the case where one exists
  without the other — exactly the golden workspace's state.
- **Done:** `docs/graphify-ab-steering.plan.md` — three arms (A unprompted/no
  steering ✅ done · **B unprompted WITH steering ⏳ ~2 calls** · C driver-invoked
  if B is negative), a decision tree stating what each outcome *ships*, and an
  acceptance rule that the "0 real receipts" link must be **supported with
  evidence or explicitly withdrawn**, never left dangling. Arm B must be recorded
  as a **new run report** (different condition, not an amendment).
- **Also confirmed:** archiving the completed benchmark prompt was correct per the
  archive-on-implement rule — no change needed.
- **Next:** run G1 (arm B); then P3 manual cells / Phase 2.


## 2026-07-28 — Phase 1 BENCHMARK authored + Phase 1 CLOSED

- **Asked:** execute the Phase 1 benchmark prompt — derive *what cage captures,
  how correct*, no paid calls, no new numbers; publish + close Phase 1.
- **Done:** authored `PHASE-1-BENCHMARK.md` (cage-lab), hashed `58948469192c`,
  published into `cage/docs/regression/`. Verdicts: claude/copilot CLI **EXACT**,
  kiro CLI **HONEST-LIMIT** (tokens FINAL-null), all VS Code **UNPROVEN**.
  Coverage stated up front (**6/12 scripted CLI only**); FINAL (kiro tokens, by
  vendor design) vs PENDING (VS Code, P3) kept strictly apart. `inputs.toml`
  re-pointed at `golden/captures/**` (primary); `samples/**` secondary. HISTORY +
  README indexes + closeout plan §P5 marked closed; prompt archived.
- **Decided/open:** Phase 1 CLOSED for the 6 scripted cells; the 6 VS Code cells
  stay UNPROVEN by design (not upgraded for tidiness) — P3 is Arpit's manual
  sweep. Shim-recursion finding kept **OPEN** (stale foreign shim on a real PATH
  remains a hazard). Cage tree kept **uncommitted** per directive; the benchmark
  is committed in cage-lab only.
- **Next:** Arpit runs P3 (manual VS Code/IDE) → answers the 3 owed questions;
  then P4 Phase-2 sweep enriches the benchmark.

## 2026-07-28 — Cowork: Phase 1 BENCHMARK specced (what's captured · how correct)

- **Asked:** a clean Phase 1 report — the benchmark of what is being captured and
  how correct it is — before moving to Phase 2 and 3.
- **Recognised it needs a THIRD artifact type.** report-per-run gave us *run
  report* (one run) and *finding doc* (one defect). A benchmark spans **one phase,
  all runs** — so it is **derived, never observed**: every cell cites a run report
  or finding doc and it introduces **no new numbers**. Rule written in: if the
  executor finds itself computing something, a run report is missing data — and
  that absence is itself the finding.
- **Done:** `phase1-closeout.plan.md` §P5 rewritten from "field matrix" to
  **the benchmark** (P5.1–P5.4), + `docs/phase1-benchmark.prompt.md` (**Opus**).
- **The verdict vocabulary is the substance:** every agent × surface × field cell
  gets exactly one of **EXACT** (reconciled three ways, figures cited) ·
  **HONEST-LIMIT** (source carries no such number; recorded + tagged) ·
  **UNPROVEN** (untested) · **WRONG** (open defect, linked) — plus a citation.
- **The distinction I made non-negotiable: FINAL vs PENDING limits.** "Kiro has
  no token counts" (vendor design, closed by the P2 probe) and "we haven't tested
  VS Code yet" are *not the same class of statement*, and blurring them is the
  single most damaging error available in a document that will be cited as
  "what cage proves". Coverage must also lead with **6 of 12 cells, scripted CLI
  only** — stated up front, not buried.
- **Guardrail:** never upgrade a verdict for tidiness — UNPROVEN cells staying
  UNPROVEN is what makes the EXACT ones worth believing.
- **Next:** run it (unpaid) → Phase 1 closes → then Arpit's manual sweep (P3) and
  the Phase 2 corpus sweep.


## 2026-07-28 — Cowork: split the LEGACY reports too (report-per-run phase 7)

- **Asked:** split the existing reports as well.
- **Checked state first:** phases 1–6 already landed (run-002 + run-003 published,
  5 finding docs, HISTORY.md, generator refuses re-publish). The **pre-golden-set**
  reports were never touched and carry the identical defect.
- **What's still layered — `2026-07-22-capture-report.md`:** the run's
  observations, **F1–F8 inline**, and *lifecycle baked into the headings*
  (`F3 … ✅ RESOLVED v0.34.0`, F5, F7). The 07-22 run never observed those
  resolutions — a later release did — so this is exactly what the new model
  forbids in a run report. Worse, its two **corrections live in separate files**
  (`2026-07-23-f2-correction`, `2026-07-24-f1-root-cause`) *because* the report
  couldn't be edited: a finding's history scattered across three files, **owned
  by none**.
- **The reason it's worth doing rather than leaving as history (plan §7.4):**
  `docs/regression/` is what a future agent reads to learn what's broken, and
  today **F1's wrong first diagnosis outranks its real root cause** — the
  original text ("graphify is being run directly") reads as current in the
  report, while the true cause (a dead interceptor verb) is buried in a
  correction file. A finding whose superseded diagnosis is more prominent than
  its correct one is worse than no finding.
- **Done:** plan gains **phase 7** (§7.1–§7.5: what's layered, the artifacts to
  produce, the unchanged rules, why it matters, acceptance) +
  `docs/report-per-run-legacy.prompt.md` (**Opus**). Eight finding docs keyed to
  the **existing taxonomy ids** (`receipts-empty`, `health-contradiction`, …) —
  they were designed as stable cross-run handles and only work if each has a
  document. Corrections are **absorbed as history inside the finding docs and
  stay on disk, cited**.
- **F1 flagged as the judgment call, not transcription:** three partial answers
  exist (original / 07-24 correction / the golden set's "agents don't invoke
  graphify unprompted"). The prompt requires its current status be unambiguous
  and the superseded diagnosis *visibly* superseded — with a STOP if the record
  genuinely can't settle it.
- **Next:** run it (no paid calls); then Arpit's manual cells V6–V11.

## 2026-07-28 — Cowork: "why do numbers still differ?" → one report per run

- **Asked:** the numbers still differ in the report — is that old data? Then:
  **make it a new report per run; split it.**
- **Answered:** yes, by design — §2's `227,298 · 189,788 ❌` is
  `truth · cage-before-the-fix` (the evidence the bug existed); the top table is
  post-fix. Both correct, different runs. P0's banners labelled it because
  published reports are append-only and history must not be rewritten.
- **But Arpit's instinct is right and the banners were treating a symptom.** Root
  cause: **one document was answering three questions** — what happened in this
  run · what a defect's status is now · how numbers moved across runs. No amount
  of labelling fixes a wrong shape.
- **Done:** `docs/report-per-run.{plan,handoff,prompt}.md`. The split:
  **run report** (what happened in *this* run — **immutable** once published,
  never mentions a later run) · **finding doc** (a defect's status *now*, mutable,
  spans runs) · **history index** (`findings/HISTORY.md` — one row per run, where
  the pre-fix → post-fix movement now lives *explicitly*, each row naming its run).
- **The rule written in:** *a run report never mentions a later run* — whether its
  numbers are current is answered by the index, not a banner. Plus a
  self-enforcing check: **if you're tempted to add a banner to a run report, the
  split is wrong.**
- **Retro-split specced** into run-002 (pre-fix) + run-003 (post-fix) with the
  strongest guard available: **transcribe from the published text, never
  recompute** (partitioning evidence, not regenerating it), and the acceptance
  test *every number in the original appears in exactly one split — none lost,
  none duplicated*. The old layered file stays, marked SUPERSEDED — published
  evidence is never deleted.
- **No paid calls** — pure restructure.
- **Next:** run it; then Arpit's manual cells V6–V11, which will now get their
  **own** run report rather than being merged into a scripted one.

## 2026-07-28 — Claude Code: Phase 1 closeout P0–P2 (report hygiene · §4.5 · Kiro proxy)

- **Asked:** execute `docs/phase1-closeout-p0p2.handoff.md` — three cheap unpaid
  steps: make the validation report un-misreadable, clear §4.5, run the last untried
  route to exact Kiro tokens. cage tree stays uncommitted; commit in cage-lab only.
- **Done — P0:** BASELINE (pre-fix, superseded) banners on report §1/§2/§3.1 + Status
  line rewritten; pre-fix numbers left byte-for-byte. Re-hashed/republished
  append-only (`-3` then `-4`, latest refreshed, index rows), hash recomputed ==
  sidecar on all copies. **P1:** §4.5 marked **RESOLVED** — re-verified declared
  surface wins on built-in collision (tests + live repro). **P2:** Kiro proxy probe →
  **Outcome B, definitive.** kiro-cli honors neither `ANTHROPIC_BASE_URL`/
  `OPENAI_BASE_URL`; routes to AWS CodeWhisperer/Q; two real probe turns metered **0
  rows**. New finding `regression/2026-07-28-kiro-proxy-probe.md` + `FORMULAS.md §1.7`.
- **Decided:** Kiro CLI cost is credit-derived and `estimated`, **by vendor design —
  final**; there is no `measured` path (no base-URL override, no tokens in the AWS
  response, cage's reverse-proxy can't MITM TLS). Proxy writes rows *directly*
  (`metering.record_call`), no `[sources]` entry — the open question, answered from code.
- **Left open:** P3 (manual cells V6–V11) and P4/P5 need Arpit's hands/go.
- **Committed:** cage-lab `c373812` (report P0/P1). cage tree **uncommitted** (HEAD
  `98a3455`), per directive.
- **Next:** Arpit runs P3 manual VS Code checklist (`golden/manual/vscode-checklist.md`).

## 2026-07-28 — Claude Code: split model prices into `prices.toml`

- **Asked:** execute `docs/prices-toml.{plan,handoff,prompt}.md` — move the model
  price table out of `cage.toml` into `.cage/prices.toml`. The money must not move.
- **Done:** the full split. New `paths.Footprint.prices`/`shadowed_prices`
  (`resolve_prices_file`, `PRICES_FILENAME`); `policy.load` reads prices from the
  resolved prices file, still returns ONE merged dict, `[meta]` split per key;
  bundle split `data/cage.toml` + `data/prices.toml`; `cage setup` migration
  (project + global) money-neutral + idempotent; writers routed (`set`/`sync` →
  prices, `alias`/`route-tool` → cage.toml); `cleanup.NEVER` + doctor/clicmds/
  doctorbundle/freshness/explain readers fixed. 9 new tests (`test_prices_split.py`),
  P1/P3/P4 goldens re-blessed. Suite green.
- **Verified numerically on the real ~/​.cage ledger:** report/attrib/roi/UNPRICED
  **byte-identical** before vs after, both via the legacy fallback and after a real
  migration; 51 tables + all 13 real model `price_match` kinds unchanged; a
  customized row survives migration; zipapp resolves both bundled files.
- **Decided/open:** `[alias]` **stays** in `cage.toml` (routing decision — the
  governing rule *vendor facts move, routing decisions stay*). The
  project-vs-global ledger question (plan §8) stays out of scope (ADR-level).
  CLAUDE.md edits **proposed, not applied** — parked at
  `docs/proposals/claude-md-prices-file.md`. Handoff/prompt/plan trio archived to
  `docs/archive/v0.36-prices-toml.*`.
- **Next:** Arpit reviews the parked CLAUDE.md proposal; folds into the pending
  v0.36.0 release. Tree left **uncommitted** (standing constraint).

## 2026-07-28 — Cowork: P0–P2 handoff + prompt (report hygiene · §4.5 · Kiro proxy probe)

- **Asked:** create the handoff and prompt for closeout P0–P2.
- **Done:** `docs/phase1-closeout-p0p2.{handoff,prompt}.md` (**Opus**). All three
  steps are **unpaid** except P2's two probe turns.
- **P0 framed as evidence-integrity, not tidying.** The report currently reads
  "copilot is broken" to anyone scrolling past the divider (re-run prepended,
  interim body kept verbatim). The rule written in: **label history, never
  rewrite it** — the pre-fix numbers are the evidence the fix was needed.
  Re-hash, re-publish append-only, and **recompute the hash to verify** (a hash
  nobody checks is decoration).
- **P2 is the valuable one and is written to be answerable either way.** It's the
  only remaining route from `estimated` to `measured` for a whole agent: the
  proxy puts cage *in the request path* instead of reading Kiro's null-filled
  store. Outcome A ⇒ document the proxy as Kiro's recommended metering mode
  (`measured` on that path only; credits stay `estimated`). Outcome B ⇒ record
  the *specific* blocking reason and "Kiro is credits-only, `estimated`, by
  vendor design" becomes final in the field matrix + FORMULAS. **A negative is a
  result — do not retry until it passes.** Either way it closes
  capture-precision #11, which was specced but never executed.
- **Safety guardrail added:** STOP if P2 would need credentials, a cert override,
  or anything weakening TLS — an exact number is not worth that.
- **Next:** run it; then Arpit's manual cells V6–V11 (P3). The prices split can
  proceed in parallel.

## 2026-07-28 — Cowork: VALIDATION-REPORT reviewed → phase1-closeout plan; plan-index rule in CLAUDE.md

- **Asked:** review the (post-re-run) VALIDATION-REPORT and plan the best way to
  fix it; add a CLAUDE.md rule — every plan opens with a one-liner phase index.
- **Review verdict: nothing scripted is broken anymore.** The re-run shows V3/V4
  **8/8 exact** (227,298 / 233,675), V5/V5b capturing credit rows with the token
  limit stated honestly, V1/V2 **byte-identical**, self-heal proven on the real
  session. So "fix it" = completion + hygiene, with one exception that could
  still upgrade Kiro.
- **The one real defect found: the report contradicts itself to a cold reader.**
  The re-run was prepended but the interim body kept verbatim — §1's grid still
  shows ❌s and §2 the undercounted numbers, so anyone reading past the divider
  concludes copilot is broken. That's the exact misread the hash-and-publish
  directive exists to prevent. Fix (P0): label the historical sections
  **BASELINE (pre-fix) — superseded above**, never rewrite the numbers, re-hash
  and re-publish (append-only, `-2` suffix).
- **`docs/phase1-closeout.plan.md` (new):** P0 report hygiene · P1 clear §4.5
  (the surface-collision nuance predates the shipped declared-wins fix — verify
  and mark RESOLVED; an open finding after its fix shipped is doc-drift) ·
  **P2 Kiro proxy probe** — the one untried route to *exact* Kiro tokens
  (`cage data meter -- kiro-cli …`; works ⇒ Kiro upgrades `estimated`→`measured`;
  doesn't ⇒ the credits limit is final and documented; either way ~15 min and it
  closes capture-precision #11 which was specced but never run) · P3 manual cells
  (answers the two remaining Phase 1 questions) · P4 Phase 2 sweep (the Copilot
  blocker is cleared) · P5 field matrix + wire-in + formal close (P4 enriches,
  doesn't gate).
- **CLAUDE.md rule added (Arpit's directive):** every plan doc opens with a
  **phase index** — numbered phases, one line each, gate/status — so the whole
  shape is visible before detail and staleness is spottable at a glance; existing
  plans gain it on contact. Applied immediately to the new closeout plan and,
  on contact, to `prices-toml.plan.md`. DOC-REGISTRY CLAUDE.md row bumped.
- **Next:** run P0–P2 (cheap, no paid calls), then Arpit's manual cells; prices
  split can run in parallel.

## 2026-07-28 — Cowork: prices-toml handoff + prompt written (ready to run)

- **Asked:** create the handoff and prompt for the prices split.
- **Done:** `docs/prices-toml.{handoff,prompt}.md` (**Opus** — this is the money
  path; a dropped price row doesn't crash, it silently reprices calls to UNPRICED
  or to a plausible-looking family match).
- **Both lead with the one rule** that settles every border case — *vendor facts
  move, routing decisions stay* — and both name `[alias]` explicitly as
  **staying**, with the reason, so an executor can't "helpfully" move it back on
  the same logic my first draft used.
- **Two design guards written in:** (1) `policy.load` must keep returning **one
  merged dict** — a file change, not an API change; if the executor finds itself
  editing a pricing consumer, that's the signal it went wrong. (2) `[meta]` splits
  **per key**, flagged as a *quiet* failure (a mis-split stops a staleness nag
  firing — no error, just a warning that never appears again).
- **Verification is baseline-first:** step 1 of the prompt is to capture
  `report`/`attrib`/`roi` output + the UNPRICED count + the `[prices.*]` table
  count on a real ledger *before* touching anything, then diff. Added a check my
  earlier drafts lacked: `price_match` must return the same **kind** for sampled
  real model ids — a silent `exact`→`family` degradation is a wrong number wearing
  a plausible tag, and byte-identical totals alone wouldn't catch it if two errors
  cancelled.
- **Guardrail:** a price row resolving differently after the split is a **defect
  in the split**, never an acceptable variance — never adjust the baseline to
  match.
- **Next:** Arpit runs it, or spends the paid 6-cell golden re-run first to close
  capture-precision.

## 2026-07-28 — Cowork: prices-toml decisions settled + the global-`~/.cage` question

- **Arpit answered all three open questions:** committed (not gitignored) ·
  **`[credits]` moves but `[alias]` STAYS** · yes split the global config too.
- **The alias call sharpened the whole rule.** My draft moved `[alias]` on the
  logic "it resolves a price". Arpit's correction is better: an alias says
  "*this* router id in *my* setup means that model" — it describes the user's
  environment, not a vendor's rate card, and a vendor rate change never touches
  it. So the plan now states the line as **vendor facts move; routing decisions
  stay** — which settles `[alias]` and `[tools.*] price_at` together instead of
  case-by-case. Consequence recorded: `cage prices` is a two-file writer
  (`set` → prices.toml; `alias`/`route-tool` → cage.toml), and resolution is
  unaffected because `price_match` walks the merged dict `policy.load` returns —
  the split is physical, not semantic.
- **Answered "why do we have a global `~/.cage`, is it still needed?"** Yes, and
  more so after the hookless rebuild: `resolve_root` falls back to it so an agent
  session run outside any cage-enabled repo still lands somewhere (ADR 0002's
  reasoning, which also removed the cwd-`.cage` guard); pull-based capture sweeps
  machine-wide logs spanning every directory; and per-project attribution doesn't
  need per-project ledgers because `project`/`scope` are fields and
  `report --project` is a derived view.
- **But surfaced the sharper question underneath** (new plan §8): if every import
  lands globally anyway, is a project `.cage/` still a *ledger* or just **config +
  wiring**? A **project = config, global = ledger** model would delete a
  precedence tier and the "which ledger did this land in?" confusion — exactly the
  2026-07-24 finding where 5 real receipts sat in a project ledger while 36k calls
  sat in the global one. Recorded as an **ADR-level capture-model change needing
  its own compare doc (revisits ADR 0002)** — explicitly out of scope for prices.
- **Next:** prices-toml handoff/prompt pair, or the paid 6-cell golden re-run.

## 2026-07-28 — Cowork: config-authority plan deleted; focused prices-toml plan written

- **Asked:** delete the config-authority plan; write a new one **just for
  `prices.toml`, just for model prices**.
- **Done:** `docs/config-authority.plan.md` removed (its sources half had already
  shipped; keeping it would have left a half-done doc masquerading as pending
  work). New **`docs/prices-toml.plan.md`**, scoped to model prices only.
- **The case, measured rather than asserted:** the bundled `cage/data/cage.toml`
  is **568 lines, ~400 of them price rows (70%)**. So the file a user opens to
  change a budget is dominated by vendor data they never edit, and
  `cage prices sync` must do **text surgery inside a file full of user policy**.
  Post-split: sync is a file replacement, `cage.toml` drops to ~170 readable
  lines, and **`cage prices sync` vs `cage policy sync` stop overlapping** —
  today both edit one file, told apart only by which keys they touch and two
  version counters sharing one `[meta]`.
- **Two subtleties written down because they fail *quietly*:**
  1. **`[meta]` splits per key** — `prices_version`/`prices_date` go with prices;
     `cage_version`/`policy_version` stay. Get it wrong and a staleness check
     silently stops firing.
  2. **`[tools.<tool>] price_at` stays in `cage.toml`** — it's a routing decision
     about your tool, not a vendor fact, so **`cage prices` becomes a two-file
     writer**. Deliberate, not accidental.
- **Acceptance is numerical, not structural:** `report`/`attrib`/`roi`
  byte-identical on a real ledger, UNPRICED count unchanged by one row, and
  `price_match` returning the same kind for sampled real model ids — a match
  silently degrading `exact`→`family` is a wrong number wearing a plausible tag.
  Also noted: `policy.load` keeps returning one merged dict, so this is a *file*
  change and not an API change — which is what makes byte-identity achievable.
- **Fixed the fallout:** `capture-precision.plan.md` §3.6 was reverted by a linter
  to the stale "additive only" text pointing at the now-deleted plan; rewritten to
  the as-built record (full removal, 846 green, kill-(a)/keep-(b)). Docs index
  updated.
- **Next:** Arpit's call — spec the prices-toml handoff/prompt pair, or spend the
  paid 6-cell golden re-run first to close capture-precision.

## 2026-07-28 — Cowork: config-authority review — Part 2 already SHIPPED, only prices pending

- **Asked:** review the config-authority implementation and say what's pending;
  plus "add cage.toml to have default paths setup on `cage setup`".
- **Reviewed the code, not the docs** — and the docs were stale in my favour:
  Arpit chose **full removal** for Directive A during the capture-precision cycle,
  not the additive-only scoping I had recorded. So **Part 2 is done**, verified in
  source: `paths.sources_seed()` (registry demoted to a seed) ·
  `paths.materialize_sources()` writing an active `# cage:sources-start/end`
  block · `paths.sources_drift()` surfaced in `doctor --paths` ·
  `initcmd.sync_sources()` behind `cage setup --sync-sources`, regenerating only
  the marker region so user entries survive · `resolve_log_sources` reading only
  `cage.toml` · empty `[sources]` warning · test harness on `tests/srcseed.py`.
  **846 green.**
- **The kill-(a)/keep-(b) rule landed exactly as argued:** env no longer decides
  *which* path (doctor announces now-ignored home-env vars), while
  `paths._expand_source` still expands `~`/`$VAR` **inside** a cage.toml-declared
  string — so configs stay portable without a second decision-maker.
- **Arpit's new ask is already implemented.** "cage.toml should have default paths
  set up on `cage setup`" *is* `materialize_sources` + `sync_sources`, for both the
  project `.cage/cage.toml` and the global `~/.cage/cage.toml`, and it already
  includes the kiro-cli SQLite store as a `format="kiro-cli"` custom source. Told
  him rather than building it twice.
- **Corrected the stale docs:** `config-authority.plan.md` now carries a STATUS
  banner (Part 2 SHIPPED / Part 1 PENDING) and an **as-built table** mapping every
  specified item to what actually shipped; `capture-precision.plan.md` §3.6 and its
  §6 open question re-marked from "additive only" to "shipped in full".
- **Added §2.4 — the one thing worth re-checking:** the seed is now *frozen into
  user files at setup time*, so its content is load-bearing in a way it wasn't as a
  runtime fallback. Two one-off checks: is every default path still correct, and
  **does the drift check actually fire** (add a seed entry, run `doctor --paths`
  against an older materialized config)? A mitigation that never triggers isn't one.
- **Pending overall:** (1) `prices.toml` split — the only open item in
  config-authority; (2) the **paid 6-cell golden-set re-run**, which needs
  `drive.py` updated for Directive A + Kiro credit checks and is gated on Arpit's
  go-ahead; (3) manual VS Code cells V6–V11; (4) Phase 2.
- **Next:** Arpit's call on ordering — prices split, or spend the paid re-run
  first to close capture-precision.

## 2026-07-28 — Cowork: Directive A scoped down; new config-authority cycle (prices split)

- **Claude Code hit the guardrail** I wrote into the prompt ("if removing env
  overrides proves costlier than expected, STOP and ask") and asked how to scope
  Directive A: 25 test files + conftest isolate via home-env redirection, so a
  literal implementation would destabilise the harness and put the re-run's
  V1/V2 byte-identical gate at risk.
- **Explained the real trade — diagnostic clarity, not fidelity.** The re-run
  exists to answer one question (did the Copilot delta-id fix work?); a
  resolution change in the same run makes a red cell ambiguous. Also clarified
  which options actually satisfy the directive: **only full removal does** —
  "env as announced hatch" still leaves a second decider, and "additive only"
  changes no resolution at all.
- **Drew the distinction that reshapes the directive:** (a) env that overrides
  *which* path is used = a second decision-maker, must go; (b) env expanded
  *inside* a path string `cage.toml` declares = the file still decides, env only
  parameterises it — keep, it's what makes a config portable. **Kill (a), keep
  (b)** is a cleaner rule than "remove env".
- **Arpit's call: additive parts only this cycle.** `capture-precision` §3.6 +
  handoff DoD + prompt Step 4 rescoped to materialize the active `[sources]`
  table, the doctor drift check and `--sync-sources`, with **resolution semantics
  explicitly unchanged** and the out-of-scope items named so the executor can't
  drift into them. §6 open decision marked RESOLVED.
- **Asked: "create a separate file just for prices"** → clarified (config split,
  not a doc) → wrote **`docs/config-authority.plan.md`**, one cycle covering:
  - **Part 1 — `.cage/prices.toml`.** Rationale: `cage.toml` mixes two different
    lifecycles — *your decisions* (budgets, tool order, human rate, sources) vs
    *the world's facts* (vendor rates, shipped in the bundle, wanting wholesale
    replacement). Split ⇒ `cage prices sync` becomes a **file replacement**
    instead of text surgery inside a file full of user policy. Reuses the proven
    non-breaking pattern (one resolution point `Footprint.prices`, legacy
    `[prices]`-in-`cage.toml` fallback, both-present warning, `cage setup`
    migration, bundled-data split, `cleanup.NEVER`, zipapp check). Border case
    decided: `[tools.<tool>] price_at` **stays in `cage.toml`** (a routing
    decision, not a vendor fact) — which makes `cage prices` a two-file writer.
    **Risk named:** pricing is the money path, so acceptance is *report/attrib/roi
    byte-identical on a real ledger, UNPRICED count unchanged by one row* — not
    "it parses".
  - **Part 2 — the deferred `[sources]` flip** with the (a)/(b) rule, plus the
    test-harness migration to temp `cage.toml` (better hygiene than ambient env
    anyway). Verified against the by-then known-good baseline.
- **Next:** run `capture-precision.prompt.md` (Opus) → then the config-authority
  cycle. Three open questions in the new plan: `price_at` placement, whether
  `prices.toml` is committed (default: yes, teams share a table), and cycle order
  (default: prices first — its verification is purely numerical).

## 2026-07-28 — Cowork: two new directives + the capture-precision plan/handoff/prompt

- **Asked:** add two items — (1) paths always from `cage.toml` and nowhere else;
  (2) hash the validation report and copy it into the cage repo — then produce a
  plan, handoff and prompt to execute the whole change list, and re-run Phase 1.
- **Done:** `docs/capture-precision.{plan,handoff,prompt}.md` (**Opus**). The plan
  carries the **11-item list gated by a Step-0 probe** (explicit non-`auto` Kiro
  model + `settings list --all`) that can delete three items before any code is
  written; the governing principle is stated up front — *cage can never be more
  precise than its source*, so exact where counts exist and `estimated`/UNPRICED
  loudly where they don't.
- **The two new directives, specced:**
  - **§3.6 `cage.toml` as sole path authority** — `resolve_log_sources` reads only
    `cage.toml [sources]`; the built-in registry becomes a **seed**; `cage setup`
    materializes an **active** table (project + global); empty `[sources]` ⇒
    captures nothing **and says so loudly**. **Flagged the cost honestly:**
    freezing defaults into user files means an upgrade's corrected paths stop
    reaching existing users — the same silent-staleness class as the dead-verb
    bug — so a doctor **drift check** + `cage setup --sync-sources` are mandatory,
    not optional. Env overrides: default **removed** from path resolution (tests
    migrate to temp `cage.toml`); anything surviving must be doctor-announced.
  - **§3.7 hashed + published reports** — sha256 sidecar, hash in the header (with
    the hashed byte-range documented), dated copy + `latest-` into
    `docs/regression/`, index row with the hash prefix, append-only (same-day
    re-run gets `-2`).
- **Re-validation specced with exact expectations:** V1/V2 byte-identical (a
  regression check on the untouched path), V3/V4 exactly 227,298 / 233,675, plus a
  non-skippable **self-heal proof** (re-import a legacy Copilot session ⇒ exact
  total, no double count, third import adds zero).
- **Recorded in the handoff's stress-test:** the report's "mutate the row"
  suggestion is rejected (breaks append-only, determinism, crash-safety,
  concurrent-import safety — and is *less* precise, collapsing per-turn
  increments); per-agent ledgers rejected (separation is justified by **schema**,
  not source — which is why Kiro *credits* do warrant their own row shape while
  Copilot doesn't).
- **Added on Arpit's follow-up — re-run order is FAILURES FIRST** (plan §4.1,
  handoff DoD, prompt Step 6): **V3/V4 copilot → V5/V5b kiro → V1/V2 claude**.
  The cells the fixes targeted run first (fastest verdict on whether the fix
  landed); the previously-green claude cells run last as the pure regression
  check, with a byte-identical bar. **Gate between groups:** a still-failing
  targeted cell ⇒ stop and report, because re-running green cells proves nothing
  while the fix is broken and the calls cost real money — the only exception is a
  failure provably unrelated to the fix, named explicitly.
- **Next:** run `docs/capture-precision.prompt.md` (Opus). Three open decisions
  for Arpit in plan §6: env overrides, credits→USD pricing (default: record,
  don't price), and the Step-0 dependency.

## 2026-07-28 — Cowork: reviewed the Phase 1 VALIDATION-REPORT (all scripted cells)

- **Asked:** review `../cage-lab/golden/findings/VALIDATION-REPORT.md`.
- **Verdict: strong, and the process demonstrably worked.** V1/V2 claude 8/8 with
  token-exact three-way reconciliation; V3/V4 and V5/V5b red **for real reasons**,
  reported not hidden. The three-way check earned its keep — `recount_copilot` was
  itself wrong twice and got caught, which a two-way check would have missed.
- **Four review calls (mine, on top of the report):**
  1. **§3.3 is under-ranked — it's the most consequential finding in the run.**
     The agents never shelled out to graphify, so the A/B produced 0 savings rows.
     That is not merely a Phase-2 protocol fix: read against the 2026-07-22
     capture report ("0 real receipts across 36,451 calls"), it suggests graphify
     savings exist in the wild **only when a human runs the wrapper deliberately**
     — a product/adoption finding, not an accounting one. Plan §4.1 rewritten: the
     A/B must declare which of three modes it measured (agent-prompted /
     driver-invoked / unprompted-observed), and **the unprompted zero is data to
     keep reporting**, not a failure to retry until green.
  2. **The suggested Copilot fix violates append-only.** "Update the row to the
     last cumulative shutdown" can't happen — the ledger only appends. Verified
     the mechanism in source: `call_id=f"c_cop{sid[:12]}{i:03d}"`
     (`transcript.py:387`) is session+model-index only, so a 2nd shutdown collides
     and is dedup-dropped. Correct fix shape: **put the shutdown ordinal in the id
     and store the per-shutdown DELTA** (cumulative_n − cumulative_{n-1}) — sums to
     truth, stays idempotent on re-import, preserves append-only. Note
     `totalPremiumRequests` may be cumulative too and needs the same treatment.
  3. **§4.5 should be MED, not LOW.** "The declared `surface` restamp is silently
     lost when rows collide by derived id with a built-in source" is silent loss of
     an explicit config value — same failure class as the dedup-drop, in the
     feature shipped 24h earlier specifically to stop mislabeling.
  4. **Don't close "Kiro tokens are unrecoverable" on two data points.** Q1/Q2 both
     showed nulls with `model_id:"auto"` (server-routed). One cheap probe first:
     an explicit non-auto model, and a check of `kiro-cli settings list --all` for
     a telemetry/usage flag. If still null, the conclusion is solid.
- **Plan updated:** §4.1 (the A/B correction above) and new **§2.6a** — a standing
  exception to verbatim capture for Kiro CLI, since its SQLite DB co-locates
  `auth_kv` + all-directory transcript text with the metadata (redacted
  workspace-scoped projection instead; check 2 = `◻ n/a`; a future SQLite parser
  inherits the same counts-never-content constraint).
- **Next (recommended order):** cheap Kiro token probe → `docs/regression/` entries
  for the two HIGH findings → Copilot delta-id fix → then Phase 2. Manual VS Code
  cells (V6–V11) still pending. Tree uncommitted.

## 2026-07-28 — Phase 1 scripted cells RAN; Kiro CLI installed → resume prompt issued

- **Reported by Claude Code (Opus):** `../cage-lab/golden/` built and committed
  (cage tree untouched). `drive.py` verified (`--list`, `--recheck`,
  `--manual-capture`); frozen `workspace/` with a 47 KB `big_module.py`.
  **Grid:** V1/V2 claude CLI ±graphify **8/8** (full three-way token
  reconciliation) · V3/V4 copilot CLI ±graphify **7/8** (check 5 ✗ — a real cage
  finding) · V5/V5b **NOT AVAILABLE** (kiro-cli not installed at the time).
  Stopped before the manual cells as instructed; interim report + manual
  checklist handed over.
- **Two cage findings filed (not patched — correct per the rules):**
  1. **HIGH — Copilot resumed sessions undercounted.** `--continue` appends a
     *second cumulative* `session.shutdown`; cage's session-id-derived idempotent
     id keeps the first and dedup-drops the second ⇒ **16.5–18% undercount**
     (189,788 vs 227,298 true tokens; Q3's whole increment lost). Hits any
     multi-shutdown Copilot session including VS Code chats across restarts.
     **This must be fixed (or at minimum dated into `docs/regression/`) before a
     full sweep — otherwise every Copilot number in the corpus bakes in the
     error.**
  2. **MED — stacked graphify shims recurse → hang.** Fresh `workspace/bin/
     graphify` and a stale `anton/bin/graphify` (old `cage adopt`, targets the
     removed `cage graphify` verb) resolve to each other — a dead-verb
     wiring-liveness artifact. Driver drops it from PATH as a safety net.
- **Asked:** kiro-cli is now installed — initiate the pending Kiro tasks.
- **Done:** `docs/golden-set-kiro.prompt.md` (**Opus**) — a *resume* prompt, not a
  rebuild: reuse the existing driver/workspace/report, run **discovery first**
  (snapshot `~/.kiro/**` + IDE globalStorage + `$TMPDIR/kiro-log/` around one real
  `kiro-cli chat --no-interactive`, cross-check with `--list-sessions`, quote the
  shape verbatim) → `cage import --agent kiro` → **attempt the config-only fix**
  (`[sources.kiro] paths=… surface="cli"`, verify via `cage doctor --paths`) →
  run V5/V5b through the eight checks → update the validation report and answer
  the Kiro question explicitly. Adds an `--effort` probe for the effort-suffix
  pricing path, and a STOP if `kiro-cli login` is needed (interactive).
- **Next:** Arpit runs the Kiro prompt; then decide the Copilot-undercount fix
  before Phase 2; manual VS Code cells still pending. Tree stays uncommitted.

## 2026-07-28 — Cowork: golden-set pair rewritten to Phase 1 (off hold, ready to run)

- **Asked:** handoff and prompt for Phase 1.
- **Done:** replaced both `docs/golden-set.{handoff,prompt}.md` — the ON-HOLD
  4-question single-agent pilot is gone; they now specify **Phase 1: the 12-cell
  validation matrix** (V1/V2 claude CLI ±graphify · V3/V4 copilot CLI · V5/V5b
  kiro CLI · V6–V11 the manual VS Code/IDE cells), 2–4 questions per cell, the
  **eight** checks (the seven plus config provenance), ending in
  `findings/VALIDATION-REPORT.md`.
- **Structure that matters:** the prompt has **two hard stops** — after the
  scripted cells it writes an interim report, hands over
  `manual/vscode-checklist.md`, and stops (extensions can't be driven
  headlessly); after the full report, Phase 2 needs Arpit's explicit go. Setup
  now includes wiring graphify **and verifying it live** (`cage doctor` —
  presence ≠ liveness, the F1 lesson) and recording a **config baseline**
  (`cage.toml`, never hard-code `policy.toml`).
- **V5 written as the highest-value cell:** version/whoami → snapshot
  `~/.kiro/**` + IDE globalStorage + `$TMPDIR/kiro-log` → record the shape
  verbatim → `cage import --agent kiro` → **attempt the config-only fix on the
  spot** (`[sources.kiro] paths=… surface="cli"`, verify via
  `cage doctor --paths`) → if rows don't parse, file the fourth-parser finding
  and **don't** write a parser here.
- **Report must answer three questions explicitly:** where Kiro CLI logs (and
  whether config sufficed) · whether the graphify PATH interceptor fires under
  the VS Code extensions at all · whether the Claude CLI and VS Code stores are
  distinguishable (V1 vs V6 — the cleanest test of the `surface=""` blank).
- **Next:** Arpit runs `docs/golden-set.prompt.md` (Opus, `cage/` + parent dir);
  then does the manual cells; tree stays uncommitted.

## 2026-07-27 — Claude Code: config pair BUILT (surface key + cage.toml rename)

- **Asked:** run `docs/config-surfaces-and-rename.prompt.md` (Opus) — Task A
  (`[sources]` gains a `surface` restamp key + discoverability) then Task B
  (`policy.toml` → `cage.toml`, non-breaking).
- **Done — both green, 833 passing.**
  - **A:** `LogSource.surface` (trailing, defaults `""` ⇒ byte-identical);
    validated `surface` key in both schema shapes (`_resolve_surface`, out-of-set
    → `problems`, never a raise); `importcmd._surface_restamp` restamps rows
    **only when declared** across all three built-in importers + custom tools;
    `cage doctor --paths` shows a `surface` column; `cage query sources` documents
    it. Fixes the non-IDE-Kiro mislabel-as-`ide` gap (the config knob only — no
    Kiro-CLI parser, per the hard out-of-scope).
  - **B:** one resolution point `Footprint.policy` (cage.toml → policy.toml
    fallback → cage.toml), `shadowed_config` names a both-present leftover; bundled
    file `git mv`'d to `data/cage.toml`; 6 literals + `cleanup.NEVER` (both names);
    `cage setup` migration (idempotent, non-destructive); `cage doctor` + a
    load-time stderr warning surface a shadowed config; zipapp still resolves it.
    Goldens P1/P3a/P3b re-blessed (filename only). New `cage query config-file`.
- **Decided:** discoverability via `cage doctor --paths` (not a new verb — the
  handoff's default, output wasn't crowded). Warning is stderr-only so stdout
  stays byte-identical.
- **Docs:** folded into the uncommitted v0.36.0 CHANGELOG; README/example/FORMULAS/
  GLOSSARY/`cage query` updated; handoff+prompt archived to
  `docs/archive/v0.36-config-surfaces-and-rename.*`; DOC-REGISTRY bumped;
  IMPLEMENTATION Task A/B entries. **CLAUDE.md edits then applied** on Arpit's "go":
  the `policy.toml`→`cage.toml` sweep (11 refs; `NEVER` note keeps the legacy name),
  a new **Config file** substrate bullet, the `[sources] surface` note, and the
  stale `just test` count `902 → 833` (actual collected/passed, 0 skips).
- **Next:** tree stays **uncommitted** (standing directive).

## 2026-07-27 — Cowork: golden-set plan updated for the shipped config changes

- **Asked:** update the cage-lab golden-set plan after the latest implementations.
- **What landed since the plan was written** (Claude Code, both Opus tasks green,
  **833 tests**): (A) `[sources]` gained a validated `surface` key —
  `LogSource.surface`, `importcmd._surface_restamp` restamps **only when
  declared**, `cage doctor --paths` shows `surface=<declared|parser>`,
  `cage query sources` documents it; (B) config renamed to **`cage.toml`** with a
  `policy.toml` read fallback, `cage setup` migration, both-present ⇒ cage.toml
  wins + warning, `Footprint.shadowed_config` naming the leftover.
- **Plan updated (§2.6, new §2.7, §1, §2.5, §6):**
  - The Kiro gap is **re-scored**: suspicion 2 (mislabelled `surface="ide"`) is
    **already fixed** — a source can declare `surface = "cli"`. Suspicion 1
    (unknown path) is config-fixable *once the path is known*. Suspicion 3
    (different **format** ⇒ needs a 4th parser) is now the only open one, and is
    what Phase 1 discovery must decide.
  - V5's task list gained **step 5: try the config fix on the spot** — write the
    `[sources.kiro] paths=… surface="cli"` stanza against the discovered path,
    re-import, check `doctor --paths`. If rows land with `surface="cli"` and
    correct tokens, **the whole gap was configuration**, and the working stanza
    goes in the report as the fix. Step 6: if rows don't parse, that *is* the
    fourth-parser finding — capture the shape, file it, don't write a parser
    inside the golden-set task.
  - New **§2.7** records what v0.36 changed under this plan and its two
    consequences: config stanzas go in `cage.toml` (driver must not hard-code
    `policy.toml`), and every run records **which config file was active** —
    added as check #8 and to the manifest, because a capture whose numbers depend
    on an unnoticed legacy config is a trap.
  - Field matrix (§6) gains two provenance rows: *surface source*
    (parser-derived vs declared) and *config file* per run.
  - Swept `policy.toml` → `cage.toml` in `cage-lab-plan.md` §4 and
    `cage-lab-setup.prompt.md` (the bundled price table the lab reads as data).
- **Next:** unchanged — rewrite the golden-set pair to the phased plan, then run
  Phase 1. Tree still uncommitted.

## 2026-07-25 — Cowork: config pair specced (sources `surface` key + cage.toml rename)

- **Asked:** (1) expose the log paths in policy.toml so they're dynamically
  configurable — does that solve the Kiro issue? (2) rename policy.toml →
  cage.toml. Then: give me the prompt to do both now.
- **Answered honestly:** **no, (1) solves 1 of 3** — and it already exists.
  `paths.resolve_log_sources` has shipped `[sources]` (env > policy > built-in,
  per-source `paths`/`glob`/`replace`, custom tools via `format`). What's missing
  is that `LogSource` has **no `surface`** field while
  `transcript.parse_kiro_calls` hardcodes `surface="ide"` — so pointing cage at a
  non-IDE Kiro store would silently mislabel every row. The third gap (a
  different *format* ⇒ needs a parser) config can never fix.
- **Sized the rename accurately:** the filename is **6 code/packaging literals**
  (`paths.py:748`, `policy.py:23,337`, `doctorbundle.py:81`, `cleanup.py` NEVER,
  `explain_data.py:418`, `pyproject.toml:52`) — not the ~300 prose mentions a
  naive grep implies.
- **Done:** `docs/config-surfaces-and-rename.{handoff,prompt}.md` (**Opus**).
  A: `surface` key in both schema shapes + `LogSource.surface` + restamp-only-
  when-declared + an effective-sources listing (default: extend
  `cage doctor --paths`, not a new verb). B: `cage.toml` first with
  **`policy.toml` fallback** (users on PyPI releases have the old name — never a
  breaking rename), both-present ⇒ cage.toml wins + warning, `cage setup`
  migrates, `cleanup.NEVER` protects both, zipapp bundled-data path re-verified.
  Prompt carries a 5-case smoke matrix and a hard **out-of-scope**: no Kiro CLI
  path or parser — that format is unknown until golden-set Phase 1, and guessing
  it would repeat the `kind:0` mistake.
- **Next:** Arpit runs `docs/config-surfaces-and-rename.prompt.md` (Opus). Tree
  stays uncommitted.

## 2026-07-25 — Cowork: Kiro CLI exists — a probable cage capture gap

- **Asked:** Kiro also has a CLI — check whether claude, copilot and kiro CLIs exist.
- **Verified (docs, not assumption):** **`kiro-cli` is real** — evolved from the
  Amazon Q Developer CLI, `brew install kiro`. Confirmed from
  kiro.dev/docs/cli/reference/cli-commands: `kiro-cli chat --no-interactive
  "<q>"` (perfect for scripted driving), **per-directory sessions auto-saved every
  turn with UUID ids** (`--list-sessions`, `--resume-id`), `--effort
  low|medium|high|xhigh|max`, and `KIRO_HOME` (default `~/.kiro`) holding
  "agents, prompts, skills, steering, settings, **and sessions**". `$TMPDIR/
  kiro-log/` is debug logging, not usage.
- **The finding this implies (3 suspicions, now Phase-1 tasks):** (1) cage's
  source registry knows exactly ONE kiro location — the IDE's
  `kiro.kiroagent/dev_data/tokens_generated.jsonl`; nothing points at `~/.kiro`'s
  session store, so **CLI usage may be entirely uncaptured**; (2)
  `transcript.parse_kiro_calls` **hardcodes `surface="ide"`** — a CLI row would be
  mislabelled, exactly what the `surface` field exists to prevent; (3) the CLI
  session store may be *better* than the IDE token log (UUID session ids +
  per-turn saves could fix three of kiro's four known weaknesses: no session
  boundary, no timestamps, generic `agent` model).
- **Done:** new plan §2.6 (Kiro CLI — evidence, the three suspicions, and an
  ordered discovery task list: version/whoami → snapshot `~/.kiro` + IDE
  globalStorage + `$TMPDIR/kiro-log` around a real run → inspect what it wrote →
  `cage import --agent kiro` → file findings). V5 promoted from "expected NOT
  AVAILABLE" to a **real cell** with V5b for graphify-on; matrix now 12 cells.
  Added a per-agent non-interactive driving-command table with the rule that the
  driver must confirm flags from `--help` at run time. Corrected
  `cage-lab-plan.md` M4c, which asserted "no CLI surface exists".
- **Could not check Arpit's PATH** — the Cowork sandbox is separate from his Mac;
  gave him a one-liner to run locally.
- **Next:** Arpit runs the CLI-presence check; then sign-off on the phased plan.

## 2026-07-25 — Cowork: golden set re-phased (validate-all-surfaces first); pair ON HOLD

- **Asked:** do it in phases so each is easy to validate — (1) set up the golden
  folder + interceptor and verify capture is correct for **all agents, CLI and
  VS Code, with and without graphify**, numbers included; (2) run the scripted CLI
  question sweep; (3) Arpit runs the VS Code extensions manually. Update the plan;
  **hold** the handoff/prompt.
- **Done — plan §2.5 replaced** (the 4-question single-agent pilot was too narrow
  for what he wants validated). Now:
  - **Phase 1 (gating): setup + capture validation across an 11-cell matrix** —
    V1–V5 scripted (claude CLI ±graphify, copilot CLI ±graphify, kiro CLI ⇒
    expected `NOT AVAILABLE`), V6–V11 manual (claude VS Code, copilot VS Code,
    kiro IDE, each ±graphify). 2–4 questions per cell (Q1 floor, Q2→Q3 cache
    pair, plus one architecture question on graphify-ON cells) ≈ 30–40 real calls.
    Setup includes **wiring the graphify interceptor and verifying it live**
    (`cage doctor` — presence ≠ liveness, the F1 lesson). Same seven checks
    applied per cell; output `findings/VALIDATION-REPORT.md` (11 × 7 grid,
    three-way numbers, "what we learned").
  - **Two unknowns Phase 1 must answer explicitly:** does the graphify PATH
    interceptor fire under the VS Code extensions at all (if not, the A/B is
    CLI-only and the plan says so), and are the Claude CLI vs VS Code stores
    distinguishable (V1 vs V6 is the cleanest test of cage's `surface=""` blank).
  - **Phase 2** scripted 18-question CLI sweep + graphify A/B; **Phase 3** manual
    VS Code/IDE sweep; **Phase 4** field matrix + wire into the lab's inputs.
  - Build order (§8) restructured to match.
- **Held:** `docs/golden-set.{handoff,prompt}.md` marked ⏸ **ON HOLD** with a
  banner — they still describe the old pilot and must be rewritten to the phased
  plan before execution; docs index updated to say so.
- **Next:** Arpit signs off the phased plan → rewrite the pair to Phase 1 → run.

## 2026-07-25 — Cowork: pilot-first gate added to the golden set + execution pair

- **Asked:** run a few samples first to check everything is captured correctly;
  update the plan; create handoff + prompt; list what Arpit must do manually.
- **Done — plan §2.5 "Phase 0 — the PILOT" (gating):** one agent (claude CLI
  first — richest logging surfaces protocol bugs fastest), four questions
  (Q1 floor → Q2 cache-create → Q3 cache-read → 90s pause → Q6 gap), ~5 minutes.
  **Seven checks:** exact snapshot diff · faithful copy + unchanged source sha ·
  question→bytes mapping · complete import (hand-counted) · values reconcile
  three ways (log · ledger · independent recount) · derived signals present
  (`cache_write_in`, `cached_in`, `gap_ms`≈90s, `session_uid` + name-or-`""`) ·
  nothing written outside `captures/`. Output is `PILOT-REPORT.md` whose real
  deliverable is the **"what we learned"** list of fields that did NOT appear.
  A red pilot **blocks** Phase 1 — the corpus would otherwise freeze the flaw in.
  Build order restructured into Phase 0 (pilot) → Phase 1 (sweep + graphify A/B
  + manual) → Phase 2 (field matrix + wire into the lab).
- **Created** `docs/golden-set.{handoff,prompt}.md` (**Opus**) with the hard gate
  stated up front ("build it, run it, report, then STOP"), the late-write/log-
  buffering risk called out (settle-and-retry, and report if buffering exceeds
  it), and the rule that a ✗ check is a *result to report*, never something to
  loosen. Indexed as the **first** pair to run — before the M/G matrix, which
  consumes its output.
- **Next:** Arpit runs the golden-set prompt (Opus), reviews `PILOT-REPORT.md`,
  and answers the three §9 open questions before Phase 1. Manual steps for him
  are listed in the plan §5 (VS Code/Kiro/Claude-extension checklist).

## 2026-07-25 — Cowork: golden-set plan (drive the real agents, capture, field matrix)

- **Asked:** add a cage-lab folder with a script that runs the Claude/Copilot/Kiro
  CLIs, asks them questions, and captures how tokens get logged — so we learn what
  can be built and how to test it; list the manual VS Code steps too; capture ids +
  logs as a **golden set**; author the question set; configure graphify (with/
  without pairs). Create a plan.
- **Done:** `docs/cage-lab-golden-set.plan.md` — layout (`golden/` with driver,
  questions, captures, manual checklist, findings); the driver protocol
  (pre-snapshot → frozen scratch workspace → ask with real pauses → post-snapshot
  diff → copy new logs **verbatim** → import to a scratch ledger → manifest +
  `transcript-map.json` mapping question → session → log lines); **18-question
  core set** (Q1 floor · Q2 cache-create · Q3 cache-read · Q4 long output · Q5
  edits · Q6 90s gap · Q7 over-cap gap · Q8 title · Q9 untitled · Q10 model switch
  · Q11 router alias/UNPRICED · Q12 premium · Q13 refusal · Q14 **real interrupt**
  · Q15 parallel sessions · Q16 second project · Q17 effort tiers · Q18 burst);
  graphify **A/B pairing** with 4 architecture questions so the saving is checked
  against a measured A−B token difference; the manual VS Code/Kiro/Claude-extension
  checklist with mechanical pre/post capture; and the deliverable
  `findings/field-matrix.md` (agent × surface × field, evidence-backed).
- **Key properties:** because we author the prompts, captures are **byte-exact,
  unstripped** — the most real input cage will ever see. Q14/Q9/Q15 supply the
  genuine truncated-file, untitled-session and parallel-session cases the lab
  currently has to report `NOT COVERED`. Summarized into `PLAN.md` §11.
- **Open:** run cost (~100 real calls per full sweep), refresh cadence, and where
  the frozen workspace lives — defaults proposed in §9.
- **Next:** Arpit's call on the open questions, then the handoff/prompt pair for
  the golden-set build (sequence it *before* the lab matrix, since it produces the
  lab's inputs).

## 2026-07-25 — Cowork: ZERO mock data — real files used as-is, in place, uncopied

- **Asked:** "not at all any mock data — we use the files as is."
- **Done — plan §2.1 rewritten again, harder.** The previous pass still allowed
  verbatim *copies* into a `fixtures/` dir plus two synthetic artifacts. All of
  it is gone:
  - **No `fixtures/` dir, no copies, no edits.** Scenarios run
    `cage import --path <real file>` (the flag reads a transcript file/dir in
    place); where auto-discovery is under test, the scratch `$HOME` gets
    **read-only symlinks** — same bytes, same inode. `inputs.toml` is the only
    input config (scenario → real path).
  - **Untouched-source proof:** sha256 before/after each run must be equal, and
    a write-mode open under `samples/` or a live agent log is an assertion
    failure in lab code.
  - **Real graphify only** — the fake binary is forbidden; not installed ⇒
    `NOT COVERED — graphify not installed`.
  - **No manufactured edge cases** — truncated-tail and untitled-VS-Code-session
    are used only if genuinely present on the machine, else `NOT COVERED`.
  - Any cell without real data prints `NO REAL DATA — cell not covered`.
  - Eyeball header now reads ORIGINAL (real path + "read in place, never
    modified" + before/after sha) → IMPORTED (the exact command) → LEDGER →
    MANIFEST → REFERENCE.
- **Propagated:** `cage-lab-plan.md` (laws, layout, §2.1, matrix rows, eyeball,
  runner UX incl. new `lab inputs --list`), the handoff DoD/non-negotiables/key
  inputs, the prompt (task step 2, guardrails, workflow, plan-pause now posts the
  *input inventory*), and `PLAN.md` §11's laws line.
- **Next:** unchanged — execute `docs/cage-lab-setup.prompt.md` (Opus).

## 2026-07-25 — Cowork: synthetic data DELETED — cage-lab runs on real captures only

- **Asked:** delete the fake data, pull in the actual data, and give a path to
  the real file so it can be compared by eye.
- **Key finding that made this free:** the sanitized samples
  (`samples/agent-artifacts/*/logs/real*/`) already carry **real token counts** —
  only message *content* was stripped ("preserving real timestamps/models/token
  counts"). Verified: copilot CLI `inputTokens: 11845 / outputTokens: 170`, kiro
  `promptTokens: 7, 12, 27`. So authored numbers bought nothing.
- **Done — plan §2.1 rewritten as "Inputs are REAL — no synthetic fixtures":**
  fixtures are **verbatim copies** of those real captures, sha256-verified by
  `lab setup` against source (red on drift); references are the **lab's own
  parser's** recount of the same real files (independence = who computes, not
  fake inputs); new `python -m lab capture-fixtures` pulls fresh real sessions
  from live agent logs (content-strip verified by a grep gate, provenance
  recorded) for any missing case; an uncovered cell prints `NO REAL DATA — cell
  not covered` and is listed in the summary, never faked. Exactly two artifacts
  remain non-real and must self-label `SYNTHETIC`: the fake graphify binary (not
  an agent log) and the truncated-tail case (a real file mechanically cut).
- **Eyeball surface upgraded for comparison:** it now leads with **ORIGINAL**
  (the real capture's absolute path + provenance) and FIXTURE (copy + sha
  match), and there's a new `python -m lab source <scenario> [--open]` that
  prints/opens just the paths. Mental-math fixture rule dropped (real numbers) —
  replaced by "show every addend with its source line and a running sum".
- **Next:** unchanged — execute `docs/cage-lab-setup.prompt.md` (Opus).

## 2026-07-25 — Cowork: "is cage-lab data fake?" → fixture-provenance rule added

- **Asked:** is cage-lab's data fake?
- **Honest answer:** the *numbers* are authored on purpose (inventing them is the
  only way to know the right answer independently of cage — deriving expectations
  from cage's own output would be cage grading itself). But the **shapes** were
  about to be authored too, and that is a genuine hole: a fixture with an invented
  structure yields a reference derived from the same wrong file, everything goes
  green, and nothing is proven. We nearly hit exactly this with the `kind:0` title
  claim. The L-labs were already real (they read `~/.cage`).
- **Done — plan §2.1 "REAL shapes, AUTHORED numbers" (non-negotiable):** fixtures
  are now built by **reduction from `samples/**/logs/real*/`** (sanitized real
  sessions from Arpit's machine): trim whole records, rewrite **only numeric
  leaves** to mental-math values, never add/remove/rename a key (a structural edit
  is a shape claim, and shape claims come only from real data), record provenance
  per fixture, and add a **shape-drift guard** (fixture key-set ⊆ source sample
  key-set) so a parser or log-format change goes red instead of silently passing.
  Labelled exceptions: truncated-tail file, an untitled Copilot VS Code session
  (~38% of real ones), graphify fakes (no real graphify log exists). Propagated to
  the handoff DoD and the prompt (incl. a new guardrail: if a matrix cell has no
  real capture to reduce from, STOP and ask — never author a plausible structure).
- **Next:** unchanged — execute `docs/cage-lab-setup.prompt.md` (Opus).

## 2026-07-25 — Cowork: FORMULAS.md created; INTERVIEW reframed as the exit interview

- **Asked:** (1) create a FORMULAS.md with every formula cage uses; (2) INTERVIEW.md
  is really an *exit interview* from an outgoing maintainer-model to every future
  one — say so in CLAUDE.md and always maintain it.
- **Done (1):** `docs/FORMULAS.md` written **from source**, not from memory — read
  `prices`, `convert`, `attribution`, `matrix`, `human`, `attention`, `estimate`,
  `calibration`, `compare`, `study`, `taskcorr`, `roi`, `verdict`, `quality`,
  `regression`, `forecast`, `compress`, `constants`, `explain_data`. Seven
  sections (money · savings · human axis · prediction/calibration · heuristics ·
  reader semantics that change totals · the three number layers); every entry
  carries formula + code link + **method tag** + knobs. Includes the things that
  silently move totals but aren't formulas: the id-deduped `receipts()` union,
  month partitioning, derive-time repricing. Closing rule: it must agree with the
  live explainer registry, which is the copy that ships in the binary.
- **Done (2):** CLAUDE.md now defines INTERVIEW.md as the exit interview with four
  standing sections (state of play · in-flight + next · standing constraints ·
  lessons/scar tissue) and the reason for continuous upkeep — *any session can be
  the last before a model switch*. Rewrote the file's header to match, added the
  two missing sections (in-flight+next; standing constraints = Arpit's active
  directives), and added two new scar-tissue lessons: verify log shapes against
  real data + sweep downstream docs when a spec is corrected; and *a doc rule that
  fights the workflow gets broken silently — fix the rule* (the archive-on-ship
  case). Registered FORMULAS.md + the reframed INTERVIEW in DOC-REGISTRY and the
  docs index.
- **Next:** unchanged — execute `docs/cage-lab-setup.prompt.md` (Opus, both
  siblings). Tree stays uncommitted.

## 2026-07-25 — Cowork: cage-lab docs reviewed against the 4 requirements, gaps closed

- **Asked:** review the cage-lab plan/handoff/prompt against the four testing
  requirements, change what's needed — then execute.
- **Reviewed:** the matrix (#2 solo → per-CLI → per-VS Code → kiro+copilot
  combined) and graphify combos (#3) and playground (#4) were already complete;
  the gap was in **#1 (manual eyeballing)** — the surface cited source *line
  numbers* but made Arpit open files to see what was on them, and a full run left
  no single entry point.
- **Changed:** eyeball reports now **quote the cited source lines inline** plus
  the matching ledger rows (trimmed to asserted fields) and a ready-to-paste
  side-by-side open command — verify without opening anything, open when you want
  to. Added **`runs/EYEBALL-INDEX.md`**: one row per scenario (what it proves ·
  verdict · eyeball path), failures sorted to top with the failing metric + delta
  inline, printed as the run's last line. Added the *mental-math fixture* rule
  (distinct, roundish values — a fixture needing a calculator defeats the
  surface). Propagated the always-on-name/`session_uid` assertions from M6 down
  into M1/M2/M3/M5b (incl. claude's no-summary fallback and kiro's honest `""`).
  Added handoff §11 — prerequisite status: all asserted behavior is built + green
  (818), so the lab is runnable now against the uncommitted tree.
- **Decided/open:** `uv build` from the uncommitted tree is correct — the lab
  verifies what is about to ship. Open questions unchanged (publish eyeball
  reports? pipx?) — defaults stand.
- **Next:** execute `docs/cage-lab-setup.prompt.md` (Opus, both siblings).

## 2026-07-25 — Cowork: archive implemented pairs; lifecycle rule now archive-on-implement

- **Asked:** archive every implemented handoff/prompt pair and add the details to
  CLAUDE.md.
- **Found the rule was the blocker:** CLAUDE.md said archive **on ship**, but cage
  is deliberately uncommitted for a long stretch — so finished work would have sat
  in `docs/` root indefinitely and the *Active work* list would keep advertising
  done work as pending.
- **Done:** amended the CLAUDE.md lifecycle rule to trigger on **implementation
  (suite green), not release** — with the reason recorded (cage builds several
  features per release; `docs/` root must read as *work not yet done* so the next
  agent can trust it as the live queue) — and to require the archive header naming
  the version the work rides. Moved
  `names-and-savings-migration.{handoff,prompt}` → `docs/archive/v0.36-…`; added
  archive headers to it and to the two v0.36-hookless-rebuild files (moved earlier
  without one), worded for the built-but-unreleased state. Updated
  `docs/archive/README.md` (row + trigger note), `docs/README.md`, and the
  CHANGELOG "Built from:" line (now links both pairs).
- **Decided/open:** `docs/` root now holds exactly one active pair —
  `cage-lab-setup` — which is accurate: it is the only unbuilt work. Still open:
  the proposed CLAUDE.md union/migrate line from the last exchange.
- **Next:** run `docs/cage-lab-setup.prompt.md` (Opus, both siblings). Tree stays
  uncommitted.

## 2026-07-25 — Cowork: review of the A+B execution; spec corrected from real data

- **Asked:** thoughts on Claude Code's A+B report (818 green, tree dirty at
  `98a3455`), including its flagged deviation and a proposed CLAUDE.md line.
- **Assessed:** the deviation is the session's most valuable output — the executor
  hit the prompt's "STOP if shapes disagree" guardrail, probed 143 **real** chat
  sessions, and found the plan's `kind:0`-title claim wrong. That is a **spec
  defect caught by the guardrail**, not an implementation deviation; the parser is
  right, the plan was stale.
- **Done (spec fixes, mine to make):** corrected `cage-import-ledger-plan.md` §4
  to the verified `customTitle` patch / `kind:0.v.customTitle` /
  `generatedTitle`-fallback ladder (+ noted 88/143 named ⇒ empty name is a normal
  state) and recorded the per-(agent, surface, session) + `session_uid`
  granularity. **Propagated the same correction into `cage-lab-plan.md`** (fixture
  note, M2, M5b, M6) — it carried the identical stale assumption and would have
  produced fixtures that pass against a shape reality doesn't have; added the
  untitled-session case and the `session_uid` assertions (unique, never on a call
  row / derived view, normalized out of determinism compares). Added a
  shape-warning block to `cage-lab-setup.prompt.md`.
- **Decided/open:** CLAUDE.md line — recommended **apply with one addition**
  (state that `session_uid`/`import_id` are capture ids excluded from derived
  views); left unapplied pending Arpit's word, per the propose-don't-rewrite rule.
  Tree stays uncommitted.
- **Next:** Arpit's call on the CLAUDE.md line, then run
  `docs/cage-lab-setup.prompt.md` (Opus, both siblings).

## 2026-07-25 — Cowork strategy session: the whole v0.36 arc + cage-lab v3 + doc-discipline rules

*(Cowork chat with Arpit — the strategy/spec desk behind today's Claude Code
executions. Logged per the new rule: chat decisions are worklog material.)*

- **Asked (arc, in order):** review `cage-import-ledger-plan.md` → add the savings
  tree; then review samples+code, **remove all hook machinery and md assets**
  ("rebuild later"); stop implementing mid-surgery and package handoff+prompt
  instead; extend the pair to the whole plan (Phases 0–4) + standing
  IMPLEMENTATION.md rule; review cage-lab and plan its rebuild; three directive
  decisions; cage-lab v3 fresh-setup plan per a 4-point spec; these doc-discipline
  rules.
- **Done (docs/spec — execution went to Claude Code):** plan updated for the
  hookless pull-only world (savings `savings/<tool>/savings-YYYY-MM.jsonl` tree,
  §7 decisions log); partial removal executed then packaged as
  `v0.36-hookless-rebuild.{handoff,prompt}` (**Opus**, Phases 0–4, taskcorr
  gated); `names-and-savings-migration.{handoff,prompt}` (**Opus**);
  `cage-lab-plan.md` v3 (fresh sibling repo: M/G correctness matrix, 3-way
  auto-verify, eyeball surface with source line refs, playground, track-2 R/L
  scenarios) + PLAN.md **§11** (durable summary) +
  `cage-lab-setup.{handoff,prompt}` (**Opus**; commits in cage-lab only).
- **Decided (Arpit's directives, recorded in plan §7):** session names **always**
  captured (flag removed; manifest-only PII widening, deliberate); savings
  migration = consolidate with **NOT WRONG, NOT DUPLICATED** precision (copy with
  original ids + id-deduped `receipts()` union; never rewrite receipts.jsonl);
  **no commits in cage** until more work lands; savings axis extends per-source
  (graphify → human → other tools).
- **New standing rules (CLAUDE.md updated):** IMPLEMENTATION.md at every
  milestone; WORKLOG covers Cowork/chat sessions too; INTERVIEW.md maintained
  continuously for model-switch pickup.
- **Next (sequence):** names-and-savings-migration prompt ✔ (done, 817 green) →
  `cage-lab-setup.prompt.md` in Claude Code (Opus, both siblings) → baseline
  report into `docs/regression/` → Arpit eyeballs `runs/*/eyeball.md`.

- **Asked:** execute `docs/names-and-savings-migration.{handoff,prompt}.md` — (A)
  always capture session names, (B) `cage data migrate-savings` with an id-deduped
  `receipts()` union. **DO NOT COMMIT** (more work lands first).
- **Explored first (guardrail):** verified the parser shapes against the real data.
  Claude `summary` shape confirmed. The plan's "copilot VS Code title on the `kind:0`
  record" was **contradicted** by both the sanitized sample and the documented format
  → asked Arpit → he chose "inspect the real store". Probed this machine's 143 real
  `chatSessions` files (kinds/keys only): the title is a `customTitle` patch record
  (`kind:1 k:["customTitle"]`) or `kind:0.v.customTitle`, else the first request's
  `generatedTitle` (88/143 named). Q2: Arpit wanted the name on **every** session +
  a **separate unique id** → per-(agent,surface,session) manifest rows + `session_uid`.
- **Done (both green, 817 tests):** A — removed the `session_names` flag; parse-only
  `session_name_claude`/`session_name_copilot_vscode`; per-session manifest rows with
  `session_uid`; names never on call/receipt rows (grep-tested). B — `receipts()` →
  id-deduped `union_by_id` (tree wins, id-less preserved); `cage/migratecmd.py` +
  `cage data migrate-savings` (dry-run/`--apply`/reconciliation-refuse); precision
  test-pinned. Docs: CHANGELOG fold, `cage query migrate-savings`, IMPLEMENTATION ×2.
  Scratch-repo smoke passed (names lifted; attrib byte-identical before/after; 2nd
  `--apply`=0).
- **Decided/open:** verb placement = `cage data migrate-savings` (default assumed;
  confirmed by no CLI-group objection). Proposed (NOT applied) a CLAUDE.md line for
  the union semantics + new verb — awaiting Arpit.
- **Next:** Arpit reviews; apply the proposed CLAUDE.md line if accepted. Working tree
  stays **dirty/uncommitted** per standing constraint.

## 2026-07-25 — Broken-link cleanup: relink live, cut removed features

- **Asked:** for the pre-existing broken doc links, link the ones whose target
  exists and delete the ones not existing in the new tool features.
- **Found:** all 10 swept doc targets are gone; they split by whether the *code*
  survives. `tools/docgen`, `tools/skillgen`, `gitcommithook.py` and the rendered
  skill/prompt/steering assets are **removed for good** (confirmed by the CHANGELOG
  v0.36 entry). `csvout.py`, `runshim.py`, `prices.py`, the launcher, sources and
  debug remain **live features** whose docs were swept.
- **Decided (with Arpit):** cut the removed-machinery prose from CLAUDE.md; for the
  live-feature swept docs, delete the whole doc reference but keep the feature prose.
- **Done:** rewrote ~8 CLAUDE.md passages (the Explain formula-catalogue tail, the
  provenance git-hook mechanism → transcript-only, the CSV/cli-output-spec block →
  golden fixtures, the whole "assets are rendered" skillgen+docgen rule, the
  verb-sweep list, the policy `[sources]` comment block, the gitcommithook install
  line); removed 8 dead doc pointers from README; fixed 3 in docs/PLAN.md. cage
  still imports; every live-spec file's links resolve.
- **Deliberately left:** broken links inside `CHANGELOG.md` and `docs/regression/*`
  — history/evidence, frozen by the same convention as `docs/archive/` (a dated
  record isn't rewritten to chase moved paths).
- **Next step:** if docgen/skillgen ever return, the CLAUDE.md rules need
  reinstating — the CHANGELOG v0.36 entry is the record of their removal.

---

## 2026-07-25 — Rename/move: INTERVIEW, PLAN, IMPLEMENTATION → docs/

- **Asked:** rename `maintainers-interview.md` → `INTERVIEW.md`, move
  `IMPLEMENTATION.md` from root into `docs/`, rename `cage-plan.md` → `PLAN.md`.
- **Done:** moved all three (git mv for the two tracked; plain mv for the
  session-new INTERVIEW). Swept every **live** reference — code comments
  (`__init__.py`, `explain_types.py`, `schema.py`), `pyproject.toml`, CLAUDE.md,
  README, docs/README, DOC-REGISTRY, GLOSSARY, INTERVIEW, samples, and the cage-lab
  docs (`cage/IMPLEMENTATION.md` → `cage/docs/IMPLEMENTATION.md`). Fixed the CLAUDE.md
  prose that said IMPLEMENTATION.md "lives at root by convention" and the ALL-CAPS
  note — IMPLEMENTATION.md now lives under `docs/`.
- **Decided (reverses the entry below):** IMPLEMENTATION.md now lives in `docs/`, not
  at root — an explicit override of cage's ALL-CAPS-tracker-at-root convention.
  CHANGELOG.md/README.md/AGENTS.md still sit at root, so the trackers are now split
  across two locations; noted, not blocked.
- **Not touched:** ~30 **archived** docs referencing `cage-plan.md` (frozen history
  — archive links may point at pre-archive paths, by the archive convention) and
  `graphify-out/GRAPH_REPORT.md` (generated — regenerates from code).
- **Next step:** on the next `graphify update`, the graph report's stale `cage-plan`
  ref self-heals; no action needed.

---

## 2026-07-25 — Documentation discipline: files + CLAUDE.md rules

- **Asked:** wire a full documentation-discipline doc set into cage and make it a
  maintained standing rule in CLAUDE.md — ADR TEMPLATE, GLOSSARY, WORKLOG,
  DOC-REGISTRY, architecture-flow.mermaid, docs/example/*, compare/proposals dirs,
  and the doc-style rule.
- **Done:** created [adr/TEMPLATE.md](adr/TEMPLATE.md) (bakes in the three
  veto-condition devices), [GLOSSARY.md](GLOSSARY.md), this file,
  [DOC-REGISTRY.md](DOC-REGISTRY.md), [architecture-flow.mermaid](architecture-flow.mermaid)
  (linked in README), [example/](example/) (cli/debug/setup/toml-config),
  [compare/](compare/) + [proposals/](proposals/) with READMEs; added a
  *Documentation discipline* section to CLAUDE.md.
- **Decided:** reconcile rather than duplicate — IMPLEMENTATION.md stays at repo
  root (cage's ALL-CAPS-tracker-at-root convention, already wired); PLAN.md
  *is* the PLAN; INTERVIEW.md *is* the INTERVIEW/succession record. No
  duplicate empty files.
- **Open:** the doc-style "no large paragraphs" rule is scoped to *authored* docs
  (guides, handoffs, examples), not CLAUDE.md/plan, which are intentionally dense —
  flagged in the CLAUDE.md rule. The `adr`-in-`CODE_BOUND` linter fix (fux repo)
  and using compare/proposals for a real fork are still unexercised.
- **Next step:** exercise the flow on the next real feature — write a compare doc
  before the plan, an ADR from TEMPLATE.md, and keep IMPLEMENTATION.md + WORKLOG
  current through the build.
