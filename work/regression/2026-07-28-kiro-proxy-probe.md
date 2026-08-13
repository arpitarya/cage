# 2026-07-28 — Kiro proxy probe (P2): the last route to exact Kiro tokens — CLOSED

**Question (capture-precision item #11, specced, never executed):** the store probe
proved Kiro CLI's token fields are null. One route was never tried — the **proxy**,
putting cage *in the request path* to count tokens itself. Does it work?

**Answer: NO. Outcome B — definitive.** Kiro CLI cost is **credit-derived and
`estimated`, by vendor design.** This closes item #11 and the third Phase 1
question permanently. Do not retry.

## What was probed (no cage code changed)

- **Does `kiro-cli` honor a base-URL / proxy override?** Checked, not assumed:
  `kiro-cli --help-all`, `chat --help`, `settings list --all` (328 settings), env.
- **Two real probe turns** under `cage data meter -- kiro-cli chat --no-interactive …`
  (one floor `Reply with exactly: ok` · one large-input ~19k-char turn), in an
  **isolated** ledger (`CAGE_BASE=<scratch>/.cage`; real `~/.cage` never named).

## The four blocking reasons (each independently fatal)

| # | blocker | evidence |
|---|---|---|
| 1 | **No base-URL env cage can use.** `cage data meter` sets only `ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL` ([metercmd.py](../../cage/metercmd.py)). kiro-cli reads neither. | Its endpoints are `api.codewhisperer.service` / `api.q.service` / `api.krs.service` / `api.cps.service` — **AWS CodeWhisperer / Amazon Q**, unset = compiled AWS defaults. No generic proxy setting; no `--base-url`/`--endpoint`/`--proxy` chat flag. |
| 2 | **Wrong protocol even if redirected.** Those endpoints speak a SigV4-signed AWS CodeWhisperer/Q protocol, not Anthropic `/v1/messages` or OpenAI `/v1/chat/completions`. | `usageparse.extract` understands only Anthropic/OpenAI `usage` shapes. Pointing `api.codewhisperer.service` at cage's reverse-proxy would also break SigV4 (signed for the AWS host). |
| 3 | **cage's proxy can't MITM TLS.** [proxy.py](../../cage/proxy.py) is a **plaintext HTTP reverse proxy**, not a CONNECT-capable TLS-terminating forward proxy. | It cannot decrypt kiro-cli's HTTPS to AWS. (Weakening TLS to force it is explicitly out of bounds — not worth an exact number.) |
| 4 | **No tokens in the response anyway — the permanent limit.** The AWS gateway reports **credits + `context_usage_percentage`**, never token counts. | Same reason the SQLite store's token fields are null on every turn. Even a perfect intercept parses null tokens. |

## Empirical result

- Both probe turns **answered correctly** (0.04 + 0.06 credits, kiro replied `ok` and
  a correct one-sentence summary), with cage's proxy up (`127.0.0.1:PORT →
  https://api.anthropic.com`).
- cage recorded **0 call rows** — the isolated ledger dir stayed empty; `cage report`
  → *"No calls recorded yet."* kiro-cli sent its traffic straight to AWS; the proxy
  never saw a request. **The negative is measured, not argued.**

## The open question answered from the code (Outcome-A path, now moot)

- **Does a proxy-metered run need a `[sources]` entry, or does the proxy write
  receipts directly?** → **Directly.** [proxy.py](../../cage/proxy.py) `_meter` calls
  `metering.record_call(route="proxy", …)` — it writes the call row itself. `[sources]`
  is the *pull/import* path (reading agent log files); the proxy is the *push/in-path*
  meter and needs no `[sources]` entry. (This is also why "0 rows" is conclusive: had
  the proxy received any traffic, it would have written rows with no config needed.)

## Consequence (documented, final)

- **Recommended Kiro metering mode:** the SQLite credits parser
  ([transcript.parse_kiro_cli_credits](../../cage/transcript.py) →
  `credits-YYYY-MM.jsonl`, `schema.make_credit`, `method="estimated"`, recorded not
  priced). There is no `measured` path.
- **`method` law:** a proxy-*measured* Kiro number *could* be `measured` — but that
  path does not exist. Credit-derived is `estimated`, always; never blurred.
- Recorded in [FORMULAS.md §1.7](../../docs/FORMULAS.md). Field matrix (P5) inherits this line.

## Reproduction

```bash
kiro-cli settings list --all | grep -iE 'url|proxy|endpoint'   # api.codewhisperer/q/krs/cps only
CAGE_BASE=/tmp/kp/.cage cage data meter -- kiro-cli chat --no-interactive "Reply with exactly: ok"
CAGE_BASE=/tmp/kp/.cage cage report                            # → "No calls recorded yet."
```
