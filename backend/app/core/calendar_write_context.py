"""Jeton de réservation transmis par requête, jamais dans un client partagé."""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

import httpx

CALENDAR_TOKEN_HEADER = "X-Eywai-Calendar-Token"
T = TypeVar("T")
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


class CalendrierReserve(ValueError):
    """Le calendrier est resté réservé par un enregistrement en cours au-delà du délai."""


MESSAGE_CALENDRIER_RESERVE = (
    "Le calendrier de ce salarié est en cours d’enregistrement par une autre personne : "
    "réessayez dans un instant."
)


def _est_reservation_calendrier(exc: Exception) -> bool:
    return getattr(exc, "code", None) == "PT409"


def relancer_si_calendrier_reserve(
    operation: Callable[[], T],
    *,
    delai_max: float = 20.0,
    dormir: Callable[[float], None] | None = None,
    maintenant: Callable[[], float] | None = None,
) -> T:
    """Rejoue une opération ENTIÈRE (relecture comprise) refusée par la réservation d'un calendrier.

    Un auteur extérieur à l'éditeur (validation d'absence, import…) peut tomber
    sur un mois qu'une RH est en train d'enregistrer : le trigger refuse son
    écriture (PT409) et rien n'est écrit. On rejoue alors toute l'opération,
    qui relit le calendrier : renvoyer la même écriture écraserait la saisie de
    la RH avec une lecture périmée. Au-delà du délai, `CalendrierReserve`.
    L'enregistrement qui détient lui-même un jeton n'attend jamais : pour lui,
    PT409 veut dire « réservation expirée ».
    """
    dormir = dormir or time.sleep
    maintenant = maintenant or time.monotonic
    debut = maintenant()
    attente = 0.25
    while True:
        try:
            return operation()
        except Exception as exc:
            if not _est_reservation_calendrier(exc) or _TOKEN.get():
                raise
            if maintenant() - debut >= delai_max:
                raise CalendrierReserve(MESSAGE_CALENDRIER_RESERVE) from exc
            dormir(attente)
            attente = min(attente * 2, 2.0)
