"""
DTOs applicatifs pour participation.

Entrées/sorties des cas d'usage (employee-data, create/list/get/delete simulation).
Helpers de construction et de conversion entité -> réponse API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from app.modules.participation.domain.entities import ParticipationSimulation


@dataclass
class EmployeeParticipationRow:
    """Une ligne de données employé pour le simulateur (salaire annuel, présence, ancienneté)."""

    employee_id: str
    first_name: str
    last_name: str
    annual_salary: float
    presence_days: int
    seniority_years: int
    has_real_salary: bool
    has_real_presence: bool


@dataclass
class SimulationCreateInput:
    """Entrée pour la création d'une simulation (aligné ParticipationSimulationCreate)."""

    year: int
    simulation_name: str
    benefice_net: float
    capitaux_propres: float
    salaires_bruts: float
    valeur_ajoutee: float
    participation_mode: str
    participation_salaire_percent: int
    participation_presence_percent: int
    interessement_enabled: bool
    interessement_envelope: float | None
    interessement_mode: str | None
    interessement_salaire_percent: int
    interessement_presence_percent: int
    results_data: Dict[str, Any]
    company_id: str
    created_by: str


def employee_row_from_dict(d: Dict[str, Any]) -> EmployeeParticipationRow:
    """Construit un EmployeeParticipationRow depuis un dict (infrastructure)."""
    return EmployeeParticipationRow(
        employee_id=str(d["employee_id"]),
        first_name=str(d.get("first_name", "")),
        last_name=str(d.get("last_name", "")),
        annual_salary=float(d.get("annual_salary", 0)),
        presence_days=int(d.get("presence_days", 0)),
        seniority_years=int(d.get("seniority_years", 0)),
        has_real_salary=bool(d.get("has_real_salary", False)),
        has_real_presence=bool(d.get("has_real_presence", False)),
    )


def build_simulation_create_input(
    year: int,
    simulation_name: str,
    benefice_net: float,
    capitaux_propres: float,
    salaires_bruts: float,
    valeur_ajoutee: float,
    participation_mode: str,
    participation_salaire_percent: int,
    participation_presence_percent: int,
    interessement_enabled: bool,
    interessement_envelope: float | None,
    interessement_mode: str | None,
    interessement_salaire_percent: int,
    interessement_presence_percent: int,
    results_data: Dict[str, Any],
    company_id: str,
    created_by: str,
) -> SimulationCreateInput:
    """Construit SimulationCreateInput depuis les champs (schéma requête + contexte)."""
    return SimulationCreateInput(
        year=year,
        simulation_name=simulation_name,
        benefice_net=benefice_net,
        capitaux_propres=capitaux_propres,
        salaires_bruts=salaires_bruts,
        valeur_ajoutee=valeur_ajoutee,
        participation_mode=participation_mode,
        participation_salaire_percent=participation_salaire_percent,
        participation_presence_percent=participation_presence_percent,
        interessement_enabled=interessement_enabled,
        interessement_envelope=interessement_envelope,
        interessement_mode=interessement_mode,
        interessement_salaire_percent=interessement_salaire_percent,
        interessement_presence_percent=interessement_presence_percent,
        results_data=results_data,
        company_id=company_id,
        created_by=created_by,
    )


def simulation_create_input_to_insert_data(
    input_data: SimulationCreateInput,
) -> Dict[str, Any]:
    """Construit le dict d'insertion Supabase depuis SimulationCreateInput (sans created_by)."""
    return {
        "company_id": input_data.company_id,
        "year": input_data.year,
        "simulation_name": input_data.simulation_name,
        "benefice_net": input_data.benefice_net,
        "capitaux_propres": input_data.capitaux_propres,
        "salaires_bruts": input_data.salaires_bruts,
        "valeur_ajoutee": input_data.valeur_ajoutee,
        "participation_mode": input_data.participation_mode,
        "participation_salaire_percent": input_data.participation_salaire_percent,
        "participation_presence_percent": input_data.participation_presence_percent,
        "interessement_enabled": input_data.interessement_enabled,
        "interessement_envelope": input_data.interessement_envelope,
        "interessement_mode": input_data.interessement_mode,
        "interessement_salaire_percent": input_data.interessement_salaire_percent,
        "interessement_presence_percent": input_data.interessement_presence_percent,
        "results_data": input_data.results_data,
    }


def entity_to_simulation_response_dict(
    entity: "ParticipationSimulation",
) -> Dict[str, Any]:
    """Convertit une entité ParticipationSimulation en dict pour ParticipationSimulationResponse."""
    from app.modules.participation.domain.entities import ParticipationSimulation

    if not isinstance(entity, ParticipationSimulation):
        raise TypeError("entity must be ParticipationSimulation")
    return {
        "id": entity.id,
        "company_id": entity.company_id,
        "year": entity.year,
        "simulation_name": entity.simulation_name,
        "benefice_net": entity.benefice_net,
        "capitaux_propres": entity.capitaux_propres,
        "salaires_bruts": entity.salaires_bruts,
        "valeur_ajoutee": entity.valeur_ajoutee,
        "participation_mode": entity.participation_mode.value
        if hasattr(entity.participation_mode, "value")
        else entity.participation_mode,
        "participation_salaire_percent": entity.participation_salaire_percent,
        "participation_presence_percent": entity.participation_presence_percent,
        "interessement_enabled": entity.interessement_enabled,
        "interessement_envelope": entity.interessement_envelope,
        "interessement_mode": entity.interessement_mode.value
        if entity.interessement_mode
        and hasattr(entity.interessement_mode, "value")
        else entity.interessement_mode,
        "interessement_salaire_percent": entity.interessement_salaire_percent,
        "interessement_presence_percent": entity.interessement_presence_percent,
        "results_data": entity.results_data,
        "created_at": entity.created_at,
        "created_by": entity.created_by,
        "updated_at": entity.updated_at,
    }


def entity_to_simulation_list_item_dict(
    entity: "ParticipationSimulation",
) -> Dict[str, Any]:
    """Convertit une entité en dict pour ParticipationSimulationListItem."""
    return {
        "id": entity.id,
        "year": entity.year,
        "simulation_name": entity.simulation_name,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
