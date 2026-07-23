"""Windows/mac parity + the path-probe diagnostic (2026-07 parity pass).

POSIX behavior is field-validated and must not change; Windows branches are
additive and keyed on env presence (`APPDATA`) rather than `sys.platform`, so
they are testable on any OS. The probe is a read-only diagnostic — asserted to
write nothing.
"""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from cage import doctorbundle, importcmd, lockutil, pathprobe, paths, render


# ── per-OS path candidates: env override wins; APPDATA adds the Windows candidate ──

def test_vscode_candidates_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("CAGE_VSCODE_USER", str(tmp_path / "vs"))
    assert paths.vscode_user_candidates() == [tmp_path / "vs"]
    assert paths.vscode_user_dir() == tmp_path / "vs"


def test_vscode_candidates_include_appdata_when_set(monkeypatch, tmp_path):
    monkeypatch.delenv("CAGE_VSCODE_USER", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    cands = paths.vscode_user_candidates()
    assert cands[-1] == tmp_path / "AppData" / "Roaming" / "Code" / "User"
    # first *existing* candidate wins:
    win = tmp_path / "AppData" / "Roaming" / "Code" / "User"
    win.mkdir(parents=True)
    if not any(c.exists() for c in cands[:-1]):  # true on CI; a dev mac has the real dir
        assert paths.vscode_user_dir() == win


def test_kiro_candidates_appdata_and_override(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.delenv("KIRO_DATA_DIR", raising=False)
    tail = Path("User") / "globalStorage" / "kiro.kiroagent"
    assert paths.kiro_data_candidates()[-1] == tmp_path / "Roaming" / "Kiro" / tail
    monkeypatch.setenv("KIRO_DATA_DIR", str(tmp_path / "kd"))
    assert paths.kiro_data_candidates() == [tmp_path / "kd"]
    assert paths.kiro_token_log() == tmp_path / "kd" / "dev_data" / "tokens_generated.jsonl"


def test_agent_log_sources_covers_all_four_agents():
    from cage import agents
    for a in agents.SURFACES:
        assert paths.agent_log_sources(a), f"{a} has no registered log sources"
    assert len(paths.agent_log_sources("copilot")) == 2  # CLI + VS Code chatSessions


# ── Windows-shaped hook commands: quoting + heal-matching ──────────────────────

def test_quoted_cage_bin_quotes_paths_with_spaces(monkeypatch):
    monkeypatch.setattr(paths, "cage_bin", lambda: r"C:\Users\Foo Bar\Scripts\cage.exe")
    assert paths.quoted_cage_bin() == '"C:\\Users\\Foo Bar\\Scripts\\cage.exe"'
    monkeypatch.setattr(paths, "cage_bin", lambda: "/usr/local/bin/cage")
    assert paths.quoted_cage_bin() == "/usr/local/bin/cage"  # no spaces → unquoted


def test_reresolve_matches_windows_and_quoted_forms(monkeypatch):
    monkeypatch.setattr(paths, "cage_bin", lambda: "/resolved/cage")
    for cmd in ("cage import --agent claude",
                "/old/path/cage import --agent claude",
                r"C:\old\cage.exe import --agent claude",
                '"C:\\Program Files\\cage\\cage.exe" import --agent claude'):
        out = paths.reresolve_cage_command(cmd)
        assert out == "/resolved/cage import --agent claude", cmd
        assert paths.is_cage_import_command(cmd)
    assert paths.reresolve_cage_command("rm -rf /") is None  # foreign hooks untouched


# ── scheduler hint: printed, OS-aware, never installed ─────────────────────────

def test_scheduler_hint_is_os_aware(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    assert render.scheduler_hint().startswith("0 * * * *")
    monkeypatch.setattr(os, "name", "nt")
    assert render.scheduler_hint().startswith("schtasks /create")


# ── lockutil: one helper, fail-open on every tier ──────────────────────────────

def test_locked_serializes_and_releases(tmp_path):
    lock = tmp_path / "x.lock"
    with lockutil.locked(lock):
        assert lock.exists()
    with lockutil.locked(lock):  # re-acquirable after release
        pass


def test_locked_fail_open_without_primitive_and_calls_on_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(lockutil, "_fcntl", None)
    monkeypatch.setattr(lockutil, "_msvcrt", None)
    seen = []
    with lockutil.locked(tmp_path / "x.lock", on_miss=seen.append):
        pass  # the with-block still runs
    assert seen == [None]  # miss reported as "no primitive", not an exception


def test_locked_fail_open_on_unwritable_lock_dir(tmp_path, monkeypatch):
    seen = []
    bad = tmp_path / "nodir" / "x.lock"
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    with lockutil.locked(bad, on_miss=seen.append):
        pass
    assert len(seen) == 1 and isinstance(seen[0], OSError)


# ── the path probe: one screen of truth, writes nothing ────────────────────────

def _isolated(monkeypatch, tmp_path):
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR",
                "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    return root


def test_doctor_paths_reports_misses_with_why_lines(tmp_path, monkeypatch):
    root = _isolated(monkeypatch, tmp_path)
    monkeypatch.chdir(root)
    out = pathprobe.run(root)
    for agent in ("claude", "copilot", "kiro"):
        assert agent in out
    assert "location absent" in out                    # empty homes → why-lines
    assert "active ledger:" in out and "precedence:" in out
    assert "CAGE_VSCODE_USER: set" in out              # env override labeled


def test_doctor_paths_counts_rows_and_cursor_state(tmp_path, monkeypatch):
    root = _isolated(monkeypatch, tmp_path)
    monkeypatch.chdir(root)
    log = tmp_path / "home-kiro_data_dir" / "dev_data" / "tokens_generated.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text('{"model":"agent","provider":"kiro","promptTokens":9,"generatedTokens":0}\n')
    out = pathprobe.run(root)
    assert "1 parseable row(s)" in out and "1 not yet imported" in out
    # after a real import the cursor covers it — and the probe must not have written:
    from types import SimpleNamespace
    from cage import clicmds
    assert clicmds.cmd_import(SimpleNamespace(agent="kiro", path=None, project=None,
                                              since=None)) == 0
    before = paths.Footprint(root).cursors.read_bytes()
    out2 = pathprobe.run(root)
    assert "cursor: already imported" in out2
    assert paths.Footprint(root).cursors.read_bytes() == before   # read-only
    assert not paths.Footprint(root).debug_log.exists()           # no debug writes


def test_doctor_paths_labels_unverified_windows_kiro_layout(tmp_path, monkeypatch):
    root = _isolated(monkeypatch, tmp_path)
    monkeypatch.delenv("KIRO_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.chdir(root)
    assert "UNVERIFIED-LAYOUT" in pathprobe.run(root)


def test_bundle_includes_redacted_paths_report(tmp_path, monkeypatch):
    root = _isolated(monkeypatch, tmp_path)
    monkeypatch.chdir(root)
    out = doctorbundle.run(root, str(tmp_path / "b.zip"))
    with zipfile.ZipFile(out) as zf:
        assert "paths.txt" in zf.namelist()
        blob = zf.read("paths.txt")
    assert str(Path.home()).encode() not in blob       # finding-#12 redaction holds


def test_probe_debug_event_fires_on_import(tmp_path, monkeypatch, capsys):
    root = _isolated(monkeypatch, tmp_path)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    monkeypatch.chdir(root)
    from types import SimpleNamespace
    from cage import clicmds
    assert clicmds.cmd_import(SimpleNamespace(agent="claude", path=None, project=None,
                                              since=None)) == 0
    log = paths.Footprint(root).debug_log.read_text()
    probes = [json.loads(l) for l in log.splitlines() if '"probe"' in l]
    assert probes and probes[0]["agent"] == "claude"
    assert probes[0]["exists"] is False and probes[0]["files_matched"] == 0


def test_import_missing_source_yields_no_phantom_file(tmp_path, monkeypatch):
    # A missing source dir used to become `[src]` — a phantom candidate that parsers
    # then "parsed" to zero rows. It now scans to an empty list.
    root = _isolated(monkeypatch, tmp_path)
    files = importcmd._scan(root, "claude", tmp_path / "nope", "**/*.jsonl", None)
    assert files == []
