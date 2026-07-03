"""
Règles métier transverses liées au statut d'emploi (sans I/O).
"""

from __future__ import annotations


def is_forfait_jour(statut: str | None, explicit: bool | None = None) -> bool:
    """True si le salarié est géré en forfait jours.

    Le booléen explicite est la source de vérité. Le libellé historique reste
    supporté pour les anciennes données non encore migrées.
    """
    if explicit is not None:
        return bool(explicit)
    if not statut:
        return False
    return "forfait jour" in statut.lower()


def is_cadre(statut: str | None) -> bool:
    """Cadre / assimilé cadre (ex. « Cadre au forfait jour »), hors non-cadre."""
    compact = (statut or "").strip().lower().replace(" ", "").replace("-", "")
    return "cadre" in compact and "noncadre" not in compact


def is_non_cadre(statut: str | None) -> bool:
    compact = (statut or "").strip().lower().replace(" ", "").replace("-", "")
    return "noncadre" in compact


def statut_categoriel_clean(statut: str | None) -> str | None:
    """Retourne le statut catégoriel sans pollution forfait jours."""
    if is_cadre(statut):
        return "Cadre"
    if is_non_cadre(statut):
        return "Non-Cadre"
    return statut


def effective_statut_for_payroll(
    statut: str | None, explicit_forfait_jour: bool | None = None
) -> str | None:
    """Libellé interne rétrocompatible pour les modules encore basés sur statut."""
    clean = statut_categoriel_clean(statut)
    if is_forfait_jour(statut, explicit_forfait_jour):
        base = clean or "Cadre"
        if "forfait jour" in base.lower():
            return base
        return f"{base} au forfait jour"
    return clean


__all__ = [
    "is_forfait_jour",
    "is_cadre",
    "is_non_cadre",
    "statut_categoriel_clean",
    "effective_statut_for_payroll",
]
