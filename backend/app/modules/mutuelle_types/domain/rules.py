"""
Règles métier pour mutuelle_types.

Règles pures : messages et critères sans accès DB ni FastAPI.
À utiliser dans la couche application.
"""

from __future__ import annotations


def message_libelle_deja_existant_avec_statut(libelle: str, statut: str) -> str:
    """Message d’erreur quand une formule avec ce libellé existe déjà (statut actif/inactif)."""
    return (
        f"Une formule de mutuelle avec le libellé '{libelle}' existe déjà pour cette entreprise (statut: {statut}). "
        "Veuillez utiliser un libellé différent ou modifier la formule existante."
    )


def message_libelle_deja_existant(libelle: str) -> str:
    """Message d’erreur quand une formule avec ce libellé existe déjà (contrainte unique)."""
    return (
        f"Une formule de mutuelle avec le libellé '{libelle}' existe déjà pour cette entreprise. "
        "Veuillez utiliser un libellé différent."
    )


def statut_formule(is_active: bool) -> str:
    """Libellé du statut pour affichage (active / inactive)."""
    return "active" if is_active else "inactive"
