# Claude Code prompt: passive human-attention minutes (derived) + attested calibration

You are adding behind-the-scenes human-effort accounting to cage: derive
**estimated human-attention minutes** from turn-timestamp gaps in the session
logs cage already imports, integrate them into the total-cost views, and keep
the manual axis as ground truth that calibrates the heuristic. Run AFTER the
current tree is reviewed/committed (ask if dirty). **No commits, tags, pushes,
or publishes.**

## Context to load first

- `CLAUDE.md`; `docs/human-baseline.design.md` (the existing human-axis ladder —
  this work extends it, never bypasses it); `cage/transcript.py` (all four
  parsers — which carry per-turn timestamps); `cage/schema.py` (additive-field
  convention); `cage/human.py` + `cage/humanview.py` + `cage/trend.py`;
  `cage/quality.py` (`cage outcome`); `cage/compare.py`, `cage/verdict.py`,
  `cage/study.py` (total-cost consumers); `cage/constants.py` + `cage/policy.py`
  (numbers-layers); `cage/calibration.py` (the measured-hit-rate pattern to
  reuse); `tools/dummyrepo/run.py`.

## The design (decided — don't re-litigate)

1. **Capture:** at import, where a transcript has per-turn timestamps, stamp an
   additive optional `gap_ms` on each call row = wall-clock gap between the end
   of the previous assistant turn and the user turn that led to this call.
   Timestamps/counts only; empty = legacy contract; composite-id derivation
   unchanged (`gap_ms` never enters the id). Agents whose logs lack turn
   timestamps (e.g. Kiro's coarse token log) get **no** field — never fabricate.
2. **Derivation (read-time only):** derived attention minutes per session/task =
   `sum(min(gap_ms, idle_cap))`. Idle cap: policy `[human] idle_cap_minutes`
   with a `constants.py` fallback (default 10, rationale comment). Changing the
   cap re-derives; the ledger is never rewritten. Deterministic: same ledger +
   policy ⇒ same minutes.
3. **Method honesty:** derived minutes are always `estimated` and labeled
   `derived (turn-gaps, capped)`. Attested minutes (existing `human-record`, new
   `cage outcome --minutes N`) rank above derived in the precedence ladder;
   **for a given task attested wins and derived is shown as reference — the two
   are never summed.**
4. **Views:** `cage human` and `cage trend` show attested vs derived on separate
   lines (never blended); `cage compare`, `cage verdict`, `cage study report`
   gain a total-cost line = agent $ + human minutes × rate, tagged with the
   human component's method, with `--agent-only` to suppress it. `matrix
   --human` unchanged (baseline receipts are a different question).
5. **Calibration of the heuristic:** where a task has BOTH attested and derived
   minutes, `cage calibration --human` reports the derived/attested ratio
   distribution — the measured accuracy of the heuristic. Below `MIN_ESTIMATE_N`
   such tasks ⇒ refuse. The heuristic never self-reports confidence.
6. **Attestation friction-drop:** `cage outcome <task> --ok/--redo` accepts
   `--minutes N` (writes the same attested human receipt path `human-record`
   uses, fail-open).

## Task

1. Explore the four parsers; implement `gap_ms` where turn timestamps exist
   (claude certainly; codex/copilot per what the real fixtures show — check
   `tests/fixtures/transcripts/`). Document per-agent availability in the module
   docstring and the fixtures README.
2. Read-time derivation helper (one module, e.g. `cage/attention.py`) used by
   every consuming view — no view computes gaps itself.
3. Wire the views (§4), the outcome flag (§6), the calibration extension (§5).
4. Constants/policy: `idle_cap_minutes` (policy-preferred, constants fallback —
   the `DEFAULT_CONFIDENCE` pattern).
5. Explain entries: "how are human minutes derived" (calculation, live values)
   + extend the human-axis concept entry. `cage query` must answer it.
6. skillgen fragments for changed CLI surface → regenerate + `--bless`.
7. Tests: exact-number derivation over seeded gaps (incl. cap boundary, missing
   timestamps, cross-month tasks), attested-beats-derived precedence,
   never-summed rule, re-import idempotence with `gap_ms` present, determinism
   double-runs, calibration refusal path. Dummyrepo scenario **S10**: seeded
   transcript with known gaps → exact derived minutes in `human`/`compare`/
   `verdict` outputs; attest one task → precedence + calibration line exact.
8. Docs: plan doc § for the attention axis, README "What's new" (in-tree),
   CHANGELOG (in-tree), `human-baseline.design.md` extension, CLAUDE.md edit
   **proposed not applied**.

## Constraints (hard)

- $0/stdlib; determinism (derived views ledger+policy-only — the cap lives in
  policy, never a clock at read time); fail-open write path; `CageError` read
  path; four agents (per-agent availability documented, surface works for all).
- `method` is sacred: derived minutes never render as anything but `estimated`;
  no view ever silently blends attested with derived.
- Additive-only schema (`gap_ms` optional; empty = legacy); ledger never
  rewritten; composite ids unchanged.
- No watcher-shaped capture: no editor plugins, activity trackers, keystroke or
  focus monitoring — transcript timestamps only. This is a product line, not a
  default.
- PII: timestamps and counts only; nothing new readable.
- No commits; working tree only.

## Acceptance criteria (self-check)

- [ ] `gap_ms` stamped only where real turn timestamps exist; absence explicit
      in views, docstrings, fixtures README.
- [ ] Derived minutes exact and deterministic in tests; cap is policy-tunable
      and re-derives without ledger changes.
- [ ] Attested > derived precedence enforced and tested; never summed.
- [ ] compare/verdict/study report show tagged total-cost lines with
      `--agent-only`; human/trend separate the two sources.
- [ ] `cage calibration --human` reports measured heuristic accuracy or refuses
      below min-n.
- [ ] S10 green; `just test` green; skillgen `--check` clean; explain entries
      answer live; zero commits.
