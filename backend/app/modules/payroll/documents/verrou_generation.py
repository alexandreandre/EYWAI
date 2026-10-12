"""Une seule génération de bulletin à la fois pour un salarié et un mois.

Deux onglets, un double clic, ou une régénération IJSS pendant une génération
lançaient deux calculs du même bulletin en parallèle, chacun écrivant ses
résultats en base. Le verrou vit en base (table `payslip_generation_locks`,
migration `20260926140000_verrou_generation_bulletin.sql`) parce que le serveur
peut tourner sur plusieurs instances ; il expire seul après `DUREE_SECONDES`.

Le verrou ne doit jamais empêcher la paie : si la base ne répond pas ou que la
migration n'est pas appliquée, la génération continue sans verrou, comme avant,
et un avertissement part dans les journaux.

Il est réentrant dans une même requête : corriger un bulletin prend le verrou,
écrit les variables du mois, puis régénère — et la régénération le redemande.
Une autre requête a son propre contexte et reste refusée.

Il est rendu à la fin de chaque génération, réussie ou non (`finally`), y
compris quand la prise n'a pas répondu : la base a pu le poser quand même.
Seul un processus arrêté net ne rend rien — c'est ce qui a bloqué un bulletin
5 minutes le 12/10/2026 (instance tombée pendant le calcul : 42 s sans une
requête vers la base, aucun rendu, puis 409 jusqu'à l'expiration). Le verrou
est donc court et prolongé tant que la génération vit : mort avec elle, il
libère le bulletin en une minute au plus.
"""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from app.core.lecture_seule import EcritureEnLectureSeule
from app.core.logging import get_logger

logger = get_logger("modules.payroll.verrou_generation")

# Un bulletin se calcule en une quinzaine de secondes. Le verrou est pris pour
# une minute et prolongé toutes les 20 secondes tant que la génération tourne :
# une instance arrêtée net le laisse expirer en une minute au plus (il bloquait
# 15 minutes le 02/10/2026, puis 5 minutes le 12/10/2026).
DUREE_SECONDES = 60
INTERVALLE_PROLONGATION_SECONDES = 20.0
# Une génération bloquée sans fin ne garde pas le bulletin plus longtemps que
# la durée qu'on donnait au verrou avant : il n'est plus prolongé au-delà.
PROLONGATION_MAX_SECONDES = 300


class GenerationDejaEnCours(ValueError):
    """Une génération du même bulletin est déjà en cours (→ 409)."""

    code = "generation_en_cours"

    def __init__(self) -> None:
        super().__init__(
            "Une génération de ce bulletin est déjà en cours, ou s'est arrêtée "
            "sans finir. Réessayez dans une minute."
        )


#: Verrous tenus par la requête en cours (salarié, année, mois).
_TENUS: ContextVar[frozenset[tuple[str, int, int]]] = ContextVar(
    "verrous_de_generation_tenus", default=frozenset()
)


def _rpc(nom: str, params: dict[str, Any]) -> Any:
    from app.core.database import get_supabase_admin_client

    return get_supabase_admin_client().rpc(nom, params).execute().data


def _prolonger(params: dict[str, Any]) -> None:
    """Repousse l'expiration du verrou tenu par ce jeton (sans effet sinon)."""
    from app.core.database import get_supabase_admin_client

    jusqu_a = datetime.now(timezone.utc) + timedelta(seconds=DUREE_SECONDES)
    get_supabase_admin_client().table("payslip_generation_locks").update(
        {"locked_until": jusqu_a.isoformat()}
    ).match(
        {
            "employee_id": params["p_employee_id"],
            "year": params["p_year"],
            "month": params["p_month"],
            "jeton": params["p_jeton"],
        }
    ).execute()


def _prolonger_tant_que(params: dict[str, Any], fini: threading.Event) -> None:
    """Prolonge le verrou à intervalles réguliers, jusqu'à la fin ou au plafond."""
    debut = datetime.now(timezone.utc)
    while not fini.wait(INTERVALLE_PROLONGATION_SECONDES):
        if (datetime.now(timezone.utc) - debut).total_seconds() > PROLONGATION_MAX_SECONDES:
            return
        try:
            _prolonger(params)
        except Exception:
            logger.warning(
                "Verrou de génération non prolongé (employee_id=%s, %02d/%s).",
                params["p_employee_id"],
                params["p_month"],
                params["p_year"],
                exc_info=True,
            )


@contextmanager
def verrou_de_generation(employee_id: str, year: int, month: int) -> Iterator[None]:
    """Tient le verrou (salarié, année, mois) le temps du bloc.

    Lève `GenerationDejaEnCours` si une autre génération le tient déjà.
    """
    cle = (str(employee_id), int(year), int(month))
    tenus = _TENUS.get()
    if cle in tenus:
        yield
        return
    params = {
        "p_employee_id": str(employee_id),
        "p_year": int(year),
        "p_month": int(month),
        "p_jeton": str(uuid.uuid4()),
    }
    #: Rien n'est parti vers la base (calcul en lecture seule) : rien à rendre.
    rien_en_base = False
    try:
        pris: bool | None = bool(
            _rpc(
                "prendre_verrou_generation_bulletin",
                {**params, "p_duree_secondes": DUREE_SECONDES},
            )
        )
    except Exception as exc:
        rien_en_base = isinstance(exc, EcritureEnLectureSeule)
        logger.warning(
            "Verrou de génération indisponible : génération sans verrou "
            "(employee_id=%s, %02d/%s).",
            employee_id,
            int(month),
            year,
            exc_info=True,
        )
        pris = None
    if pris is False:
        raise GenerationDejaEnCours()
    fini = threading.Event()
    if pris:
        threading.Thread(
            target=_prolonger_tant_que,
            args=(params, fini),
            name="prolonger-verrou-generation",
            daemon=True,
        ).start()
    jeton_contexte = _TENUS.set(tenus | {cle})
    try:
        yield
    finally:
        fini.set()
        _TENUS.reset(jeton_contexte)
        # Pris, ou peut-être pris (la réponse s'est perdue) : rendu avec notre
        # jeton, qui ne supprime que le verrou de cette génération.
        if pris or (pris is None and not rien_en_base):
            try:
                _rpc("rendre_verrou_generation_bulletin", params)
            except Exception:
                logger.warning(
                    "Verrou de génération non rendu (employee_id=%s, %02d/%s) : "
                    "il expirera seul.",
                    employee_id,
                    int(month),
                    year,
                    exc_info=True,
                )
