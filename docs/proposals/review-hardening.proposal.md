---
doc: proposal — v0.44 review hardening: the confirmed findings not covered by the sibling proposal
status: proposed
raised: 2026-08-02
owner: unclaimed (P2 is Sonnet-mechanical; P4 touches joins, Opus)
---

# Proposal — review hardening (v0.37.0→v0.44.0 findings, phased)

Three phases remain. Each is independently landable, and none is caught by a test
today — all were adversarially verified against a **green** suite, so "green after"
proves nothing on its own.

Evidence: [review](../regression/2026-08-02-review-v0.37.0-to-v0.44.0.md). Sibling
proposal owns the credits defects:
[copilot-credits-integrity](copilot-credits-integrity.proposal.md).

| phase | what | tier |
|---|---|---|
| **P2** | honest-refusal fixes — adoption `--since` · OTel `$0` · hooks-off residue | 2 |
| **P3** | wiring hygiene — line endings · Windows gaps · wiringscan bookkeeping | 5 |
| **P4** | durable joins & scale — full shas · commitview defaults · coverage scope | 5 |

**P0 and P1 shipped 2026-08-03** (v0.45.0, in tree) and their bodies are **removed
from this file, not struck through** — `proposals/` must read as ideas *not yet built*.
Their record, including P1's one deliberate divergence from this spec, is the
[IMPLEMENTATION.md entry](../IMPLEMENTATION.md).

**The divergence worth inheriting:** P1 as filed asked for a `verbmap.REMOVED`-style
migration row of old event spellings. The build **declined** it — a hand-kept map goes
stale in the very release that renames an event. The fix-hint derives from live
`hookcmd.EVENTS` instead, matching `wiringscan`'s own rule that *the detector is the
live parser*. Where this proposal and the shipped code disagree, the code wins.

## P2 — honest-refusal fixes

- `adoption.py:188` — half B is month-granular only: wrap receipts in `ledger.since(...)`
  like half A (roi/report/chats already double-filter). Fix the masking test (its
  stale row sits in a fully-skipped month — move it in-month).
- `otelout.py:85` — unpriced linked receipt exports `cage.saved_usd: 0.0`, violating
  "omitted, never zero". Fix in `convert` (an Optional-returning variant owning the
  unpriced-vs-zero distinction), not by re-implementing dispatch in otelout — the
  credits rung already drifted between the two.
- `otelout.py:59` — `gen_ai.system` is deprecated (→ `gen_ai.provider.name`) before
  the pinned semconv 1.42.0: verify against the pinned spec and either bump attribute
  + changelog, or pin the version the emitted names are actually true for.
- `claudewire.py:175` — hooks-off path routes through `_strip_stale_hooks`, leaving
  `{"hooks": {}}` and the file behind; `_wire_hooks(root, False)` already implements
  the documented drop-and-remove — call it. Strengthen the two-way-switch test to
  assert file absence, not just `hook_status == 0`.
- `adoption.py:206` — a genuinely ambiguous shared-session receipt renders UNJOINED's
  "capture gap worth chasing" text — a false fact. Add an AMBIGUOUS reason with its
  own honest sentence.

## P3 — wiring hygiene

- `.gitattributes` — pin `cage/data/shims/graphify text eol=lf` (the POSIX twin); a
  Windows contributor with `autocrlf=true` otherwise ships a CRLF sh shim to every
  user, and the byte-identical test can't see it (compares against the same corrupted
  bytes).
- `kirowire.py:89–91` — the committed kiro L1 hook is POSIX-sh with no Windows twin
  and no named gap: twin it or name it in `HOOK_GAPS` + doctor (the graphify pair and
  the kiro-MCP Windows note are the precedents).
- `copilotwire.py:38` / `agents.py:65–68` — `sessionStart`/`sessionEnd` are cage's own
  invented names and `_session()` assumes Claude's `session_id` payload shape, while
  status output claims auto-close is wired. Until **L1-FIELD** verifies on a real
  install, the gaps text must say "unverified on a real Copilot" — the no-invented-
  event-names rule, applied to output honesty.
- `claudewire.py:116,189` · `copilotwire.py:57–58,83` — non-dict entries in a
  hand-edited hooks file raise `AttributeError` and crash `cage setup`; guard shapes,
  leave foreign-shaped files alone (copilotwire currently *deletes* a foreign file
  whose `hooks` value isn't a dict).
- `wiringscan.py:554` — `inventory()`'s `covered` set compares displays carrying
  " (L1 hooks)" suffixes against bare displays: every wired hook re-lists as a
  "leftover". Compare on a suffix-free key. Also `:199` — `committed_artifacts()`
  never enumerates `.github/hooks/cage.json` or the committed `.kiro/settings/mcp.json`,
  so the headline `wiring` check can't flag a dead verb in them; and `:313` — the
  cross-twin `interceptor_dead` flag paints a live, metering twin dead (and doctor
  claims "UNMETERED") when only the other OS's twin is stale.

## P4 — durable joins & scale

- **Full shas at write, prefix-match at read:** tasks (`rev-parse --short`),
  provenance, and attested hours join by exact short-sha equality — git's abbreviation
  auto-scales with object count, and the day it grows every historical join silently
  degrades (DANGLING_TASK / orphaned provenance / attestation falls to `~` estimate,
  breaking "an attestation always wins"). Store full shas (free at write), prefix-match
  with an **ambiguity refusal** — which also fixes `cage insights commit <prefix>`
  silently rendering the newest of several matches where git itself refuses.
  Related: **ID-ENTROPY** (same merge-by-identity family, already queued).
- `commitview.py:216–221` — no default window: one full-patch `git show` per commit
  over the whole history + `w not in wanted` over a list (O(n²)). Bounded default
  `--since` (footnoted, like every other cut) + `wanted` as a set.
- `authorcapture.py:105–107` — `_uncovered` judges coverage over **all** edits in a
  transcript including other repos', so a rarely-committed repo re-parses the whole
  machine's transcript corpus on every read, forever. Scope coverage to this repo's
  edits.
- `hookcmd.py:60–65,129` — session-end auto-close rides the throttled, switchable
  `ensure_captured`: any cage read in the last 60s (or `on_read=false`) and the
  session's final calls are missing when `_open_tasks` runs. A lifecycle hook calls
  the unthrottled `importcmd.run`.
- `linematch.py:213,269` — quoted paths (`core.quotePath`, non-ASCII) and rename
  syntax key the three maps differently → a landed `café.py` proposal scores DROPPED.
  `-c core.quotePath=false` + rename-key handling.
- `transcript.py:223–238` — Edit/MultiEdit context lines count as agent `suggested`
  (never reads `old_string`): inflates suggested/kept_modified and opens the
  false-agent-credit direction ADR 0008 calls impossible. Subtract
  `old_string ∩ new_string` normalized lines.
- `tools/cigraphify.py:807,739` — the determinism check never asserts exit 0 (a
  crashing report passes `"" == ""`), and the intercept check diffs rows by positional
  slice over sorted shards. Assert success + non-empty; diff by id-set
  (`graphifymeter._graphify_receipt_ids` exists).

## Trigger

None — these are defects and fragilities, filed as one program so they ship
deliberately rather than as drive-bys. Each phase is independently landable and picks
up under the standing lifecycle.
