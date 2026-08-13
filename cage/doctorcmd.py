"""`cage doctor` — verify a project's Cage setup is correct and working.

A deterministic, $0 health check any agent (claude / copilot / kiro) can run
to confirm Cage is installed and wired before trusting its numbers. Each check returns
(level, detail): level is "ok" | "warn" | "fail". The overall status is the worst level
(fail > warn > ok); the CLI exits non-zero on any fail so scripts/agents can gate on it.

No network, no LLM. The ledger round-trip writes to a throwaway temp dir, never the
project ledger, so running the doctor records nothing.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import datetime as _dt

from cage import (agents, debuglog, importcmd, ledger, paths, policy, prices, render,
                  schema, wiringscan)

_OK, _WARN, _FAIL = "ok", "warn", "fail"
_RANK = {_OK: 0, _WARN: 1, _FAIL: 2}


def _tool() -> tuple[str, str]:
    from cage import __version__
    if paths.distribution() == "zipapp":
        # A pyz has no `cage` on PATH by design — pull-based capture is the story
        # (docs/restricted-environments.md); a PATH warn here would always fire.
        return _OK, (f"cage {__version__} (zipapp) — pull-based capture "
                     "(`import`/`export`/`report`); hooks need an importable install")
    if not shutil.which("cage"):
        return _WARN, "`cage` not on PATH (running, but not globally callable)"
    return _OK, f"cage {__version__} on PATH"


def _footprint(active: Path, source: str) -> tuple[str, str]:
    """The active ledger sink, per the capture precedence (plan §3.7). Names *which* sink
    is live (project vs global vs --ledger override) so a user with both a project `.cage/`
    and a global `~/.cage` knows where capture lands — one sink per run, never both."""
    base = paths.Footprint(active).base
    if not base.is_dir():
        return _FAIL, ("no ledger yet — `cage setup` for this project, or "
                       "`cage setup --global` for project-less capture into ~/.cage")
    return _OK, f"active ledger: {source} → {base}"


def _policy(root: Path) -> tuple[str, str]:
    foot = paths.Footprint(root)
    active = foot.policy
    try:
        pol = policy.load(active)
    except Exception as exc:  # noqa: BLE001 — surface the parse error, don't raise
        return _FAIL, f"{active.name} failed to load: {exc}"
    name = active.name if active.exists() else "no project config (bundled defaults apply)"
    n_prices = sum(len(r) for r in pol.get("prices", {}).values() if isinstance(r, dict))
    prices_name = foot.prices.name if foot.prices.exists() else "bundled default"
    prices_note = f"prices from {prices_name} ({n_prices} rows)"
    shadowed = foot.shadowed_config
    shadowed_prices = foot.shadowed_prices
    if shadowed is not None:
        return _WARN, (f"config: {name} loads, {prices_note} "
                       f"— but a legacy {shadowed.name} sits beside it and is ignored; "
                       f"delete it (cage.toml wins)")
    if shadowed_prices is not None:
        return _WARN, (f"config: {name} loads, {prices_note} — but a legacy "
                       f"[prices]/[credits] block in {shadowed_prices.name} is ignored "
                       f"({paths.PRICES_FILENAME} wins); remove those tables")
    return _OK, f"config: {name} loads, {prices_note}"


def _metering(active: Path) -> tuple[str, str]:
    """Honest three-agent capture matrix (plan §3.7). Capture is **pull-based and the
    only path**: explicit `cage import` / `cage data export` (and the optional foreground
    `cage data watch`) capture every surface in ``agents.SURFACES``, client-independent —
    no hooks, so nothing depends on which client wrote the log. MCP is the wired *read*
    surface; whether it's installed says nothing about whether capture ran. Surfaces the
    **last import: N ago** staleness signal."""
    wired = agents.status(active)
    rows = []
    for a in agents.SURFACES:
        state = "MCP read wired" if wired.get(a, False) else "MCP read not wired"
        rows.append(f"\n      · {a:<8} {state:<48} | capture: cage import --agent {a}")
    li = importcmd.last_import(active)
    rel = render.ago(li) if li else ""
    foot = (f"\n      last import: {rel}" if rel
            else "\n      last import: never — run `cage import` (or `cage data watch`)")
    foot += (f"\n      (automate with your own scheduler line, e.g. `{render.scheduler_hint()}`; "
             "cage installs no scheduler.)")
    # Capture health (docs/capture-health): the triple-gated "installed but capturing
    # nothing" verdict — the same one `cage report` surfaces, defined once in
    # report.capture_warnings. Fresh install (never imported ⇒ no `_health`) says so and
    # does no live probe (a read-only doctor, like the rest of this check).
    from cage import report
    health = importcmd.capture_health(active)
    warns = report.capture_warnings(health)
    if not health:
        # Under capture-on-read every read sweeps before it renders, so an empty
        # `_health` no longer means "you haven't run `cage import`" — it means capture
        # never ran: disabled (`[capture] enabled=false` / `CAGE_CAPTURE=0`) or a swept
        # source errored. Doctor itself deliberately does NOT sweep (it diagnoses capture,
        # so masking the state it reports would defeat the check — capture-architecture
        # §8/§10), hence this stays a read of recorded facts.
        from cage import policy as _pol
        if not _pol.capture_enabled(policy.load(paths.Footprint(active).policy)):
            foot += ("\n      capture health: capture disabled ([capture] enabled=false "
                     "or CAGE_CAPTURE=0) — no sweep runs; `cage report` shows only what's "
                     "already captured")
        else:
            foot += ("\n      capture health: nothing captured yet — run a read "
                     "(`cage report`) or `cage import`; if it stays empty, `CAGE_DEBUG=1 "
                     "cage import` then `cage debug` for the reason")
        level = _OK
    elif warns:
        foot += "".join(f"\n      {w}" for w in warns)
        level = _WARN
    else:
        foot += "\n      capture health: every installed agent is capturing"
        level = _OK
    head = ("capture is pull-based — `cage import`/`cage data export` is the only path "
            "(no hooks); MCP is the wired read surface:")
    return level, head + "".join(rows) + foot


def _capture_timeline(active: Path) -> tuple[str, str]:
    """Per-source, per-**mode** (pull/push) last-seen + counts (capture-architecture
    §12.4) — the one place that answers "what has cage captured, how, and when" across
    the whole pull+push model, symmetric for every agent.

    Built **read-only** from the ledger it already holds — doctor deliberately does NOT
    sweep first (a sweep would mask the very breakage this diagnoses, §8/§10), so the
    timeline reflects the state as-is. **pull** rows are calls the import sweep landed
    (grouped to a surface); **push** rows are receipts a live meter filed (graphify/fux via
    `record_receipt`). Uses `render.ago` (wall clock) — doctor is a diagnostic, never a
    derived-from-ledger view, so determinism holds. Informational (never fails)."""
    try:
        calls = ledger.calls(active)
        receipts = ledger.receipts(active)
    except Exception as exc:  # noqa: BLE001 — a broken ledger is reported elsewhere
        return _OK, f"capture timeline unavailable ({exc})"
    pull_n: dict[str, int] = {a: 0 for a in agents.SURFACES}
    pull_ts: dict[str, str] = {a: "" for a in agents.SURFACES}
    for c in calls:
        a = agents.row_surface(c.get("agent"))
        if a in pull_n:
            pull_n[a] += 1
            ts = c.get("ts", "")
            if ts > pull_ts[a]:
                pull_ts[a] = ts
    push_n: dict[str, int] = {}
    push_ts: dict[str, str] = {}
    for r in receipts:
        if r.get("tool") == "human":
            continue  # a legacy Tier-1 row (axis removed v0.36), not a capture mode
        tool = r.get("tool") or "?"
        push_n[tool] = push_n.get(tool, 0) + 1
        ts = r.get("ts", "")
        if ts > push_ts.get(tool, ""):
            push_ts[tool] = ts
    # ADR 0006: kiro's IDE rows route to the machine ledger, so on a project ledger its
    # row here is legitimately empty. Naming the sink is the difference between "kiro
    # captures elsewhere" and "kiro capture is broken" — which is the whole job of this
    # check. Cheap and read-only: a path resolution, never a second ledger read.
    kiro_sink = paths.kiro_routed(active)
    rows = []
    for a in agents.SURFACES:
        seen = render.ago(pull_ts[a]) if pull_ts[a] else "never"
        cnt = f"{pull_n[a]:,} rows" if pull_n[a] else "—"
        if a == "kiro" and kiro_sink is not None:
            rows.append(f"\n      · {a:<9} pull   {'→ ' + str(paths.Footprint(kiro_sink).base)}"
                        f"\n        (IDE rows are a machine fact — ADR 0006; "
                        f"`cage query kiro-routing`)")
            continue
        rows.append(f"\n      · {a:<9} pull   {seen:<10} {cnt}")
    for tool in ("graphify", "fux", *sorted(t for t in push_n if t not in ("graphify", "fux"))):
        seen = render.ago(push_ts.get(tool, "")) if push_ts.get(tool) else "never"
        cnt = f"{push_n.get(tool, 0):,} receipts" if push_n.get(tool) else "—"
        rows.append(f"\n      · {tool:<9} push   {seen:<10} {cnt}")
    return _OK, ("capture timeline (last seen · this ledger; doctor does not sweep):"
                 + "".join(rows))


def _capture_quality(root: Path) -> tuple[str, str]:
    """Distinguishes a log-bearing agent that IS capturing rows from one whose
    capture is present but nearly worthless — ``tokens_out == 0`` across every
    recorded call (F3, work/regression/2026-07-22-capture-report.md). Kiro's
    on-disk log is coarse *by design* (module docstring, cage/transcript.py:
    "output tokens often 0") and hits this in real use; the same signal is worth
    surfacing for any agent, so the check is agent-agnostic in mechanism.

    Deliberately **separate** from ``_metering``'s "installed but capturing
    nothing" gate (``capture_warnings``, files==0). That gate stays silent for a
    present-but-thin kiro log on purpose
    (``test_kiro_present_but_empty_is_silent_not_broken``) — a coarse log is
    normal, not broken. This check only fires once real rows exist and are
    *still* nearly worthless, which is a different, narrower signal: not "capture
    is off" but "capture is on and this is the ceiling — use the proxy."

    Read-only from the ledger, like ``_capture_timeline`` (doctor never sweeps —
    §8/§10); informational, never fails doctor outright."""
    try:
        calls = ledger.calls(root)
    except Exception:  # noqa: BLE001 — a broken ledger is reported by other checks
        return _OK, "capture quality unavailable (ledger read failed)"
    per_agent: dict[str, dict] = {}
    for c in calls:
        a = agents.row_surface(c.get("agent"))
        if a not in agents.SURFACES:
            continue
        g = per_agent.setdefault(a, {"calls": 0, "tokens_in": 0, "tokens_out": 0})
        g["calls"] += 1
        g["tokens_in"] += c.get("tokens_in", 0)
        g["tokens_out"] += c.get("tokens_out", 0)
    thin = [(a, g) for a, g in per_agent.items() if g["calls"] and g["tokens_out"] == 0]
    if not thin:
        return _OK, "every capturing agent's log carries real output-token data"
    lines = []
    for a, g in sorted(thin):
        lines.append(f"\n      · {a}: {g['calls']:,} call(s), {g['tokens_in']:,} input "
                     f"token(s), 0 output — coarse/input-only capture. Higher-fidelity: "
                     f"cage data meter -- <{a} cmd>  (see `cage data proxy`)")
    return _WARN, ("capture is present but token-thin (input-only log, by design "
                   "for some agents):" + "".join(lines))


def _pricing(root: Path) -> tuple[str, str]:
    """Scan recorded calls for models that bill $0 with no exact *or* family price
    row — the silent-$0 sharp edge. A wrong $0 must read as UNPRICED here, not hide."""
    try:
        pol = policy.load(paths.Footprint(root).policy)
        calls = ledger.calls(root)
    except Exception:  # noqa: BLE001 — a broken policy/ledger is reported by other checks
        return _OK, "no priced ledger to check yet"
    from cage import receiptprice
    dangling = receiptprice.dangling_routes(pol)
    if dangling:  # a broken explicit route needs no calls to be wrong (plan §4.5)
        broken = ", ".join(f"[tools.{t}] price_at = {v!r}" for t, v in dangling.items())
        return _WARN, ("dangling tool route(s) — no price row resolves, the tool's "
                       f"receipts stay UNPRICED: {broken}")
    if not calls:
        return _OK, "no calls recorded yet — nothing to price-check"
    unpriced, family = set(), set()
    for c in calls:
        _, match, _ = prices.call_usd_match(pol, c)
        tag = f"{c.get('provider') or '—'}/{c.get('model') or '—'}"
        if match == "none":
            unpriced.add(tag)
        elif match == "family":
            family.add(tag)
    if unpriced:
        return _WARN, ("UNPRICED models billing $0 (run `cage prices unpriced` for "
                       "ready-to-run fix lines): " + ", ".join(sorted(unpriced)))
    if family:
        return _OK, "all models priced (some by family approx): " + ", ".join(sorted(family))
    return _OK, "all recorded models have an exact price row"


def _credits(root: Path) -> tuple[str, str]:
    """Billed-credit coverage: how many recorded rows carry the provider's own credit
    figure, and whether a rate exists to price them (COPILOT-CREDITS rung 1).

    **Advisory only — this check never fails, and never warns.** Credit coverage is a
    property of the *store*, not of the user's setup: VS Code persists `copilotCredits`
    on some requests and not others, and no action on this machine changes that. Calling
    partial coverage a fault would be blaming someone for a vendor's logging, and would
    train readers to ignore a red line they cannot clear. What it does buy is the answer
    to "why is some copilot spend priced differently from the rest", visible before
    anyone asks — plus the one actionable case (credits recorded, rate unset), stated as
    an `ok` with a runnable fix rather than an alarm."""
    from cage import creditprice
    try:
        pol = policy.load(paths.Footprint(root).policy)
        calls = ledger.calls(root)
    except Exception:  # noqa: BLE001 — a broken policy/ledger is reported by other checks
        return _OK, "no ledger to check yet"
    withc = [c for c in calls if creditprice.recorded(c) is not None]
    if not withc:
        return _OK, "no billed credits recorded — every row prices by token × table"
    agents_ = sorted({c.get("agent") or "?" for c in withc})
    surfaces = sorted({c.get("surface") or "?" for c in withc})
    where = f"{'/'.join(agents_)} credits on {len(withc)}/{len(calls)} rows ({', '.join(surfaces)})"
    unrated = [c for c in withc if creditprice.unrated(pol, c)]
    if unrated:
        return _OK, (f"{where}; no rate set — shown as counts, priced by token × table. "
                     + creditprice.rate_hint(creditprice.agents_needing_rate(unrated)))
    rates = sorted({policy.credit_rate(pol, a) for a in agents_} - {None})
    shown = ", ".join(f"${r:g}/cr" for r in rates)
    return _OK, f"{where}; rate set ({shown}) — those rows price by credits × rate"


# The VS Code setting that turns on each of the three opt-in Copilot-metrics stores
# (COPILOT-METRICS handoff §4.6) — named here so an absent gated source tells the user
# exactly how to enable it, the same "state, not a fault" discipline `_credits` uses.
_COPILOT_METRIC_GATES = {
    "sidecar": "chat.agentHost.agentDebugLog.enabled",
    "debuglog": "github.copilot.chat.agentDebugLog.fileLogging.enabled",
    "otel": "github.copilot.chat.otel.dbSpanExporter.enabled",
}


def _copilot_metrics(active: Path) -> tuple[str, str]:
    """Per-source Copilot-metrics coverage: which of the five on-disk stores
    (COPILOT-METRICS handoff §4.1/§4.4) has landed a row in `.cage/ledger/copilot/`, and
    — for the three opt-in stores — the VS Code setting that turns it on when absent.

    **Advisory only — the `_credits` precedent.** Absence of an opt-in store's rows is a
    state (the setting is off, or nothing has been captured since it was turned on), not
    a fault of this installation, so this check never warns or fails. Reads the ledger
    directly (like `_credits`), not an on-disk file probe — it answers "what has cage
    actually captured", the same question every other doctor line here answers."""
    try:
        rows = ledger.copilot_metrics_raw(active)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"copilot-metrics check skipped: {exc}"
    counts: dict[str, int] = {}
    for r in rows:
        s = r.get("source", "?")
        counts[s] = counts.get(s, 0) + 1
    lines = []
    for s in schema.COPILOT_METRIC_SOURCES:
        n = counts.get(s, 0)
        if n:
            lines.append(f"{s}: {n} row(s)")
        elif s in _COPILOT_METRIC_GATES:
            lines.append(f"{s}: none yet — enable `{_COPILOT_METRIC_GATES[s]}`")
        else:
            lines.append(f"{s}: none yet")
    return _OK, "copilot-metrics (.cage/ledger/copilot/): " + "; ".join(lines)


def _kiro_metrics(active: Path) -> tuple[str, str]:
    """Per-source Kiro-metrics coverage: which of the three grains (KIRO-METRICS
    handoff §4.1/§4.4) has landed a row in `.cage/ledger/kiro/`, plus the
    **upgrade-watch**: has kiro-cli started filling the `cli-turn` token slots that are
    NULL on every real store probed so far?

    **Advisory only — the `_copilot_metrics` precedent.** Absence of a grain's rows is
    a state (kiro not installed, or no usage since last import), not a fault, so this
    check never warns or fails. Reads the ledger directly, not an on-disk file probe —
    "what has cage actually captured", the same question `_copilot_metrics` answers."""
    try:
        rows = ledger.kiro_metrics_raw(active)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"kiro-metrics check skipped: {exc}"
    counts: dict[str, int] = {}
    turn_upgraded = False
    for r in rows:
        s = r.get("source", "?")
        counts[s] = counts.get(s, 0) + 1
        if s == "cli-turn" and (r.get("tokens_in") or r.get("tokens_out")
                                or r.get("cached_in") or r.get("cached_out")):
            turn_upgraded = True
    lines = []
    for s in schema.KIRO_METRIC_SOURCES:
        n = counts.get(s, 0)
        if s == "ide":
            lines.append(f"ide: {n} row(s)" if n
                         else "ide: none yet — run the research §6 schema probe if "
                              "Kiro IDE is in use")
        elif s == "cli-turn":
            if not n:
                lines.append("cli-turn: none yet")
            elif turn_upgraded:
                lines.append(f"cli-turn: {n} row(s) — non-NULL token slots detected, "
                             "per-turn kiro tokens are now exact")
            else:
                lines.append(f"cli-turn: {n} row(s), token slots NULL — "
                             "upgrade-watch armed")
        else:
            lines.append(f"{s}: {n} row(s)" if n else f"{s}: none yet")
    return _OK, "kiro-metrics (.cage/ledger/kiro/): " + "; ".join(lines)


# Claude Code's own default sweep is 30 days (`cleanupPeriodDays`); nudging 5 days
# early gives an import cadence a real chance to beat it (CLAUDE-METRICS handoff §4.6).
_CLAUDE_RETENTION_NUDGE_DAYS = 25


def _claude_metrics(active: Path) -> tuple[str, str]:
    """Claude-metrics coverage (CLAUDE-METRICS handoff §4.6): raw vs collapsed chat
    counts in `.cage/ledger/claude/`, plus a retention nudge — Claude Code auto-deletes
    transcripts after ~30 days by default (`cleanupPeriodDays`), so a store whose newest
    transcript is already >25 days old is close to losing history capture never reached.

    **Advisory only — the `_copilot_metrics`/`_kiro_metrics` precedent**: an absent
    store or store dir is a state (never imported yet, or Claude Code not in use), not
    a fault. The retention nudge is the one path this check ever warns on — a real,
    time-bound risk of losing data, unlike the vendor-optionality the copilot/kiro
    checks report. Reads the ledger directly for counts (like `_credits`); the mtime
    probe is a best-effort read of the real transcript store and never a diagnostic
    gate — any failure there is swallowed, never surfaced as a warn/fail."""
    try:
        raw = ledger.claude_metrics_raw(active)
        collapsed = ledger.claude_metrics(active)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"claude-metrics check skipped: {exc}"
    if not raw:
        return _OK, ("claude-metrics (.cage/ledger/claude/): none yet — "
                     "run `cage import --agent claude`")
    detail = (f"claude-metrics (.cage/ledger/claude/): {len(raw)} raw row(s), "
             f"{len(collapsed)} chat(s)")
    try:
        pol = policy.load(paths.Footprint(active).policy)
        newest = None
        for src in paths.agent_log_sources("claude", pol):
            for f in importcmd.glob_source(src.path, src.glob):
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                if newest is None or mtime > newest:
                    newest = mtime
        if newest is not None:
            age_days = (_dt.datetime.now(_dt.timezone.utc)
                       - _dt.datetime.fromtimestamp(newest, _dt.timezone.utc)).days
            if age_days > _CLAUDE_RETENTION_NUDGE_DAYS:
                return _WARN, (detail + f" — newest transcript is {age_days}d old; "
                              "Claude Code deletes transcripts after ~30 days by "
                              "default (`cleanupPeriodDays`) — import regularly")
    except Exception:  # noqa: BLE001 — the nudge is best-effort, never a doctor gate
        pass
    return _OK, detail


def _bundled_prices(root: Path) -> tuple[str, str]:
    """Compare the project policy's [meta] against the installed bundle's — a newer
    bundle means researched price rows this project isn't using yet. Recommendation
    only, never auto-applied (`cage prices sync` is the user's move)."""
    try:
        from cage import pricescmd
        foot = paths.Footprint(root)
        # prices_version lives in the prices file after the split (prices-toml plan §2.1):
        # read it there, not the policy file, or a migrated project reads as pre-0.19.
        if not foot.prices.exists():
            return _OK, "no project config — the installed bundle's prices apply directly"
        project = policy.load_project_raw(foot.prices)
    except Exception:  # noqa: BLE001 — a broken prices file is reported by the policy check
        return _OK, "project prices unreadable — see the policy check"
    bundled_v = str(policy.bundled_raw().get("meta", {}).get("prices_version") or "?")
    rec = pricescmd.sync_recommendation(project.get("meta", {}))
    if rec:
        return _WARN, rec
    return _OK, f"project prices are current with the bundle ({bundled_v})"


def _policy_version(root: Path) -> tuple[str, str]:
    """The non-price sibling of `_bundled_prices` (plan §3.10): a newer bundled
    ``policy_version`` means tunables/defaults this project hasn't discovered.
    Recommendation only, never auto-applied (`cage policy sync` is the user's
    move; pure price drift keeps the `cage prices sync` hint above)."""
    try:
        from cage import policysync
        if not paths.Footprint(root).policy.exists():
            return _OK, "no project config — the bundled defaults apply directly"
        project = policy.load_project_raw(paths.Footprint(root).policy)
    except Exception:  # noqa: BLE001 — a broken policy is reported by the policy check
        return _OK, "project policy unreadable — see the policy check"
    bundled_v = str(policy.bundled_raw().get("meta", {}).get("policy_version") or "?")
    rec = policysync.sync_recommendation(project.get("meta", {}))
    if rec:
        return _WARN, rec
    return _OK, f"project policy defaults are current with the bundle (v{bundled_v})"


def _prices_age(root: Path) -> tuple[str, str]:
    """The bundle's *own* age (plan §3.3) — a project faithfully synced to a
    6-month-old bundle is confidently stale. Doctor is a diagnostic, not a derived
    view, so wall-clock today is the right anchor here (and the handoff wants the
    age visible even on an empty ledger); the report footer stays data-relative.
    One wording, one home: `freshness.age_line`."""
    import datetime as _dt

    from cage import freshness
    try:
        pol = policy.load(paths.Footprint(root).policy)
    except Exception:  # noqa: BLE001 — a broken policy is reported by the policy check
        return _OK, "project policy unreadable — see the policy check"
    sd = policy.prices_stale_days(pol)
    if sd <= 0:
        return _OK, "age check disabled ([prices] stale_days = 0)"
    line = freshness.age_line(pol, _dt.date.today())
    if line:
        return _WARN, line
    meta = policy.bundled_raw().get("meta", {})
    stamped = freshness._parse_date(meta.get("prices_date") or meta.get("prices_version"))
    if stamped is None:
        return _OK, "bundled [meta] carries no parseable prices_date — nothing to age"
    n = (_dt.date.today() - stamped).days
    return _OK, f"bundled prices are {n} days old (stale after {sd})"


def _state_dir(root: Path) -> tuple[str, str]:
    """State-dir size + prune-candidate visibility (bloat should be visible before
    it's a problem). Informational — `cage data cleanup` is the remedy."""
    foot = paths.Footprint(root)
    if not foot.state.exists():
        return _OK, "no state dir yet"
    try:
        from cage import cleanup
        pol = policy.load(foot.policy)
        files = [p for p in foot.state.iterdir() if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        stale = cleanup.scan(root, pol)
        status = (f"state/: {len(files)} file(s), {size / 1024:.0f} KB · cleanup "
                  f"{'on' if policy.cleanup_enabled(pol) else 'OFF'} "
                  f"({policy.cleanup_days(pol)}d)")
        if stale:
            return _OK, status + (f" · {len(stale)} prune candidate(s) — "
                                  "`cage data cleanup` to review")
        return _OK, status + " · nothing stale"
    except Exception as exc:  # noqa: BLE001 — informational check, never blocks doctor
        return _OK, f"state dir present (scan skipped: {exc})"


def _committed_commands(root: Path) -> list[tuple[str, str]]:
    """(file, command-string) pairs from every *project-committed* wired file. The
    user-level configs (~/.copilot/hooks, .git/hooks) are per-machine by nature and
    deliberately not scanned."""
    from cage import cfgio
    out: list[tuple[str, str]] = []

    def hooks_cmds(rel: str) -> None:
        for entries in cfgio.load_json(root / rel).get("hooks", {}).values():
            for e in entries:
                for h in e.get("hooks", []):
                    out.append((rel, h.get("command", "")))

    hooks_cmds(".claude/settings.json")
    for name, srv in cfgio.load_json(root / ".mcp.json").get("mcpServers", {}).items():
        if name == "cage":
            out.append((".mcp.json", srv.get("command", "")))
    for name, srv in cfgio.load_json(root / ".vscode" / "mcp.json").get("servers", {}).items():
        if name == "cage":
            out.append((".vscode/mcp.json", srv.get("command", "")))
    for hook in sorted((root / ".kiro" / "hooks").glob("*.kiro.hook")):
        cmd = cfgio.load_json(hook).get("then", {}).get("command", "")
        out.append((f".kiro/hooks/{hook.name}", cmd))
    return out


def _is_machine_absolute_cage(command: str) -> bool:
    """A cage command whose executable is a machine-absolute path — the sharing bug
    (plan §5): committed, it ships one dev's filesystem layout to the whole team."""
    bin0, _ = paths._split_bin(command)
    if not bin0:
        return False
    name = bin0.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name not in ("cage", "cage.exe"):
        return False
    import re as _re
    return bin0.startswith(("/", "~")) or bool(_re.match(r"[A-Za-z]:[\\/]", bin0))


def _portability(root: Path) -> tuple[str, str]:
    """No committed wired file may carry a machine-absolute cage path — teammates'
    clones get broken wiring. Also verifies the committed shim exists, kept its
    execute bit, and actually resolves cage on THIS machine.

    **There is no exception left.** `.kiro/settings/mcp.json` was one — Kiro spawns MCP
    servers from its install dir with no workspace variable, so neither the shim nor a
    variable works there — until it went **path-free** (`python3 -m cage mcp`,
    `kirowire.py`), which carries no path at all. A kiro entry still holding an absolute
    path is now a *finding with a fix*, not standing advice. What that form costs is
    checked separately, by `_kiro_mcp`."""
    from cage import cfgio, runshim
    cmds = _committed_commands(root)
    shim = runshim.shim_path(root)
    wired = bool(cmds)
    if not wired and not shim.exists():
        return _OK, "no committed wiring yet — nothing to check"

    problems: list[str] = []
    stale = sorted({f for f, c in cmds if _is_machine_absolute_cage(c)})
    if stale:
        problems.append("machine-absolute cage path in committed file(s): "
                        + ", ".join(stale)
                        + " — teammates' clones get broken wiring; re-run `cage setup "
                          "--wire-only --<agent>` to migrate to the shim")
    referenced = any("cage-run" in c for _, c in cmds)
    if referenced and not shim.exists():
        problems.append("wiring references .cage/bin/cage-run but the shim is missing "
                        "— re-run `cage setup`")
    notes: list[str] = []
    if shim.exists():
        import os as _os
        import subprocess
        if _os.name == "posix" and not _os.access(shim, _os.X_OK):
            problems.append("shim exists but lost its execute bit (core.fileMode=false "
                            "clone?) — `chmod +x .cage/bin/cage-run` or re-run `cage setup`")
        try:  # run via sh so a stripped execute bit doesn't mask the resolution answer
            argv = ([str(shim) + ".cmd"] if _os.name == "nt" else ["sh", str(shim)])
            r = subprocess.run(argv + ["--version"], capture_output=True, text=True,
                               timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                notes.append(f"shim resolves → {r.stdout.strip()}")
            elif r.returncode == 0:
                problems.append("shim runs but resolves to no cage on this machine "
                                "(fail-open exit 0) — capture is off here")
            else:
                problems.append(f"shim failed to run (exit {r.returncode})")
        except Exception as exc:  # noqa: BLE001 — diagnosis must not crash doctor
            problems.append(f"shim run check skipped: {exc}")
    kiro = cfgio.load_json(root / ".kiro" / "settings" / "mcp.json") \
        .get("mcpServers", {}).get("cage") or {}
    if kiro and _is_machine_absolute_cage(kiro.get("command", "")):
        problems.append("kiro MCP still carries a machine-absolute cage path — it is "
                        "committable now via the path-free form; re-run "
                        "`cage setup --wire-only --kiro`")
    # Wiring mode (docs/restricted-environments.md): the mode lives in project policy;
    # the on-disk shim carries a marker in its launcher variant. Report which is
    # active, and warn on drift (policy flipped but `cage setup` not re-run).
    launcher_pol = policy.python_launcher(policy.load(paths.Footprint(root).policy))
    mode = "python-launcher" if launcher_pol else "standard"
    if shim.exists():
        shim_is_py = runshim._PY_MARKER in shim.read_text(encoding="utf-8")
        if shim_is_py != launcher_pol:
            problems.append(f"wiring mode is {mode} in policy but the shim is "
                            f"{'python-launcher' if shim_is_py else 'standard'} — "
                            "re-run `cage setup` to rewrite the wiring")
    if problems:
        return _WARN, "; ".join(problems + notes)
    detail = f"mode: {mode} · committed wiring is portable (no absolute cage paths)"
    return _OK, "; ".join([detail] + notes) if notes else detail


def _kiro_mcp(root: Path) -> tuple[str, str]:
    """Can the interpreter Kiro will resolve actually import cage?

    Going path-free (`python3 -m cage mcp`) is what made `.kiro/settings/mcp.json`
    committable — but it buys portability with a dependency on *which* `python3` wins
    on PATH. If cage lives in a virtualenv that interpreter is not in, the MCP server
    fails to start **and says nothing**: Kiro shows no cage tools and no error. That is
    the same silent-capture class as F1, one layer up, so it is checked rather than
    assumed.

    The probe is the honest one — resolve the command, then ask *it* to import cage.
    Nothing else can answer the question (a same-name interpreter is not the same
    environment). Fail-open: a probe that cannot run reports itself, never crashes
    doctor and never claims a pass."""
    import os as _os
    import subprocess
    from cage import cfgio, kirowire
    server = cfgio.load_json(root / ".kiro" / "settings" / "mcp.json") \
        .get("mcpServers", {}).get("cage") or {}
    if not server:
        return _OK, "kiro MCP not wired here — nothing to check"
    cmd = server.get("command", "")
    if cmd not in (kirowire.PATH_FREE["command"], kirowire.PATH_FREE_WIN["command"]):
        return _OK, f"kiro MCP uses {cmd!r} (not the path-free form) — interpreter probe skipped"
    resolved = shutil.which(cmd)
    if not resolved:
        fix = ("run `cage setup --python-launcher` to write the `py -3` form for this "
               "machine (machine-specific — gitignore .kiro/settings/mcp.json on a "
               "mixed-OS team)" if _os.name == "nt" else
               f"put a {cmd!r} on PATH, or re-run `cage setup --wire-only --kiro`")
        return _FAIL, f"kiro MCP names {cmd!r} but nothing by that name is on PATH — " \
                      f"Kiro will start no cage server, silently; {fix}"
    try:
        r = subprocess.run([resolved, "-c", "import cage"],
                           capture_output=True, text=True, timeout=15)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never takes doctor down
        return _WARN, f"kiro MCP interpreter probe skipped ({exc}) — could not confirm " \
                      f"{resolved} imports cage"
    if r.returncode != 0:
        return _FAIL, (f"kiro MCP resolves {cmd!r} → {resolved}, which CANNOT import "
                       f"cage — the server will fail to start and Kiro will show no "
                       f"error. Install cage for that interpreter "
                       f"(`{resolved} -m pip install cage-flux`) or re-run `cage setup "
                       f"--python-launcher` from the environment cage lives in")
    return _OK, f"kiro MCP is path-free and committable; {cmd!r} → {resolved} imports cage"


def _wiring(scan) -> tuple[str, str]:
    """Every installed artifact's cage verb, checked against the **live parser**
    (`cage/wiringscan.py`). A renamed verb makes a hook or shim exit 1 with its output
    going nowhere — indistinguishable from cage being absent, which is why this class
    of failure went unseen for 9 days (F1). Read-only: nothing is executed.

    User-level artifacts are scanned deliberately (both real failures were user-level);
    `_portability` above stays committed-only because it answers a different question.
    A dead *wired* command is `✗` (capture is silently off) — the only fault class left
    now that the rendered assets (and their staleness check) were removed with hooks."""
    problems = [d.line for d in scan.dead]
    if not problems:
        return _OK, "all wired commands name live verbs"
    fix = "re-run `cage setup --wire-only --<agent>` to heal the wiring"
    return _FAIL, "; ".join(problems + [fix])


def _interceptor(root: Path, scan) -> tuple[str, str]:
    """Existence + **the right twin** + PATH + **liveness**. Existence alone reported ✅
    for 9 days while the shim's capability probe named a removed verb and every graphify
    call fell through to the unmetered binary — existence is not liveness (F1).

    The twin check is the Windows half of the same lesson: `bin/graphify` is a bash
    script with no extension, and Windows resolves a bare `graphify` only through
    PATHEXT — so a project scaffolded on POSIX and opened on Windows has an interceptor
    file, on PATH, naming live verbs, that **can never run**. Reporting that as ✅ would
    recreate F1 on a new OS (docs/shim-contract.md)."""
    from cage import paths
    shim = root / "bin" / paths.graphify_shim_name()
    other = next(p for p in paths.graphify_shims(root) if p != shim)
    if not shim.exists():
        if other.exists():
            return _FAIL, (f"bin/{other.name} is installed but this OS resolves a bare "
                           f"`graphify` only to bin/{shim.name}, which is missing — the "
                           "interceptor can never run, so every graphify call is "
                           "UNMETERED and silent. Fix: re-run `cage setup` (it writes "
                           "both twins)")
        return _WARN, "graphify interceptor not installed (ok if you don't use graphify)"
    if scan.dead_interceptors:
        # Name the twin that actually carries the dead verb. This used to print
        # `bin/{shim.name}` — the twin THIS OS resolves — whichever one was stale, so a
        # POSIX dev with a dead `graphify.cmd` was told to look at a healthy file. It is
        # still a failure either way: the other twin is what a teammate on the other OS
        # runs, and a dead verb there is silently unmetered capture.
        names = ", ".join(f"bin/{n}" for n in sorted(scan.dead_interceptors))
        return _FAIL, (f"{names} probes a verb that no longer exists — every "
                       "graphify call falls through UNMETERED and silently; re-run "
                       "`cage setup --wire-only --<agent>` to refresh it")
    import os
    on_path = str(shim.parent) in os.environ.get("PATH", "").split(os.pathsep)
    if not on_path:
        return _WARN, f"bin/{shim.name} exists but bin/ is not on PATH (open a new shell)"
    return _OK, "graphify interceptor installed, on PATH, and naming live verbs"


def _path_interceptor(root: Path) -> tuple[str, str]:
    """The graphify that **actually runs** — resolved the way the shell does, first
    executable on PATH wins (`cage/pathshim.py`, B-fix-1).

    `_interceptor` above can only see this root's `bin/graphify`. The shim that runs may
    belong to a *different* project, and that is not hypothetical: an adopt-era shim in
    another repo won on PATH, probed a removed verb, and ran graphify unmetered for nine
    days while doctor — run here — reported ✅.

    `foreign` is deliberately **ok**-level: "no interceptor anywhere" is the same
    condition `_interceptor` already warns about, and a second warn naming the same
    absence is noise. `dead` is a failure because capture is silently off; `shadowed`
    warns because it is a fact no root-scoped check can see. Nothing is executed."""
    from cage import pathshim
    try:
        ps = pathshim.classify(root)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"PATH interceptor check skipped: {exc}"

    if ps.state == "absent":
        return _OK, "no `graphify` on PATH — nothing to intercept"
    if ps.state == "foreign":
        return _OK, (f"the graphify on PATH is {ps.winner} — not a cage interceptor, so "
                     "graphify runs unmetered (see the interceptor check above)")
    if ps.state == "shadowed":
        return _WARN, (f"`graphify` resolves to {ps.winner}, NOT this project's "
                       f"{ps.root_shim} — the shim you installed here never runs. Fix: "
                       f"put {Path(ps.root_shim).parent} earlier on PATH, or remove "
                       f"{ps.winner}")
    if ps.state == "dead":
        verb = " ".join(ps.verbs)
        fix = (f"`cage setup --wire-only --claude` (cage refreshes it — "
               f"{ps.managed_root} is cage-managed)" if ps.healable
               else _out_of_root_fix(ps))
        return _FAIL, (f"the graphify that runs is {ps.winner} — a cage interceptor "
                       f"probing `cage {verb}`, which this CLI no longer accepts, so "
                       "every graphify call falls through UNMETERED and silently. "
                       f"Fix: {fix}")
    return _OK, f"`graphify` resolves to {ps.winner} — a cage interceptor naming live verbs"


def _launcher_gap(root: Path) -> tuple[str, str]:
    """GF-LAUNCHER: python-launcher mode removes `cage` from PATH entirely, but the
    graphify interceptor's capability probe (shim-contract.md B5) needs exactly that — it
    runs `cage data graphify --help` before deciding whether to meter. So **neither twin**
    can ever meter a graphify call in this mode; both degrade to correct, unmetered
    passthrough, silently. That combination — launcher mode ON, an interceptor installed
    — is precisely where the silent gap bites, and it is otherwise invisible: nothing
    else in this check list looks at both switches at once.

    Advisory, not a failure: launcher mode is a deliberate choice for a locked-down
    endpoint, and an unmetered interceptor there is a known, accepted trade — the fix
    would have to move both twins together (a decision, not a patch; tracked as
    GF-LAUNCHER) — but a silent trade a user never sees is exactly the class of gap this
    whole checklist exists to surface out loud."""
    launcher_pol = policy.python_launcher(policy.load(paths.Footprint(root).policy))
    if not launcher_pol:
        return _OK, "not in python-launcher mode"
    shim = next((p for p in paths.graphify_shims(root) if p.exists()), None)
    if shim is None:
        return _OK, "python-launcher mode; no graphify interceptor installed"
    interpreter, resolved = _arm2_interpreter()
    if resolved:
        return _OK, (f"python-launcher mode; bin/{shim.name} meters via the B5 arm-2 "
                     f"interpreter ({interpreter} -m cage)")
    return _WARN, (
        f"python-launcher mode is on and bin/{shim.name} is installed, but neither a "
        f"`cage` command nor an importable `{interpreter} -m cage` resolves here, so "
        "graphify runs UNMETERED. Install cage into the interpreter that wins on PATH "
        "(the same silent-start class `kiro-mcp` checks). See "
        "`cage query graphify-shims` and docs/restricted-environments.md.")


def _arm2_interpreter() -> tuple[str, bool]:
    """`(spelling, importable)` for the B5 **arm 2** the twins fall back to when no `cage`
    command resolves (GF-LAUNCHER verdict B, shim-contract B5b).

    The check inverted with that build and the inversion is the point: the old text said
    launcher mode means *unmetered, always*, which stopped being true the moment the
    interceptor learned to reach cage through an interpreter. What is worth warning about
    now is the same thing `kiro-mcp` warns about — **cage is importable by some other
    interpreter than the one that wins on PATH**, which is silent in exactly the F1 way.

    Probes the twins' own spellings, in the twins' own order (D8): `python3` on POSIX,
    `py -3` then `python` on Windows. Fail-open — a probe that cannot run reports
    not-importable rather than raising into doctor."""
    import os as _os
    import subprocess
    spellings = ([("py", ["py", "-3"]), ("python", ["python"])] if _os.name == "nt"
                 else [("python3", ["python3"])])
    for name, argv in spellings:
        if not shutil.which(argv[0]):
            continue
        try:
            probe = subprocess.run([*argv, "-m", "cage", "data", "graphify", "--help"],
                                   capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return name, True
    return (spellings[0][0] if spellings else "python3"), False


def _out_of_root_fix(ps) -> str:
    """The fix line for a dead interceptor cage must **not** write to. Cage never edits a
    file outside a cage-managed root, so the remedy is handed to the user — but it has to
    be runnable, or the finding is noise people learn to ignore."""
    win = Path(ps.winner)
    if win.parent.name == "bin":
        return (f"run `cage setup --project-only` in {win.parent.parent} (adopts it and "
                f"rewrites the shim), or delete {ps.winner}")
    return (f"delete {ps.winner} (graphify then runs unmetered but unbroken), or replace "
            "its `cage " + " ".join(ps.verbs) + "` probe with `cage "
            + (ps.fix_tail or "data graphify") + "`")


def _hook_bypass(root: Path) -> tuple[str, str]:
    """An agent hook invoking graphify by absolute path (`cage/hookbypass.py`, B-fix-3).

    **Advisory by design, never a failure.** graphify's hook is working exactly as
    designed; cage merely cannot observe that path. Reporting it at the same severity as
    a dead cage shim would cry failure on a correct third-party integration — the surest
    way to train people to ignore the check that catches real silent data loss."""
    from cage import hookbypass
    try:
        found = hookbypass.scan(root)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"hook-bypass check skipped: {exc}"
    if not found:
        return _OK, "no agent hook reaches graphify past the interceptor"
    note = ("cage never modifies these — graphify owns them; `cage query stale-wiring` "
            "explains what stays visible")
    return _WARN, "; ".join([b.line for b in found] + [note])


def _graph_staleness(root: Path) -> tuple[str, str]:
    """GC4 (graphify-capture): is `graphify-out/graph.json` older than HEAD? A stale graph
    answers architecture questions about code that has since changed — a wrong answer, and
    the saving GC2 attributes to a report-read is then reading a stale map. Shelled out to
    git (never imported), cwd-oriented like the other project checks, fully fail-open:
    non-repo / no graph / git error all degrade to an OK informational line, never a raise."""
    gj = root / "graphify-out" / "graph.json"
    if not gj.exists():
        return _OK, "no graphify-out/graph.json — graphify not used in this project (ok)"
    try:
        graph_mtime = gj.stat().st_mtime
    except OSError:
        return _OK, "graphify-out/graph.json present (unreadable — staleness not checked)"
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ct", "HEAD"],
                           capture_output=True, text=True, timeout=10)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"graph.json present (git staleness check skipped: {exc})"
    if r.returncode != 0 or not r.stdout.strip():
        return _OK, "graphify-out/graph.json present (not a git repo — staleness not checked)"
    try:
        head_ct = int(r.stdout.strip())
    except ValueError:
        return _OK, "graphify-out/graph.json present (unparseable HEAD time)"
    if graph_mtime < head_ct:
        days = int((head_ct - graph_mtime) / 86_400)
        span = f" by ~{days}d" if days else ""
        return _WARN, (f"graphify-out/graph.json predates HEAD{span} — code changed after "
                       "the graph was built; its answers (and report-read savings) may be "
                       "stale. Rebuild: `graphify update .`")
    return _OK, "graphify-out/graph.json is current with HEAD"


def _graphify_usage(active: Path) -> tuple[str, str]:
    """The GC1 usage breadcrumb, read back as one sentence: *"graphify ran N×, R
    receipts, U unmeasurable"* — the distinction the 0-real-receipts mystery lacked.
    Read-only from `state/graphify-usage.jsonl` (never a money view); informational,
    never fails doctor. Silent-shaped when graphify has never run here."""
    try:
        from cage import usagelog
        s = usagelog.summary(active)
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"graphify usage check skipped: {exc}"
    if not s["runs"]:
        return _OK, ("graphify usage: no runs recorded yet (state/graphify-usage.jsonl) "
                     "— runs are logged by the shim and by transcript detection at import")
    o = s["outcomes"]
    other = o["non-measured"] + o["error"]
    detail = (f"graphify ran {s['runs']}× — {o['receipt']} receipt(s), "
              f"{o['unmeasurable']} unmeasurable, {o['empty']} empty")
    if other:
        detail += f", {other} non-measured/error"
    return _OK, detail


def _graphify_coverage() -> tuple[str, str]:
    """Which agent surfaces can file a graphify savings receipt at all, and — for the one
    that cannot — *why not*, in the same words the explainer uses.

    This exists because a zero is ambiguous and the ambiguity is expensive: an agent
    showing no graphify savings could mean nobody ran it, or that cage has no route for
    that surface. Through v0.46 the second was true for copilot VS Code and for kiro, and
    nothing in the product said so — the numbers were simply, silently narrower than they
    read. Informational, never a failure: a structural limit of somebody else's store is
    not a fault in this installation. Reads `graphifytx.GRAPHIFY_COVERAGE`, the one table
    the explainer reads too, so a gap can never be worded two ways."""
    try:
        from cage import graphifytx
        lines = graphifytx.coverage_lines()
        gaps = [row for row in graphifytx.GRAPHIFY_COVERAGE if not row[2]]
    except Exception as exc:  # noqa: BLE001 — a diagnostic never crashes doctor
        return _OK, f"graphify coverage check skipped: {exc}"
    head = (f"graphify savings routes: {len(lines) - len(gaps)}/{len(lines)} surfaces file "
            f"receipts" + (f"; {len(gaps)} structurally cannot" if gaps else ""))
    return _OK, head + "\n     · " + "\n     · ".join(lines) + \
        "\n     (`cage query graphify-coverage`; backfill an upgraded route with "\
        "`cage import --rescan-graphify`)"


def _receipts(active: Path, scan) -> tuple[str, str]:
    """Are there savings receipts to attribute? Zero receipts means `cage insights
    attrib` has nothing to work with — but the *reason* matters, and reporting it bare
    would misread a dead interceptor as "you never used the savings tools". When the
    interceptor is dead the line says so and points up at the wiring check; the two
    together tell the true story (F1's deferred check, shipped with its prerequisite)."""
    try:
        n = len(ledger.read_kind(active, "receipts"))
    except Exception as exc:  # noqa: BLE001 — diagnosis must never crash doctor
        return _OK, f"receipts check skipped: {exc}"
    if n:
        return _OK, f"{n} savings receipt(s) — attribution has data"
    if scan.interceptor_dead:
        return _WARN, ("receipts: 0 — the graphify interceptor is dead (see wiring "
                       "above); fix it before concluding the tools are unused")
    return _WARN, ("receipts: 0 — attribution has no data yet; savings are recorded by "
                   "`cage data graphify -- …`, the fux/compressor shims, and the "
                   "response cache")


def _ago(ts: str) -> str:
    """Human "(3m ago)" for an ISO timestamp; fail-open to ''. Health-check only —
    uses a clock, but doctor is never a derived-from-ledger view, so determinism holds."""
    try:
        when = _dt.datetime.fromisoformat(ts)
        now = _dt.datetime.now(when.tzinfo)
        secs = max(0, int((now - when).total_seconds()))
        if secs < 90:
            return f"({secs}s ago)"
        if secs < 5400:
            return f"({secs // 60}m ago)"
        if secs < 172800:
            return f"({secs // 3600}h ago)"
        return f"({secs // 86400}d ago)"
    except Exception:  # noqa: BLE001
        return ""


def _last_problem(root: Path) -> str:
    """The most recent exception/skip in the debug log, as a short one-liner."""
    for ev in reversed(debuglog.tail(root, 200)):
        if ev.get("event") == "exception":
            return f"{ev.get('agent', '?')}/{ev.get('context', '?')}: {ev.get('error', '?')} {_ago(ev.get('ts', ''))}"
        if ev.get("skip"):
            return f"{ev.get('agent', '?')} skipped: {ev.get('skip')} {_ago(ev.get('ts', ''))}"
    return ""


def _capture_trace(root: Path) -> tuple[str, str]:
    """Per-agent capture event + last error, from the metadata-only debug log.
    Off by default: when debug is disabled this row just says how to turn it on; it
    never writes anything (the log only exists under `CAGE_DEBUG=1`). The events are
    the import/push produce/skip breadcrumbs (`cage/capturelog.py` + the CAGE_DEBUG
    push-site logs), not hooks — capture is pull-based."""
    try:
        pol = policy.load(paths.Footprint(root).policy)
    except Exception:  # noqa: BLE001
        pol = {}
    if not policy.debug_enabled(pol):
        return _OK, ("capture debug off — set CAGE_DEBUG=1 (or [debug] enabled=true) to record a "
                     "metadata-only per-agent capture breadcrumb + errors to .cage/state/debug.log; "
                     "then `cage debug` to read them")
    seen = debuglog.last_seen(root)
    rows = []
    for a in agents.SURFACES:
        recs = [r for (ag, _ev), r in seen.items() if ag == a]
        if recs:
            latest = max(recs, key=lambda r: r.get("ts", ""))
            rows.append(f"\n      · {a:<8} last event: {latest.get('event', '?'):<14} {_ago(latest.get('ts', ''))}")
        else:
            rows.append(f"\n      · {a:<8} no capture events seen yet")
    problem = _last_problem(root)
    if problem:
        rows.append(f"\n      ⚠ last issue: {problem}")
    return _OK, "capture debug ON — per-agent last capture event (`cage debug` for full events):" + "".join(rows)


def _ledger_roundtrip() -> tuple[str, str]:
    """Write + read a receipt in a throwaway ledger — proves the write path works."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            f = paths.Footprint(Path(tmp)).receipts
            row = schema.make_receipt(tool="graphify", raw_alternative=10, actual=4)
            if not ledger.append(f, row):
                return _FAIL, "ledger.append returned False — ledger not writable"
            back = ledger.read(f)
            if len(back) == 1 and back[0].get("saved") == 6:
                return _OK, "ledger write+read round-trip OK (saved derived correctly)"
            return _FAIL, "round-trip mismatch — ledger read did not return the row"
    except Exception as exc:  # noqa: BLE001
        return _FAIL, f"ledger round-trip raised: {exc}"


def version_footer(root: Path) -> dict:
    """The honest "versions installed" answer (handoff §5): running cage (+ `zipapp`
    tag), the bundled `[meta]` versions, and the project policy's `[meta]` if one
    exists — per-artifact versions are unknowable (artifacts are stampless), this is
    the closest real signal. Reuses the same project-vs-bundle read `_bundled_prices`/
    `_policy_version` already do."""
    from cage import __version__
    bundled = policy.bundled_raw().get("meta", {})
    out = {
        "cage": __version__,
        "zipapp": paths.distribution() == "zipapp",
        "bundled": {"prices_version": bundled.get("prices_version"),
                    "policy_version": bundled.get("policy_version")},
        "project": None,
    }
    pol_path = paths.Footprint(root).policy
    if pol_path.exists():
        try:
            project_meta = policy.load_project_raw(pol_path).get("meta", {})
            out["project"] = {"prices_version": project_meta.get("prices_version"),
                              "policy_version": project_meta.get("policy_version")}
        except Exception:  # noqa: BLE001 — a broken policy is reported by the policy check
            out["project"] = {}
    return out


def wiring_report(root: Path) -> dict:
    """`cage doctor --wiring` payload: the installed-artifact inventory
    (`wiringscan.inventory`) + the version footer, as one plain-dict data structure
    for the text and `--json` renderers to share (house pattern)."""
    inv = wiringscan.inventory(root)
    return {
        "items": [{"agent": a.agent, "kind": a.kind, "scope": a.scope,
                   "display": a.display, "status": a.status, "detail": a.detail}
                  for a in inv.items],
        "rollups": [{"agent": r.agent, "verdict": r.verdict, "missing": list(r.missing),
                     "dead": r.dead, "stale": r.stale} for r in inv.rollups],
        "version": version_footer(root),
    }


_STATUS_GLYPH = {"current": "✔", "stale": "·", "dead": "✗", "foreign": "○"}


def render_wiring_text(rep: dict) -> str:
    """The text form of `wiring_report()` — one data structure, two renderers (the
    `--json` branch just dumps the dict as-is)."""
    lines = ["Wiring inventory (project + global/user; read-only):"]
    for scope in ("project", "global"):
        rows = [it for it in rep["items"] if it["scope"] == scope]
        if not rows:
            continue
        lines.append(f"\n  {scope}:")
        for it in rows:
            glyph = _STATUS_GLYPH.get(it["status"], "?")
            agent = it["agent"] or "-"
            lines.append(f"    {glyph} {agent:<8} {it['kind']:<13} {it['display']:<42} {it['status']}"
                        + (f" — {it['detail']}" if it["detail"] else ""))
    lines.append("")
    for r in rep["rollups"]:
        lines.append(f"  {r['agent']:<8} {_rollup_line(r)}")
    v = rep["version"]
    tag = " (zipapp)" if v["zipapp"] else ""
    foot = f"\ncage {v['cage']}{tag} · bundled prices {v['bundled']['prices_version']} · bundled policy v{v['bundled']['policy_version']}"
    if v["project"]:
        foot += (f" · project prices {v['project'].get('prices_version')}"
                 f" · project policy v{v['project'].get('policy_version')}")
    lines.append(foot)
    return "\n".join(lines)


def _rollup_line(r: dict) -> str:
    """Four mutually-exclusive verdicts (wiringscan._agent_inventory): "needs healing"
    takes priority over "fully wired" when something present is broken."""
    v = r["verdict"]
    if v == "partially wired" and r["missing"]:
        v += f" (missing: {', '.join(r['missing'])})"
    elif v == "needs healing":
        v += f" ({r['dead']} dead)"
    return v


def run(root: Path) -> dict:
    """Run every check; return {status, checks:[{name, level, detail}]}.

    Ledger checks run against the **active** sink (``--ledger``/``CAGE_BASE`` → project
    ``.cage/`` → global ``~/.cage``), so the project-less user's global ledger is the one
    inspected; wiring/interceptor checks stay cwd-oriented (they're about *this* project)."""
    active = paths.resolve_root(root)
    source = paths.active_ledger_source(root)
    # One scan feeds three checks (wiring / interceptor / receipts) so the artifact
    # enumeration and parser build happen once. Fail-open: a scan that can't run must
    # not take the whole doctor down with it.
    try:
        scan = wiringscan.run(root)
    except Exception:  # noqa: BLE001
        scan = wiringscan.Scan(dead=[], stale_assets=[], interceptor_dead=False)
    checks = [
        ("tool", *_tool()),
        ("footprint", *_footprint(active, source)),
        ("policy", *_policy(active)),
        ("pricing", *_pricing(active)),
        # Directly below `pricing`: a credits-priced row is exactly the row `pricing`
        # would otherwise have called UNPRICED, so the two lines answer one question.
        ("credits", *_credits(active)),
        # Directly below `credits`: same "vendor-recorded facts, advisory only" tier,
        # widened from the priced `credits` field to the whole COPILOT-METRICS row.
        ("copilot-metrics", *_copilot_metrics(active)),
        # Directly below `copilot-metrics`: the kiro twin of the same "vendor-recorded
        # facts, advisory only" tier (KIRO-METRICS handoff §4.6).
        ("kiro-metrics", *_kiro_metrics(active)),
        # Directly below `kiro-metrics`: the claude twin of the same tier, plus a
        # retention nudge neither copilot nor kiro's checks need (CLAUDE-METRICS
        # handoff §4.6).
        ("claude-metrics", *_claude_metrics(active)),
        ("prices-meta", *_bundled_prices(active)),
        ("prices-age", *_prices_age(active)),
        ("policy-version", *_policy_version(active)),
        ("state", *_state_dir(active)),
        ("portability", *_portability(root)),
        # Directly below `portability`: going path-free is what made kiro's MCP config
        # committable, and this is the condition that buys — read them together.
        ("kiro-mcp", *_kiro_mcp(root)),
        # `wiring` must render ABOVE `receipts`: a dead verb is the *reason* receipts
        # can be empty, and the receipts line points back up at it.
        ("wiring", *_wiring(scan)),
        ("metering", *_metering(active)),
        ("timeline", *_capture_timeline(active)),
        ("capture-quality", *_capture_quality(active)),
        ("trace", *_capture_trace(active)),
        ("interceptor", *_interceptor(root, scan)),
        # The PATH-winning pair must render directly below `interceptor`: they answer
        # the same question at a wider scope (what actually runs, vs what this root
        # installed), and reading them apart invites the false ✅ they exist to kill.
        ("path-interceptor", *_path_interceptor(root)),
        ("launcher-gap", *_launcher_gap(root)),
        ("hook-bypass", *_hook_bypass(root)),
        ("graph-staleness", *_graph_staleness(root)),
        ("graphify-usage", *_graphify_usage(active)),
        # Directly below `graphify-usage`: that line says how often graphify RAN,
        # this one says which surfaces cage could have FILED from — a thin number
        # is only readable with both.
        ("graphify-coverage", *_graphify_coverage()),
        ("receipts", *_receipts(active, scan)),
        ("ledger", *_ledger_roundtrip()),
    ]
    rows = [{"name": n, "level": lv, "detail": d} for n, lv, d in checks]
    status = max((r["level"] for r in rows), key=lambda lv: _RANK[lv])
    return {"status": status, "checks": rows}
