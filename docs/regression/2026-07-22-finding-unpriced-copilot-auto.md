# Finding — `copilot/auto` is UNPRICED (`unpriced-copilot-auto`)

**Severity:** MEDIUM · **Status:** ◻ OPEN — user-action item (route the router
pseudo-model); a default bundled alias is a proposal · **Surface:** copilot pricing

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) |

## Status now

OPEN. This is a user-action item, not a cage code defect — cage already surfaces it
loudly (`⚠ 24 calls … UNPRICED`). It resolves when the router pseudo-model is
routed to whatever `copilot/auto` actually resolves to. A *default* bundled alias
(with a loud "approximate — auto is a router" note) is a standing proposal.

## Evidence (as observed 2026-07-22)

24 of 60 copilot calls use model `copilot/auto` → 975,842 tokens billing **$0** —
40% of copilot's captured calls contribute no cost, so copilot's real spend is
understated. cage already flags it.

## Action

Route the router pseudo-model:

```
cage prices alias copilot/auto --to copilot/claude-sonnet-4.6   # or whatever auto resolves to
```

Consider shipping a *default* alias for `copilot/auto` in the bundled policy with a
loud "approximate — auto is a router" note, since every Copilot user hits this.

## History

**2026-07-22 (observed, lab-run-001):** 24/60 copilot calls UNPRICED via
`copilot/auto` (975,842 tokens, $0). Already surfaced by cage; no new logging
needed. Remains a user-action item as of this record.
