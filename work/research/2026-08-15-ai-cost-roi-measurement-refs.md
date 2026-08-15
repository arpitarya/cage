# 2026-08-15 — How companies measure AI cost/benefit and ROI

**Take-away:** most enterprises still can't measure AI ROI with confidence (29% of
execs can, per IBM; 95% of GenAI pilots never reach measurable P&L impact, per MIT
Project NANDA). The frameworks that exist split into three layers — consultancy-level
ROI models (Deloitte's ROI Performance Index, BCG's 10-20-70 rule, Gartner TCO/ROI
toolkits, IBM hard/soft KPIs), FinOps unit-economics tracking underneath them (token as
billable unit, per-use-case attribution, moving toward per-outcome as agentic workloads
outgrow simple token counting), and — most relevant to cage — developer/coding-agent
ROI frameworks (DX Core 4, and a stricter framework built on cycle time, code turnover,
defect escape rate, and **token cost per merged PR** rather than raw token spend).

Not grounding a specific fork or proposal — filed as general industry reference,
requested standalone. Relevant to any future cage ROI/value-reporting design: the
"cost per outcome, not per token" shift (§3) and "token cost per merged PR" metric (§4)
are both direct analogs to what a `cage` cost rollup would need to expose to be useful
rather than just accurate.

Web research only — no local probe, no code run. Sourced 2026-08-15.

---

## 1 · The measurement gap (why this is hard)

- Only **29% of executives** say they can measure AI ROI with confidence, even though
  79% report productivity gains. — [IBM, How to maximize AI ROI in 2026](https://www.ibm.com/think/insights/ai-roi)
- **95% of enterprise GenAI pilots** fail to reach production or deliver measurable
  P&L impact; only ~5% of custom GenAI tools survive the pilot-to-production
  transition. — [MIT Project NANDA, "State of AI in Business 2025," via Forbes](https://www.forbes.com/sites/jasonsnyder/2025/08/26/mit-finds-95-of-genai-pilots-fail-because-companies-avoid-friction/),
  [Legal.io summary](https://www.legal.io/blog/5719519/MIT-Report-Finds-95-of-AI-Pilots-Fail-to-Deliver-ROI-Exposing-GenAI-Divide)
- **80%+ of enterprise AI initiatives** fail to deliver intended business value (RAND
  Corporation analysis); **77% of AI project failures are organizational**, not
  technical. — cited in [BCG 10-20-70 explainer](https://blog.exceeds.ai/10-20-70-rule-ai/)
- MIT's diagnosis: companies track **adoption** (logins, seat activation) instead of
  **workflow transformation** — *"count workflows redesigned, not logins."* Shadow
  AI use (unofficial personal tools) reportedly generates $2–10M/year in savings at
  some Fortune 500s, invisible to official ROI tracking. — [Forbes](https://www.forbes.com/sites/jasonsnyder/2025/08/26/mit-finds-95-of-genai-pilots-fail-because-companies-avoid-friction/)
- Deloitte names the core methodological blocker: isolating AI's share of a gain from
  concurrent process/tooling changes — *"we only managed to get a ballpark estimate...
  it was hard to separate the gains from AI initiatives from those of other
  initiatives."* — [Deloitte, AI ROI: the paradox of rising investment and elusive returns](https://www.deloitte.com/dk/en/issues/generative-ai/ai-roi-the-paradox-of-rising-investment-and-elusive-returns.html)

## 2 · Consultancy-level ROI frameworks

- **Deloitte — AI ROI Performance Index**: direct financial return + revenue growth
  + operational cost savings + speed-to-result. Typical payback **2–4 years** (vs.
  7–12 months expected for ordinary tech spend). Only 15% report significant
  measurable GenAI ROI today (38% expect it within a year); for agentic AI it's 10%,
  mostly on a 1–5 year horizon. **85% of "ROI leaders" use different frameworks/
  timeframes for generative vs. agentic AI** rather than one universal formula. —
  [Deloitte](https://www.deloitte.com/dk/en/issues/generative-ai/ai-roi-the-paradox-of-rising-investment-and-elusive-returns.html),
  [Deloitte State of GenAI in the Enterprise hub](https://www.deloitte.com/uk/en/issues/generative-ai/state-of-generative-ai-in-enterprise.html)
- **BCG — 10-20-70 rule**: AI value creation splits ~10% algorithms/model choice, 20%
  data/tech infrastructure, **70% people and process** (workflow redesign, change
  management, adoption coaching, the measurement system itself). Most companies invert
  this, spending 80–90% of budget on the 30% layer. — [BCG 10-20-70 explainer](https://blog.exceeds.ai/10-20-70-rule-ai/)
- **Gartner — TCO + ROI toolkits**: pushes past sticker price into the full cost stack
  (infrastructure/compute, integration, fine-tuning, monitoring, governance,
  change management) netted against quantified benefit categories. — [Gartner ROI/TCO toolkit](https://www.gartner.com/en/documents/1456125),
  [Gartner Enterprise Guide to Generative AI](https://www.gartner.com/en/topics/generative-ai)
- **IBM — hard vs. soft ROI KPIs**: hard = labor cost reduction, operational
  efficiency, new revenue from AI-powered products/faster dev cycles; soft = employee
  satisfaction/retention, decision speed/accuracy, customer satisfaction. Cited data:
  product teams on best practices report **median 55% ROI** on GenAI; holistic AI
  strategy → **22% higher ROI** on content-supply-chain use cases, **30% higher** on
  broader GenAI integration; technical-debt reduction improves AI ROI by up to **29%**.
  — [IBM](https://www.ibm.com/think/insights/ai-roi)

## 3 · FinOps / unit-economics layer (how spend actually gets metered)

- **FinOps Foundation methodology**: token as the fundamental billable unit — input
  (prompt) and output (generated) tokens tracked and priced separately. Three maturity
  tiers: request counting (crude) → token estimation → actual provider-supplied token
  counts (accurate baseline). For provisioned/reserved capacity, effective-rate formula
  factoring utilization: `Spend = PTU Rate × (2 − Utilization Rate) × Token Count`.
  Implementation is centralized (proxy tagged by use case) or decentralized (shared
  SDKs / IaC modules with enforced tagging) — either way, the goal is **attributing
  cost to a use case so its value can be evaluated against its spend**. — [FinOps.org, How to Build a Generative AI Cost and Usage Tracker](https://www.finops.org/wg/how-to-build-a-generative-ai-cost-and-usage-tracker/)
- 2026 coverage: FinOps practice is moving **"beyond token economics"** as agentic
  (multi-step, multi-call, tool-using) workflows make simple per-token accounting
  insufficient — cost needs attribution per *task*/*outcome*, not just per call. —
  [SiliconANGLE](https://siliconangle.com/2026/06/10/finops-ai-goes-beyond-token-economics-agentic-costs-emerge-finopsx/),
  [Computer Weekly](https://www.computerweekly.com/news/366641816/How-the-AI-boom-is-reshaping-tech-cost-management)

## 4 · Developer / coding-agent ROI (closest analog to cage)

- **DX Core 4** (blends DORA + SPACE + DevEx): Speed (cycle time), Effectiveness
  (diffs/tasks completed), Quality (bug rate, rollbacks, deploy failures), Impact
  (developer-reported satisfaction/time saved). Simple formula:
  `Monthly Hours Reclaimed = Weekly Hours Saved × #Engineers × 4`,
  `Value = Hours Reclaimed × Hourly Labor Cost`, `ROI = Value ÷ Tooling Cost`. Worked
  example: 80 engineers × 2.4 hrs/week saved × $78/hr → $59,900/month value against
  $1,520/month tooling spend ≈ **39x ROI**. — [getDX, AI coding tools ROI calculator](https://getdx.com/blog/ai-roi-calculator/)
- **Stricter engineering-leader framework**: warns naive metrics mislead — developers
  may complete 21% more tasks and merge 98% more PRs while DORA metrics (deploy
  frequency, lead time, change failure rate, MTTR) stay flat, because review time can
  rise 91% and eat the generation-speed gain. Recommended KPIs: **cycle time**
  (first commit → production, "the single most important delivery metric"), **code
  turnover ratio** (% AI-assisted code reverted/rewritten within 30 days; healthy <15%),
  **review time per PR**, **defect escape rate** (AI-co-authored code shown ~1.7x more
  issues, ~2.74x more security vulnerabilities in their data), **DORA metrics**,
  **developer time allocation** (generation vs. review/debugging), and **token cost
  per merged PR** — total AI spend divided by *shipped outcomes*, explicitly not raw
  token consumption. Misleading metrics named: lines of code (inflated 2–5x with no
  quality gain), commit count, raw PR volume, self-reported productivity (~39-point
  perception gap vs. reality), AI-suggestion acceptance rate (doesn't track code
  survival). Hidden costs flagged beyond subscription price: review overhead, code
  churn, wasted/re-sent context tokens (claimed 50–62% of some bills), "cognitive
  debt" from unreviewed AI code, security remediation, incident response. —
  [amux.io, How to Measure AI Coding Agent ROI](https://amux.io/guides/measuring-ai-coding-agent-roi/)

## 5 · Common pitfalls named across sources

- Confusing adoption (usage/logins) with value (workflow outcomes) — MIT's central
  finding.
- Failing to attribute AI's share of a gain vs. concurrent process/tooling change —
  Deloitte's finding.
- Applying one ROI framework to every AI investment instead of splitting by category
  (generative vs. agentic, or per-use-case) — Deloitte's 85%-of-leaders finding.
- Over-indexing budget/attention on the model/infrastructure layer (BCG: only ~30% of
  value) instead of the people/process layer driving the other ~70%.
- Tracking surface activity metrics (PR count, acceptance rate, LoC) that rise while
  real delivery metrics (cycle time, defect rate, DORA) stay flat or worsen.
- Undercounting hidden costs (review overhead, rework/churn, wasted context tokens,
  security remediation) that don't show up on the subscription invoice.

## Sources

- [IBM — How to maximize AI ROI in 2026](https://www.ibm.com/think/insights/ai-roi)
- [Deloitte — AI ROI: the paradox of rising investment and elusive returns](https://www.deloitte.com/dk/en/issues/generative-ai/ai-roi-the-paradox-of-rising-investment-and-elusive-returns.html)
- [Deloitte — State of Generative AI in the Enterprise (hub)](https://www.deloitte.com/uk/en/issues/generative-ai/state-of-generative-ai-in-enterprise.html)
- [Forbes — MIT finds 95% of GenAI pilots fail because companies avoid friction](https://www.forbes.com/sites/jasonsnyder/2025/08/26/mit-finds-95-of-genai-pilots-fail-because-companies-avoid-friction/)
- [Legal.io — summary of MIT Project NANDA "State of AI in Business 2025"](https://www.legal.io/blog/5719519/MIT-Report-Finds-95-of-AI-Pilots-Fail-to-Deliver-ROI-Exposing-GenAI-Divide)
- [BCG 10-20-70 rule — explainer](https://blog.exceeds.ai/10-20-70-rule-ai/)
- [Gartner — ROI and TCO Calculator toolkit](https://www.gartner.com/en/documents/1456125)
- [Gartner — Enterprise Guide to Generative AI](https://www.gartner.com/en/topics/generative-ai)
- [FinOps Foundation — How to Build a Generative AI Cost and Usage Tracker](https://www.finops.org/wg/how-to-build-a-generative-ai-cost-and-usage-tracker/)
- [SiliconANGLE — FinOps AI goes beyond token economics as agentic costs emerge](https://siliconangle.com/2026/06/10/finops-ai-goes-beyond-token-economics-agentic-costs-emerge-finopsx/)
- [Computer Weekly — How the AI boom is reshaping tech cost management](https://www.computerweekly.com/news/366641816/How-the-AI-boom-is-reshaping-tech-cost-management)
- [getDX — AI coding tools ROI calculator (DX Core 4)](https://getdx.com/blog/ai-roi-calculator/)
- [amux.io — How to Measure AI Coding Agent ROI: The Engineering Leader's Framework](https://amux.io/guides/measuring-ai-coding-agent-roi/)
- [NVIDIA — State of AI Report 2026](https://blogs.nvidia.com/blog/state-of-ai-report-2026/)
- [Forbes — AI ROI Measurement: New Metrics for 2026 (56% of CEOs see zero ROI)](https://www.forbes.com/sites/guneyyildiz/2026/01/28/56-of-ceos-see-zero-roi-from-ai-heres-what-the-12-who-profit-do-differently/)

## Why it was asked

Arpit asked, standalone, how companies are measuring AI cost/benefit and ROI —
general market research, not tied to a specific cage fork or proposal. Filed here per
house rule (research gets written up in the same session it's gathered) since the
"cost per outcome, not per token" and "token cost per merged PR" patterns above are
directly relevant precedent for any future cage ROI/value-reporting surface.
