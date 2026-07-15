"""`cage data proxy` — a thin metering reverse-proxy (plan §5, §9.5).

The protocol-targeted meter for clients you can't edit. Point any agent's base URL
at it (Claude Code `ANTHROPIC_BASE_URL`, Codex/Copilot `OPENAI_BASE_URL`, …); it
forwards verbatim to the real upstream, tees the response to extract `usage`, and
records one call row. Fail-open and fail-fast: a metering or parse error never
changes the bytes the client receives. The library path needs no proxy at all.
"""
from __future__ import annotations

import http.server
import urllib.request
from functools import partial
from pathlib import Path

from cage import metering, usageparse

_DEFAULT_UPSTREAM = "https://api.anthropic.com"
_HOP = {"host", "content-length", "connection", "accept-encoding"}


class _Handler(http.server.BaseHTTPRequestHandler):
    upstream = _DEFAULT_UPSTREAM
    root: Path | None = None
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        try:
            resp = self._forward(body)
            data = resp.read()
            self._respond(resp.status, resp.headers.items(), data)
        except Exception as exc:  # upstream/network failure — surface 502, never hang
            self.send_error(502, f"cage data proxy upstream error: {exc}")
            return
        self._meter(data)

    do_GET = do_POST  # health/models endpoints pass through the same way

    def _forward(self, body: bytes):
        url = self.upstream.rstrip("/") + self.path
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP}
        req = urllib.request.Request(url, data=body or None, headers=headers,
                                     method=self.command)
        return urllib.request.urlopen(req, timeout=600)

    def _respond(self, status, header_items, data: bytes) -> None:
        self.send_response(status)
        for k, v in header_items:
            if k.lower() not in _HOP | {"transfer-encoding"}:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _meter(self, data: bytes) -> None:
        try:
            model, tin, tout, cached = usageparse.extract(data, self.path)
            if tin or tout:
                provider = "anthropic" if "/messages" in self.path else "openai"
                metering.record_call(route="proxy", provider=provider, model=model,
                                     tokens_in=tin, tokens_out=tout, cached_in=cached,
                                     agent="proxy", root=self.root)
        except Exception:  # pragma: no cover — metering is best-effort
            pass

    def log_message(self, *a) -> None:  # quiet by default
        pass


def serve(root: Path, port: int = 8788, upstream: str = _DEFAULT_UPSTREAM) -> int:
    handler = partial(_Handler)
    _Handler.upstream, _Handler.root = upstream, root
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"cage data proxy: 127.0.0.1:{port} → {upstream}  (metering to {root}/.cage; Ctrl-C to stop)")
    print(f"  point your agent at it, e.g.  export ANTHROPIC_BASE_URL=http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ncage data proxy: stopped.")
    finally:
        httpd.server_close()
    return 0
