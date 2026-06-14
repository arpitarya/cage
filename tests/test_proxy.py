"""Proxy usage extraction: Anthropic + OpenAI, JSON + SSE streams + live metering."""
from __future__ import annotations

import http.server
import threading
import time
import urllib.request
from functools import partial

from cage import ledger, proxy, usageparse


def test_anthropic_json_usage():
    body = (b'{"model":"claude-opus-4-8","usage":{"input_tokens":100,'
            b'"output_tokens":50,"cache_read_input_tokens":20}}')
    model, tin, tout, cached = usageparse.extract(body, "/v1/messages")
    assert (model, tin, tout, cached) == ("claude-opus-4-8", 120, 50, 20)


def test_openai_json_usage():
    body = b'{"model":"gpt-4o","usage":{"prompt_tokens":100,"completion_tokens":40}}'
    model, tin, tout, cached = usageparse.extract(body, "/v1/chat/completions")
    assert (model, tin, tout, cached) == ("gpt-4o", 100, 40, 0)


def test_anthropic_sse_stream():
    sse = (
        'event: message_start\n'
        'data: {"type":"message_start","message":{"model":"claude-opus-4-8",'
        '"usage":{"input_tokens":80,"cache_read_input_tokens":10}}}\n\n'
        'event: message_delta\n'
        'data: {"type":"message_delta","usage":{"output_tokens":42}}\n\n'
        'data: [DONE]\n\n'
    ).encode()
    model, tin, tout, cached = usageparse.extract(sse, "/v1/messages")
    assert model == "claude-opus-4-8"
    assert tin == 90 and cached == 10 and tout == 42


def test_openai_sse_stream():
    sse = (
        'data: {"model":"gpt-4o","choices":[{"delta":{"content":"hi"}}]}\n\n'
        'data: {"model":"gpt-4o","usage":{"prompt_tokens":55,"completion_tokens":12}}\n\n'
        'data: [DONE]\n\n'
    ).encode()
    model, tin, tout, cached = usageparse.extract(sse, "/v1/chat/completions")
    assert model == "gpt-4o" and tin == 55 and tout == 12


def test_garbage_body_is_zero():
    assert usageparse.extract(b"not json at all", "/v1/messages") == ("", 0, 0, 0)


class _Upstream(http.server.BaseHTTPRequestHandler):
    BODY = b'{"model":"claude-opus-4-8","usage":{"input_tokens":100,"output_tokens":50}}'

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.BODY)))
        self.end_headers()
        self.wfile.write(self.BODY)

    def log_message(self, *a):
        pass


def _serve(handler):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def test_proxy_forwards_and_meters(proj):
    up, up_port = _serve(_Upstream)
    proxy._Handler.upstream = f"http://127.0.0.1:{up_port}"
    proxy._Handler.root = proj
    px, port = _serve(partial(proxy._Handler))
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/messages",
                                     data=b'{"x":1}', method="POST")
        resp = urllib.request.urlopen(req, timeout=5).read()
        assert b"usage" in resp                       # client gets the bytes unchanged
        for _ in range(50):                            # _meter runs after the response
            if ledger.calls(proj):
                break
            time.sleep(0.02)
    finally:
        px.shutdown(); up.shutdown()
    (call,) = ledger.calls(proj)
    assert call["tokens_in"] == 100 and call["tokens_out"] == 50 and call["agent"] == "proxy"

