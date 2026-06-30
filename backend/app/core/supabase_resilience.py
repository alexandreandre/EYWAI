"""Résilience réseau pour le client Supabase (httpx / HTTP/2, errno 35 macOS)."""

from __future__ import annotations

import errno
import time
from typing import Callable, TypeVar

import httpx

_TRANSIENT_ERRNOS = frozenset({errno.EAGAIN, errno.EWOULDBLOCK, 35, 11})
_TRANSIENT_HTTP_STATUSES = frozenset({429, 502, 503, 504, 520, 521, 522, 523, 524})
_TRANSIENT_MARKERS = (
    "resource temporarily unavailable",
    "errno 35",
    "connection reset",
    "broken pipe",
    "sslv3_alert_bad_record_mac",
    "bad record mac",
    "ssl/tls alert",
)

T = TypeVar("T")


def is_transient_supabase_error(exc: BaseException) -> bool:
    """True si l'erreur ressemble à un problème réseau passager vers Supabase."""
    if isinstance(exc, OSError) and exc.errno in _TRANSIENT_ERRNOS:
        return True
    if isinstance(
        exc,
        (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError, httpx.TimeoutException),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = getattr(exc.response, "status_code", None)
        if status in _TRANSIENT_HTTP_STATUSES:
            return True
    # supabase_auth.errors.AuthRetryableError signale explicitement un retry.
    if exc.__class__.__name__ == "AuthRetryableError":
        return True
    cause = exc.__cause__
    if cause is not None and cause is not exc:
        return is_transient_supabase_error(cause)
    msg = str(exc).lower()
    if any(m in msg for m in _TRANSIENT_MARKERS):
        return True
    # Détection par message pour les codes HTTP transitoires remontés via str(exc).
    return any(
        f" {status} " in msg or f"'{status} " in msg or f'"{status} ' in msg
        for status in _TRANSIENT_HTTP_STATUSES
    )


def create_supabase_httpx_client() -> httpx.Client:
    """
    Client HTTP partagé pour Supabase.

    HTTP/2 désactivé : évite des ReadError [Errno 35] sous charge locale (macOS + httpcore).
    """
    return httpx.Client(http2=False, timeout=60.0)


def execute_with_retry(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    base_delay_s: float = 0.05,
) -> T:
    """Réessaie les appels Supabase sur erreurs réseau transitoires."""
    last: BaseException | None = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if is_transient_supabase_error(exc) and attempt < retries - 1:
                time.sleep(base_delay_s * (attempt + 1))
                continue
            raise
    assert last is not None
    raise last
