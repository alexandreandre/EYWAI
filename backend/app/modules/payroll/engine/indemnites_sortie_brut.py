"""Indemnités de départ soumises à cotisations, portées par le brut.

Le dossier de départ (module Départs) calcule le préavis et l'indemnité
compensatrice de congés payés. Ce sont des salaires : elles se cotisent et
s'imposent comme le reste du brut. Le bulletin de sortie les ajoutait après
les cotisations, ce qui donnait un net supérieur au brut (salarié 086,
Colorplast, juillet 2026). Elles entrent donc dans le brut, ici, avant les
cotisations ; `creer_bulletin_sortie` ne les ajoute plus une seconde fois.

Les indemnités de licenciement et de rupture conventionnelle sont ajoutées
après cotisations par le bulletin de sortie pour leur part exclue des
cotisations ; la part qui dépasse les limites (régime calculé par le dossier,
engine/regime_indemnites_rupture) entre ici au brut.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .regime_indemnites_rupture import lignes_brut_parts_soumises

LIBELLES_SOUMISES = (
    ("indemnite_preavis", "Indemnité compensatrice de préavis"),
    ("indemnite_conges", "Indemnité compensatrice de congés payés"),
    # Départ volontaire à la retraite : soumise aux cotisations, à la CSG/CRDS
    # et à l'impôt pour tout son montant (BOSS, Indemnités de rupture, § 1560).
    ("indemnite_depart_retraite", "Indemnité de départ à la retraite"),
    # Fin de période d'essai, délai de prévenance non respecté par l'employeur :
    # les salaires qu'il aurait perçus (L1221-25), DSN 017.
    ("indemnite_delai_prevenance", "Indemnité compensatrice de délai de prévenance"),
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
                # Indemnité conventionnelle versée : son libellé (DSN 006).
                "libelle": str(indemnite.get("libelle_bulletin") or libelle),
                "quantite": None,
                "taux": None,
                "gain": round(montant, 2),
                "perte": None,
                "is_indemnite_sortie": True,
            }
        )
    lignes.extend(lignes_brut_parts_soumises(dossier))
    return lignes
