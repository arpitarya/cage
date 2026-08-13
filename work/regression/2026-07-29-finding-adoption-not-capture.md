# Finding — the graphify gap is ADOPTION, not capture (measured) — CURRENT STATUS

> **Status update (2026-08-01) — the finding doc owns its Status line, and this is it.**
>
> **Status: ◻ OPEN — CORROBORATED on a second surface and extended to kiro.**
> [Leg D](2026-08-01-leg-d-run-report.md) re-ran the same six questions in **VS Code /
> IDE** with graphify installed for all three agents: **claude invoked graphify
> unprompted (2 queries, 18,456 tokens saved, `route: transcript`); copilot and kiro did
> not invoke it at all** (0 usage rows each). The 2026-07-29 conclusion — *the gap is
> adoption, not capture* — holds on the extension surface, and now covers **three**
> agents rather than two. Severity is unchanged: product/behavioural, not a cage defect.
>
> _Body-only update: this header sits **above** the `HASH-COVERS-BELOW` marker. The text
> below is byte-identical to what was published on 2026-07-29 — including its original
> `Status:` line, which is the status **as of that date**, not the current one. The
> current status is the one in this header._

**Finding sha256 (body below the marker = the whole file as originally published):**
`309efd465fdf36452333f77a7719ac08cd74222cd01e3c8209b921a9cd860353`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
# Finding — the graphify gap is ADOPTION, not capture (measured)

**Severity:** — (product/behavioral, not a cage defect) · **Status:** ◻ OPEN ·
**Surface:** graphify savings capture across agents · **From:** 2026-07-29 run report.

## What was measured
A clean-room A/B (70 real prompts, graphify the only variable) split the graphify-ON arm
into **adoption** (plain question) vs **capture** (explicitly invoked):

| cell | graphify receipts |
|---|---|
| copilot ON, plain question | **0** — never reached for graphify |
| copilot ON, explicitly invoked | **23** — cage caught every run |
| claude ON, plain (hook + CLAUDE.md) | **1** — auto-adopted once |
| every OFF arm | 0 (correct) |

## Conclusion
- **Capture works.** When graphify actually runs, cage files a receipt for it — 24/24,
  all via the transcript route, `modeled`, conf 0.6. The **F1 copilot-CLI detector built
  this session accounts for 23 of the 24** — validated on real traffic, not a fixture.
- **The gap is adoption.** copilot's graphify-ON is a **passive user-level `/graphify`
  skill** (installed to `~/.copilot/skills/`), never auto-injected — so a plain question
  yields 0. claude's PreToolUse hook + CLAUDE.md drive weak auto-adoption (1/14 here).
- This directly answers the C/G1 question the whole cycle chased: "0 real receipts across
  36,451 calls" was **not** a capture bug — it is agents not invoking graphify unprompted.

## Product implications (filed, not built)
- If graphify savings matter for an agent, its ON steering must be **active** (claude's
  hook model), not a passive skill (copilot's). A copilot equivalent of claude's PreToolUse
  reminder would move adoption; that is a graphify wiring change, not a cage one.
- cage's job — *see the saving when it happens* — is met on both scriptable CLIs.
