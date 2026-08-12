# MACHINE — probed facts about this machine

**Why this file exists (2026-08-12):** a session told Arpit nine queue items needed
hardware he did not have. **Copilot and Kiro were installed the whole time** — the
session asserted an impossibility without probing for it, and hours were spent on the
wrong premise (WORKLOG 2026-08-12, *"the premise I got wrong"*; the same failure
OTEL-SEMCONV-PIN recorded a week earlier). The rule this file enforces: **probe
first, then claim.** Any statement of the form *"item X needs hardware/tooling that
isn't here"* must cite a dated row below. If the row is missing, the probe is the
next action — never the assumption.

Every row is a probed observation with a date and the evidence. A row older than
~30 days is a re-probe prompt, not a fact. Update this file in the same change as
the probe (DOC-REGISTRY row bumps with it).

| fact | value | probed | evidence |
|---|---|---|---|
| Claude Code installed + hooks field-verified | yes | 2026-08-02 | L1-FIELD claude leg, verified with evidence (WORKLOG) |
| GitHub Copilot installed | yes | 2026-08-12 | probed during the GF-LAUNCHER build (WORKLOG, *"the premise I got wrong"*) |
| Kiro installed | yes | 2026-08-12 | probed during the GF-LAUNCHER build (WORKLOG, *"the premise I got wrong"*) |
| copilot + kiro hooks fire (L1) | unverified | 2026-08-12 | L1-FIELD still open — `--status` claims yes, not field-verified |

The consequence worth stating: with Kiro installed, **KIRO-MCP-FIELD's five-minute
binary check is runnable on this machine today** — what the hands-only tier still
needs is Arpit driving the real editors, not different hardware.
