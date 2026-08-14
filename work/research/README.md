# work/research/ — dated research docs

**Evidence, never spec.** Each file is one investigation: an external-source probe, a
store/format survey, a competitive or ecosystem scan — anything whose output is
*findings* rather than a decision. Proposals, compare docs, plan entries and
`IMPLEMENTATION.md` **link here as their grounding**; where a doc here disagrees with the
living spec, the spec wins.

House rule (CLAUDE.md): a session that does research writes it up here **in that same
session**, with sources, paths and versions probed, so a future agent can re-verify.
Research is the sourced-findings twin of [`regression/`](../regression/), which holds
*measured* evidence from cage-lab runs.

| doc | probed | finding |
|---|---|---|
| [chat-title store probes](2026-08-14-chat-title-store-probes.md) | 2026-08-14 | copilot CLI **does** carry a chat name — in `workspace.yaml`, a sibling of the `events.jsonl` cage reads (24/32 sessions). kiro CLI carries **none**: no title field at any depth, `latest_summary` NULL on all 20 rows. P0.2 of the ledger restructure |
| [claude per-chat usage fetch spec](2026-08-13-claude-per-chat-usage-fetch-spec.md) | 2026-08-13 | what a per-chat usage read needs from the Claude Code store |
| [copilot per-chat usage fetch spec](2026-08-13-copilot-per-chat-usage-fetch-spec.md) | 2026-08-13 | the same question for Copilot's two stores |
| [kiro per-chat usage fetch spec](2026-08-13-kiro-per-chat-usage-fetch-spec.md) | 2026-08-13 | the same question for Kiro; the CLI's token slots are still NULL (upgrade-watch) |
| [graphify store evidence](2026-08-07-graphify-store-evidence.md) | 2026-08-07 | which stores can carry a graphify tool run — the basis for `graphifytx.GRAPHIFY_COVERAGE` |
| [OTel GenAI semconv pin](2026-08-03-otel-genai-semconv-pin.md) | 2026-08-03 | why the pin names a repo and a maturity rather than a version. The export it grounded was deleted in v0.50; the record stands |
| [copilot credit fields on real stores](2026-08-02-copilot-credit-fields-real-stores.md) | 2026-08-02 | `credits`/`session_credits`/`nano_aiu` as they actually appear |
| [copilot VS Code token sources](copilot-vscode-token-sources.md) | (first occupant) | where VS Code Copilot's token counts really live |

**Undated first occupant.** `copilot-vscode-token-sources.md` predates the naming
convention and is deliberately left as-is: renaming it would break the citations that
made it the rule's worked example.
