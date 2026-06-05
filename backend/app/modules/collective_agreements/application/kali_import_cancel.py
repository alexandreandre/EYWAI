"""Annulation coopérative des imports KALI / Légifrance en cours."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_CANCEL_LOCK = threading.Lock()
_CANCELLED_IDCC: set[str] = set()
_CATALOG_SYNC_CANCEL = threading.Event()


class KaliImportCancelled(Exception):
    """Import interrompu à la demande de l'utilisateur."""


def _normalize_idcc(idcc: str) -> str:
    return str(idcc or "").strip()


def request_cancel_idcc(idcc: str) -> bool:
    norm = _normalize_idcc(idcc)
    if not norm:
        return False
    with _CANCEL_LOCK:
        _CANCELLED_IDCC.add(norm)
    return True


def request_cancel_catalog_sync() -> bool:
    _CATALOG_SYNC_CANCEL.set()
    return True


def is_cancel_requested(*, idcc: str | None = None) -> bool:
    if _CATALOG_SYNC_CANCEL.is_set():
        return True
    if idcc:
        norm = _normalize_idcc(idcc)
        with _CANCEL_LOCK:
            return norm in _CANCELLED_IDCC
    return False


def clear_cancel_idcc(idcc: str) -> None:
    norm = _normalize_idcc(idcc)
    with _CANCEL_LOCK:
        _CANCELLED_IDCC.discard(norm)


def clear_catalog_sync_cancel() -> None:
    _CATALOG_SYNC_CANCEL.clear()


def raise_if_cancelled(*, idcc: str | None = None) -> None:
    if is_cancel_requested(idcc=idcc):
        raise KaliImportCancelled()


@contextmanager
def kali_import_scope(*, idcc: str) -> Iterator[None]:
    """Réinitialise le flag d'annulation IDCC au démarrage d'un import unitaire."""
    clear_cancel_idcc(idcc)
    try:
        yield
    finally:
        clear_cancel_idcc(idcc)


def reset_kali_import_cancel_state_for_tests() -> None:
    with _CANCEL_LOCK:
        _CANCELLED_IDCC.clear()
    _CATALOG_SYNC_CANCEL.clear()
