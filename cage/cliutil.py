"""Shared CLI helpers (≤50 lines)."""
from __future__ import annotations

import json as _json
from pathlib import Path

from cage import paths


def root() -> Path:
    """The project root (nearest `.cage/`) or the cwd if none has been init'd yet."""
    return paths.find_project_root() or Path.cwd()


def emit(args, payload: dict, text: str) -> int:
    """Print machine-readable JSON when ``--json`` is set, else the human text."""
    if getattr(args, "json", False):
        print(_json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0
