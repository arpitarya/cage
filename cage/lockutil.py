"""One fail-open cross-process file lock for the capture path ($0/stdlib).

Serializes a read-check-append section against another cage process (two hooks
firing at once, an import racing a SessionEnd) so idempotency checks can't both
pass before either write lands. One implementation, three tiers:

- POSIX: ``fcntl.flock`` (exclusive, blocks until the peer releases);
- Windows: ``msvcrt.locking`` on the first byte (``LK_LOCK`` retries ~10s, then
  raises — treated as untakeable, below);
- neither available / lock file unwritable: **proceed unlocked** — exactly the
  pre-lock behavior. The id-dedupe backstop at each call site stays the
  correctness guarantee; the lock only closes the wasted-work window.

Fail-open discipline: ``locked()`` never raises into the caller. When the lock
can't be taken the context still runs; callers that hold a debug logger record
the miss themselves (``importcmd``) so "the backstop is carrying dedupe alone"
stays attributable under ``CAGE_DEBUG=1``.
"""
from __future__ import annotations

import contextlib
from pathlib import Path

try:  # POSIX
    import fcntl as _fcntl
except ImportError:  # pragma: no cover — Windows
    _fcntl = None
try:  # Windows
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover — POSIX
    _msvcrt = None


def _acquire(fh) -> bool:
    if _fcntl is not None:
        _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
        return True
    if _msvcrt is not None:  # pragma: no cover — exercised on Windows CI
        _msvcrt.locking(fh.fileno(), _msvcrt.LK_LOCK, 1)
        return True
    return False  # no lock primitive on this platform — proceed unlocked


def _release(fh) -> None:
    if _fcntl is not None:
        _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
    elif _msvcrt is not None:  # pragma: no cover — exercised on Windows CI
        fh.seek(0)
        _msvcrt.locking(fh.fileno(), _msvcrt.LK_UNLCK, 1)


@contextlib.contextmanager
def locked(lock_file: Path, on_miss=None):
    """Hold an exclusive lock on ``lock_file`` for the with-block; fail-open.

    ``on_miss(exc_or_none)`` is called (itself guarded) when the lock could not
    be taken — an OSError, or no primitive on this platform (``None``) — so the
    caller can debug-log the degraded mode without this module importing the
    logger (no import cycle, no policy load here).
    """
    fh = None
    held = False
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_file, "a+")  # noqa: SIM115 — released in finally; a+ never truncates a peer
        held = _acquire(fh)
        if not held and on_miss is not None:
            with contextlib.suppress(Exception):
                on_miss(None)
    except OSError as e:
        if fh is not None:
            fh.close()
        fh = None
        if on_miss is not None:
            with contextlib.suppress(Exception):
                on_miss(e)
    try:
        yield
    finally:
        if fh is not None:
            with contextlib.suppress(OSError):
                if held:
                    _release(fh)
            fh.close()
