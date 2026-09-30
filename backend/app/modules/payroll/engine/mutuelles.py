"""Les types de mutuelle d'un salarié, lus une fois par bulletin et jamais sautés.

Un bulletin ne sort pas sans ses mutuelles. Une lecture qui échoue (délai réseau)
est retentée deux fois ; si elle échoue encore, le calcul s'arrête avec un
message, au lieu de continuer sans les parts de mutuelle — septembre à blanc de
Comitech, 29/09/2026 : 127 € de mutuelle disparus, net trop haut de 130 €, pour
un simple avertissement. Une mutuelle de la fiche introuvable ou désactivée
arrête aussi le calcul : elle disparaissait de la même façon.

La lecture est gardée sur le contexte de paie : cotisations, CSG, net imposable
et net social lisent les mêmes lignes.
"""

from __future__ import annotations

import time
from typing import Any

from app.core import database
from app.core.logging import get_logger
from app.modules.payroll.engine.lectures import LectureIndispensable

logger = get_logger(__name__)

#: Relectures après un premier échec, et pause entre deux essais (secondes).
RELECTURES = 2
PAUSE = 1.0


class MutuelleIllisible(LectureIndispensable):
    """La mutuelle du salarié n'a pas pu être lue : le bulletin n'est pas calculé."""


def mutuelles_du_salarie(contexte: Any, mutuelle_type_ids: list[Any] | None) -> list[dict[str, Any]]:
    """Les types de mutuelle actifs de la fiche, ou une erreur — jamais une liste amputée."""
    ids = [str(i) for i in (mutuelle_type_ids or []) if i]
    if not ids:
        return []
    cle = tuple(sorted(ids))
    cache = getattr(contexte, "_mutuelles_lues", None)
    if cache is None:
        cache = {}
        try:
            contexte._mutuelles_lues = cache
        except AttributeError:
            pass
    if cle in cache:
        return cache[cle]

    derniere: Exception | None = None
    lignes: list[dict[str, Any]] | None = None
    for essai in range(RELECTURES + 1):
        try:
            reponse = (
                database.get_supabase_admin_client()
                .table("company_mutuelle_types")
                .select("*")
                .in_("id", ids)
                .eq("is_active", True)
                .execute()
            )
            lignes = list(reponse.data or [])
            break
        except Exception as exc:  # noqa: BLE001 — réseau : on relit, puis on s'arrête
            derniere = exc
            logger.warning("Lecture des mutuelles, essai %s sur %s : %s", essai + 1, RELECTURES + 1, exc)
            if essai < RELECTURES:
                time.sleep(PAUSE * (essai + 1))
    if lignes is None:
        raise MutuelleIllisible(
            "La mutuelle du salarié n'a pas pu être lue (connexion à la base "
            "interrompue). Le bulletin n'a pas été calculé : réessayez dans un instant."
        ) from derniere

    trouves = {str(m.get("id")) for m in lignes}
    manquants = [i for i in ids if i not in trouves]
    if manquants:
        raise MutuelleIllisible(
            "Une mutuelle de la fiche du salarié est introuvable ou désactivée. "
            "Le bulletin n'a pas été calculé : corrigez la mutuelle de la fiche "
            "(ou réactivez-la dans les réglages), puis relancez."
        )
    cache[cle] = lignes
    return lignes
