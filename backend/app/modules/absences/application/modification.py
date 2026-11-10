"""Modifier un congé après création — orchestration pure.

Retour du 10/11/2026 (RTT posé au mauvais jour chez MAJI) : un congé saisi
ne se corrigeait qu'en l'annulant puis en le ressaisissant. La modification
fait ces deux gestes en un : l'ancienne demande est annulée (le planning est
restauré), la nouvelle passe par la création, donc par les mêmes contrôles
(jours, demi-journées, soldes, fériés) ; si la nouvelle est refusée,
l'ancienne est rétablie et le refus remonte tel quel.

Les arrêts ne passent pas par ici : leurs dates portent IJSS, subrogation et
signalements DSN, qui ont leurs propres parcours.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

logger = logging.getLogger(__name__)

#: Congés dont les jours se modifient après création.
TYPES_MODIFIABLES = frozenset(
    {
        "conge_paye",
        "rtt",
        "jtc",
        "sans_solde",
        "repos_compensateur",
        "recuperation_modulation",
        "evenement_familial",
    }
)


def refus_modification(ancienne: Mapping[str, Any]) -> str | None:
    """La phrase qui dit pourquoi ce congé ne se modifie pas, ou `None`."""
    type_ = str(ancienne.get("type") or "")
    if type_ not in TYPES_MODIFIABLES:
        if type_.startswith("arret"):
            return (
                "Un arrêt ne se modifie pas ici : ses dates portent les IJSS et la DSN. "
                "Annulez-le puis ressaisissez-le."
            )
        return "Ce type d'absence ne se modifie pas après création."
    statut = str(ancienne.get("status") or "")
    if statut != "validated":
        if statut == "pending":
            return "Une demande en attente se valide ou se refuse ; elle ne se modifie pas."
        return "Cette demande est annulée ou refusée : posez un nouveau congé."
    return None


def remplacer_absence(
    *,
    annuler: Callable[[], Any],
    creer: Callable[[], dict],
    retablir: Callable[[], Any],
) -> dict:
    """Annule l'ancienne demande, crée la nouvelle ; rétablit l'ancienne si la
    création est refusée. Rien ne reste à moitié fait sans le dire."""
    annuler()
    try:
        return creer()
    except Exception:
        try:
            retablir()
        except Exception as exc:
            logger.exception("Congé d'origine non rétabli après un refus de modification")
            raise RuntimeError(
                "La modification est refusée et le congé d'origine n'a pas pu être "
                "rétabli : il est annulé. Ressaisissez-le dans « Saisir les congés »."
            ) from exc
        raise


__all__ = ["TYPES_MODIFIABLES", "refus_modification", "remplacer_absence"]
