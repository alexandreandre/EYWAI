"""Router API — simulation paie (bulletin, arrêt maladie, etc.)."""

from __future__ import annotations

import traceback
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.modules.payroll.application import simulation_queries
from app.modules.payroll.application.simulation_arret_maladie import (
    run_simulation_arret_maladie,
)
from app.modules.payroll.schemas.requests import SimulationArretMaladieRequest
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/simulation", tags=["Simulation paie"])


class ReverseCalculationRequest(BaseModel):
    employee_id: Optional[str] = None
    net_target: float = Field(gt=0)
    net_type: Literal["net_a_payer", "net_imposable"]
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    options: Dict[str, Any] = Field(default_factory=dict)


class SimulationCreateRequest(BaseModel):
    employee_id: Optional[str] = None
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    scenario_name: Optional[str] = None
    scenario_data: Dict[str, Any] = Field(default_factory=dict)
    prefill_from_real: bool = False


class SimulationCompareRequest(BaseModel):
    payslip_id: str


def _require_rh_or_admin(current_user: User) -> str:
    if current_user.is_platform_admin:
        return str(current_user.active_company_id or "")
    active_company_id = current_user.active_company_id
    if not active_company_id or not current_user.has_rh_access_in_company(active_company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux RH et administrateurs.",
        )
    return str(active_company_id)


@router.post("/arret-maladie")
def simulation_arret_maladie(
    body: SimulationArretMaladieRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Simulation maintien / IJSS pour un arrêt maladie (même moteur que le bulletin).
    Réservé aux profils avec accès RH sur l'entreprise active.
    """
    try:
        return run_simulation_arret_maladie(body, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la simulation arrêt maladie."
        ) from None


@router.post("/reverse-calculation")
def reverse_calculation(
    body: ReverseCalculationRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.run_reverse_calculation_for_company(
            company_id=company_id,
            employee_id=body.employee_id,
            net_target=body.net_target,
            net_type=body.net_type,
            options=body.options or {},
        )
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors du calcul inverse."
        ) from None


@router.post("/create-payslip")
def create_payslip_simulation(
    body: SimulationCreateRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.create_payslip_simulation_record(
            company_id=company_id,
            created_by=str(current_user.id),
            employee_id=body.employee_id,
            month=body.month,
            year=body.year,
            scenario_name=body.scenario_name,
            scenario_data=body.scenario_data or {},
            prefill_from_real=bool(body.prefill_from_real),
        )
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la création de la simulation."
        ) from None


@router.get("/employee/{employee_id}")
def get_employee_simulations(
    employee_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.list_employee_simulations(
            company_id, employee_id, month=month, year=year
        )
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la récupération des simulations."
        ) from None


@router.get("/{simulation_id}")
def get_simulation(
    simulation_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.get_simulation_detail(simulation_id, company_id)
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la récupération de la simulation."
        ) from None


@router.post("/{simulation_id}/compare")
def compare_simulation_with_real(
    simulation_id: str,
    body: SimulationCompareRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.compare_simulation_with_payslip(
            simulation_id, company_id, body.payslip_id
        )
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la comparaison simulation/réel."
        ) from None


@router.delete("/{simulation_id}")
def delete_simulation(
    simulation_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.delete_simulation(simulation_id, company_id)
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la suppression de la simulation."
        ) from None


@router.get("/predefined-scenarios/{employee_id}")
def get_predefined_scenarios(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        return simulation_queries.get_predefined_scenarios(company_id, employee_id)
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la génération des scénarios."
        ) from None


@router.get("/{simulation_id}/pdf")
def download_simulation_pdf(
    simulation_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        pdf_bytes = simulation_queries.generate_simulation_pdf(simulation_id, company_id)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="simulation_{simulation_id}.pdf"'
            },
        )
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la génération du PDF."
        ) from None


@router.get("/{simulation_id}/html")
def preview_simulation_html(
    simulation_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        company_id = _require_rh_or_admin(current_user)
        html_content = simulation_queries.generate_simulation_html(
            simulation_id, company_id
        )
        return HTMLResponse(content=html_content)
    except HTTPException:
        raise
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la génération de l'aperçu HTML."
        ) from None
