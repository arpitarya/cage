"""Entry point for ``python -m tools.docgen``."""
from __future__ import annotations

from tools.docgen.gen import main

if __name__ == "__main__":
    raise SystemExit(main())
