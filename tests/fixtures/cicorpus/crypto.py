"""Password hashing, key derivation and constant-time comparison primitives.

Everything in here is deliberately dependency-free: the auth layer must keep working
in a stripped-down runtime where only the standard library is available.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

DEFAULT_ITERATIONS = 240_000
SALT_BYTES = 16
DIGEST_BYTES = 32
SUPPORTED_ALGORITHMS = ("pbkdf2_sha256", "pbkdf2_sha512", "scrypt")


class UnsupportedAlgorithm(ValueError):
    """Raised when a stored record names an algorithm this build cannot verify."""


def new_salt(size: int = SALT_BYTES) -> str:
    """A fresh random salt, hex encoded so it survives a JSON round trip."""
    return secrets.token_hex(size)


def _pbkdf2(password: str, salt: str, iterations: int, algorithm: str) -> bytes:
    digest_name = algorithm.split("_", 1)[1]
    return hashlib.pbkdf2_hmac(digest_name, password.encode("utf-8"),
                               bytes.fromhex(salt), iterations, dklen=DIGEST_BYTES)


def _scrypt(password: str, salt: str) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                          n=2 ** 14, r=8, p=1, dklen=DIGEST_BYTES)


def hash_password(password: str, salt: str, *, iterations: int = DEFAULT_ITERATIONS,
                  algorithm: str = "pbkdf2_sha256") -> str:
    """Derive a hex digest for ``password`` under ``salt``.

    The algorithm is stored alongside the digest so a record hashed by an older release
    keeps verifying after the default moves on.
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise UnsupportedAlgorithm(algorithm)
    if algorithm == "scrypt":
        return _scrypt(password, salt).hex()
    return _pbkdf2(password, salt, iterations, algorithm).hex()


def verify_password(password: str, salt: str, digest: str, *,
                    iterations: int = DEFAULT_ITERATIONS,
                    algorithm: str = "pbkdf2_sha256") -> bool:
    """Constant-time check of ``password`` against a stored digest.

    Uses :func:`hmac.compare_digest` rather than ``==`` so a caller cannot time the
    comparison to learn the digest prefix.
    """
    try:
        candidate = hash_password(password, salt, iterations=iterations,
                                  algorithm=algorithm)
    except (UnsupportedAlgorithm, ValueError):
        return False
    return hmac.compare_digest(candidate, digest)


def needs_rehash(record: dict) -> bool:
    """True when a stored record was hashed with weaker parameters than today's default."""
    if record.get("algorithm") not in SUPPORTED_ALGORITHMS:
        return True
    if record.get("algorithm") == "scrypt":
        return False
    return int(record.get("iterations", 0)) < DEFAULT_ITERATIONS


def upgrade_record(record: dict, password: str) -> dict:
    """Re-hash a verified password under the current defaults, preserving the user id."""
    salt = new_salt()
    return {
        **record,
        "salt": salt,
        "iterations": DEFAULT_ITERATIONS,
        "algorithm": "pbkdf2_sha256",
        "digest": hash_password(password, salt),
    }


def sign(payload: bytes, key: bytes) -> str:
    """Detached HMAC signature over ``payload``, hex encoded."""
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, key: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign(payload, key), signature)


def random_key(size: int = 32) -> bytes:
    """A key suitable for :func:`sign`; sourced from the OS CSPRNG, never from ``random``."""
    return os.urandom(size)
