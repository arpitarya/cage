"""`cage authorship verify` — a deterministic consistency pass over the provenance buffer
(plan §3.5). **Report-only by design**: this command always exits 0. It is meant
to be wired into CI for visibility, never as a gate — see the hard constraint
"cage authorship verify is report-only, never fails the build".
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from cage import originrecord, schema


def _commit_exists(root: Path, sha: str) -> bool:
    try:
        subprocess.run(("git", "-C", str(root), "cat-file", "-e", sha),
                       capture_output=True, timeout=5, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def run(root: Path) -> dict:
    """`{"warnings": [str, ...]}` — never raises, never reflects a "fail" status.

    v2: a `--strict` flag that exits non-zero could make this CI-gateable; v1
    deliberately never does (cage law: report-only, never blocks the build).
    """
    warnings: list[str] = []
    try:
        rows = originrecord.read_all(root)
    except Exception:  # noqa: BLE001 — verify must never itself break
        return {"warnings": ["could not read the provenance ledger"]}

    for row in rows:
        sha = row.get("sha", "")
        if sha and not _commit_exists(root, sha):
            warnings.append(f"{row.get('id')}: sha {sha!r} not found in this repo's git log")
        if row.get("origin") == "human" and row.get("method") != "heuristic":
            warnings.append(f"{row.get('id')}: origin='human' outside an attestation "
                            f"(method={row.get('method')!r}, expected 'heuristic')")
        method = row.get("method")
        if method not in schema.PROV_METHODS:
            warnings.append(f"{row.get('id')}: unknown method {method!r}")
    return {"warnings": warnings}
