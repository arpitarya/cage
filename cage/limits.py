"""`cage limits` — provider quota windows + estimated AI-credit consumption (plan §3.8).

**Not a ledger substrate.** Quota (a provider rate-limit %) is a *decaying live gauge*,
not durable truth, so the latest snapshot per (agent, window) lives in a machine-local
state file (`.cage/state/limits.json`), **overwritten not appended, never synced to
refs/notes**. Credits are **estimated** from tokens × a policy multiplier, for
token-based providers only — every figure labelled `estimated`, sourced, and ending with
a "reconcile against your provider dashboard" note. A shape-mismatch emits nothing.

Write side: `snapshot_codex` (called fail-open from `importcmd.import_codex`) reads the
`rate_limits` block Codex already writes. Read side: `rollup`/`render_limits` derive the
view from the state file (quota) + the ledger (credits) — $0, no network, no LLM.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from cage import credits, ledger, paths, render, transcript

# Display-only labels for the window sizes Codex reports (verified: 10080=weekly,
# 43200=monthly; 300/1440 included defensively). An unknown size falls back to "<n>m".
_WINDOW_LABELS = {300: "5h", 1440: "daily", 10080: "weekly", 43200: "monthly"}


def _load(foot: paths.Footprint) -> dict:
    try:
        return json.loads(foot.limits.read_text(encoding="utf-8")) if foot.limits.exists() else {}
    except (ValueError, OSError):  # fail-open: a corrupt snapshot just means none shown
        return {}


def _save(foot: paths.Footprint, data: dict) -> None:
    try:
        foot.limits.parent.mkdir(parents=True, exist_ok=True)
        foot.limits.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    except OSError:  # noqa: BLE001 — fail-open: an unpersistable snapshot is simply absent next read
        pass


# ── write side: latest-only Codex quota snapshot ────────────────────────────

def snapshot_codex(root: Path, files) -> int:
    """Merge the latest rate-limit snapshot per window from ``files`` (Codex rollouts)
    into the machine-local state file — overwrite semantics, keeping the freshest by
    observed ts. Returns #windows persisted. **Fail-open**: an unreadable/odd rollout is
    skipped, never raises into the import path. A renamed/missing `rate_limits` block
    yields no snapshot (and no error)."""
    try:
        foot = paths.Footprint(root)
        state = _load(foot)
        agent_state = dict(state.get("codex", {}))
        for f in files:
            try:
                text = Path(f).read_text(encoding="utf-8")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line or "rate_limit" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                for snap in transcript._codex_rate_limits(rec):
                    key = str(snap["window_minutes"])
                    prev = agent_state.get(key)
                    if prev is None or (snap["observed_ts"] or "") >= (prev.get("observed_ts") or ""):
                        agent_state[key] = snap
        if agent_state:
            state["codex"] = agent_state
            _save(foot, state)
        return len(agent_state)
    except Exception:  # noqa: BLE001 — fail-open: quota capture never breaks an import
        return 0


# ── read side: the derived view ─────────────────────────────────────────────

def _window_label(minutes: int) -> str:
    return _WINDOW_LABELS.get(minutes, f"{minutes}m")


def _quota_view(foot: paths.Footprint) -> list[dict]:
    state = _load(foot)
    out: list[dict] = []
    for agent in sorted(state):
        windows = state[agent]
        if not isinstance(windows, dict):
            continue
        rows = []
        for wm in sorted(windows, key=lambda k: int(k) if str(k).lstrip("-").isdigit() else 0):
            snap = windows[wm] if isinstance(windows[wm], dict) else {}
            up = snap.get("used_percent")
            rows.append({"window_minutes": int(wm) if str(wm).lstrip("-").isdigit() else wm,
                         "label": _window_label(int(wm)) if str(wm).lstrip("-").isdigit() else str(wm),
                         "remaining_pct": round(100 - up, 1) if isinstance(up, (int, float)) else None,
                         "resets_at": snap.get("resets_at"),
                         "observed_ts": snap.get("observed_ts")})
        out.append({"agent": agent, "windows": rows})
    return out


def _credits_view(root: Path, pol: dict) -> list[dict]:
    groups: dict[tuple, int] = {}
    for c in ledger.calls(root):
        key = (c.get("agent", ""), c.get("provider", ""), c.get("model", ""))
        groups[key] = groups.get(key, 0) + c.get("tokens_in", 0) + c.get("tokens_out", 0)
    out: list[dict] = []
    for (agent, provider, model), tokens in sorted(groups.items()):
        cr = credits.tokens_to_credits(pol, provider, model, tokens)
        out.append({"agent": agent, "provider": provider, "model": model,
                    "tokens": tokens, "credits": cr,
                    "method": "estimated" if cr is not None else None})
    return out


def rollup(root: Path, pol: dict) -> dict:
    """The `cage limits` data: local quota windows (state file) + estimated credit
    consumption (ledger × policy multiplier). Derived, deterministic, $0."""
    foot = paths.Footprint(root)
    return {"quota": _quota_view(foot), "credits": _credits_view(root, pol)}


# ── render ──────────────────────────────────────────────────────────────────

_RECONCILE = ("· every quota/credit figure is estimated — reconcile against your provider "
              "dashboard. Quota is a latest-only local snapshot, not a ledger.")


def _reset_str(epoch) -> str:
    """A reset moment as a deterministic UTC stamp (epoch seconds → `YYYY-MM-DD HH:MMZ`),
    or "—" for a missing/odd value. Absolute (not relative) keeps the table deterministic."""
    if not isinstance(epoch, (int, float)):
        return "—"
    try:
        return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    except (OverflowError, OSError, ValueError):
        return "—"


def render_limits(data: dict) -> str:
    parts: list[str] = []
    quota = data["quota"]
    if not quota:
        parts.append("Quota: no local snapshot yet — run `cage import --agent codex` to "
                     "capture Codex rate-limit windows (no other agent reports quota locally).")
    for a in quota:
        rows = [[w["label"],
                 f"{w['remaining_pct']:.0f}%" if w["remaining_pct"] is not None else "—",
                 _reset_str(w["resets_at"]),
                 render.ago(w["observed_ts"] or "") or "—"] for w in a["windows"]]
        body = render.table(["window", "remaining", "resets (UTC)", "observed"], rows, rights={1})
        parts.append(f"Quota · {a['agent']} (local rollout snapshot, estimated)\n\n{body}")

    crows = []
    for r in data["credits"]:
        if r["credits"] is not None:
            credit, src = f"≈ {r['credits']:.2f}", "estimated · tokens × policy[credits]"
        else:
            credit, src = "—", "no multiplier configured ([credits] in policy.toml)"
        crows.append([r["agent"], f"{r['provider']}/{r['model']}",
                      render.tok(r["tokens"]), credit, src])
    if crows:
        body = render.table(["agent", "model", "tokens", "credits", "source"], crows, rights={2, 3})
        parts.append("Estimated AI-credit consumption (token-based providers only)\n\n" + body)

    parts.append(_RECONCILE)
    return "\n\n".join(parts)
