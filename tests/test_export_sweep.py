"""Export imports everything first (plan §3.7): sweep-then-emit, flag/policy
precedence, fail-open sweep, and the bundle manifest's refresh record."""
from __future__ import annotations

import json
import zipfile

import pytest

from cage import cli, exportcmd, importcmd, ledger, schema, study
from cage.paths import Footprint


@pytest.fixture
def root(proj, monkeypatch):
    (proj / ".cage").mkdir()
    monkeypatch.chdir(proj)
    return proj


def _seed(root):
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8", tokens_in=10,
        ts="2026-07-01T00:00:00Z", call_id="c_e1"))


def test_export_sweeps_all_agents_even_with_agent_filter(root, monkeypatch, capsys):
    _seed(root)
    swept = []
    monkeypatch.setattr(importcmd, "run",
                        lambda r, agent, args: swept.append(agent) or [])
    assert cli.main(["export", "--agent", "claude", "--format", "jsonl"]) == 0
    # --agent filters the OUTPUT; the sweep is always the full all-agent pass.
    assert swept == ["all"]
    out = capsys.readouterr().out
    assert "c_e1" not in out  # claude filter excludes the lib-agent row


def test_no_import_flag_and_policy_toggle_skip_sweep(root, monkeypatch, capsys):
    _seed(root)
    swept = []
    monkeypatch.setattr(importcmd, "run",
                        lambda r, agent, args: swept.append(agent) or [])
    assert cli.main(["export", "--no-import"]) == 0
    assert swept == []
    Footprint(root).policy.write_text("[capture]\nimport_before_export = false\n",
                                      encoding="utf-8")
    assert cli.main(["export"]) == 0
    assert swept == []
    capsys.readouterr()


def test_export_json_carries_refresh_object(root, monkeypatch, capsys):
    _seed(root)
    monkeypatch.setattr(importcmd, "run", lambda r, agent, args: [])
    assert cli.main(["export", "--format", "json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["refresh"] == {"ran": True, "new_calls": 0}
    assert d["total"]["calls"] == 1


def test_sweep_failure_is_fail_open(root, monkeypatch, capsys):
    _seed(root)
    def boom(r, agent, args):
        raise RuntimeError("broken parser")
    monkeypatch.setattr(importcmd, "run", boom)
    assert cli.main(["export", "--format", "jsonl"]) == 0
    cap = capsys.readouterr()
    assert "c_e1" in cap.out                       # export still emitted the ledger
    assert "import refresh failed" in cap.err      # and said why, on stderr


def test_study_bundle_manifest_records_refresh(root, monkeypatch, capsys):
    _seed(root)
    monkeypatch.setattr(importcmd, "run", lambda r, agent, args: [])
    out = root / "bundle.zip"
    assert cli.main(["export", "--study", str(out)]) == 0
    assert "self-refreshed: +0 call(s)" in capsys.readouterr().out
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["refresh"] == {"ran": True, "new_calls": 0}
    # --no-import → snapshot, and the manifest says so
    out2 = root / "bundle2.zip"
    assert cli.main(["export", "--study", str(out2), "--no-import"]) == 0
    assert "snapshot only" in capsys.readouterr().out
    with zipfile.ZipFile(out2) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["refresh"] == {"ran": False, "new_calls": 0}


def test_import_bundles_surfaces_sweep_tag(root, tmp_path, capsys):
    _seed(root)
    bundle = tmp_path / "b.zip"
    study.export_bundle(root, str(bundle), refresh={"ran": True, "new_calls": 7})
    analysis = tmp_path / "analysis"
    (analysis / ".cage").mkdir(parents=True)
    lines = study.import_bundles(analysis, [str(bundle)])
    assert "swept +7 at export" in lines[0]


def test_bundle_bytes_deterministic_under_no_import(root):
    _seed(root)
    a, b = root / "a.zip", root / "b.zip"
    study.export_bundle(root, str(a), refresh={"ran": False, "new_calls": 0})
    study.export_bundle(root, str(b), refresh={"ran": False, "new_calls": 0})
    assert a.read_bytes() == b.read_bytes()
