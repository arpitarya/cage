"""The capture manifest — `imports.jsonl` (import-ledger plan §4).

One append-only audit row per import sweep (per agent×surface) and per graphify run,
answering "what did cage capture, when, from where, and how much?" for both the pull
(import) and push (graphify) paths. Deliberately a **separate** file from the
git-authorship `provenance.jsonl` (which answers a different question — who wrote which
files); overloading it would blur two record types.

PII: `source_path` is tilde-relative (`importcmd._tilde`, strips $HOME/username) and
counts-only — never absolute, never file contents. An import sweep emits **one row per
(agent, surface, session)** it captured (ADR-CONSUMERS): each row carries the log's `session`
id, a cage-minted `session_uid` (a `n_…` id unique to this manifest row, distinct from
the sweep-wide `import_id` FK), and the best-available `session_name` — **always**
captured now (the earlier `[capture] session_names` opt-in is gone). Name lifting:
claude ← the transcript `summary` record (fallback the cwd basename / `project`);
copilot VS Code ← the chat `customTitle`/`generatedTitle`; copilot CLI / kiro ← `""`
(honest empty, never a session id as a name). A name is user-authored prose — a
deliberate, recorded PII widening for THIS local audit file only (ADR-CLI); it never
touches a call/receipt/savings row and is never read by a derived view. The graphify
row's `session` is the task (already a validated cwd basename), and its name = that task.

Never read by any derived view — it is an audit trail, so it never changes a reported
number. Fail-open on every write: a manifest error is traced under CAGE_DEBUG and
swallowed, never raised into the capture path.

**The one scoped carve-out (chats-view proposal):** `imports.jsonl` is never read by a
derived **money** view; `cage insights chats` joins `session_name` for **display labels
only** — every numeric cell derives from ledger + policy alone (pinned by
`tests/test_chats.py`'s money-independence test: deleting this file changes zero
numeric cells, only labels fall back to session ids).
"""
from __future__ import annotations

from pathlib import Path

from cage import debuglog, ids


def new_import_id() -> str:
    """A fresh per-sweep import id (`i_…`) minted once per `importcmd.run` and threaded
    onto every call row that sweep appends (the FK back to this manifest row)."""
    return ids.new_id("i")


def new_graphify_id() -> str:
    return ids.new_id("g")


def new_session_uid() -> str:
    """A fresh per-manifest-row session id (`n_…`) — the "separate unique id" every named
    session gets, distinct from the sweep-wide `import_id`. Minted once per (agent,
    surface, session) manifest row so a captured session is individually addressable."""
    return ids.new_id("n")


def _append(root: Path, row: dict) -> bool:
    import json

    from cage import __version__
    row.setdefault("cage_version", __version__)
    foot_imports = _imports_path(root)
    try:
        foot_imports.parent.mkdir(parents=True, exist_ok=True)
        with foot_imports.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        return True
    except OSError as e:
        try:
            debuglog.exception(root, "manifest.append", e)
        except Exception:  # noqa: BLE001
            pass
        return False


def _imports_path(root: Path) -> Path:
    from cage import paths
    return paths.Footprint(root).imports


def record_import(root: Path, *, import_id: str, agent: str, surface: str,
                  session: str, session_uid: str, source_path: str, files_scanned: int,
                  rows_appended: int, tokens_in: int, tokens_out: int, cached_in: int,
                  ts: str, session_name: str = "") -> bool:
    """One manifest row per (agent, surface, session) an import sweep captured rows from
    (ADR-CONSUMERS). `session` is the log's own session id; `session_uid` is the cage-minted
    `n_…` id unique to this row; `session_name` is the best-available human name (``""``
    when the log carries none — honest, never fabricated). Fail-open."""
    row = {"kind": "import", "import_id": import_id, "session_uid": session_uid,
           "ts": ts, "agent": agent, "surface": surface, "session": session,
           "source_path": source_path, "files_scanned": int(files_scanned),
           "rows_appended": int(rows_appended), "tokens_in": int(tokens_in),
           "tokens_out": int(tokens_out), "cached_in": int(cached_in)}
    if session_name:
        row["session_name"] = session_name
    return _append(root, row)


def record_graphify(root: Path, *, import_id: str, op: str, session: str,
                    source_path: str, saving_id: str, saved: float, source_files: int,
                    ts: str, session_name: str = "") -> bool:
    """One manifest row per graphify run that filed a saving. `session` is the task
    (cwd basename); `source_path` is the out-dir / cited-file root (count-safe). Fail-open."""
    row = {"kind": "graphify", "import_id": import_id, "ts": ts, "tool": "graphify",
           "op": op, "session_id": session, "source_path": source_path,
           "saving_id": saving_id, "saved": round(float(saved), 6),
           "source_files": int(source_files)}
    if session_name:
        row["session_name"] = session_name
    return _append(root, row)


def read(root: Path) -> list[dict]:
    """Every manifest row (import + graphify) from **both homes**, oldest first.

    P3a (v0.51) moved the manifest from `ledger/imports.jsonl` to `state/imports.jsonl`.
    The legacy file is read first (it is strictly older) and is **never written, migrated
    or deleted** — every real install has rows there, and dropping them would make each
    existing chat title silently fall back to a session id.

    Rows are not deduped across the two: they are disjoint by construction (the old file
    stopped being appended to the moment the new one started), and an id-dedupe here would
    be machinery guarding an event that cannot occur. Tolerates a truncated tail in either."""
    from cage import ledger, paths
    foot = paths.Footprint(root)
    rows = ledger.read(foot.imports_legacy)
    rows.extend(ledger.read(foot.imports))
    return rows
