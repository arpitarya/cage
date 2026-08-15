"""The ADR set's countable claims, re-derived from code — never from another doc's prose.

Three assertions, each computed independently:

1. The ADR set size — `docs/adr/README.md`'s frontmatter word and `CLAUDE.md`'s
   "The set is …" sentence — against `len(sorted(Path("docs/adr").glob("0*.md")))`.
2. ADR-CLI's per-group command counts (every `## \\`cage <group>\\` — N ...` heading)
   and its total addressable-command count, against `cli.build_parser()`.
3. The MCP read-tool count in ADR-CLI and `CLAUDE.md`, against
   `len(mcpserver.TOOLS) - len(mcpserver.WRITE_TOOLS)`.

**What this deliberately does not cover:** any count whose source is prose, a
measurement, or a table cell a human maintains — that is the rest of the ADR
correctness sweep's job (`work/regression/`), not this gate's.
`tests/test_adr_output_blocks.py` covers fenced output blocks; `tests/test_cli_reference.py`
covers command/flag *existence*. This file covers arithmetic about the parser and
nothing else — passing it does not mean an ADR's prose is otherwise true.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from cage import cli, mcpserver

REPO = Path(__file__).resolve().parent.parent
ADR_DIR = REPO / "docs" / "adr"
README = ADR_DIR / "README.md"
CLAUDE_MD = REPO / "CLAUDE.md"
ADR_CLI = ADR_DIR / "0003_cli.md"

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15,
}


def _word_to_int(word: str) -> int:
    key = word.strip().lower()
    assert key in _WORDS, f"unknown spelled number {word!r} — add it to _WORDS in this test"
    return _WORDS[key]


# ── ground truth: walk the live parser the same way test_cli_reference.py does ──

def _subaction(par):
    return next((a for a in par._actions if isinstance(a, argparse._SubParsersAction)), None)


def _choice_positional(par):
    return next((a for a in par._actions
                 if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
                 and a.choices), None)


def _group_actions(par):
    a = _choice_positional(par)
    return list(a.choices) if a is not None and a.dest == "action" else []


def _walk(par, path, out):
    sub = _subaction(par)
    if sub:
        out[" ".join(path)] = False
        for name, sp in sub.choices.items():
            _walk(sp, path + [name], out)
        return
    actions = _group_actions(par)
    if actions:
        out[" ".join(path)] = False
        for name in actions:
            out[" ".join(path + [name])] = True
        return
    out[" ".join(path)] = True


def _surface():
    out: dict[str, bool] = {}
    _walk(cli.build_parser(), [], out)
    return out


_SURFACE = _surface()
_LEAVES = sorted(p for p, leaf in _SURFACE.items() if leaf and p)
_GROUPS = sorted(p for p, leaf in _SURFACE.items() if not leaf and p and " " not in p)
_TOTAL_LEAVES = len(_LEAVES)
_TOTAL_TOP_LEVEL = len({p.split(" ", 1)[0] for p in _SURFACE if p})


def _group_leaf_count(group: str) -> int:
    return sum(1 for p in _LEAVES
               if p.startswith(group + " ") and p.count(" ") == group.count(" ") + 1)


# ── 1. the ADR set size ─────────────────────────────────────────────────────────

def test_adr_set_size_in_readme_frontmatter():
    true_count = len(sorted(ADR_DIR.glob("0*.md")))
    frontmatter = README.read_text(encoding="utf-8").split("---", 2)[1]
    m = re.search(r"the ADR set — (\S+) maintained records", frontmatter)
    assert m, ("docs/adr/README.md's frontmatter no longer reads "
               "'the ADR set — N maintained records' — update this test's pattern")
    assert _word_to_int(m.group(1)) == true_count, (
        f"docs/adr/README.md's frontmatter says {m.group(1)!r} maintained records, "
        f"but there are {true_count} files matching docs/adr/0*.md")


def test_adr_set_size_in_claude_md():
    true_count = len(sorted(ADR_DIR.glob("0*.md")))
    body = CLAUDE_MD.read_text(encoding="utf-8")
    m = re.search(r"The set is (\S+) records", body)
    assert m, "CLAUDE.md no longer reads 'The set is N records' — update this test's pattern"
    assert _word_to_int(m.group(1)) == true_count, (
        f"CLAUDE.md says 'The set is {m.group(1)} records', but there are "
        f"{true_count} files matching docs/adr/0*.md")


# ── 2. ADR-CLI's per-group and total command counts ─────────────────────────────

def test_adr_cli_per_group_headings_match_the_parser():
    body = ADR_CLI.read_text(encoding="utf-8")
    headings = re.findall(
        r"^## `cage (\S+)` — (\d+) (?:commands?|actions?|derived views?)$", body, re.M)
    assert headings, ("docs/adr/0003_cli.md has no '## `cage <group>` — N ...' "
                       "headings — update this test's pattern")
    seen = set()
    for group, count_str in headings:
        seen.add(group)
        assert group in _GROUPS, (
            f"docs/adr/0003_cli.md documents a heading for `cage {group}`, "
            f"which is not a live parser group ({sorted(_GROUPS)})")
        true_count = _group_leaf_count(group)
        assert int(count_str) == true_count, (
            f"docs/adr/0003_cli.md says `cage {group}` has {count_str} commands, "
            f"but the parser has {true_count}")
    missing = set(_GROUPS) - seen
    assert not missing, f"docs/adr/0003_cli.md has no per-group heading for: {sorted(missing)}"


def test_adr_cli_total_command_count():
    body = ADR_CLI.read_text(encoding="utf-8")
    frontmatter = body.split("---", 2)[1]
    assert f"{_TOTAL_LEAVES} addressable commands" in frontmatter, (
        f"docs/adr/0003_cli.md's frontmatter total-command count is stale — "
        f"the parser has {_TOTAL_LEAVES} leaves")
    assert f"**{_TOTAL_LEAVES} addressable commands**" in body, (
        f"docs/adr/0003_cli.md's total-command count is stale — "
        f"the parser has {_TOTAL_LEAVES} leaves")


def test_adr_cli_top_level_entry_count():
    body = ADR_CLI.read_text(encoding="utf-8")
    frontmatter = body.split("---", 2)[1]
    assert f"{_TOTAL_TOP_LEVEL} top-level entries" in frontmatter, (
        f"docs/adr/0003_cli.md's frontmatter top-level-entry count is stale — "
        f"the parser has {_TOTAL_TOP_LEVEL} top-level entries")


# ── 3. the MCP read-tool count ───────────────────────────────────────────────────

def _true_read_tool_count() -> int:
    return len(mcpserver.TOOLS) - len(mcpserver.WRITE_TOOLS)


def test_mcp_read_tool_count_in_adr_cli():
    true_count = _true_read_tool_count()
    body = ADR_CLI.read_text(encoding="utf-8")
    m = re.search(r"(\d+) read tools? \+ exactly one write tool", body)
    assert m, ("docs/adr/0003_cli.md no longer reads 'N read tool(s) + exactly one "
               "write tool' — update this test's pattern")
    assert int(m.group(1)) == true_count, (
        f"docs/adr/0003_cli.md's `cage mcp` row says {m.group(1)} read tools, but "
        f"len(mcpserver.TOOLS) - len(mcpserver.WRITE_TOOLS) = {true_count}")


def test_mcp_read_tool_count_in_claude_md():
    true_count = _true_read_tool_count()
    body = CLAUDE_MD.read_text(encoding="utf-8")
    m = re.search(r"MCP surface = (\d+) read tools?", body)
    assert m, "CLAUDE.md no longer reads 'MCP surface = N read tools' — update this test's pattern"
    assert int(m.group(1)) == true_count, (
        f"CLAUDE.md says 'MCP surface = {m.group(1)} read tools', but "
        f"len(mcpserver.TOOLS) - len(mcpserver.WRITE_TOOLS) = {true_count}")
