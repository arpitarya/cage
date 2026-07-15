"""`cage authorship origin <sha>` — read surface for authorship attribution (plan §3.5).

`origin="unknown"` is a **read-time default**, never a written row: a sha with no
provenance fragment anywhere (local buffer or `refs/notes/cage-provenance`) simply
has no row, and `explain()` reports unknown by *absence*, not by materializing a
row into the ledger. The only way `origin="human"` is ever written is through
`attest()` — explicit, human-initiated triage — never an automatic default.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from cage import originrecord, render, schema
from cage.constants import DEFAULT_CONFIDENCE


def _resolve_sha(root: Path, sha: str) -> str:
    """`HEAD` (or any rev) → its short sha, so `cage authorship origin HEAD` matches the short
    shas recorded by `originrecord` (fail-open: returns the input unresolved)."""
    try:
        out = subprocess.run(("git", "-C", str(root), "rev-parse", "--short", sha),
                             capture_output=True, text=True, timeout=5, check=True)
        return out.stdout.strip() or sha
    except (OSError, subprocess.SubprocessError):
        return sha


def explain(root: Path, sha: str) -> dict:
    """All recorded rows for `sha`, plus a derived top-line `origin`/`confidence`/
    `method` summary. No rows anywhere ⇒ the unknown default, never written back."""
    resolved = _resolve_sha(root, sha)
    rows = originrecord.for_sha(root, resolved)
    if not rows:
        return {"sha": resolved, "origin": "unknown", "confidence": 0.0,
               "method": None, "rows": []}
    best = max(rows, key=lambda r: r.get("confidence", 0.0))
    return {"sha": resolved, "origin": best.get("origin", "unknown"),
           "confidence": best.get("confidence", 0.0), "method": best.get("method"),
           "rows": rows}


def render_origin(data: dict) -> str:
    head = f"{data['sha']}  ·  origin={data['origin']}  ·  confidence={data['confidence']}"
    if not data["rows"]:
        return head + "\n\n  (no provenance recorded — unknown by absence, not a stored row)"
    rows = [[r.get("agent") or "—", ", ".join(r.get("files", [])), r.get("method", ""),
            r.get("origin", ""), f"{r.get('confidence', 0.0):.2f}"] for r in data["rows"]]
    body = render.table(["agent", "files", "method", "origin", "confidence"], rows)
    return head + "\n\nProvenance rows\n" + body


def attest(root: Path, sha: str, *, origin: str, agent: str = "") -> str:
    """Human-triage path: a person asserts this sha's origin. Always
    `method="heuristic"` (no automated signal fired — a person looked at it) and a
    fixed, policy-overridable low confidence. Attesting `origin="unknown"` is a
    no-op — unknown isn't a fact worth writing, it's the absence of one.

    Returns a status: ``"recorded"`` (a row was written), ``"invalid-origin"``
    (unknown / not in the enum), ``"no-diff"`` (sha not found or empty diff), or
    ``"already-attested"`` (an attestation already covers this sha+agent — the
    append-only ledger won't shadow it). The truthiness of the status maps to the
    old bool contract: only ``"recorded"`` is truthy as a written-a-row signal,
    so callers can still branch on it, while the distinct strings let the CLI
    report *why* a no-op happened instead of guessing."""
    if origin == "unknown" or origin not in schema.ORIGINS:
        return "invalid-origin"
    resolved = _resolve_sha(root, sha)
    files = [f for f, _, _ in originrecord.commit_numstat(root, resolved)]
    if not files:
        return "no-diff"  # sha not found / no diff — nothing to attest against
    # The append-only dedup key omits `origin`, so a prior heuristic attestation
    # on this (sha, agent) would silently shadow a new one — surface it instead.
    prior = [r for r in originrecord.for_sha(root, resolved)
             if r.get("method") == "heuristic" and (r.get("agent") or "") == (agent or "")]
    if prior:
        return "already-attested"
    conf = DEFAULT_CONFIDENCE["estimated"]
    ok = originrecord.record(root, sha=resolved, files=files, agent=agent,
                             method="heuristic", origin=origin, confidence=conf)
    return "recorded" if ok else "no-diff"
