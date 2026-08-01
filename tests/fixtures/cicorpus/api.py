"""HTTP entry points — the only layer that knows about requests and status codes.

Every handler is a pure function of (request, stores) so the whole surface is testable
without a server: routing, error mapping and serialization all happen here, and the auth
layer below never learns that HTTP exists.
"""
from __future__ import annotations

import datetime as dt
import json

from auth import (AccountLocked, InvalidCredentials, SessionExpired, authenticate_token,
                  login, logout, refresh)

STATUS_TEXT = {
    200: "OK", 201: "Created", 400: "Bad Request", 401: "Unauthorized",
    403: "Forbidden", 404: "Not Found", 423: "Locked", 500: "Internal Server Error",
}


class Response(dict):
    """A response is a plain dict; this subclass only adds serialization helpers."""

    def body(self) -> str:
        return json.dumps(self, separators=(",", ":"), sort_keys=True)

    @property
    def status(self) -> int:
        return int(self.get("status", 500))

    @property
    def status_text(self) -> str:
        return STATUS_TEXT.get(self.status, "Unknown")


def _error(status: int, message: str) -> Response:
    return Response({"status": status, "error": message})


def _require(request: dict, *fields: str) -> Response | None:
    missing = [f for f in fields if not request.get(f)]
    if missing:
        return _error(400, f"missing fields: {', '.join(sorted(missing))}")
    return None


def handle_login(request: dict, users: dict, *, key: bytes,
                 now: dt.datetime | None = None) -> Response:
    """Route a login request through the auth layer and map refusals onto status codes.

    A missing user and a wrong password both return 401 with the same body, so the
    endpoint does not leak which usernames exist.
    """
    if bad := _require(request, "user", "password"):
        return bad
    record = users.get(request["user"])
    if record is None:
        return _error(401, "invalid credentials")
    try:
        session, updated = login(request["user"], request["password"], record,
                                 key=key, now=now)
    except AccountLocked:
        return _error(423, "account temporarily locked")
    except InvalidCredentials:
        return _error(401, "invalid credentials")
    users[request["user"]] = updated
    return Response({"status": 200, "token": session.token,
                     "expires_in": session.remaining_seconds(now)})


def handle_refresh(request: dict, sessions: dict, *, key: bytes,
                   now: dt.datetime | None = None) -> Response:
    """Extend a live session. An expired one is a 401, never a silent re-issue."""
    if bad := _require(request, "token"):
        return bad
    session = sessions.get(request["token"])
    if session is None:
        return _error(401, "unknown session")
    try:
        fresh = refresh(session, key=key, now=now)
    except SessionExpired:
        return _error(401, "session expired")
    del sessions[request["token"]]
    sessions[fresh.token] = fresh
    return Response({"status": 200, "token": fresh.token,
                     "expires_in": fresh.remaining_seconds(now)})


def handle_logout(request: dict, sessions: dict, revoked: set) -> Response:
    if bad := _require(request, "token"):
        return bad
    session = sessions.pop(request["token"], None)
    if session is None:
        return _error(404, "unknown session")
    logout(session, revoked)
    return Response({"status": 200})


def handle_whoami(request: dict, revoked: set, *, key: bytes,
                  now: dt.datetime | None = None) -> Response:
    """Resolve a bearer token to a user, honouring the revocation list."""
    token = (request.get("headers", {}).get("authorization", "")
             .removeprefix("Bearer ").strip())
    if not token:
        return _error(401, "missing bearer token")
    if token in revoked:
        return _error(401, "session revoked")
    try:
        user = authenticate_token(token, key, now=now)
    except SessionExpired:
        return _error(401, "session expired")
    except InvalidCredentials:
        return _error(401, "invalid token")
    return Response({"status": 200, "user": user})


ROUTES = {
    ("POST", "/login"): handle_login,
    ("POST", "/refresh"): handle_refresh,
    ("POST", "/logout"): handle_logout,
    ("GET", "/whoami"): handle_whoami,
}


def dispatch(method: str, path: str) -> object | None:
    """Look up a handler; ``None`` means 404 at the edge, before any auth work."""
    return ROUTES.get((method.upper(), path))
