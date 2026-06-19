"""Solde de congés payés à la date de sortie — pont vers le module absences."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class CpSoldeSortie:
    jours_restants: float
    conges_acquis: float
    conges_pris: float
    n1_remaining: float | None = None
    n_remaining: float | None = None
    source: str = "absences.compute_cp_period_balances"


def get_cp_solde_a_la_sortie(
    employee_id: str,
    exit_date: date,
    supabase_client: Any = None,
) -> CpSoldeSortie | None:
    """Retourne le solde CP à la date de sortie (source canonique : module absences)."""
    _ = supabase_client
    from app.modules.absences.application.queries import get_absence_balances_at_date

    balances = get_absence_balances_at_date(employee_id, exit_date)
    if not balances:
        return None

    cp = balances.get("conges_payes") or {}
    jours_restants = float(cp.get("solde", 0) or 0)
    conges_acquis = float(cp.get("acquis", 0) or 0)
    conges_pris = float(cp.get("pris", 0) or 0)

    return CpSoldeSortie(
        jours_restants=max(0.0, jours_restants),
        conges_acquis=conges_acquis,
        conges_pris=conges_pris,
        n1_remaining=cp.get("n1_remaining"),
        n_remaining=cp.get("n_remaining"),
    )
