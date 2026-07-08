"""P0 fixture corpus — `cage import` parses every agent × surface log to exact rows.

Each `tests/fixtures/transcripts/<agent>/<surface>/` dir carries a sanitized
session-log sample in the agent's real on-disk shape plus `expected.json` (the
exact call rows + plant metadata — see the corpus README). The test plants the
log into an isolated fake agent home at its real relative location, runs the
real default (pathless) `cage import` scan, and asserts the ledger rows match
byte-for-byte — ids included (they're deterministic), `ts` excluded only where
the log carries no timestamp and the row gets a write-time stamp (codex/kiro).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import agents, clicmds, ledger, paths

CORPUS = Path(__file__).parent / "fixtures" / "transcripts"
SURFACES_TESTED = ("cli", "vscode")
FIXTURES = sorted(p.parent.relative_to(CORPUS) for p in CORPUS.glob("*/*/expected.json"))


def _load(fixture: Path) -> dict:
    return json.loads((CORPUS / fixture / "expected.json").read_text(encoding="utf-8"))


def _plant(fixture: Path, spec: dict, home: Path) -> None:
    dst = home / spec["plant"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CORPUS / fixture / spec["log"], dst)


def _isolated_root(d, monkeypatch):
    (d / ".cage").mkdir(parents=True)
    # Isolate every agent home so the default (pathless) scan never reads real machine data.
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR",
                "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    monkeypatch.chdir(d)
    return d


def _comparable(rows: list[dict], volatile: list[str]) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        for v in volatile:
            assert r.pop(v), f"volatile field {v!r} missing/empty on {r.get('id')}"
        out.append(r)
    return sorted(out, key=lambda r: r["id"])


def test_corpus_covers_every_agent_and_surface():
    # The four-agent invariant, structurally: a missing fixture dir is a failure,
    # never a silently narrower parametrization.
    want = {Path(a) / s for a in agents.SURFACES for s in SURFACES_TESTED}
    assert set(FIXTURES) == want


@pytest.mark.parametrize("fixture", FIXTURES, ids=[str(f) for f in FIXTURES])
def test_import_parses_fixture_to_exact_rows(fixture, tmp_path, monkeypatch, capsys):
    agent = fixture.parts[0]
    spec = _load(fixture)
    root = _isolated_root(tmp_path, monkeypatch)
    _plant(fixture, spec, tmp_path / f"home-{spec['env'].lower()}")

    args = SimpleNamespace(agent=agent, path=None, project=None, since=None)
    assert clicmds.cmd_import(args) == 0
    assert f"✔ {agent}: imported {len(spec['rows'])} call(s)" in capsys.readouterr().out

    actual = _comparable(ledger.calls(root), spec["volatile"])
    expected = sorted(spec["rows"], key=lambda r: r["id"])
    assert actual == expected  # exact rows: ids, tokens, provider/model, session, project

    # Idempotency: a re-import (cursor + id-dedupe) leaves the shards byte-identical.
    before = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    assert clicmds.cmd_import(args) == 0
    assert b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls")) == before


def test_unverified_stand_ins_are_flagged_not_silent():
    # The three VS Code stand-ins (handoff §10) must say so in expected.json and the
    # README — an invented format masquerading as verified is worse than a gap.
    readme = (CORPUS / "README.md").read_text(encoding="utf-8")
    for fixture in FIXTURES:
        spec = _load(fixture)
        if not spec["format_verified"]:
            assert fixture.parts[1] == "vscode"  # only extension formats may be stand-ins
            assert "UNVERIFIED-FORMAT" in readme
    verified = {f.as_posix() for f in FIXTURES if _load(f)["format_verified"]}
    # Every CLI format is pinned against a real client log. (as_posix: `str(Path)`
    # renders `claude\cli` on Windows and the comparison keys must be OS-independent.)
    assert {f"{a}/cli" for a in agents.SURFACES} <= verified
