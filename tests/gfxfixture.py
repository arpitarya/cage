"""Loader for the graphify store fixtures — **parse first, substitute in parsed strings.**

The fixtures pin real store records and carry a placeholder repo root that each test
rewrites to its own `tmp_path`. The obvious way to do that is a text replace on the raw
JSON before parsing, and it is wrong: on Windows `str(tmp_path)` is `C:\\Users\\…`, whose
backslashes land inside JSON string literals as **invalid escapes**, so every fixture-driven
test dies with `JSONDecodeError` — 26 of them did, in v0.47.0's CI, on Windows only
(the POSIX legs and all three graphify legs were green, which is exactly why it shipped).

So: `json.loads` first, walk the parsed object, substitute in string *values*, and
re-serialize with `json.dumps`, which escapes whatever separator the platform uses. A
fixture loaded this way cannot be broken by a path separator again.

Mixed separators in the result (`C:\\Users\\x/graphify-out/GRAPH_REPORT.md`) are deliberate
and are the *point* of the exercise — real Windows stores mix them too, and the route
normalizes with `.replace("\\\\", "/")`. Do not "tidy" them into one convention here; that
would hide the case the tests exist to cover.
"""
from __future__ import annotations

import json
from pathlib import Path

PLACEHOLDER = "/tmp/gfxrepo"


def _sub(value, root: str):
    """Recursively rewrite the placeholder inside parsed strings — never in raw JSON."""
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, root)
    if isinstance(value, dict):
        return {k: _sub(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [_sub(v, root) for v in value]
    return value


def load_json(path: Path, root: Path):
    """One JSON document (the kiro-CLI `conversations_v2.value` fixtures)."""
    return _sub(json.loads(path.read_text(encoding="utf-8")), str(root))


def load_jsonl(path: Path, root: Path) -> list[dict]:
    """The records of a JSONL fixture (the copilot VS Code `chatSessions` fixtures)."""
    return [_sub(json.loads(line), str(root))
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dump_jsonl(records: list[dict]) -> str:
    """Serialize records back to JSONL. `json.dumps` escapes the platform's separators,
    which is the whole reason this module exists."""
    return "\n".join(json.dumps(r) for r in records) + "\n"
