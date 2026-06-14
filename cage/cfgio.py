"""Idempotent JSON + markered-text config writers shared by agent wiring (≤50 lines)."""
from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def upsert_block(path: Path, start: str, end: str, block: str, default: str = "") -> None:
    """Insert or replace a `start…end`-delimited block in a text file."""
    text = path.read_text(encoding="utf-8") if path.exists() else default
    body = f"{start}\n{block}\n{end}"
    if start in text and end in text:
        head, _, rest = text.partition(start)
        _, _, tail = rest.partition(end)
        text = head + body + tail
    else:
        text = (text.rstrip() + "\n\n" + body + "\n") if text.strip() else body + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
