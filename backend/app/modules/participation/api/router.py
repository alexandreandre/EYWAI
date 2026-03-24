"""
Router API participation (Participation & Intéressement).

Appelle uniquement l'application du module. Aucune logique métier : validation (schémas),
résolution du contexte (company_id), appel commands/queries, format réponse.
Comportement HTTP identique au legacy.
"""
from __future__ import annotations

import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.modules.participation.api.dependencies import (
    get_current_user,
    ParticipationUserContext,
)
from app.modules.participation.application import (
    DuplicateSimulationNameError,
    create_participation_simulation,
    delete_participation_simulation,
    get_employee_participation_data,
    get_participation_simulation,
    list_participation_simulations,
)
from app.modules.participation.application.dto import (
    build_simulation_create_input,
    entity_to_simulation_list_item_dict,
    entity_to_simulation_response_dict,
)
from app.modules.participation.schemas import (
    EmployeeDataResponse,
    EmployeeParticipationDataItem,
    ParticipationSimulationCreate,
    ParticipationSimulationListItem,
    ParticipationSimulationResponse,
)

router = APIRouter(
    prefix="/api/participation",
    tags=["Participation & Intéressement"],
)

_ERR_NO_COMPANY = "Impossible de déterminer l'entreprise de l'utilisateur."
_ERR_SIMULATION_NOT_FOUND = "Simulation non trouvée."


def _require_company_id(user: ParticipationUserContext) -> str:
    """Retourne le company_id de l'utilisateur ou lève 403."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=403, detail=_ERR_NO_COMPANY)
    return str(company_id)


@router.get("/employee-data/{year}", response_model=EmployeeDataResponse)
def get_employee_participation_data_route(
    year: int,
    user: ParticipationUserContext = Depends(get_current_user),
) -> EmployeeDataResponse:
    """
    Récupère les données des employés pour le simulateur Participation & Intéressement :
    salaire annuel cumulé, jours de présence, ancienneté.
    """
    try:
        company_id = _require_company_id(user)
        rows = get_employee_participation_data(company_id, year)
        items = [
            EmployeeParticipationDataItem(
                employee_id=r.employee_id,
                first_name=r.first_name,
                last_name=r.last_name,
                annual_salary=r.annual_salary,
                presence_days=r.presence_days,
                seniority_years=r.seniority_years,
                has_real_salary=r.has_real_salary,
                has_real_presence=r.has_real_presence,
            )
            for r in rows
        ]
        return EmployeeDataResponse(employees=items, year=year)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du calcul des données: {str(e)}",
        )


@router.post("/simulations", response_model=ParticipationSimulationResponse)
def create_participation_simulation_route(
    simulation: ParticipationSimulationCreate,
    user: ParticipationUserContext = Depends(get_current_user),
) -> ParticipationSimulationResponse:
    """Crée une nouvelle simulation de participation & intéressement."""
    try:
        company_id = _require_company_id(user)
        created_by = str(user.id)
        input_data = build_simulation_create_input(
            year=simulation.year,
            simulation_name=simulation.simulation_name,
            benefice_net=simulation.benefice_net,
            capitaux_propres=simulation.capitaux_propres,
            salaires_bruts=simulation.salaires_bruts,
            valeur_ajoutee=simulation.valeur_ajoutee,
            participation_mode=simulation.participation_mode,
            participation_salaire_percent=simulation.participation_salaire_percent,
            participation_presence_percent=simulation.participation_presence_percent,
            interessement_enabled=simulation.interessement_enabled,
            interessement_envelope=simulation.interessement_envelope,
            interessement_mode=simulation.interessement_mode,
            interessement_salaire_percent=simulation.interessement_salaire_percent,
            interessement_presence_percent=simulation.interessement_presence_percent,
            results_data=simulation.results_data,
            company_id=company_id,
            created_by=created_by,
        )
        entity = create_participation_simulation(input_data)
        return ParticipationSimulationResponse(
            **entity_to_simulation_response_dict(entity)
        )
    except DuplicateSimulationNameError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Une simulation avec le nom '{e.simulation_name}' existe déjà pour l'année {e.year}.",
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la simulation: {str(e)}",
        )


@router.get("/simulations", response_model=List[ParticipationSimulationListItem])
def list_participation_simulations_route(
    year: Optional[int] = None,
    user: ParticipationUserContext = Depends(get_current_user),
) -> List[ParticipationSimulationListItem]:
    """Liste les simulations de participation & intéressement de l'entreprise."""
    try:
        company_id = _require_company_id(user)
        entities = list_participation_simulations(company_id, year)
        return [
            ParticipationSimulationListItem(
                **entity_to_simulation_list_item_dict(e)
            )
            for e in entities
        ]
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des simulations: {str(e)}",
        )


@router.get(
    "/simulations/{simulation_id}",
    response_model=ParticipationSimulationResponse,
)
def get_participation_simulation_route(
    simulation_id: str,
    user: ParticipationUserContext = Depends(get_current_user),
) -> ParticipationSimulationResponse:
    """Récupère une simulation de participation & intéressement par son ID."""
    try:
        company_id = _require_company_id(user)
        entity = get_participation_simulation(simulation_id, company_id)
        if not entity:
            raise HTTPException(
                status_code=404,
                detail=_ERR_SIMULATION_NOT_FOUND,
            )
        return ParticipationSimulationResponse(
            **entity_to_simulation_response_dict(entity)
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération de la simulation: {str(e)}",
        )


@router.delete("/simulations/{simulation_id}")
def delete_participation_simulation_route(
    simulation_id: str,
    user: ParticipationUserContext = Depends(get_current_user),
) -> dict:
    """Supprime une simulation de participation & intéressement."""
    try:
        company_id = _require_company_id(user)
        deleted = delete_participation_simulation(simulation_id, company_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=_ERR_SIMULATION_NOT_FOUND,
            )
        return {"message": "Simulation supprimée avec succès."}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la suppression de la simulation: {str(e)}",
        )
