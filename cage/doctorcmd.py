"""`cage doctor` — verify a project's Cage setup is correct and working.

A deterministic, $0 health check any agent (claude / codex / copilot / kiro) can run
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

from cage import agents, debuglog, importcmd, ledger, paths, policy, prices, render, schema

_OK, _WARN, _FAIL = "ok", "warn", "fail"
_RANK = {_OK: 0, _WARN: 1, _FAIL: 2}


def _tool() -> tuple[str, str]:
    if not shutil.which("cage"):
        return _WARN, "`cage` not on PATH (running, but not globally callable)"
    from cage import __version__
    return _OK, f"cage {__version__} on PATH"


def _footprint(active: Path, source: str) -> tuple[str, str]:
    """The active ledger sink, per the capture precedence (plan §3.7). Names *which* sink
    is live (project vs global vs --ledger override) so a user with both a project `.cage/`
    and a global `~/.cage` knows where capture lands — one sink per run, never both."""
    base = paths.Footprint(active).base
    if not base.is_dir():
        return _FAIL, ("no ledger yet — `cage init` for this project, or "
                       "`cage setup --global` for project-less capture into ~/.cage")
    return _OK, f"active ledger: {source} → {base}"


def _policy(root: Path) -> tuple[str, str]:
    try:
        pol = policy.load(paths.Footprint(root).policy)
        return _OK, f"policy loads ({len(pol.get('prices', {}))} model prices)"
    except Exception as exc:  # noqa: BLE001 — surface the parse error, don't raise
        return _FAIL, f"policy.toml failed to load: {exc}"


def _hooks(root: Path) -> tuple[str, str]:
    """Hooks are an *optional* real-time add-on, not the capture contract: they fire only
    under a CLI client — a VS Code extension of Codex/Kiro/Copilot never runs them. So a
    missing/wired hook is informational, never a failure; the universal path is `cage
    import`/`cage export`."""
    wired = [s for s, on in agents.status(root).items() if on]
    if not wired:
        return _OK, ("no agent hooks wired (optional) — capture via `cage import` / "
                     "`cage export`; wire real-time CLI hooks with `cage setup --wire-only --<agent>`")
    return _OK, (f"real-time hooks wired (CLI-only, optional): {', '.join(wired)} — "
                 "they don't fire under a VS Code extension; `cage import` is the universal path")


def _metering(active: Path) -> tuple[str, str]:
    """Honest four-agent capture matrix (plan §3.7). Capture is **pull-based**: explicit
    `cage import` / `cage export` (and the optional foreground `cage watch`) is the universal,
    client-independent path for every surface in ``agents.SURFACES``. Hooks are an optional
    real-time add-on that fire only under a CLI client — never under a VS Code extension —
    so a *wired* hook is not the same as a *firing* one. When capture-debug is on, the
    per-agent heartbeat shows whether a hook has actually fired (and when); otherwise the
    row honestly says the hook is wired but may not fire. No hook is ever labelled
    'capture wired'. Surfaces the pull-based **last import: N ago** staleness signal."""
    wired = agents.status(active)
    seen = debuglog.last_seen(active)  # only populated when CAGE_DEBUG is on
    rows = []
    for a in agents.SURFACES:
        recs = [r for (ag, _ev), r in seen.items() if ag == a]
        if recs:
            latest = max(recs, key=lambda r: r.get("ts", ""))
            state = f"hook fired {render.ago(latest.get('ts', ''))} (real-time)"
        elif wired.get(a, False):
            state = "hook wired — CLI-only, may not fire (e.g. a VS Code extension)"
        else:
            state = "no hook (capture via import)"
        rows.append(f"\n      · {a:<8} {state:<48} | universal: cage import --agent {a}")
    li = importcmd.last_import(active)
    rel = render.ago(li) if li else ""
    foot = (f"\n      last import: {rel}" if rel
            else "\n      last import: never — run `cage import` (or `cage watch`)")
    foot += (f"\n      (automate with your own scheduler line, e.g. `{render.scheduler_hint()}`; "
             "cage installs no scheduler.)")
    head = ("capture is pull-based — `cage import`/`cage export` is the universal path; "
            "hooks are an optional CLI-only real-time add-on (they don't fire under a VS "
            "Code extension):")
    return _OK, head + "".join(rows) + foot


def _pricing(root: Path) -> tuple[str, str]:
    """Scan recorded calls for models that bill $0 with no exact *or* family price
    row — the silent-$0 sharp edge. A wrong $0 must read as UNPRICED here, not hide."""
    try:
        pol = policy.load(paths.Footprint(root).policy)
        calls = ledger.calls(root)
    except Exception:  # noqa: BLE001 — a broken policy/ledger is reported by other checks
        return _OK, "no priced ledger to check yet"
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


def _bundled_prices(root: Path) -> tuple[str, str]:
    """Compare the project policy's [meta] against the installed bundle's — a newer
    bundle means researched price rows this project isn't using yet. Recommendation
    only, never auto-applied (`cage prices sync` is the user's move)."""
    try:
        from cage import pricescmd
        if not paths.Footprint(root).policy.exists():
            return _OK, "no project policy.toml — the installed bundle's prices apply directly"
        project = policy.load_project_raw(paths.Footprint(root).policy)
    except Exception:  # noqa: BLE001 — a broken policy is reported by the policy check
        return _OK, "project policy unreadable — see the policy check"
    bundled_v = str(policy.bundled_raw().get("meta", {}).get("prices_version") or "?")
    rec = pricescmd.sync_recommendation(project.get("meta", {}))
    if rec:
        return _WARN, rec
    return _OK, f"project prices are current with the bundle ({bundled_v})"


def _state_dir(root: Path) -> tuple[str, str]:
    """State-dir size + prune-candidate visibility (bloat should be visible before
    it's a problem). Informational — `cage cleanup` is the remedy."""
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
                                  "`cage cleanup` to review")
        return _OK, status + " · nothing stale"
    except Exception as exc:  # noqa: BLE001 — informational check, never blocks doctor
        return _OK, f"state dir present (scan skipped: {exc})"


def _interceptor(root: Path) -> tuple[str, str]:
    shim = root / "bin" / "graphify"
    if not shim.exists():
        return _WARN, "graphify interceptor not installed (ok if you don't use graphify)"
    import os
    on_path = str(shim.parent) in os.environ.get("PATH", "").split(os.pathsep)
    if not on_path:
        return _WARN, "bin/graphify exists but bin/ is not on PATH (open a new shell)"
    return _OK, "graphify interceptor installed and on PATH"


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
    """Per-agent capture heartbeat + last error, from the metadata-only debug log.
    Off by default: when debug is disabled this row just says how to turn it on; it
    never writes anything (the heartbeat/log only exist under `CAGE_DEBUG=1`)."""
    try:
        pol = policy.load(paths.Footprint(root).policy)
    except Exception:  # noqa: BLE001
        pol = {}
    if not policy.debug_enabled(pol):
        return _OK, ("capture debug off — set CAGE_DEBUG=1 (or [debug] enabled=true) to record a "
                     "metadata-only per-hook heartbeat + errors to .cage/state/debug.log; "
                     "then `cage debug` to read them")
    seen = debuglog.last_seen(root)
    rows = []
    for a in agents.SURFACES:
        recs = [r for (ag, _ev), r in seen.items() if ag == a]
        if recs:
            latest = max(recs, key=lambda r: r.get("ts", ""))
            rows.append(f"\n      · {a:<8} last fired: {latest.get('event', '?'):<14} {_ago(latest.get('ts', ''))}")
        else:
            rows.append(f"\n      · {a:<8} never fired (no hook heartbeat seen)")
    problem = _last_problem(root)
    if problem:
        rows.append(f"\n      ⚠ last issue: {problem}")
    return _OK, "capture debug ON — per-agent last hook fired (`cage debug` for full events):" + "".join(rows)


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


def run(root: Path) -> dict:
    """Run every check; return {status, checks:[{name, level, detail}]}.

    Ledger checks run against the **active** sink (``--ledger``/``CAGE_BASE`` → project
    ``.cage/`` → global ``~/.cage``), so the project-less user's global ledger is the one
    inspected; wiring/interceptor checks stay cwd-oriented (they're about *this* project)."""
    active = paths.resolve_root(root)
    source = paths.active_ledger_source(root)
    checks = [
        ("tool", *_tool()),
        ("footprint", *_footprint(active, source)),
        ("policy", *_policy(active)),
        ("pricing", *_pricing(active)),
        ("prices-meta", *_bundled_prices(active)),
        ("state", *_state_dir(active)),
        ("hooks", *_hooks(root)),
        ("metering", *_metering(active)),
        ("trace", *_capture_trace(active)),
        ("interceptor", *_interceptor(root)),
        ("ledger", *_ledger_roundtrip()),
    ]
    rows = [{"name": n, "level": lv, "detail": d} for n, lv, d in checks]
    status = max((r["level"] for r in rows), key=lambda lv: _RANK[lv])
    return {"status": status, "checks": rows}
