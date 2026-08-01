"""Session authentication: login, session lifetime, and token minting.

The auth layer owns *who someone is*. It never talks HTTP and never touches storage
directly — the API layer hands it a record and takes back a session or a refusal.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
from dataclasses import dataclass, field

from crypto import (random_key, sign, upgrade_record, needs_rehash, verify_password,
                    verify_signature)

SESSION_TTL_MINUTES = 60
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class AuthError(Exception):
    """Base class for every refusal this module can produce."""


class InvalidCredentials(AuthError):
    """The password did not verify against the stored digest."""


class AccountLocked(AuthError):
    """Too many failed attempts inside the lockout window."""


class SessionExpired(AuthError):
    """The presented session is past its expiry."""


@dataclass
class Session:
    """An authenticated session. Immutable once minted; refresh returns a new one."""
    user: str
    issued_at: dt.datetime
    expires_at: dt.datetime
    token: str
    scopes: tuple[str, ...] = field(default_factory=tuple)

    def is_expired(self, now: dt.datetime | None = None) -> bool:
        return (now or dt.datetime.now(dt.timezone.utc)) >= self.expires_at

    def remaining_seconds(self, now: dt.datetime | None = None) -> int:
        delta = self.expires_at - (now or dt.datetime.now(dt.timezone.utc))
        return max(0, int(delta.total_seconds()))

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def _mint_token(user: str, expires_at: dt.datetime, key: bytes) -> str:
    """A signed, self-describing token: base64(payload) + "." + hmac(payload)."""
    payload = json.dumps({"user": user, "exp": expires_at.isoformat()},
                         separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{body}.{sign(payload, key)}"


def _read_token(token: str, key: bytes) -> dict:
    """Decode and verify a token minted by :func:`_mint_token`."""
    body, _, signature = token.partition(".")
    padding = "=" * (-len(body) % 4)
    payload = base64.urlsafe_b64decode(body + padding)
    if not verify_signature(payload, key, signature):
        raise InvalidCredentials("token signature does not verify")
    return json.loads(payload)


def _locked_out(record: dict, now: dt.datetime) -> bool:
    if int(record.get("failed_attempts", 0)) < MAX_FAILED_ATTEMPTS:
        return False
    last = record.get("last_failure")
    if not last:
        return False
    since = now - dt.datetime.fromisoformat(last)
    return since < dt.timedelta(minutes=LOCKOUT_MINUTES)


def login(user: str, password: str, record: dict, *, key: bytes | None = None,
          now: dt.datetime | None = None) -> tuple[Session, dict]:
    """Authenticate ``user`` against a stored ``record`` and open a session.

    Returns the session and a (possibly rewritten) record — the record is rewritten when
    the stored digest was produced with weaker parameters than the current default, so
    logging in transparently upgrades an old account.

    Raises :class:`AccountLocked` before ever touching the digest, so a locked account
    costs an attacker no information about whether the password was right.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    key = key or random_key()
    if _locked_out(record, now):
        raise AccountLocked(user)
    ok = verify_password(password, record["salt"], record["digest"],
                         iterations=int(record.get("iterations", 0)) or None or 240_000,
                         algorithm=record.get("algorithm", "pbkdf2_sha256"))
    if not ok:
        record = {**record, "failed_attempts": int(record.get("failed_attempts", 0)) + 1,
                  "last_failure": now.isoformat()}
        raise InvalidCredentials(user)
    if needs_rehash(record):
        record = upgrade_record(record, password)
    record = {**record, "failed_attempts": 0, "last_failure": None}
    expires_at = now + dt.timedelta(minutes=SESSION_TTL_MINUTES)
    session = Session(user=user, issued_at=now, expires_at=expires_at,
                      token=_mint_token(user, expires_at, key),
                      scopes=tuple(record.get("scopes", ())))
    return session, record


def refresh(session: Session, *, key: bytes, now: dt.datetime | None = None) -> Session:
    """Extend a still-valid session. An expired session is never refreshed."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if session.is_expired(now):
        raise SessionExpired(session.user)
    expires_at = now + dt.timedelta(minutes=SESSION_TTL_MINUTES)
    return Session(user=session.user, issued_at=session.issued_at,
                   expires_at=expires_at,
                   token=_mint_token(session.user, expires_at, key),
                   scopes=session.scopes)


def authenticate_token(token: str, key: bytes, *, now: dt.datetime | None = None) -> str:
    """Verify a bearer token and return the user it names."""
    now = now or dt.datetime.now(dt.timezone.utc)
    claims = _read_token(token, key)
    if dt.datetime.fromisoformat(claims["exp"]) <= now:
        raise SessionExpired(claims["user"])
    return claims["user"]


def logout(session: Session, revoked: set[str]) -> None:
    """Revoke a session by token. Revocation is the caller's store to keep."""
    revoked.add(session.token)
