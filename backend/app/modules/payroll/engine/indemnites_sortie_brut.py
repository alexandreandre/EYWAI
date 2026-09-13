"""Indemnités de départ soumises à cotisations, portées par le brut.

Le dossier de départ (module Départs) calcule le préavis et l'indemnité
compensatrice de congés payés. Ce sont des salaires : elles se cotisent et
s'imposent comme le reste du brut. Le bulletin de sortie les ajoutait après
les cotisations, ce qui donnait un net supérieur au brut (Demory,
Colorplast, juillet 2026). Elles entrent donc dans le brut, ici, avant les
cotisations ; `creer_bulletin_sortie` ne les ajoute plus une seconde fois.

Les indemnités exonérées (licenciement, rupture conventionnelle) restent
ajoutées après cotisations par le bulletin de sortie.
"""

from __future__ import annotations

from typing import Any, Dict, List

LIBELLES_SOUMISES = (
    ("indemnite_preavis", "Indemnité compensatrice de préavis"),
    ("indemnite_conges", "Indemnité compensatrice de congés payés"),
)


def lignes_indemnites_sortie_soumises(contexte: Any) -> List[Dict[str, Any]]:
    """Lignes de brut pour les indemnités soumises du dossier de départ."""
    dossier = getattr(contexte, "exit_indemnities", None)
    if not isinstance(dossier, dict):
        return []
    lignes: List[Dict[str, Any]] = []
    for cle, libelle in LIBELLES_SOUMISES:
        indemnite = dossier.get(cle) or {}
        if not isinstance(indemnite, dict):
            continue
        try:
            montant = float(indemnite.get("montant") or 0)
        except (TypeError, ValueError):
            montant = 0.0
        if montant <= 0:
            continue
        lignes.append(
            {
                "libelle": libelle,
                "quantite": None,
                "taux": None,
                "gain": round(montant, 2),
                "perte": None,
                "is_indemnite_sortie": True,
            }
        )
    return lignes
