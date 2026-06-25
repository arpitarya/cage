"""The library adapter — `cage.meter()` / `record_call()` at the provider boundary.

Tool-agnostic and fail-open: you call it, it doesn't wrap you, and a metering
error never propagates into the request path (plan §5, §10). Records token *counts*
and cost — never prompt bodies. Cost is computed from `policy.toml` when the caller
doesn't supply one (Orff already knows its cost, so it passes `est_cost_usd`).
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from cage import ledger, paths, policy, prices, schema


def _resolve_root(root: Path | None) -> Path:
    return root or paths.find_project_root() or Path.cwd()


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
    if est_cost_usd is None:
        est_cost_usd = prices.call_cost_usd(_policy_for(str(r)), provider, model,
                                            tokens_in, tokens_out, cached_in)
    row = schema.make_call(route=route, provider=provider, model=model,
                           tokens_in=tokens_in, tokens_out=tokens_out,
                           cached_in=cached_in, est_cost_usd=est_cost_usd,
                           scope=scope, **fields)
    return row["id"] if ledger.append_row(r, "calls", row) else ""


def record_receipt(*, tool: str, raw_alternative: float, actual: float,
                   call: str = "", task: str = "", scope: str = "",
                   root: Path | None = None, **fields) -> str:
    """Append one savings receipt; return its id (empty string on failure)."""
    r = _resolve_root(root)
    row = schema.make_receipt(tool=tool, raw_alternative=raw_alternative, actual=actual,
                              call=call, task=task, scope=scope, **fields)
    return row["id"] if ledger.append_row(r, "receipts", row) else ""


def record_human(*, task: str, minutes: float | None = None, usd: float | None = None,
                 task_type: str = "", rate_usd_per_hr: float | None = None,
                 call: str = "", agent: str = "", measured: bool = False,
                 root: Path | None = None) -> str:
    """Append one ``tool="human"`` Tier-1 receipt (design §5). Fail-open + idempotent.

    Re-recording the same ``(task, call)`` is a no-op (returns "") so a replayed
    outcome flow never double-counts (criterion 6). Stores the *input* (minutes /
    type / usd); USD is derived at read time by `human.py`.
    """
    r = _resolve_root(root)
    for existing in ledger.receipts(r):
        if existing.get("tool") == "human" and existing.get("task") == task \
                and existing.get("call", "") == call:
            return ""  # already recorded — idempotent, no double count
    method = "measured" if measured else "estimated"
    meta = {k: v for k, v in (("task_type", task_type), ("rate_usd_per_hr", rate_usd_per_hr),
                              ("agent", agent)) if v}
    if usd is not None:
        unit, raw = "usd", float(usd)
    elif minutes is not None:
        unit, raw = "minutes", float(minutes)
    else:
        unit, raw = "tokens", 0.0  # resolver falls to task-type table / global default
    row = schema.make_receipt(tool="human", raw_alternative=raw, actual=0.0, unit=unit,
                              call=call, task=task, method=method, meta=meta)
    return row["id"] if ledger.append_row(r, "receipts", row) else ""


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
        except Exception:
            pass
