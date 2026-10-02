"""Une seule génération de bulletin à la fois pour un salarié et un mois.

Deux onglets, un double clic, ou une régénération IJSS pendant une génération
lançaient deux calculs du même bulletin en parallèle, chacun écrivant ses
résultats en base. Le verrou vit en base (table `payslip_generation_locks`,
migration `20260926140000_verrou_generation_bulletin.sql`) parce que le serveur
peut tourner sur plusieurs instances ; il expire seul après `DUREE_SECONDES`,
la durée maximale d'une requête.

Le verrou ne doit jamais empêcher la paie : si la base ne répond pas ou que la
migration n'est pas appliquée, la génération continue sans verrou, comme avant,
et un avertissement part dans les journaux.

Il est réentrant dans une même requête : corriger un bulletin prend le verrou,
écrit les variables du mois, puis régénère — et la régénération le redemande.
Une autre requête a son propre contexte et reste refusée.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from app.core.logging import get_logger

logger = get_logger("modules.payroll.verrou_generation")

# Un bulletin se calcule en une quinzaine de secondes. Une génération coupée
# net (instance arrêtée) ne rend pas son verrou : il bloquait 15 minutes, calé
# sur --timeout 900 de Cloud Run (recette du 02/10/2026). Cinq minutes suffisent.
DUREE_SECONDES = 300


class GenerationDejaEnCours(ValueError):
    """Une génération du même bulletin est déjà en cours (→ 409)."""

    code = "generation_en_cours"

    def __init__(self) -> None:
        super().__init__(
            "Une génération de ce bulletin est déjà en cours, ou s'est arrêtée "
            "sans finir. Réessayez dans 5 minutes au plus."
        )


#: Verrous tenus par la requête en cours (salarié, année, mois).
_TENUS: ContextVar[frozenset[tuple[str, int, int]]] = ContextVar(
    "verrous_de_generation_tenus", default=frozenset()
)


def _rpc(nom: str, params: dict[str, Any]) -> Any:
    from app.core.database import get_supabase_admin_client

    return get_supabase_admin_client().rpc(nom, params).execute().data


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
    try:
        pris: bool | None = bool(
            _rpc(
                "prendre_verrou_generation_bulletin",
                {**params, "p_duree_secondes": DUREE_SECONDES},
            )
        )
    except Exception:
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
    jeton_contexte = _TENUS.set(tenus | {cle})
    try:
        yield
    finally:
        _TENUS.reset(jeton_contexte)
        if pris:
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
