"""ADR-FRONTMATTER — every record's frontmatter is a clean key: value block, forever.

**Why this exists.** ADR frontmatter looks like YAML (`docs/adr/TEMPLATE.md`'s four
keys: `adr` / `status` / `audience` / `update-rule`), but nothing in this stdlib-only
project ever parses it as YAML — no dependency does that job, and `pyproject.toml`
declares `dependencies = []` by law. The `status` and `update-rule` values are long
hand-written prose, and a **colon immediately followed by a space (or by end of
line)** inside that prose is indistinguishable, to any real YAML parser, from the
start of a brand-new mapping key: `yaml.safe_load` throws "mapping values are not
allowed here" on exactly this shape. **Two records broke this way independently**
(`0002_coverage.md`'s `update-rule` — "...is such a change: it reassigns..." —
and `0009_authorship.md`'s `status` — "...What IS built:\\n  the claude...") —
found only by a human reading the raw file, not by anything in the suite. That is
the failure this test closes: the same defect class caught mechanically, before a
third record breaks the same way.

**Why not just add PyYAML and parse it for real:** this project's dependency list
is empty by law ("stdlib only — $0, deterministic, dependency-free", see
`pyproject.toml` and `README.md`), and nothing else in the test suite reaches for a
third-party package. The frontmatter shape is simple and fixed enough that a plain
stdlib scan finds the exact defect class without one — reaching for a parser this
project otherwise refuses would be a bigger change than the bug it fixes.

**What this deliberately does not do:** validate the *content* of `status` or
`update-rule` (staleness, accuracy) — that is the ADR-correctness sweep's job
(`work/regression/`), not this gate's. This test only proves the block is
*structurally sound* — the right four keys, no stray colon that would make any
future tooling choke on it.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADR_DIR = REPO / "docs" / "adr"

REQUIRED_KEYS = ("adr", "status", "audience", "update-rule")

# A frontmatter key line: starts at column 0, `name:` optionally followed by a value
# on the same line. Continuation lines (the rest of a multi-line value) are indented.
_KEY_LINE = re.compile(r"^([a-zA-Z][\w-]*):[ \t]?(.*)$")

# The defect class itself: a colon immediately followed by whitespace, or sitting at
# the very end of a line — the two shapes a plain-scalar YAML parser reads as "a new
# mapping key starts here", inside a value that is supposed to be a continuous string.
_MIDVALUE_COLON = re.compile(r":(\s|$)")


def _adr_files() -> list[Path]:
    files = sorted(ADR_DIR.glob("0*.md"))
    assert files, "no docs/adr/0*.md files found — the glob or the path is broken"
    return files


def _frontmatter_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, (
        f"{path.name} has no closed frontmatter block — need two '---' delimiter "
        "lines before any content")
    return parts[1].splitlines()


def _walk(path: Path):
    """Yields (key, value_fragment, is_first_line_of_key) for every non-blank line
    in the frontmatter block, exactly as a human skimming the file would read it:
    a line starting at column 0 with `key:` opens a field; anything indented under
    it continues that field's value."""
    current_key = None
    for raw in _frontmatter_lines(path):
        if not raw.strip():
            continue
        is_continuation = raw[:1] in (" ", "\t")
        m = _KEY_LINE.match(raw) if not is_continuation else None
        if m:
            current_key = m.group(1)
            yield current_key, m.group(2), True
        else:
            yield current_key, raw, False


def test_every_frontmatter_field_is_free_of_the_colon_defect():
    """The mechanical half of 'frontmatter is broken' — a stray ': ' or a trailing
    ':' inside a status/update-rule value. Reports every offending file and the
    exact fragment, so a fix is a find-and-replace, not an investigation."""
    problems = []
    for path in _adr_files():
        keys_seen: list[str] = []
        for key, fragment, is_key_line in _walk(path):
            if key is None:
                problems.append(f"{path.name}: content before any frontmatter key: {fragment!r}")
                continue
            if is_key_line:
                keys_seen.append(key)
            m = _MIDVALUE_COLON.search(fragment)
            if m:
                start = max(0, m.start() - 40)
                snippet = fragment[start:m.start() + 20]
                problems.append(
                    f"{path.name} [{key}]: ...{snippet!r}... — a colon followed by "
                    "whitespace/end-of-line inside a value. Any real YAML parser reads "
                    "this as a new mapping key ('mapping values are not allowed here'). "
                    "Replace with an em dash (—) or a comma; see docs/adr/TEMPLATE.md.")
        missing = [k for k in REQUIRED_KEYS if k not in keys_seen]
        if missing:
            problems.append(f"{path.name}: missing frontmatter key(s) {missing}")
        extra = sorted(set(keys_seen) - set(REQUIRED_KEYS))
        if extra:
            problems.append(f"{path.name}: unexpected frontmatter key(s) {extra}")
        for key in REQUIRED_KEYS:
            if keys_seen.count(key) > 1:
                problems.append(
                    f"{path.name}: key {key!r} appears {keys_seen.count(key)} times — "
                    "frontmatter is probably malformed, likely from the same colon defect")
    assert not problems, "ADR frontmatter defects:\n  " + "\n  ".join(problems)


def test_every_frontmatter_block_is_delimited_and_non_empty():
    """The structural half: two '---' lines exist, and there is something between
    them. Separated from the colon check so a missing block reads as a missing
    block, not as sixteen 'missing key' failures."""
    problems = []
    for path in _adr_files():
        lines = _frontmatter_lines(path)
        if not any(line.strip() for line in lines):
            problems.append(f"{path.name}: frontmatter block is empty")
    assert not problems, "\n  ".join(problems)
