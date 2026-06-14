"""`cage budget` + the Cage guard — ceilings per session / day (plan §8.1).

Sums recorded spend against `policy.budgets` and reports headroom. `on_exceed`
is advisory here (`warn`); the in-path guard (`check`) is the enforcement hook a
gateway calls *before* a paid call, returning whether to proceed.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import ledger, policy, render


def _today_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).date().isoformat()


def spend(root: Path, session: str | None = None) -> dict:
    calls = ledger.calls(root)
    today = _today_utc()
    day_usd = sum(c.get("est_cost_usd", 0.0) for c in calls if (c.get("ts") or "")[:10] == today)
    sess_usd = sum(c.get("est_cost_usd", 0.0) for c in calls
                   if session and c.get("session") == session)
    return {"day_usd": round(day_usd, 6), "session_usd": round(sess_usd, 6),
            "session": session, "day": today}


def check(root: Path, pol: dict, session: str | None = None,
          add_usd: float = 0.0) -> dict:
    """Would spending `add_usd` more breach a ceiling? Returns the verdict, never raises."""
    b = policy.budgets(pol)
    s = spend(root, session)
    verdicts = {}
    for scope, cap_key in (("session", "session_usd"), ("day", "daily_usd")):
        cap = b.get(cap_key)
        used = s["session_usd"] if scope == "session" else s["day_usd"]
        verdicts[scope] = {"cap": cap, "used": round(used, 6),
                           "would_be": round(used + add_usd, 6),
                           "over": bool(cap and used + add_usd > cap)}
    over = any(v["over"] for v in verdicts.values())
    return {"on_exceed": b.get("on_exceed", "warn"), "over": over,
            "proceed": not (over and b.get("on_exceed") == "block"), "scopes": verdicts}


def render_budget(verdict: dict) -> str:
    rows = []
    for scope, v in verdict["scopes"].items():
        cap = render.usd(v["cap"]) if v["cap"] is not None else "—"
        flag = "  ⚠ OVER" if v["over"] else ""
        rows.append([scope, render.usd(v["used"]), cap,
                     render.pct(v["used"], v["cap"] or 0) + flag])
    body = render.table(["scope", "used", "cap", "of cap"], rows, rights={1, 2})
    return f"Budget ({verdict['on_exceed']} on exceed)\n\n{body}"
