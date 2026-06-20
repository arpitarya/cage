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

from cage import agents, ledger, paths, policy, schema

_OK, _WARN, _FAIL = "ok", "warn", "fail"
_RANK = {_OK: 0, _WARN: 1, _FAIL: 2}


def _tool() -> tuple[str, str]:
    if not shutil.which("cage"):
        return _WARN, "`cage` not on PATH (running, but not globally callable)"
    from cage import __version__
    return _OK, f"cage {__version__} on PATH"


def _footprint(root: Path) -> tuple[str, str]:
    if not (root / ".cage").is_dir():
        return _FAIL, "no .cage/ — run `cage adopt` (or `cage init`)"
    return _OK, f".cage/ present at {root / '.cage'}"


def _policy(root: Path) -> tuple[str, str]:
    try:
        pol = policy.load(paths.Footprint(root).policy)
        return _OK, f"policy loads ({len(pol.get('prices', {}))} model prices)"
    except Exception as exc:  # noqa: BLE001 — surface the parse error, don't raise
        return _FAIL, f"policy.toml failed to load: {exc}"


def _hooks(root: Path) -> tuple[str, str]:
    wired = [s for s, on in agents.status(root).items() if on]
    if not wired:
        return _WARN, "no agent hooks wired — `cage adopt` or `cage hooks install`"
    return _OK, f"metering hooks wired: {', '.join(wired)}"


def _interceptor(root: Path) -> tuple[str, str]:
    shim = root / "bin" / "graphify"
    if not shim.exists():
        return _WARN, "graphify interceptor not installed (ok if you don't use graphify)"
    import os
    on_path = str(shim.parent) in os.environ.get("PATH", "").split(os.pathsep)
    if not on_path:
        return _WARN, "bin/graphify exists but bin/ is not on PATH (open a new shell)"
    return _OK, "graphify interceptor installed and on PATH"


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
    """Run every check; return {status, checks:[{name, level, detail}]}."""
    checks = [
        ("tool", *_tool()),
        ("footprint", *_footprint(root)),
        ("policy", *_policy(root)),
        ("hooks", *_hooks(root)),
        ("interceptor", *_interceptor(root)),
        ("ledger", *_ledger_roundtrip()),
    ]
    rows = [{"name": n, "level": lv, "detail": d} for n, lv, d in checks]
    status = max((r["level"] for r in rows), key=lambda lv: _RANK[lv])
    return {"status": status, "checks": rows}
