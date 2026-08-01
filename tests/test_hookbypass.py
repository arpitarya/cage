"""Agent hooks that reach graphify past cage's interceptor (B-fix-3).

graphify ≥0.9.30 writes its claude PreToolUse hook with an **absolute** exe path, so the
command never traverses PATH: the interceptor cannot see it, and a hook is not a Bash tool
call, so the transcript route cannot either. Both cage capture routes are blind.

The load-bearing assertion is `test_bypass_is_advisory_never_a_failure`. graphify is
working exactly as designed here — only cage's *visibility* is missing — so reporting it
at the same severity as a dead cage shim would cry failure on a correct third-party
integration, which is how a check gets ignored. `test_the_hook_is_never_modified` is the
other half: graphify owns the artifact; cage reports, explains, and stops.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import doctorcmd, hookbypass


def _claude_hook(root: Path, command: str, *, matcher: str = "Bash|Grep") -> Path:
    p = root / ".claude" / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}]}}))
    return p


def _kiro_hook(root: Path, command: str) -> Path:
    p = root / ".kiro" / "hooks" / "graphify.kiro.hook"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"name": "graphify", "version": "1", "when": {"type": "x"},
                             "then": {"type": "command", "command": command}}))
    return p


def _cage_interceptor(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n# cage: graphify metering interceptor\n"
                    'exec cage data graphify -- "$@"\n')
    path.chmod(0o755)
    return path


# ── detection ───────────────────────────────────────────────────────────────────

def test_absolute_path_hook_is_a_bypass(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPHIFY_HOOK_STRICT", raising=False)
    exe = "/opt/venv/bin/graphify"
    _claude_hook(tmp_path, f"{exe} hook-guard search")
    (found,) = hookbypass.scan(tmp_path)
    assert found.exe == exe and not found.strict
    assert "bypassed" in found.line and exe in found.line
    assert "explicit `graphify query` are unaffected" in found.line


def test_bare_name_is_not_a_bypass(tmp_path):
    """A bare `graphify` traverses PATH, so the interceptor sees it. Whether that
    interceptor is healthy is `pathshim`'s question, not this one."""
    _claude_hook(tmp_path, "graphify hook-guard search")
    assert hookbypass.scan(tmp_path) == []


def test_a_path_pointing_at_the_interceptor_is_not_a_bypass(tmp_path):
    """If the absolute path happens to BE a cage interceptor, cage sees the call after
    all — reporting it would be a false positive."""
    exe = _cage_interceptor(tmp_path / "bin" / "graphify")
    _claude_hook(tmp_path, f"{exe} hook-guard read")
    assert hookbypass.scan(tmp_path) == []


def test_cages_own_command_is_not_a_bypass(tmp_path):
    _claude_hook(tmp_path, "cage data graphify -- graphify query 'x'")
    assert hookbypass.scan(tmp_path) == []


def test_kiro_hook_files_are_covered(tmp_path):
    _kiro_hook(tmp_path, "/opt/venv/bin/graphify hook-guard search")
    (found,) = hookbypass.scan(tmp_path)
    assert found.artifact == ".kiro/hooks/graphify.kiro.hook"


def test_foreign_hooks_are_read_deliberately(tmp_path):
    """`wiringscan` skips non-cage hooks — never ours to judge. Here the whole point is
    that the hook is written by somebody else, so it must be read."""
    _claude_hook(tmp_path, "/elsewhere/graphify hook-guard read")
    assert len(hookbypass.scan(tmp_path)) == 1


def test_repeated_commands_report_once(tmp_path):
    """One hook block commonly repeats a command across matchers; three identical lines
    would be noise, not evidence."""
    p = tmp_path / ".claude" / "settings.json"
    p.parent.mkdir(parents=True)
    cmd = "/opt/venv/bin/graphify hook-guard search"
    p.write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": m, "hooks": [{"type": "command", "command": cmd}]}
        for m in ("Bash|Grep", "Read|Glob")]}}))
    assert len(hookbypass.scan(tmp_path)) == 1


def test_quoted_path_survives_tokenization(tmp_path):
    _claude_hook(tmp_path, '"/opt/my venv/bin/graphify" hook-guard read')
    (found,) = hookbypass.scan(tmp_path)
    assert found.exe == "/opt/my venv/bin/graphify"


# ── severity + strict escalation ────────────────────────────────────────────────

def test_bypass_is_advisory_never_a_failure(tmp_path):
    """graphify works as designed; only cage's visibility is missing. Never `fail`."""
    _claude_hook(tmp_path, "/opt/venv/bin/graphify hook-guard search")
    level, detail = doctorcmd._hook_bypass(tmp_path)
    assert level == "warn"
    assert "never modifies" in detail


def test_strict_flag_escalates_the_wording(tmp_path):
    """With --strict the read hook DENIES the first raw read — the avoided read is a real
    saving that may never produce a metered query."""
    _claude_hook(tmp_path, "/opt/venv/bin/graphify hook-guard read --strict")
    (found,) = hookbypass.scan(tmp_path)
    assert found.strict
    assert "unmeterable by any current route" in found.line
    assert doctorcmd._hook_bypass(tmp_path)[0] == "warn"     # still advisory


def test_strict_env_escalates_too(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPHIFY_HOOK_STRICT", "1")
    _claude_hook(tmp_path, "/opt/venv/bin/graphify hook-guard read")
    assert hookbypass.scan(tmp_path)[0].strict


def test_strict_env_set_to_off_does_not_escalate(tmp_path, monkeypatch):
    """An exported-but-disabled flag must not trigger the strong wording, or the strong
    wording stops meaning anything."""
    monkeypatch.setenv("GRAPHIFY_HOOK_STRICT", "0")
    _claude_hook(tmp_path, "/opt/venv/bin/graphify hook-guard read")
    assert not hookbypass.scan(tmp_path)[0].strict


def test_clean_project_is_quiet(tmp_path):
    level, detail = doctorcmd._hook_bypass(tmp_path)
    assert level == "ok" and "past the interceptor" in detail


# ── never written, never run ────────────────────────────────────────────────────

def test_the_hook_is_never_modified(tmp_path):
    """graphify owns this artifact. Report, explain, stop."""
    p = _claude_hook(tmp_path, "/opt/venv/bin/graphify hook-guard read --strict")
    before = p.read_bytes()
    hookbypass.scan(tmp_path)
    doctorcmd._hook_bypass(tmp_path)
    assert p.read_bytes() == before


def test_scan_executes_nothing(tmp_path, monkeypatch):
    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("the scan must never execute anything")

    for target in ("subprocess.run", "subprocess.Popen", "os.system", "os.execv"):
        monkeypatch.setattr(target, _boom, raising=False)
    _claude_hook(tmp_path, "/opt/venv/bin/graphify hook-guard search")
    assert len(hookbypass.scan(tmp_path)) == 1


def test_malformed_hook_file_contributes_nothing(tmp_path):
    """Fail-open per artifact: a diagnostic must never be the thing that breaks."""
    p = tmp_path / ".claude" / "settings.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert hookbypass.scan(tmp_path) == []
