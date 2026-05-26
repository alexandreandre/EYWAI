"""Router API — simulation paie (bulletin, arrêt maladie, etc.)."""

from __future__ import annotations

import json
import traceback
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.database import supabase
from app.core.security import get_current_user
from app.modules.payroll.application.simulation_commands import (
    comparer_simulation_reel,
    creer_simulation_bulletin,
    generer_scenarios_predefinis,
    get_simulated_payslip_generator,
    run_reverse_calculation,
)
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
    if current_user.is_super_admin:
        return str(current_user.active_company_id or "")
    active_company_id = current_user.active_company_id
    if not active_company_id or not current_user.has_rh_access_in_company(active_company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux RH et administrateurs.",
        )
    return str(active_company_id)


def _parse_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _load_company(company_id: str) -> Dict[str, Any]:
    response = (
        supabase.table("companies")
        .select("*")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Entreprise introuvable.")
    return response.data


def _load_employee(employee_id: str, company_id: str) -> Dict[str, Any]:
    response = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    employee = response.data
    if str(employee.get("company_id") or "") != str(company_id):
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    return employee


def _load_baremes() -> Dict[str, Any]:
    configs = (
        supabase.table("payroll_config")
        .select("config_key, config_data")
        .eq("is_active", True)
        .execute()
    )
    rows = configs.data or []
    db_baremes = {r["config_key"]: _parse_json_dict(r.get("config_data")) for r in rows}
    pas_data = db_baremes.get("pas", {})
    pas_baremes = pas_data.get("baremes", []) if isinstance(pas_data, dict) else []
    primes_data = db_baremes.get("primes", {})
    if isinstance(primes_data, dict):
        primes_list = primes_data.get("primes", [])
    elif isinstance(primes_data, list):
        primes_list = primes_data
    else:
        primes_list = []

    return {
        "cotisations": db_baremes.get("cotisations", {}),
        "pas": pas_baremes if isinstance(pas_baremes, list) else [],
        "smic": db_baremes.get("smic", {}),
        "pss": db_baremes.get("pss", {}),
        "frais_pro": db_baremes.get("frais_pro", {}),
        "heures_supp": db_baremes.get("heures_supp", {}),
        "primes": primes_list if isinstance(primes_list, list) else [],
        "conventions_collectives": {},
    }


def _employee_to_payroll_payload(employee: Dict[str, Any]) -> Dict[str, Any]:
    salaire_de_base = employee.get("salaire_de_base")
    salaire_base = 0.0
    if isinstance(salaire_de_base, dict):
        salaire_base = float(salaire_de_base.get("valeur") or 0)
    return {
        "id": employee.get("id"),
        "first_name": employee.get("first_name") or "",
        "last_name": employee.get("last_name") or "",
        "statut": employee.get("statut") or "Non-cadre",
        "duree_hebdomadaire": float(employee.get("duree_hebdomadaire") or 35),
        "salaire_base": salaire_base,
        "taux_prelevement_source": float(employee.get("taux_prelevement_source") or 0),
        "job_title": employee.get("job_title") or "",
        "hire_date": employee.get("hire_date") or "",
    }


def _manual_employee_payload(options: Dict[str, Any]) -> Dict[str, Any]:
    manual_params = options.get("manual_params") if isinstance(options, dict) else {}
    if not isinstance(manual_params, dict):
        manual_params = {}
    return {
        "id": "manual",
        "first_name": "Simulation",
        "last_name": "Manuelle",
        "statut": manual_params.get("statut") or "Non-cadre",
        "duree_hebdomadaire": float(manual_params.get("duree_hebdomadaire") or 35),
        "salaire_base": float(
            options.get("salaire_base_override")
            or manual_params.get("salaire_base")
            or 0
        ),
        "taux_prelevement_source": float(
            manual_params.get("taux_prelevement_source") or 0
        ),
    }


def _company_to_payroll_payload(company: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "identification": {
            "raison_sociale": company.get("name") or company.get("legal_name") or "",
            "siret": str(company.get("siret") or ""),
            "adresse": company.get("address") or company.get("headquarters_address") or "",
        },
        "parametres_paie": {
            "effectif": int(company.get("employee_count") or company.get("effectif") or 0),
            "taux_specifiques": company.get("taux_specifiques") or {},
        },
    }


def _load_simulation(simulation_id: str, company_id: str) -> Dict[str, Any]:
    response = (
        supabase.table("payroll_simulations")
        .select("*")
        .eq("id", simulation_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Simulation introuvable.")
    return response.data


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
        company = _load_company(company_id)
        baremes = _load_baremes()
        employee_payload = (
            _employee_to_payroll_payload(_load_employee(body.employee_id, company_id))
            if body.employee_id
            else _manual_employee_payload(body.options)
        )
        result = run_reverse_calculation(
            employee_data=employee_payload,
            company_data=_company_to_payroll_payload(company),
            baremes=baremes,
            calendrier={},
            saisies={},
            net_target=body.net_target,
            net_type=body.net_type,
            options=body.options or {},
        )
        return result
    except HTTPException:
        raise
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
        company = _load_company(company_id)
        baremes = _load_baremes()
        employee_payload = (
            _employee_to_payroll_payload(_load_employee(body.employee_id, company_id))
            if body.employee_id
            else _manual_employee_payload(body.scenario_data)
        )
        simulation = creer_simulation_bulletin(
            employee_data=employee_payload,
            company_data=_company_to_payroll_payload(company),
            baremes=baremes,
            month=body.month,
            year=body.year,
            scenario_data=body.scenario_data or {},
            prefill_from_real=bool(body.prefill_from_real),
        )
        payslip_data = simulation.get("payslip_data", {})
        inserted = (
            supabase.table("payroll_simulations")
            .insert(
                {
                    "company_id": company_id,
                    "employee_id": body.employee_id,
                    "month": body.month,
                    "year": body.year,
                    "simulation_type": "payslip",
                    "scenario_name": body.scenario_name,
                    "scenario_data": body.scenario_data or {},
                    "payslip_data": payslip_data,
                    "created_by": str(current_user.id),
                }
            )
            .execute()
        )
        sim_id = inserted.data[0]["id"] if inserted.data else None
        if not sim_id:
            raise HTTPException(status_code=500, detail="Simulation non sauvegardée.")
        return {
            "simulation_id": sim_id,
            "payslip_data": payslip_data,
            "pdf_url": f"/api/simulation/{sim_id}/pdf",
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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
        query = (
            supabase.table("payroll_simulations")
            .select("id, employee_id, month, year, simulation_type, scenario_name, payslip_data, created_at")
            .eq("company_id", company_id)
            .eq("employee_id", employee_id)
            .order("created_at", desc=True)
        )
        if month is not None:
            query = query.eq("month", month)
        if year is not None:
            query = query.eq("year", year)
        rows = query.execute().data or []
        return [
            {
                "id": r.get("id"),
                "employee_id": r.get("employee_id"),
                "month": r.get("month"),
                "year": r.get("year"),
                "simulation_type": r.get("simulation_type"),
                "scenario_name": r.get("scenario_name"),
                "net_a_payer": (r.get("payslip_data") or {}).get("net_a_payer"),
                "created_at": r.get("created_at"),
            }
            for r in rows
        ]
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
        row = _load_simulation(simulation_id, company_id)
        return {
            "id": row.get("id"),
            "employee_id": row.get("employee_id"),
            "company_id": row.get("company_id"),
            "month": row.get("month"),
            "year": row.get("year"),
            "simulation_type": row.get("simulation_type"),
            "scenario_name": row.get("scenario_name"),
            "scenario_data": row.get("scenario_data") or {},
            "payslip_data": row.get("payslip_data") or {},
            "created_at": row.get("created_at"),
            "created_by": row.get("created_by"),
            "updated_at": row.get("updated_at"),
        }
    except HTTPException:
        raise
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
        simulation = _load_simulation(simulation_id, company_id)
        payslip = (
            supabase.table("payslips")
            .select("id, company_id, payslip_data")
            .eq("id", body.payslip_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not payslip.data:
            raise HTTPException(status_code=404, detail="Bulletin réel introuvable.")
        return comparer_simulation_reel(
            bulletin_simule=simulation.get("payslip_data") or {},
            bulletin_reel=payslip.data.get("payslip_data") or {},
        )
    except HTTPException:
        raise
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
        _load_simulation(simulation_id, company_id)
        supabase.table("payroll_simulations").delete().eq("id", simulation_id).eq(
            "company_id", company_id
        ).execute()
        return {"success": True}
    except HTTPException:
        raise
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
        employee = _load_employee(employee_id, company_id)
        scenarios = generer_scenarios_predefinis(_employee_to_payroll_payload(employee))
        return {"scenarios": scenarios}
    except HTTPException:
        raise
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
        simulation = _load_simulation(simulation_id, company_id)
        generator_cls = get_simulated_payslip_generator()
        pdf_bytes = generator_cls().generate_pdf(simulation.get("payslip_data") or {})
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="simulation_{simulation_id}.pdf"'
            },
        )
    except HTTPException:
        raise
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
        simulation = _load_simulation(simulation_id, company_id)
        generator_cls = get_simulated_payslip_generator()
        html_content = generator_cls().generate_html(simulation.get("payslip_data") or {})
        return HTMLResponse(content=html_content)
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la génération de l'aperçu HTML."
        ) from None
