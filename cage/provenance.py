"""`cage why <call-id>` — full provenance: the call + every receipt against it (plan §7)."""
from __future__ import annotations

from pathlib import Path

from cage import ledger, render


def explain(root: Path, call_id: str) -> dict:
    call = next((c for c in ledger.calls(root) if c.get("id") == call_id), None)
    return {"call": call, "receipts": ledger.receipts_for(root, call_id)}


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
            f"  cost     {render.usd(call.get('est_cost_usd',0.0))}    "
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
