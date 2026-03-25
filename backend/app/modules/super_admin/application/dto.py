"""
DTOs internes du module super_admin.

Structures pour échange application <-> infrastructure.
La logique applicative est dans commands.py, queries.py, service.py ;
les entrées/sorties restent en dict pour compatibilité exacte avec le legacy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GlobalStatsDto:
    """Données agrégées pour GET /dashboard/stats."""

    companies_total: int = 0
    companies_active: int = 0
    users_total: int = 0
    users_by_role: Dict[str, int] = field(default_factory=dict)
    employees_total: int = 0
    super_admins_total: int = 0
    top_companies: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CompanyListItemDto:
    """Une entreprise dans la liste GET /companies (avec employees_count, users_count, group_name)."""

    raw: Dict[str, Any]  # Placeholder : champs réels à définir en migration


@dataclass
class ReductionFillonResultDto:
    """Résultat détaillé du calcul réduction Fillon (structure dict conservée en migration)."""

    payload: Dict[str, Any]  # Structure complète retournée par le legacy endpoint
