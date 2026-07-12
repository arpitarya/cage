"""`cage meter -- <cmd>` — run a command with the metering proxy in front (plan §7).

Spins the proxy up on an ephemeral port in a background thread, points the agent's
base-URL env vars at it, runs the command to completion, then tears the proxy down.
The command's own stdio is untouched — Cage only meters the wire.
"""
from __future__ import annotations

import http.server
import os
import socket
import subprocess
import threading
from functools import partial
from pathlib import Path

from cage.proxy import _DEFAULT_UPSTREAM, _Handler


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(root: Path, argv: list[str], upstream: str = _DEFAULT_UPSTREAM) -> int:
    argv = list(argv)
    if argv and argv[0] == "--":          # tolerate `cage meter -- <cmd> …`
        argv = argv[1:]
    if not argv:
        print("cage meter: nothing to run (usage: cage meter -- <cmd> [args…])")
        return 2
    port = _free_port()
    _Handler.upstream, _Handler.root = upstream, root
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(_Handler))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "ANTHROPIC_BASE_URL": base, "OPENAI_BASE_URL": base,
           "CAGE_ACTIVE": "1"}
    print(f"cage meter: running under proxy {base} → {upstream}")
    try:
        return subprocess.run(argv, env=env).returncode
    finally:
        httpd.shutdown()
        httpd.server_close()
        print(f"cage meter: done — `cage report` to see what {argv[0]!r} spent.")
