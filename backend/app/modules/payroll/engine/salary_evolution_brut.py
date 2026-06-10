"""Application evolution_salaire_mois dans le calcul du brut."""

from __future__ import annotations

from typing import Any, Dict, List

from .contexte import ContextePaie


def _evolution_mois(contexte: ContextePaie) -> Dict[str, Any] | None:
    remuneration = contexte.contrat.get("remuneration") or {}
    evo = remuneration.get("evolution_salaire_mois")
    return evo if isinstance(evo, dict) else None


def salaire_contractuel_avec_evolution(
    contexte: ContextePaie,
    salaire_contractuel: float,
) -> float:
    """Remplace le salaire mensuel par le montant proratisé si changement en cours de mois."""
    evo = _evolution_mois(contexte)
    if evo and evo.get("prorata"):
        try:
            return float(evo["prorata"]["montant_mois"])
        except (TypeError, ValueError, KeyError):
            pass
    return salaire_contractuel


def lignes_rappel_salaire(contexte: ContextePaie) -> List[Dict[str, Any]]:
    """Ligne distincte de rappel rétroactif (mois antérieurs au bulletin courant)."""
    evo = _evolution_mois(contexte)
    if not evo:
        return []
    rappel = evo.get("rappel")
    if not isinstance(rappel, dict):
        return []
    montant = rappel.get("montant")
    try:
        montant_f = float(montant or 0)
    except (TypeError, ValueError):
        return []
    if montant_f <= 0:
        return []

    debut = rappel.get("periode_debut") or ""
    fin = rappel.get("periode_fin") or ""
    if debut and fin:
        libelle = f"Rappel de salaire (période {debut} au {fin})"
    else:
        libelle = "Rappel de salaire"

    return [
        {
            "libelle": libelle,
            "quantite": None,
            "taux": None,
            "gain": round(montant_f, 2),
            "perte": None,
        }
    ]


__all__ = [
    "salaire_contractuel_avec_evolution",
    "lignes_rappel_salaire",
]
