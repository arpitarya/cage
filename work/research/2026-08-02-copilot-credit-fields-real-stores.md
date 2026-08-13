---
doc: research — what the real Copilot stores actually record for billed credits
date: 2026-08-02
probed: VS Code 1.126 chatSessions (155 files) · Copilot CLI 1.0.65 events.jsonl (3 sessions) · ~/.cage real ledger
relates: copilot-vscode-token-sources.md (the desk study this verifies)
---

# Copilot credit fields, measured on real stores

**Takeaway:** `copilotCredits` is real, per-request, and fractional — the desk study
was right. But the *other* half of the plan was wrong: cage's existing `premium` field
is an **int**, and every real `totalPremiumRequests` value is a fraction below 1, so
copilot-CLI billing data has been silently floored to zero and dropped on every import
since the field shipped.

Probed while implementing COPILOT-CREDITS. Counts only — no prompt or response bodies
were read out of any store.

## 1 · VS Code chatSessions — `copilotCredits` confirmed

`~/Library/Application Support/Code/User/workspaceStorage/*/chatSessions/*.jsonl`,
155 files, 348 requests.

| fact | value |
|---|---|
| requests carrying `copilotCredits` | **11 / 348** (3.2%) |
| type | `float`, always |
| range | 0.100185 … 1.382565 |
| `modelId` on every one | `copilot/auto` |
| `sessionCopilotCredits` | **absent** in this VS Code version |

Three things follow, and all three are now encoded in the build:

- **It prices exactly the rows nothing else could.** Every credit-bearing request is
  `copilot/auto` — the router id that matches no price row by design. This is the
  UNPRICED hole closing with the vendor's own number.
- **Coverage is partial and is the store's doing, not the user's.** 3.2% here. Nothing
  a user configures changes it, which is why `cage doctor`'s credits line is advisory
  and never a warning.
- **Values are fractional to 6dp**, so capture rounds nothing and display (2dp) is
  kept strictly separate from the stored fact.

`sessionCopilotCredits` is deliberately not captured even where present: it is a
running session total, so summing it per request would multi-count.

## 2 · Copilot CLI — the finding: `premium` cannot hold its own value

`~/.copilot/session-state/<id>/events.jsonl`, `session.shutdown`, 3 sessions:

```
totalPremiumRequests: 0.33      ← float, in all three
totalNanoAiu:         2001650000 / 2493505000 / 844175000
```

Cage reads that key through `transcript._first_int`, which does `int(0.33) → 0`; then
`schema.make_call`'s `if premium:` drops the key entirely.

**Confirmed downstream on the real ledger** (`~/.cage`): 13 copilot-CLI call rows,
**not one carrying a `premium` field**. The billing signal the field exists to capture
has never survived a single import.

- This is a *silent* loss — no error, no warning, the row just looks like it had no
  premium requests. Same failure class as the F1 dead-verb finding: an absent signal
  and a broken capture path are indistinguishable from the outside.
- **Fixed by widening, not by repairing.** The build stamps the new float `credits`
  field from the same counter and leaves `premium` exactly as it was (legacy int
  contract, id scheme untouched). The pricing ladder reads `credits` on both copilot
  surfaces and never falls back to `premium`.
- `premium` therefore remains a field that is structurally wrong for its own source.
  It is now unused by pricing, but it is still written and still exported — carried
  forward as its own OPEN-WORK item rather than left implicit here.

## 3 · `totalNanoAiu` is present in the CLI store

The desk study placed nano-AIU only in the host-side session DB, whose path "is never
published to clients". It is in fact right there in `session.shutdown`.

This does **not** unblock nano-AIU pricing: the blocker was never access, it was that
GitHub publishes no nano-AIU → USD rate card, and inventing one would be invented
precision (proposal §6). Recording the correction so the next reader does not re-derive
the availability question — the trigger for that work is still *a published rate*.

## 4 · What the fixture corpus does and does not cover

`tests/fixtures/transcripts/copilot/cli/events.jsonl` carries an **integer**
`totalPremiumRequests: 2`, which is not the real-world shape. It was left alone (it is a
`format_verified` fixture and changing its value would move the `premium` column of the
exact-row corpus for reasons unrelated to this work); the fractional case is covered
directly in `tests/test_copilot_credits.py`, where the input is controlled precisely.

Worth revisiting if the corpus is ever re-captured from a live CLI.

## Sources

- Probes run 2026-08-02 against this machine's stores; commands are plain `json.loads`
  sweeps, reproducible from the paths above.
- Desk study this verifies: [copilot-vscode-token-sources.md](copilot-vscode-token-sources.md).
- Billing basis: [github.blog — usage-based billing](https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/) (retrieved 2026-07-11, cited in `data/prices.toml`).
