"""Taux horaire — domaine pur (variables paie astreinte)."""

from __future__ import annotations

from typing import Any

DUREE_LEGALE_HEBDO = 35.0


def _salaire_mensuel(employee: dict[str, Any]) -> float:
    salaire = employee.get("salaire_de_base")
    if isinstance(salaire, dict):
        try:
            return float(salaire.get("valeur") or 0)
        except (TypeError, ValueError):
            return 0.0
    if isinstance(salaire, (int, float)):
        return float(salaire)
    return 0.0


def resolve_hourly_rate(employee: dict[str, Any]) -> float:
    """Taux horaire brut = salaire mensuel / heures mensuelles contractuelles."""
    salaire = _salaire_mensuel(employee)
    duree_hebdo = float(employee.get("duree_hebdomadaire") or DUREE_LEGALE_HEBDO)
    if duree_hebdo <= 0:
        duree_hebdo = DUREE_LEGALE_HEBDO
    heures_mens = (duree_hebdo * 52) / 12
    if heures_mens <= 0 or salaire <= 0:
        return 0.0
    return round(salaire / heures_mens, 4)
