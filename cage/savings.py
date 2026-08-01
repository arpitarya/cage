"""The dedicated savings writer — one row per tool saving into the per-source tree
`savings/<tool>/savings-<month>.jsonl` (import-ledger plan §3).

A thin wrapper over `schema.make_savings` + `ledger.append_row(root, ("savings", tool),
row)`: the writer resolves `savings/<tool>/savings-<month>.jsonl` from the row's `tool`
+ `ts`, and reads glob the whole tree (`ledger.savings`). Fail-open like every push
path — a write error returns ``""`` and is traced under ``CAGE_DEBUG``, never raised
into the tool's own result. The push sink is resolved through the ONE canonical resolver
(`paths.canonical_ledger`) that push and pull share, and each row carries a non-PII
`route_key` (a hash of the resolved ledger-root path) so a read can reclaim a stray
saving by exact key — the same discipline `metering.record_receipt` holds.

Savings rows are receipt-compatible, so they surface through `ledger.receipts`'s union
in every attribution/roi/report view with no per-view change (plan §3).
"""
from __future__ import annotations

from pathlib import Path

from cage import debuglog, ledger, paths, schema


def record(root: Path | None = None, *, tool: str, raw_alternative: float, actual: float,
           op: str = "", session: str = "", task: str = "", unit: str = "tokens",
           method: str = "modeled", confidence: float = 1.0, source_files: int = 0,
           import_id: str = "", savings_id: str | None = None, ts: str | None = None,
           **_ignore) -> str:
    """Append one savings row for ``tool`` into `savings/<tool>/`; return its id (``""``
    on failure). Fail-open: any error is traced and swallowed, never raised. The push
    sink is the canonical ledger; a non-PII `route_key` is stamped for exact-key
    reclaim, exactly like `metering.record_receipt`."""
    try:
        # Honor an explicit root directly (the caller already resolved it); only a
        # rootless push falls to the ONE canonical resolver — exactly `_resolve_root`.
        r = Path(root) if root is not None else paths.canonical_ledger()
        row = schema.make_savings(
            tool=tool, raw_alternative=raw_alternative, actual=actual, op=op,
            session=session, task=task, unit=unit, method=method, confidence=confidence,
            source_files=source_files, import_id=import_id,
            route_key=paths.routing_key(r), savings_id=savings_id, ts=ts)
        ok = ledger.append_row(r, ("savings", tool), row)
        debuglog.event(r, event="receipt", tool=tool, produced=bool(ok),
                       skip_reason="" if ok else "push-sink-unresolved")
        return row["id"] if ok else ""
    except Exception as e:  # noqa: BLE001 — a savings write must never break the tool
        try:
            debuglog.exception(Path(root) if root is not None else Path.cwd(),
                               "savings.record", e)
        except Exception:  # noqa: BLE001
            pass
        return ""
