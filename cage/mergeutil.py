"""Pure union-by-row-id for append-only fragments — the CRDT under both notes refs.

Append-only logs (provenance §3.5, calls/receipts §3.6.3) are merged by **row id**:
two machines only ever *add* globally-unique ids, never edit a shared line, so a union
keyed on `id` is order-independent and conflict-free. The one wrinkle is what to do if
the *same* id reappears (a re-synced buffer): callers decide via `on_collision`.

This is the shared core. Provenance passes a `PROVENANCE_METHOD_TRUST` tie-break (a
re-synced row must never read as a stronger method than its real input); the ledger
passes nothing and keeps first-by-id (call/receipt ids never legitimately collide, so
the policy is "document the rule, never silently overwrite"). **That invariant is only
as true as `ids.new_id`'s entropy** — it was measurably false at 16 bits (~1 in 229 over
200k ids, `work/regression/2026-08-02-finding-call-id-collisions.md`), which is what
widening the random field to 32 bits fixed. A collision here is a *dropped row*, not a
conflict to resolve, so the generator is this function's real precondition. Kept here, not in
`notessync`; it was shared with the deleted `ledgersync` (SURFACE-CUT) and is kept
generic because a future second notes writer would want the same core.
"""
from __future__ import annotations

from typing import Callable


def union_by_id(existing: list[dict], incoming: list[dict],
                *, on_collision: Callable[[dict, dict], dict] | None = None) -> list[dict]:
    """Union two row lists by `id`, preserving existing-then-new insertion order.

    A row without an `id` is dropped (can't be merged safely). On a repeated id,
    `on_collision(prior, row)` chooses the winner; with no callback the prior row wins
    (plain first-by-id) — never a silent overwrite.
    """
    by_id: dict[str, dict] = {r["id"]: r for r in existing if r.get("id")}
    for row in incoming:
        rid = row.get("id")
        if not rid:
            continue
        prior = by_id.get(rid)
        if prior is None:
            by_id[rid] = row
        elif on_collision is not None:
            by_id[rid] = on_collision(prior, row)
        # else: keep first-by-id (prior) — append-only ids don't legitimately collide
    return list(by_id.values())
