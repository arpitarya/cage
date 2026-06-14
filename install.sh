#!/usr/bin/env bash
# Install the Cage flux (editable: repo edits live-reflect in the `cage` binary).
# $0, idempotent. Run from the repo root.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3.14 || command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)"
echo "Using interpreter: $PY ($($PY --version 2>&1))"
case "$($PY -c 'import sys;print(sys.version_info>=(3,11))')" in
  True) ;; *) echo "Cage needs Python ≥3.11 (tomllib). Found $($PY --version)"; exit 1;;
esac

echo "→ engine (editable)"
"$PY" -m pip install -q --user -e "$REPO" || "$PY" -m pip install -q --user --break-system-packages -e "$REPO"

echo
echo "✔ Cage installed. Verify:  cage --version   (or: $PY -m cage --version)"
echo "  In any project:         cage init  →  meter calls  →  cage report"
if ! command -v cage >/dev/null 2>&1; then
  echo "  Note: 'cage' is not on PATH yet — add your user-base bin dir:"
  echo "    export PATH=\"\$($PY -c 'import site,os;print(os.path.join(site.USER_BASE,\"bin\"))'):\$PATH\""
fi
