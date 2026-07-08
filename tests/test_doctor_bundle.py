"""`cage doctor --bundle` — one redacted, counts-never-content diagnostics archive."""
from __future__ import annotations

import json
import zipfile
from types import SimpleNamespace

import pytest

from cage import clicmds, doctorbundle, importcmd
from cage.errors import CageError

ALWAYS = {"manifest.json", "doctor.txt", "doctor.json", "version.txt",
          "footprint.txt", "policy-provenance.txt"}
STATE = {"state/debug.log", "state/hooks-seen.jsonl", "state/cursors.json"}

# Content-bearing markers that must never appear anywhere in the bundle — the
# fixture transcript deliberately plants them upstream of capture.
PII_MARKERS = (b"content stripped", b'"prompt"', b'"raw_alternative"')


def _seeded_root(tmp_path, monkeypatch, debug: bool):
    (tmp_path / ".cage").mkdir()
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    if debug:
        monkeypatch.setenv("CAGE_DEBUG", "1")
    home = tmp_path / "home-claude_config_dir" / "projects" / "p"
    home.mkdir(parents=True)
    home.joinpath("s.jsonl").write_text(json.dumps(
        {"type": "assistant", "uuid": "u1", "timestamp": "2026-06-14T10:00:00Z",
         "message": {"model": "claude-opus-4-8",
                     "content": [{"type": "text", "text": "[content stripped]"}],
                     "usage": {"input_tokens": 100, "output_tokens": 50}}}) + "\n",
        encoding="utf-8")
    importcmd.run(tmp_path, "claude", SimpleNamespace(path=None, project=None, since=None))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_bundle_members_and_manifest(tmp_path, monkeypatch):
    root = _seeded_root(tmp_path, monkeypatch, debug=True)
    out = doctorbundle.run(root, str(tmp_path / "b.zip"))
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert ALWAYS <= names
        assert STATE <= names  # debug on → log + heartbeat + cursors all captured
        manifest = json.loads(zf.read("manifest.json"))
        assert set(manifest["included"]) == names - {"manifest.json"}
        assert manifest["skipped"] == {}
        foot = zf.read("footprint.txt").decode("utf-8")
        assert "1 row(s)" in foot and "calls-2026-06.jsonl" in foot  # counts, never bodies
        prov = zf.read("policy-provenance.txt").decode("utf-8")
        assert "bundled default" in prov and "CLAUDE_CONFIG_DIR" in prov


def test_bundle_is_counts_never_content(tmp_path, monkeypatch):
    root = _seeded_root(tmp_path, monkeypatch, debug=True)
    out = doctorbundle.run(root, str(tmp_path / "b.zip"))
    with zipfile.ZipFile(out) as zf:
        blob = b"".join(zf.read(n) for n in zf.namelist())
    for marker in PII_MARKERS:
        assert marker not in blob


def test_bundle_redacts_the_home_prefix(tmp_path, monkeypatch):
    # Absolute paths are diagnostic signal, but the username inside $HOME is identity
    # the bundle doesn't need — every member renders the home prefix as `~`
    # (2026-07 manual validation finding #12).
    from pathlib import Path
    root = _seeded_root(tmp_path, monkeypatch, debug=True)
    out = doctorbundle.run(root, str(tmp_path / "b.zip"))
    home = str(Path.home()).encode("utf-8")
    with zipfile.ZipFile(out) as zf:
        for n in zf.namelist():
            assert home not in zf.read(n), f"home prefix leaked in {n}"


def test_bundle_absent_state_is_skipped_with_reason(tmp_path, monkeypatch):
    root = _seeded_root(tmp_path, monkeypatch, debug=False)  # no debug → no state files
    out = doctorbundle.run(root, str(tmp_path / "b.zip"))
    with zipfile.ZipFile(out) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert "state/debug.log" in manifest["skipped"]  # reasoned, not silently missing


def test_bundle_unwritable_target_raises_cage_error(tmp_path, monkeypatch):
    root = _seeded_root(tmp_path, monkeypatch, debug=False)
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    with pytest.raises(CageError, match="cannot write bundle"):
        doctorbundle.run(root, str(blocker / "b.zip"))  # parent is a file


def test_bundle_bytes_deterministic(tmp_path, monkeypatch):
    # Fixed zip epoch + fixed member order: same inputs ⇒ same archive bytes.
    # Doctor's human "(N ago)" ages are pinned so a second-boundary between the
    # two runs can't flake the comparison (the ages are presentation, not data).
    monkeypatch.setattr("cage.render.ago", lambda ts: "(pinned ago)")
    monkeypatch.setattr("cage.doctorcmd._ago", lambda ts: "(pinned ago)")
    root = _seeded_root(tmp_path, monkeypatch, debug=False)
    a = doctorbundle.run(root, str(tmp_path / "a.zip")).read_bytes()
    b = doctorbundle.run(root, str(tmp_path / "b.zip")).read_bytes()
    assert a == b


def test_cli_doctor_bundle_flag(tmp_path, monkeypatch, capsys):
    _seeded_root(tmp_path, monkeypatch, debug=False)
    rc = clicmds.cmd_doctor(SimpleNamespace(json=False, bundle=str(tmp_path / "cli.zip")))
    out = capsys.readouterr().out
    assert "diagnostics bundle written" in out and (tmp_path / "cli.zip").exists()
    assert rc in (0, 1)  # doctor's own status codes unchanged by the flag
