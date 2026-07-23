"""The generated `[sources]` comment block in the bundled policy.toml (v0.29, the
sources-defaults handoff, part A).

The block is *inert documentation*: `tools/docgen --target policy` regenerates it
from `paths._builtin_log_sources()` between the `# cage:sources-start` /
`# cage:sources-end` sentinels, every line a comment. These tests pin the four
properties that make it safe: it drifts when a built-in source is added (CI catches
it), it is idempotent + prose-preserving, it is **~-relative and env-independent**
(the handoff §8 trap — same bytes on any machine), and it stays **inert** (a fresh
project sees no active `[sources]` table, so capture is byte-identical to the
built-ins).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import agents, clicmds, initcmd, ledger, paths, policy
from tools.docgen import gen

CORPUS = Path(__file__).parent / "fixtures" / "transcripts"


def _block(text: str) -> str:
    """The interior between the sentinels (exclusive)."""
    lines = text.split("\n")
    i, j = lines.index(gen.SOURCES_START), lines.index(gen.SOURCES_END)
    return "\n".join(lines[i + 1:j])


# ── drift: a new built-in source can't ship without regenerating ──────────────

def test_check_fails_when_a_builtin_source_is_added_without_regen(monkeypatch):
    orig = paths._builtin_log_sources

    def _extra(agent):
        base = orig(agent)
        if agent == "copilot":
            return [*base, (paths.Path.home() / "extra", "*/new.jsonl")]  # a 3rd source
        return base

    monkeypatch.setattr(paths, "_builtin_log_sources", _extra)
    # the descriptor (2 copilot entries) now disagrees with the registry (3) → loud fail
    with pytest.raises(SystemExit) as e:
        gen.gen_policy()
    assert "copilot" in str(e.value) and "docgen" in str(e.value)


def test_glob_change_in_the_registry_drifts_the_block(monkeypatch):
    before = _block(gen.gen_policy())
    monkeypatch.setitem(paths._FORMAT_GLOB, "kiro", "TOKENS-*")
    orig = paths._builtin_log_sources
    monkeypatch.setattr(paths, "_builtin_log_sources",
                        lambda a: [(orig(a)[0][0], "TOKENS-*")] if a == "kiro" else orig(a))
    after = _block(gen.gen_policy())
    assert before != after and "TOKENS-*" in after  # glob is pulled live from the registry


# ── idempotence + prose preservation ──────────────────────────────────────────

def test_regeneration_is_idempotent():
    once = gen.gen_policy()  # regen over the on-disk (already generated) file
    assert once == gen.POLICY.read_text(encoding="utf-8")  # a fixed point on disk
    assert gen._regen_sources_block(once) == gen._regen_sources_block(
        gen._regen_sources_block(once))  # re-running the block pass never moves it


def test_prose_around_the_sentinels_survives():
    text = (f"# top prose\n[meta]\nx = 1\n\n{gen.SOURCES_START}\n# STALE\n"
            f"{gen.SOURCES_END}\n# bottom prose\n[human]\ny = 2\n")
    out = gen._regen_sources_block(text)
    assert "# top prose" in out and "# bottom prose" in out  # prose both sides survives
    assert "[meta]" in out and "[human]" in out
    assert "# STALE" not in out  # interior replaced
    assert "where cage looks for each agent" in out  # by the generated block


def test_missing_sentinels_fail_loudly():
    with pytest.raises(SystemExit) as e:
        gen._regen_sources_block("# a policy with no sentinels\n[meta]\n")
    assert "sentinels" in str(e.value) and "docgen" in str(e.value)


# ── the §8 trap: ~-relative + env-independent ─────────────────────────────────

def test_block_is_tilde_relative_not_machine_absolute():
    block = _block(gen.gen_policy())
    assert "~/.claude/projects" in block            # the ~-relative default form
    assert str(paths.Path.home()) not in block      # never the resolved absolute home


def test_generation_is_env_independent(monkeypatch):
    baseline = _block(gen.gen_policy())
    # env overrides redirect _builtin_log_sources' *paths*; the block must not move.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/somewhere/else/.claude")
    monkeypatch.setenv("COPILOT_HOME", "/tmp/copilot-home")
    monkeypatch.setenv("KIRO_DATA_DIR", "/var/kiro")
    assert _block(gen.gen_policy()) == baseline     # identical bytes


def test_block_names_all_three_agents_with_env_and_unverified_label():
    block = _block(gen.gen_policy())
    from cage import agents
    for a in agents.SURFACES:
        assert f"# {a}   (redirect home:" in block
    assert "CLAUDE_CONFIG_DIR" in block and "KIRO_DATA_DIR" in block
    assert "%APPDATA%" in block and "UNVERIFIED-LAYOUT" in block  # other-OS + Windows Kiro


# ── the load-bearing inertness test ───────────────────────────────────────────

def test_fresh_project_sees_no_active_sources_but_the_block_is_present(tmp_path, monkeypatch):
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
                "KIRO_DATA_DIR", "CAGE_VSCODE_USER"):
        monkeypatch.delenv(env, raising=False)
    root = tmp_path / "proj"
    initcmd.run(root, pointer=False)
    fp = paths.Footprint(root)
    text = fp.policy.read_text(encoding="utf-8")
    assert "cage:sources-start" in text                        # the block shipped
    assert not policy.load_project_raw(fp.policy).get("sources")  # but no active table
    # and capture still resolves exactly the built-ins, tagged built-in.
    res = paths.resolve_log_sources(policy.load(fp.policy))
    for agent in agents.SURFACES:
        got = [(s.path, s.glob) for s in res.sources if s.agent == agent]
        assert got == paths._builtin_log_sources(agent)
        assert all(s.provenance == "built-in" for s in res.sources if s.agent == agent)


# ── capture identity: the inert block changes not one captured byte ───────────

def _capture(root: Path, agent: str, spec: dict, policy_text: str, monkeypatch) -> bytes:
    base = root / ".cage"
    base.mkdir(parents=True)
    (base / "policy.toml").write_text(policy_text, encoding="utf-8")
    home = root / f"home-{spec['env'].lower()}"
    dst = home / spec["plant"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CORPUS / agent / "cli" / spec["log"], dst)
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR",
                "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(root / f"home-{env.lower()}"))
    monkeypatch.delenv("CAGE_CAPTURE", raising=False)
    monkeypatch.chdir(root)
    assert clicmds.cmd_import(SimpleNamespace(agent=agent, path=None, project=None,
                                              since=None)) == 0
    return b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))


@pytest.mark.parametrize("agent", agents.SURFACES)
def test_bundled_policy_with_block_captures_identically_to_empty(agent, tmp_path, monkeypatch):
    spec = json.loads((CORPUS / agent / "cli" / "expected.json").read_text(encoding="utf-8"))
    bundled = _capture(tmp_path / "a", agent, spec, policy.default_toml(), monkeypatch)
    empty = _capture(tmp_path / "b", agent, spec, "# no sources table\n", monkeypatch)
    assert bundled and bundled == empty  # the comment block adds no source, drops none
