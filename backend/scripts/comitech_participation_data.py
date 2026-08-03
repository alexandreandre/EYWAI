"""Données participation Comitech Composite — exercice clos au 31/12/2025 (Quadra)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.donnees_nominatives import charger_ou_vide

PARTICIPATION_EXERCISE_YEAR = 2025
PARTICIPATION_SIMULATION_NAME = (
    "Participation 2025 — Quadra (exercice clos 31/12/2025)"
)
PARTICIPATION_EXERCISE_LABEL = "PARTICIPATION 2025"
PARTICIPATION_SOURCE = "Registre Quadra — PRIME PARTICIPATION exercice 2025"

# Totaux entreprise (fiche Quadra)
PARTICIPATION_RSP = 31_840.06
PARTICIPATION_SALAIRES_BRUTS = 515_009.15
PARTICIPATION_DEDUCTIONS_MAINTIEN = 15_419.75
PARTICIPATION_BASES_PONDEREE = 447_003.88
PARTICIPATION_PASS_ANNUEL = 46_368.0  # 3 × PASS = 139 104 €

PARTICIPATION_PAYROLL_YEAR = 2026
PARTICIPATION_PAYROLL_MONTH = 5

PARTICIPATION_MODE = "salaire"
PARTICIPATION_SALAIRE_PERCENT = 100
PARTICIPATION_PRESENCE_PERCENT = 0


@dataclass(frozen=True)
class ParticipationEmployeeSeed:
    """Montants participation par salarié (brut après plafonnement Quadra)."""

    last_name: str
    first_hint: str | None
    gross_amount: float
    advance_amount: float = 0.0
    advance_label: str = "décembre 2025"
    last_name_aliases: tuple[str, ...] = ()


def _charger_participation() -> tuple[ParticipationEmployeeSeed, ...]:
    """Salariés éligibles (≥ 3 mois d'ancienneté au 31/12/2025) et leurs montants.

    Nom, prénom et montant de participation sont des données personnelles : la
    table vit dans `data/comitech/referentiel/participation-2025.json`, hors
    dépôt Git.
    """
    return tuple(
        ParticipationEmployeeSeed(
            last_name=ligne["last_name"],
            first_hint=ligne.get("first_hint"),
            gross_amount=ligne["gross_amount"],
            advance_amount=ligne.get("advance_amount", 0.0),
            advance_label=ligne.get("advance_label", "décembre 2025"),
            last_name_aliases=tuple(ligne.get("last_name_aliases") or ()),
        )
        for ligne in charger_ou_vide("comitech", "participation-2025")
    )


COMITECH_PARTICIPATION_2025: tuple[ParticipationEmployeeSeed, ...] = (
    _charger_participation()
)


def participation_simulation_payload(
    company_id: str,
    results_data: dict[str, Any],
) -> dict[str, Any]:
    """Dict d'insertion Supabase pour participation_simulations."""
    return {
        "company_id": company_id,
        "year": PARTICIPATION_EXERCISE_YEAR,
        "simulation_name": PARTICIPATION_SIMULATION_NAME,
        "benefice_net": 0,
        "capitaux_propres": 0,
        "salaires_bruts": PARTICIPATION_SALAIRES_BRUTS,
        "valeur_ajoutee": PARTICIPATION_SALAIRES_BRUTS,
        "participation_mode": PARTICIPATION_MODE,
        "participation_salaire_percent": PARTICIPATION_SALAIRE_PERCENT,
        "participation_presence_percent": PARTICIPATION_PRESENCE_PERCENT,
        "interessement_enabled": False,
        "interessement_envelope": None,
        "interessement_mode": None,
        "interessement_salaire_percent": 50,
        "interessement_presence_percent": 50,
        "results_data": results_data,
    }
