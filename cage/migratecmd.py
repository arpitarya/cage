"""`cage data migrate-savings` — consolidate historical graphify receipts into the
dedicated savings tree, precisely (import-ledger plan §3, revised 2026-07-25).

The problem: graphify savings used to land in the shared `receipts.jsonl`; they now belong
in `savings/graphify/`. The bar Arpit set is **NOT WRONG, NOT DUPLICATED** — the migration
must never lose a saving dollar and never count one twice.

The mechanism, all three parts load-bearing:

1. **Copy, never move.** Historical `tool=="graphify"` rows are *copied* from
   `receipts.jsonl` into `savings/graphify/`, each into the month shard chosen from its
   **own `ts`**, keeping its **original row id**. `receipts.jsonl` is never rewritten — the
   only ledger mutation is append (the append-only law).
2. **Read-side dedupe.** `ledger.receipts()` is an id-deduped union (`mergeutil.union_by_id`,
   tree wins), so a row now present in both stores is read exactly once. This is what makes
   the number exact under an idempotent re-run, a half-completed migration, or a crash
   mid-copy.
3. **Reconciliation gate.** Dry-run by default (prints per-store row count + Σ`saved` and
   exactly what would copy); `--apply` **refuses** when the stores disagree — an id in both
   with a different `saved` — because then the totals cannot reconcile and a copy would be a
   guess. graphify only: human/fux rows stay in `receipts.jsonl` until their sources get
   tree dirs.

Migration never edits a row (method/confidence/fields are preserved) — it only relocates a
verbatim copy. Typed `CageError` at the CLI boundary; the underlying `ledger.append_row` is
fail-open, so a partial write is caught and reported (and safe to re-run — idempotent).
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger
from cage.errors import CageError

_TOOL = "graphify"  # the only source with a tree dir today (plan §3 scope)


def _saved(row: dict) -> float:
    try:
        return float(row.get("saved", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def plan(root: Path) -> dict:
    """The reconciliation analysis — pure, no writes. Compares the legacy `receipts.jsonl`
    graphify rows against the `savings/graphify/` tree and reports what a `--apply` would
    copy, plus any **conflict** (an id in both stores with a different `saved`) that blocks
    a safe migration."""
    legacy = [r for r in ledger.read_kind(root, "receipts") if r.get("tool") == _TOOL]
    tree = [r for r in ledger.savings(root) if r.get("tool") == _TOOL]
    tree_by_id = {r["id"]: r for r in tree if r.get("id")}

    to_copy: list[dict] = []
    conflicts: list[str] = []
    overlap = 0
    idless = 0
    for r in legacy:
        rid = r.get("id")
        if not rid:
            idless += 1  # an id-less row can't be merged by identity — it stays put, still read
            continue
        t = tree_by_id.get(rid)
        if t is None:
            to_copy.append(r)
        else:
            overlap += 1
            if _saved(t) != _saved(r):
                conflicts.append(rid)

    # The union total is what `ledger.receipts()` reports: distinct graphify ids, tree wins.
    union: dict[str, dict] = {}
    for r in legacy + tree:
        rid = r.get("id")
        if rid:
            union[rid] = r if rid not in tree_by_id else tree_by_id[rid]  # tree wins on dup
    return {
        "tool": _TOOL,
        "legacy_count": len(legacy), "legacy_saved": sum(_saved(r) for r in legacy),
        "tree_count": len(tree), "tree_saved": sum(_saved(r) for r in tree),
        "overlap": overlap, "idless": idless,
        "to_copy": to_copy,
        "to_copy_count": len(to_copy), "to_copy_saved": sum(_saved(r) for r in to_copy),
        "union_count": len(union), "union_saved": sum(_saved(r) for r in union.values()),
        "conflicts": conflicts,
    }


def apply(root: Path) -> dict:
    """Execute the migration: copy each not-yet-migrated legacy graphify row **verbatim**
    (original id, own-`ts` shard) into `savings/graphify/`. Refuses on a reconciliation
    conflict; verifies the union total is unchanged afterward. Returns the plan dict plus
    ``copied``."""
    p = plan(root)
    if p["conflicts"]:
        raise CageError(
            f"refusing --apply: {len(p['conflicts'])} {_TOOL} id(s) are in both "
            f"receipts.jsonl and savings/{_TOOL}/ with a different `saved` value "
            f"({', '.join(p['conflicts'][:3])}{'…' if len(p['conflicts']) > 3 else ''}). "
            "The stores disagree, so the totals cannot reconcile — resolve by hand; "
            "no rows were copied.")
    before_union = p["union_saved"]
    copied = 0
    for r in p["to_copy"]:
        # A verbatim copy keeps id / ts / method / confidence / every field; append_row
        # picks the month shard from the row's own ts and (if enrolled) stamps `machine`.
        if ledger.append_row(root, ("savings", _TOOL), dict(r)):
            copied += 1
    if copied != p["to_copy_count"]:
        raise CageError(
            f"migration incomplete: copied {copied} of {p['to_copy_count']} {_TOOL} row(s) "
            "(ledger not fully writable?). Safe to re-run — the copy is idempotent (id-deduped).")
    after = plan(root)
    if abs(after["union_saved"] - before_union) > 1e-6:
        raise CageError(  # never expected — verbatim same-id copies leave the union invariant
            "migration reconciliation failed: the union total changed "
            f"({before_union:g} → {after['union_saved']:g}). This is a bug — re-run is safe "
            "(id-deduped), but the discrepancy must be investigated.")
    p["copied"] = copied
    return p


def _fmt(n: float) -> str:
    return f"{int(n):,}" if float(n).is_integer() else f"{n:,.2f}"


def render(p: dict, *, applied: bool) -> str:
    """The dry-run / apply text (house dry-run pattern). Counts + Σ`saved` for both stores,
    the overlap, and what would copy / was copied. `saved` is summed in the rows' own unit
    (graphify is tokens)."""
    tool = p["tool"]
    lines: list[str] = []
    head = (f"migrate-savings — copied {p.get('copied', 0)} {tool} row(s)"
            if applied else "migrate-savings — dry run (no changes written)")
    lines.append(head)
    lines.append("")
    lines.append(f"  {'store':<22} {'rows':>6}   Σ saved")
    lines.append(f"  {'receipts.jsonl':<22} {p['legacy_count']:>6}   {_fmt(p['legacy_saved'])}")
    lines.append(f"  {'savings/'+tool+'/':<22} {p['tree_count']:>6}   {_fmt(p['tree_saved'])}")
    lines.append(f"  {'─ overlap (same id)':<22} {p['overlap']:>6}")
    verb = "copied" if applied else "would copy"
    lines.append(f"  {'─ '+verb:<22} {p.get('copied', p['to_copy_count']):>6}   {_fmt(p['to_copy_saved'])}")
    lines.append(f"  {'─ union (post-migrate)':<22} {p['union_count']:>6}   {_fmt(p['union_saved'])}"
                 "   ← what `cage insights attrib` reads (unchanged)")
    if p["idless"]:
        lines.append(f"  ({p['idless']} legacy {tool} row(s) carry no id — left in receipts.jsonl, still read)")
    lines.append("")
    if applied:
        lines.append(f"✔ receipts.jsonl unchanged (append-only); original ids kept, sharded by ts.")
        if not p.get("copied"):
            lines.append("  nothing to copy — already migrated (idempotent).")
    else:
        if p["to_copy_count"]:
            lines.append(f"run with --apply to copy {p['to_copy_count']} {tool} row(s) into "
                         f"savings/{tool}/. receipts.jsonl is never rewritten.")
        else:
            lines.append("nothing to migrate — already consolidated (or no legacy graphify rows).")
    return "\n".join(lines)


def run_cli(root: Path, *, do_apply: bool) -> tuple[dict, str]:
    """CLI entry: dry-run by default, `--apply` executes. Returns (payload, text)."""
    p = apply(root) if do_apply else plan(root)
    payload = {k: v for k, v in p.items() if k != "to_copy"}  # drop the raw row list from JSON
    return payload, render(p, applied=do_apply)
