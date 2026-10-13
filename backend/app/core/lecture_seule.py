"""Lecture seule : un calcul répété lit la base une fois et n'y écrit jamais.

Le brut d'une prime pour un net voulu (lot 30) rejoue le bulletin du mois du
salarié plusieurs fois, en ne changeant que la prime essayée, en mémoire.
Chaque essai relisait toute la base — 56 requêtes environ, 16,7 s sur le site
de test pour une prime de 100 € nets (lot 31).

Dans un bloc `with lecture_seule():`

- chaque lecture (GET, HEAD) part une fois ; la même requête (adresse,
  filtres, en-têtes hors cookie) retrouve ensuite la réponse en mémoire. Les
  essais suivants calculent donc sur exactement les mêmes données que le
  premier, sans attendre la base ;
- toute écriture est refusée avant de partir (`EcritureEnLectureSeule`) ;
- `ecritures_permises()` vaut False : un calcul qui enregistre un résultat au
  passage le garde en mémoire (voir `compute_and_persist_grant`) ;
- `lire_une_fois()` garde une lecture longue à décoder (les 4 Mo de barèmes)
  et en rend une copie neuve à chaque appel.

La mémoire vit le temps du bloc, dans le contexte de la requête : deux
requêtes simultanées ne la partagent pas, et rien n'en reste après. Hors du
bloc, le client se comporte exactement comme `httpx.Client`.

`lectures_partagees()` (lot 43) sert la génération d'un bulletin, qui écrit :
une même lecture ne part qu'une fois tant que rien n'a été écrit ; toute
écriture part, puis vide la mémoire, et les lectures suivantes repartent vers
la base. Une génération relisait 22 fois une donnée déjà lue (la fiche, la
société, les périodes des variables…), autant d'allers-retours pour rien.
Dans un bloc `lecture_seule()` ouvert à l'intérieur, la lecture seule décide.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, TypeVar

import httpx

T = TypeVar("T")

#: Méthodes HTTP qui ne changent rien en base.
METHODES_DE_LECTURE = frozenset({"GET", "HEAD"})

#: En-têtes de transport : le corps gardé est déjà décompressé et mesuré.
_ENTETES_DE_TRANSPORT = frozenset({"content-encoding", "content-length", "transfer-encoding"})

#: Réponses qu'une nouvelle tentative peut changer : jamais gardées.
_STATUTS_PASSAGERS = frozenset({408, 425, 429})


class EcritureEnLectureSeule(RuntimeError):
    """Un calcul en lecture seule a tenté d'écrire : rien n'est parti."""


@dataclass
class LecturesGardees:
    """Les réponses lues pendant un bloc `lecture_seule()`."""

    reponses: dict[tuple, tuple[int, list[tuple[str, str]], bytes]] = field(default_factory=dict)
    #: Lectures décodées, gardées en JSON (voir `lire_une_fois`).
    decodees: dict[Hashable, str] = field(default_factory=dict)
    #: Lectures parties vers la base, et lectures servies depuis la mémoire.
    envoyees: int = 0
    servies: int = 0
    verrou: threading.Lock = field(default_factory=threading.Lock, repr=False)


_EN_COURS: ContextVar[LecturesGardees | None] = ContextVar("lecture_seule", default=None)
_PARTAGEES: ContextVar[LecturesGardees | None] = ContextVar("lectures_partagees", default=None)


@contextmanager
def lecture_seule() -> Iterator[LecturesGardees]:
    """Le temps du bloc : lectures gardées, écritures refusées."""
    lectures = LecturesGardees()
    jeton = _EN_COURS.set(lectures)
    try:
        yield lectures
    finally:
        _EN_COURS.reset(jeton)


@contextmanager
def lectures_partagees() -> Iterator[LecturesGardees]:
    """Le temps du bloc : une même lecture part une fois tant que rien n'est écrit."""
    lectures = LecturesGardees()
    jeton = _PARTAGEES.set(lectures)
    try:
        yield lectures
    finally:
        _PARTAGEES.reset(jeton)


def lectures_partagees_en_cours() -> LecturesGardees | None:
    """Les lectures du bloc `lectures_partagees()` en cours, ou None."""
    return _PARTAGEES.get()


def lecture_seule_en_cours() -> LecturesGardees | None:
    """Les lectures du bloc en cours, ou None hors lecture seule."""
    return _EN_COURS.get()


def ecritures_permises() -> bool:
    """False dans un bloc `lecture_seule()` : rien ne doit être enregistré."""
    return _EN_COURS.get() is None


def lire_une_fois(cle: Hashable, lire: Callable[[], T]) -> T:
    """Une lecture longue à décoder, faite une fois par bloc de lecture seule.

    Hors lecture seule : `lire()`, à chaque appel. En lecture seule : la
    première valeur est gardée en JSON, et chaque appel en rend une copie
    neuve — un essai qui modifierait la sienne ne touche pas les suivants.
    `lire()` doit rendre des données JSON (dictionnaires, listes, textes,
    nombres) : c'est le cas de tout ce qui vient de la base.
    """
    lectures = _EN_COURS.get()
    if lectures is None:
        return lire()
    with lectures.verrou:
        gardee = lectures.decodees.get(cle)
    if gardee is None:
        valeur: Any = lire()
        gardee = json.dumps(valeur, ensure_ascii=False)
        with lectures.verrou:
            lectures.decodees[cle] = gardee
    return json.loads(gardee)


#: En-têtes sans effet sur les données rendues : le cookie `__cf_bm` que pose
#: Cloudflare devant Supabase change au fil des réponses.
_ENTETES_HORS_CLE = frozenset({"cookie"})


def _cle(request: httpx.Request) -> tuple:
    entetes = tuple(
        sorted(
            (nom.lower(), valeur)
            for nom, valeur in request.headers.multi_items()
            if nom.lower() not in _ENTETES_HORS_CLE
        )
    )
    return (request.method, str(request.url), entetes)


class ClientHttpSupabase(httpx.Client):
    """Le client HTTP partagé de Supabase (tables et stockage).

    Hors des blocs, il envoie chaque requête telle quelle. En lecture seule, il
    garde les lectures et refuse les écritures. En lectures partagées, il garde
    les lectures jusqu'à la première écriture, qui part et vide la mémoire.
    """

    def send(self, request: httpx.Request, **kwargs) -> httpx.Response:  # type: ignore[override]
        lectures = _EN_COURS.get()
        if lectures is None:
            partagees = _PARTAGEES.get()
            if partagees is None:
                return super().send(request, **kwargs)
            if request.method not in METHODES_DE_LECTURE:
                try:
                    return super().send(request, **kwargs)
                finally:
                    # Après l'écriture, partie ou non : rien de ce qui a été
                    # lu avant ne vaut plus.
                    with partagees.verrou:
                        partagees.reponses.clear()
            return self._lire_en_gardant(partagees, request, **kwargs)
        if request.method not in METHODES_DE_LECTURE:
            raise EcritureEnLectureSeule(
                f"Écriture refusée : calcul en lecture seule ({request.method} {request.url.path})."
            )
        return self._lire_en_gardant(lectures, request, **kwargs)

    def _lire_en_gardant(
        self, lectures: LecturesGardees, request: httpx.Request, **kwargs
    ) -> httpx.Response:
        cle = _cle(request)
        with lectures.verrou:
            gardee = lectures.reponses.get(cle)
        if gardee is not None:
            statut, entetes, corps = gardee
            reponse = httpx.Response(statut, headers=entetes, content=corps, request=request)
            reponse.elapsed = timedelta(0)
            with lectures.verrou:
                lectures.servies += 1
            return reponse
        reponse = super().send(request, **kwargs)
        reponse.read()
        with lectures.verrou:
            lectures.envoyees += 1
            if reponse.status_code < 500 and reponse.status_code not in _STATUTS_PASSAGERS:
                lectures.reponses[cle] = (
                    reponse.status_code,
                    [
                        (nom, valeur)
                        for nom, valeur in reponse.headers.multi_items()
                        if nom.lower() not in _ENTETES_DE_TRANSPORT
                    ],
                    reponse.content,
                )
        return reponse
