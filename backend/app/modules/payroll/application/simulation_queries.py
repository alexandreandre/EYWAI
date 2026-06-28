"""
Requêtes et assemblage de contexte pour les simulations de paie (sans accès HTTP).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
    company_code_postal,
    get_idcc_for_agreement,
    resolve_minimum_salary_value,
)
from app.modules.payroll.application import simulation_commands
from app.modules.payroll.engine.baremes_loader import assembler_baremes, ensure_dict
from app.modules.payroll.infrastructure import simulation_repository


def parse_json_dict(value: Any) -> Dict[str, Any]:
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


def load_baremes() -> Dict[str, Any]:
    rows = simulation_repository.fetch_active_payroll_config_rows()
    db_baremes = {
        r["config_key"]: ensure_dict(r.get("config_data")) for r in rows
    }
    conventions = simulation_repository.fetch_convention_collective_rules()
    return assembler_baremes(db_baremes, conventions)


def load_company(company_id: str) -> Dict[str, Any]:
    row = simulation_repository.fetch_company_row(company_id)
    if not row:
        raise LookupError("Entreprise introuvable.")
    return row


def load_employee(employee_id: str, company_id: str) -> Dict[str, Any]:
    row = simulation_repository.fetch_employee_row(employee_id)
    if not row:
        raise LookupError("Employé introuvable.")
    if str(row.get("company_id") or "") != str(company_id):
        raise LookupError("Employé introuvable.")
    return row


def load_simulation(simulation_id: str, company_id: str) -> Dict[str, Any]:
    row = simulation_repository.fetch_simulation_row(simulation_id, company_id)
    if not row:
        raise LookupError("Simulation introuvable.")
    return row


def _apply_cc_minimum_override(
    scenario_data: Dict[str, Any],
    *,
    company: Dict[str, Any],
    employee: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not scenario_data.get("apply_cc_minimum"):
        return scenario_data
    agreement_id: Optional[str] = None
    classification: Dict[str, Any] = {}
    if employee:
        agreement_id = employee.get("collective_agreement_id")
        classification = parse_json_dict(employee.get("classification_conventionnelle"))
    manual_params = scenario_data.get("manual_params")
    if isinstance(manual_params, dict):
        agreement_id = agreement_id or manual_params.get("collective_agreement_id")
        if not classification:
            raw = manual_params.get("classification_conventionnelle")
            classification = (
                raw if isinstance(raw, dict) else parse_json_dict(raw)
            )
    if not agreement_id:
        return scenario_data
    minimum = resolve_minimum_salary_value(
        str(agreement_id),
        classification,
        code_postal=company_code_postal(company),
    )
    if minimum is None:
        return scenario_data
    updated = dict(scenario_data)
    updated["salaire_base_override"] = minimum
    return updated


def employee_to_payroll_payload(
    employee: Dict[str, Any],
    company: Dict[str, Any],
) -> Dict[str, Any]:
    salaire_de_base = employee.get("salaire_de_base")
    salaire_base = 0.0
    if isinstance(salaire_de_base, dict):
        salaire_base = float(salaire_de_base.get("valeur") or 0)
    specificites = employee.get("specificites_paie")
    if not isinstance(specificites, dict):
        specificites = parse_json_dict(specificites)
    hire_date = employee.get("hire_date") or ""
    from app.shared.seniority_reference import (
        resolve_date_anciennete_prime,
        resolve_seniority_reference_date,
    )

    seniority_ref = resolve_seniority_reference_date(employee) or ""
    date_anciennete_prime = resolve_date_anciennete_prime(employee) or hire_date
    return {
        "id": employee.get("id"),
        "first_name": employee.get("first_name") or "",
        "last_name": employee.get("last_name") or "",
        "statut": employee.get("statut") or "Non-cadre",
        "duree_hebdomadaire": float(employee.get("duree_hebdomadaire") or 35),
        "salaire_base": salaire_base,
        "taux_prelevement_source": float(employee.get("taux_prelevement_source") or 0),
        "job_title": employee.get("job_title") or "",
        "emploi": employee.get("job_title") or "",
        "hire_date": hire_date,
        "seniority_reference_date": seniority_ref or None,
        "date_entree": date_anciennete_prime,
        "type_contrat": employee.get("contract_type") or "",
        "date_conclusion_contrat": employee.get("date_conclusion_contrat") or "",
        "date_debut_execution": employee.get("date_debut_execution") or "",
        "date_naissance": employee.get("date_naissance") or "",
        "classification_conventionnelle": parse_json_dict(
            employee.get("classification_conventionnelle")
        ),
        "convention_collective": build_convention_collective_payload(
            employee, company
        ),
        "collective_agreement_id": employee.get("collective_agreement_id"),
        "maintien_regime_apprenti": bool(
            specificites.get("maintien_regime_apprenti", False)
        ),
    }


def manual_employee_payload(
    options: Dict[str, Any],
    company: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    manual_params = options.get("manual_params") if isinstance(options, dict) else {}
    if not isinstance(manual_params, dict):
        manual_params = {}
    classification = manual_params.get("classification_conventionnelle")
    if isinstance(classification, dict):
        classification_dict = classification
    else:
        classification_dict = parse_json_dict(classification)

    agreement_id = manual_params.get("collective_agreement_id")
    idcc = manual_params.get("idcc")
    if not idcc and agreement_id:
        idcc = get_idcc_for_agreement(str(agreement_id))

    convention_collective: Dict[str, Any] = {}
    if idcc:
        libelle = manual_params.get("convention_libelle") or ""
        if not libelle and company:
            libelle = (
                company.get("collective_agreement")
                or company.get("collective_agreement_name")
                or ""
            )
        convention_collective = {"idcc": str(idcc), "libelle": str(libelle).strip()}
    elif company:
        convention_collective = build_convention_collective_payload({}, company)

    hire_date = (
        manual_params.get("date_entree")
        or manual_params.get("hire_date")
        or ""
    )

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
        "type_contrat": manual_params.get("type_contrat")
        or manual_params.get("contract_type")
        or "",
        "date_conclusion_contrat": manual_params.get("date_conclusion_contrat") or "",
        "date_debut_execution": manual_params.get("date_debut_execution") or "",
        "date_naissance": manual_params.get("date_naissance") or "",
        "date_entree": hire_date,
        "hire_date": hire_date,
        "classification_conventionnelle": classification_dict,
        "convention_collective": convention_collective,
        "collective_agreement_id": agreement_id,
        "maintien_regime_apprenti": bool(
            manual_params.get("maintien_regime_apprenti", False)
        ),
    }


def company_to_payroll_payload(company: Dict[str, Any]) -> Dict[str, Any]:
    cp = company_code_postal(company) or ""
    ville = company.get("adresse_ville") or ""
    if not ville:
        address = company.get("address") or company.get("headquarters_address")
        if isinstance(address, dict):
            ville = address.get("ville") or ""
    return {
        "identification": {
            "raison_sociale": company.get("name") or company.get("legal_name") or "",
            "siret": str(company.get("siret") or ""),
            "adresse": {
                "code_postal": cp,
                "ville": ville,
            },
        },
        "adresse_code_postal": cp,
        "parametres_paie": {
            "effectif": int(
                company.get("employee_count") or company.get("effectif") or 0
            ),
            "idcc": company.get("idcc") or "",
            "taux_specifiques": company.get("taux_specifiques") or {},
        },
    }


def resolve_employee_payload(
    company_id: str,
    employee_id: Optional[str],
    options_or_scenario: Dict[str, Any],
) -> Dict[str, Any]:
    company = load_company(company_id)
    if employee_id:
        employee = load_employee(employee_id, company_id)
        return employee_to_payroll_payload(employee, company)
    return manual_employee_payload(options_or_scenario, company)


def run_reverse_calculation_for_company(
    company_id: str,
    employee_id: Optional[str],
    net_target: float,
    net_type: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    company = load_company(company_id)
    baremes = load_baremes()
    options = _apply_cc_minimum_override(
        options or {},
        company=company,
        employee=load_employee(employee_id, company_id) if employee_id else None,
    )
    employee_payload = resolve_employee_payload(company_id, employee_id, options or {})
    return simulation_commands.run_reverse_calculation(
        employee_data=employee_payload,
        company_data=company_to_payroll_payload(company),
        baremes=baremes,
        calendrier={},
        saisies={},
        net_target=net_target,
        net_type=net_type,
        options=options or {},
    )


def create_payslip_simulation_record(
    company_id: str,
    created_by: str,
    employee_id: Optional[str],
    month: int,
    year: int,
    scenario_name: Optional[str],
    scenario_data: Dict[str, Any],
    prefill_from_real: bool,
) -> Dict[str, Any]:
    company = load_company(company_id)
    employee = load_employee(employee_id, company_id) if employee_id else None
    scenario_data = _apply_cc_minimum_override(
        scenario_data or {},
        company=company,
        employee=employee,
    )
    baremes = load_baremes()
    employee_payload = (
        employee_to_payroll_payload(employee, company)
        if employee
        else manual_employee_payload(scenario_data or {}, company)
    )
    simulation = simulation_commands.creer_simulation_bulletin(
        employee_data=employee_payload,
        company_data=company_to_payroll_payload(company),
        baremes=baremes,
        month=month,
        year=year,
        scenario_data=scenario_data or {},
        prefill_from_real=prefill_from_real,
    )
    payslip_data = simulation.get("payslip_data", {})
    sim_id = simulation_repository.insert_simulation_row(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "month": month,
            "year": year,
            "simulation_type": "payslip",
            "scenario_name": scenario_name,
            "scenario_data": scenario_data or {},
            "payslip_data": payslip_data,
            "created_by": created_by,
        }
    )
    if not sim_id:
        raise RuntimeError("Simulation non sauvegardée.")
    return {
        "simulation_id": sim_id,
        "payslip_data": payslip_data,
        "pdf_url": f"/api/simulation/{sim_id}/pdf",
    }


def list_employee_simulations(
    company_id: str,
    employee_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> List[Dict[str, Any]]:
    rows = simulation_repository.list_simulation_rows(
        company_id, employee_id, month=month, year=year
    )
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


def get_simulation_detail(simulation_id: str, company_id: str) -> Dict[str, Any]:
    row = load_simulation(simulation_id, company_id)
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


def compare_simulation_with_payslip(
    simulation_id: str,
    company_id: str,
    payslip_id: str,
) -> Dict[str, Any]:
    simulation = load_simulation(simulation_id, company_id)
    payslip = simulation_repository.fetch_payslip_row(payslip_id, company_id)
    if not payslip:
        raise LookupError("Bulletin réel introuvable.")
    return simulation_commands.comparer_simulation_reel(
        bulletin_simule=simulation.get("payslip_data") or {},
        bulletin_reel=payslip.get("payslip_data") or {},
    )


def delete_simulation(simulation_id: str, company_id: str) -> Dict[str, bool]:
    load_simulation(simulation_id, company_id)
    simulation_repository.delete_simulation_row(simulation_id, company_id)
    return {"success": True}


def get_predefined_scenarios(company_id: str, employee_id: str) -> Dict[str, Any]:
    company = load_company(company_id)
    employee = load_employee(employee_id, company_id)
    scenarios = simulation_commands.generer_scenarios_predefinis(
        employee_to_payroll_payload(employee, company)
    )
    return {"scenarios": scenarios}


def generate_simulation_pdf(simulation_id: str, company_id: str) -> bytes:
    simulation = load_simulation(simulation_id, company_id)
    generator_cls = simulation_commands.get_simulated_payslip_generator()
    return generator_cls().generate_pdf(simulation.get("payslip_data") or {})


def generate_simulation_html(simulation_id: str, company_id: str) -> str:
    simulation = load_simulation(simulation_id, company_id)
    generator_cls = simulation_commands.get_simulated_payslip_generator()
    return generator_cls().generate_html(simulation.get("payslip_data") or {})
