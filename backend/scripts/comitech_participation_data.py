"""Données participation Comitech Composite — exercice clos au 31/12/2025 (Quadra)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


# Salariés éligibles (≥ 3 mois d'ancienneté au 31/12/2025).
# Exclus : LACAQUE Virginie, MALACARNE Laura.
COMITECH_PARTICIPATION_2025: tuple[ParticipationEmployeeSeed, ...] = (
    ParticipationEmployeeSeed("BOUDJEMAA", "Lahouari", 2.51),
    ParticipationEmployeeSeed("BOUFRIDA", "Samir", 1_752.57, 500.0),
    ParticipationEmployeeSeed(
        "BOUVEYRON",
        "Michel",
        3_503.94,
        1_000.0,
        last_name_aliases=("BOUVERYON",),
    ),
    ParticipationEmployeeSeed(
        "CASANOVA",
        "Vitor",
        1_935.47,
        500.0,
        last_name_aliases=("CASANOVA DA SILVA",),
    ),
    ParticipationEmployeeSeed("CHAMBERT", "Lucas", 876.94, 500.0),
    ParticipationEmployeeSeed("CORDEAU", "Olivier", 768.74),
    ParticipationEmployeeSeed(
        "DA SILVA CARDOSO",
        "Vitor",
        24.80,
        last_name_aliases=("DA SILVA", "CASANOVA DA SILVA"),
    ),
    ParticipationEmployeeSeed(
        "MARCHICH",
        "Hafida",
        841.68,
        250.0,
        last_name_aliases=("EL IDRISSI",),
    ),
    ParticipationEmployeeSeed("GARCIA", "Mickael", 2_752.11, 1_000.0),
    ParticipationEmployeeSeed("GENAND", "Catherine", 2_360.25, 500.0),
    ParticipationEmployeeSeed("GOYAT", "Stephane", 1_615.65, 500.0),
    ParticipationEmployeeSeed(
        "PRONIER",
        "Nadine",
        2_120.19,
        500.0,
        last_name_aliases=("GROS",),
    ),
    ParticipationEmployeeSeed("JEAN", "David", 587.71, 250.0),
    ParticipationEmployeeSeed("MARTINEZ", "Veronique", 472.22),
    ParticipationEmployeeSeed(
        "MARCHICH",
        "Yamena",
        1_616.20,
        500.0,
        last_name_aliases=("OUASSIF",),
    ),
    ParticipationEmployeeSeed("POINSIGNON", "Thibault", 2_364.32, 500.0),
    ParticipationEmployeeSeed("SARDA", "Dominique", 3_502.71, 1_000.0),
    ParticipationEmployeeSeed("SOW", "Mamadou", 763.60, 250.0),
    ParticipationEmployeeSeed("TROUILLOUD", "Florian", 2_269.02, 500.0),
    ParticipationEmployeeSeed("VALLAT", "Romain", 1_709.43, 500.0),
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
