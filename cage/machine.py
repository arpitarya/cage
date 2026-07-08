"""Opaque machine id for the fleet study (roadmap P5, plan §4.9).

A **random** id generated once into ``.cage/state/machine.json`` — never the
hostname, username, or anything derivable from the machine (the analyst keeps
the name↔id mapping offline, on paper if they like). Once the id exists, every
ledger append stamps it as an additive optional ``machine`` field on
calls/receipts/tasks (`ledger.append_row`), giving cross-machine dedupe sanity,
per-machine coverage, and paired phase deltas.

**Opt-in by existence**: no id file ⇒ no stamping ⇒ rows stay byte-identical to
the legacy contract. The id is created by study enrollment (`cage study
join`/`start`) — a non-study ledger never grows the field. Entropy lives only
in the id itself (the same rule as `ids.new_id`); derive-time reads carry no
randomness. Read/write both fail-open — an unreadable state file just means no
stamp, never a broken append.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from cage import paths

_cache: dict[str, str] = {}  # positive hits only — a miss re-checks the file


def _file(root: Path) -> Path:
    return paths.Footprint(root).state / "machine.json"


def machine_id(root: Path) -> str:
    """This ledger's machine id, or "" when not enrolled (the legacy contract)."""
    key = str(root)
    if key in _cache:
        return _cache[key]
    try:
        f = _file(root)
        if not f.exists():
            return ""
        mid = str(json.loads(f.read_text(encoding="utf-8")).get("machine", ""))
        if mid:
            _cache[key] = mid
        return mid
    except (ValueError, OSError):  # fail-open: unreadable state ⇒ no stamp
        return ""


def ensure(root: Path) -> str:
    """The machine id, generated on first call (enrollment). Fail-open: if the
    state dir can't be written the id is "" and rows simply stay unstamped."""
    mid = machine_id(root)
    if mid:
        return mid
    mid = "m_" + secrets.token_hex(8)  # opaque — no hostname, no username, no time
    try:
        f = _file(root)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"machine": mid}) + "\n", encoding="utf-8")
        _cache[str(root)] = mid
        return mid
    except OSError:
        return ""


def stamp(root: Path, row: dict) -> dict:
    """Add ``machine`` to a row about to be appended — only when enrolled and the
    writer didn't already set it (bundle imports carry the *source* machine)."""
    if "machine" not in row:
        mid = machine_id(root)
        if mid:
            row["machine"] = mid
    return row
