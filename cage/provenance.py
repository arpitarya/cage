"""`cage insights why <call-id>` — full provenance: the call + every receipt against it (plan §7)."""
from __future__ import annotations

from pathlib import Path

from cage import ledger, paths, policy, prices, render


def explain(root: Path, call_id: str, pol: dict | None = None) -> dict:
    call = next((c for c in ledger.calls(root) if c.get("id") == call_id), None)
    if pol is None:
        try:
            pol = policy.load(paths.Footprint(root).policy)
        except Exception:  # noqa: BLE001 — library default; CLI passes a checked pol
            pol = {}
    # Repriced like report/budget — a transcript-sourced call stores est_cost_usd=0.0.
    usd = prices.call_usd(pol, call) if call else 0.0
    return {"call": call, "usd": round(usd, 6), "receipts": ledger.receipts_for(root, call_id)}


def render_why(data: dict, call_id: str) -> str:
    call = data["call"]
    if not call:
        return f"cage: no call {call_id!r} in the ledger."
    head = (f"{call['id']}  ·  {call.get('ts','')}\n"
            f"  task     {call.get('task') or '—'}    route {call.get('route') or '—'}"
            f"    agent {call.get('agent') or '—'}\n"
            f"  model    {call.get('provider','')}/{call.get('model','')}\n"
            f"  tokens   {render.tok(call.get('tokens_in',0))} in "
            f"({render.tok(call.get('cached_in',0))} cached) / "
            f"{render.tok(call.get('tokens_out',0))} out\n"
            f"  cost     {render.usd(data.get('usd', call.get('est_cost_usd', 0.0)))}    "
            f"latency {call.get('latency_ms',0):,} ms    ok={call.get('ok',True)}")
    rcpts = data["receipts"]
    if not rcpts:
        return head + "\n\n  (no savings receipts filed against this call)"
    rows = [[r["tool"], r.get("unit", "tokens"), render.tok(r.get("raw_alternative", 0)),
             render.tok(r.get("actual", 0)), render.tok(r.get("saved", 0)),
             r.get("method", "")] for r in rcpts]
    body = render.table(["tool", "unit", "raw alt", "actual", "saved", "method"],
                        rows, rights={2, 3, 4})
    return head + "\n\nReceipts\n" + body
