"""Jeton de réservation transmis par requête, jamais dans un client partagé."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import httpx

CALENDAR_TOKEN_HEADER = "X-Eywai-Calendar-Token"
_TOKEN: ContextVar[str | None] = ContextVar("calendar_write_token", default=None)


@contextmanager
def calendar_write_token(token: str) -> Iterator[None]:
    previous = _TOKEN.set(token)
    try:
        yield
    finally:
        _TOKEN.reset(previous)


def apply_calendar_write_token(request: httpx.Request) -> None:
    """Tous les auteurs Supabase d'une même opération portent son jeton.

    Le header vit sur la requête HTTP, pas sur les headers du client singleton.
    Un jeton résiduel ne peut donc pas être repris par une autre RH.
    """
    request.headers.pop(CALENDAR_TOKEN_HEADER, None)
    token = _TOKEN.get()
    if token and request.url.path.startswith("/rest/v1/"):
        request.headers[CALENDAR_TOKEN_HEADER] = token
