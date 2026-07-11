"""Build ``cage.pyz`` — a single-file stdlib zipapp over the cage package.

The restricted-environments distribution tier (docs/restricted-environments.md,
handoff docs/cage-handoff-restricted-env.md): endpoints that block unknown exes or
have no pip/PyPI access run cage as ``py cage.pyz <cmd>`` through their approved
Python interpreter. Built by CI on the release trigger and attached to the GitHub
release next to a SHA256SUMS file — never built-and-attached from a laptop; this
module exists so CI, the dummyrepo scenario runner (S13), and tests share one
build path.

Build-time only, dev-tool rules: stdlib only, never imported by cage at runtime,
never in the wheel. ``cage/data/**`` rides along because it lives inside the
package directory — no package-data plumbing.
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipapp
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def build(out: Path) -> Path:
    """Stage the cage package and zipapp it.

    The ``__main__.py`` is written by hand instead of via zipapp's ``main=``
    parameter: zipapp's template calls ``main()`` without ``sys.exit``, which
    would swallow cage's exit codes (0 ok · 1 error · 2 usage · 130 interrupt —
    the CLI error contract). The body mirrors ``cage/__main__.py``."""
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / "app"
        shutil.copytree(REPO_ROOT / "cage", stage / "cage",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "__main__.py").write_text(
            "from cage.cli import main\n\nraise SystemExit(main())\n",
            encoding="utf-8", newline="\n")
        out.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(stage, out,
                              interpreter="/usr/bin/env python3", compressed=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.buildpyz",
                                 description="build cage.pyz (stdlib zipapp)")
    ap.add_argument("--out", default="dist-pyz/cage.pyz",
                    help="output path (default: dist-pyz/cage.pyz)")
    args = ap.parse_args(argv)
    print(build(Path(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
