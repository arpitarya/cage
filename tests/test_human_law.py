"""Stage-5 cage-law guards for the human axis: $0 imports + determinism (criteria 8, 2b)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cage import demo, humanview, metering, policy

_STDLIB_OK = {"datetime", "re", "subprocess", "pathlib", "os", "json", "itertools"}
_NEW_MODULES = ("convert", "human", "tasks", "trend", "humanview")


# ── criterion 8 — new modules import stdlib + cage.* only; no new dependency
def test_new_modules_are_stdlib_and_cage_only():
    pkg = Path(__file__).resolve().parent.parent / "cage"
    for name in _NEW_MODULES:
        tree = ast.parse((pkg / f"{name}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    assert top in _STDLIB_OK or top == "cage", f"{name}: import {a.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top in _STDLIB_OK or top == "cage" or top == "__future__", \
                    f"{name}: from {node.module}"


def test_no_runtime_dependency_declared():
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    assert "dependencies = []" in pyproject


# ── criterion 2b — same (ledger, policy, env) ⇒ identical rollup (determinism)
def test_rollup_is_deterministic(proj, monkeypatch):
    metering._policy_for.cache_clear()
    demo.seed(proj)
    metering.record_human(task=demo.TASK, task_type="feature", agent="claude-code", root=proj)
    monkeypatch.setenv("CAGE_HUMAN_RATE", "120")
    pol = policy.load(None)
    a = humanview.rollup(proj, pol)
    b = humanview.rollup(proj, pol)
    assert a == b
    assert a["source"] == "env" and a["rate"] == 120.0
