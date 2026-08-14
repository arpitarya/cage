"""The library adapter — `cage.meter()` / `record_call()` at the provider boundary.

Tool-agnostic and fail-open: you call it, it doesn't wrap you, and a metering
error never propagates into the request path (plan §5, §10). Records token *counts*
— never prompt bodies, and since USAGE-ONLY (ADR 0011) never a derived cost either.
A caller that already knows its own billed figure (Orff passes `est_cost_usd`) still
has it stored verbatim; cage computes none and reads none.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from cage import debuglog, ledger, paths, policy, schema


def _resolve_root(root: Path | None) -> Path:
    # Capture is global by default (§3.7): a no-project caller writes the global
    # ledger, never a stray .cage/ in whatever dir the process happens to run from.
    # `canonical_ledger` is the ONE resolver push and pull share (capture-architecture
    # §3.1) — no direct `resolve_root` in a push path — and it traces the decision
    # under CAGE_DEBUG so a stranded-saving mystery is one grep.
    return root or paths.canonical_ledger()


@lru_cache(maxsize=8)
def _policy_for(root_str: str) -> dict:
    return policy.load(paths.Footprint(Path(root_str)).policy)


@lru_cache(maxsize=8)
def _scope_for(root_str: str) -> str:
    """Best-effort `scope` (top-level changed dir) for a root, cached per process so the
    git shell-out runs once per root — never on every metered call (plan §3.6.2; the
    write-path-perf design note). Fail-open ⇒ ""; reuses `tasks.scope_for`, no new git."""
    try:
        from cage import tasks
        return tasks.scope_for(Path(root_str))
    except Exception:  # noqa: BLE001 — metering must never raise out of resolution
        return ""


def record_call(*, route: str, provider: str, model: str, tokens_in: int = 0,
                tokens_out: int = 0, cached_in: int = 0, est_cost_usd: float | None = None,
                scope: str = "", root: Path | None = None, **fields) -> str:
    """Append one call row; return its id (empty string if the write failed).

    `scope` (top-level changed dir, plan §3.6.2) is passed through when known; callers
    that don't supply it leave it "" (the legacy, non-monorepo case). `meter()` resolves
    it best-effort via `_scope_for`."""
    r = _resolve_root(root)
    # `est_cost_usd` is **accepted and stored, never computed** (USAGE-ONLY, ADR 0011).
    # The field stays on the row under the append-only law and a self-costing provider's
    # own figure is still recorded verbatim, but cage no longer derives one — there is no
    # price table left to derive it from, and no view reads it.
    row = schema.make_call(route=route, provider=provider, model=model,
                           tokens_in=tokens_in, tokens_out=tokens_out,
                           cached_in=cached_in,
                           est_cost_usd=0.0 if est_cost_usd is None else est_cost_usd,
                           scope=scope, **fields)
    ok = ledger.append_row(r, "calls", row)
    _record_consumer_twin(r, row, route=route, provider=provider, model=model,
                          tokens_in=tokens_in, tokens_out=tokens_out,
                          cached_in=cached_in, scope=scope, call_ok=ok, **fields)
    return row["id"] if ok else ""


def _record_consumer_twin(root: Path, call_row: dict, *, route: str, provider: str,
                          model: str, tokens_in: int, tokens_out: int, cached_in: int,
                          scope: str, call_ok: bool, **fields) -> None:
    """The consumer half of `record_call`'s **dual write** (P1, v0.51).

    Every producer now owns one directory under `ledger/`, and this is the consumer's:
    `ledger/consumer/calls-<month>.jsonl`. It reverses
    [ADR-CONSUMERS](../docs/adr/0006_consumer.md)'s *"never given a metric ledger"*, which
    is recorded there rather than contradicted quietly.

    **Dual-write, never a cutover, and that is not caution — it is the rollback.** The
    `calls` row is still written unchanged: it is what `ledger.join_table` resolves a
    receipt's `call=` against, and it is what remains if this kind is ever withdrawn.
    Reverting P1 is deleting one call site, not a migration.

    **The twin carries the call row's id**, which is what lets `ledger.spend()` suppress
    exactly the dual-written rows rather than every row whose agent looks like a
    consumer's — see `ledger.consumer_twin_calls` for why that distinction is the whole
    safety argument.

    **A failed `calls` write still writes the twin, with no `call` link.** The usage
    happened either way and a metering path never discards a measured fact to keep two
    stores tidy; an unlinked twin simply suppresses nothing.

    Fail-open **absolutely** — this runs inside a caller's request path, and
    ADR-CONSUMERS makes never-raising-into-a-request an *invariant*, not a policy. Any
    failure is swallowed and traced under `CAGE_DEBUG` (fail-open but never silent)."""
    try:
        twin = schema.make_consumer_metric(
            route=route, provider=provider, model=model,
            call=call_row.get("id", "") if call_ok else "",
            agent=fields.get("agent", "lib") or "lib",
            session=fields.get("session", ""), task=fields.get("task", ""),
            project=fields.get("project", ""), scope=scope,
            tokens_in=tokens_in, tokens_out=tokens_out, cached_in=cached_in,
            cache_write_in=fields.get("cache_write_in", 0),
            latency_ms=fields.get("latency_ms", 0), ok=fields.get("ok", True),
            retries=fields.get("retries", 0), import_id=fields.get("import_id", ""),
            machine=fields.get("machine", ""), ts=call_row.get("ts"))
        if not ledger.append_row(root, "consumer", twin):
            debuglog.event(root, event="consumer-metric", produced=False,
                           skip_reason="append-failed", call=call_row.get("id", ""))
    except Exception as exc:  # noqa: BLE001 — metering never raises into a request path
        debuglog.event(root, event="consumer-metric", produced=False,
                       skip_reason=f"{type(exc).__name__}: {exc}")


def record_receipt(*, tool: str, raw_alternative: float, actual: float,
                   call: str = "", task: str = "", scope: str = "",
                   root: Path | None = None, **fields) -> str:
    """Append one savings receipt; return its id (empty string on failure)."""
    r = _resolve_root(root)
    # Stamp the non-PII project routing key on every pushed receipt (graphify/fux/proxy)
    # so a read can reclaim a stray saving by exact key (capture-architecture §9.6).
    # Additive: a caller that already passed `route_key` in **fields wins.
    fields.setdefault("route_key", paths.routing_key(r))
    row = schema.make_receipt(tool=tool, raw_alternative=raw_alternative, actual=actual,
                              call=call, task=task, scope=scope, **fields)
    ok = ledger.append_row(r, "receipts", row)
    debuglog.event(r, event="receipt", tool=tool, produced=bool(ok),
                   skip_reason="" if ok else "push-sink-unresolved")
    return row["id"] if ok else ""


@dataclass
class Recorder:
    """Mutable handle yielded by `meter()` — fill it in inside the block."""
    route: str
    task: str = ""
    session: str = ""
    agent: str = "lib"
    provider: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cached_in: int = 0
    ok: bool = True
    retries: int = 0
    root: Path | None = None
    call_id: str = field(default="", init=False)

    def usage(self, *, provider: str, model: str, tokens_in: int, tokens_out: int,
              cached_in: int = 0) -> "Recorder":
        self.provider, self.model = provider, model
        self.tokens_in, self.tokens_out, self.cached_in = tokens_in, tokens_out, cached_in
        return self


@contextmanager
def meter(route: str, *, task: str = "", session: str = "", agent: str = "lib",
          root: Path | None = None):
    """Time a call and record it on exit. Fail-open — never raises out of cleanup."""
    rec = Recorder(route=route, task=task, session=session, agent=agent, root=root)
    t0 = time.monotonic()
    try:
        yield rec
    except Exception:
        rec.ok = False
        raise
    finally:
        try:
            latency_ms = int((time.monotonic() - t0) * 1000)
            if rec.provider:
                rec.call_id = record_call(
                    route=rec.route, provider=rec.provider, model=rec.model,
                    tokens_in=rec.tokens_in, tokens_out=rec.tokens_out,
                    cached_in=rec.cached_in, task=rec.task, session=rec.session,
                    agent=rec.agent, latency_ms=latency_ms, ok=rec.ok,
                    retries=rec.retries, scope=_scope_for(str(_resolve_root(rec.root))),
                    root=rec.root)
        except Exception as e:  # noqa: BLE001 — fail-open: metering must never raise out of cleanup
            # ADD-only (not a rewrite): make the swallow reachable under CAGE_DEBUG
            # instead of truly silent. The trace is itself fully guarded so it can
            # never break the metered call — the no-raise guarantee stays absolute.
            try:
                from cage import debuglog  # local import keeps the hot path import-light
                debuglog.exception(_resolve_root(rec.root), "meter.record", e)
            except Exception:  # noqa: BLE001 — even tracing must never break a metered call
                pass
