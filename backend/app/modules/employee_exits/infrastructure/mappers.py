"""
Mappers : construction de payloads DB et structures métier (dict).

build_exit_record, build_document_data_from_exit : comportement identique au router.
Aucune dépendance FastAPI.
"""
from typing import Any, Dict, Optional


def build_exit_record(
    company_id: str,
    employee_id: str,
    exit_type: str,
    initial_status: str,
    exit_request_date: str,
    last_working_day: str,
    notice_period_days: int,
    is_gross_misconduct: bool,
    notice_indemnity_type: Optional[str],
    notice_start_date: Optional[str],
    notice_end_date: Optional[str],
    exit_reason: Optional[str],
    initiated_by: str,
) -> Dict[str, Any]:
    """Construit le payload d'insertion employee_exits (comportement identique au router)."""
    return {
        "company_id": company_id,
        "employee_id": employee_id,
        "exit_type": exit_type,
        "status": initial_status,
        "exit_request_date": exit_request_date,
        "last_working_day": last_working_day,
        "notice_period_days": notice_period_days,
        "is_gross_misconduct": is_gross_misconduct,
        "notice_indemnity_type": notice_indemnity_type,
        "notice_start_date": notice_start_date,
        "notice_end_date": notice_end_date,
        "exit_reason": exit_reason,
        "initiated_by": initiated_by,
    }


def build_document_data_from_exit(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    include_indemnities: bool = False,
) -> Dict[str, Any]:
    """Construit document_data pour ExitDocumentDetails (comportement identique au router)."""
    document_data = {
        "employee": {
            "first_name": employee_data.get("first_name", ""),
            "last_name": employee_data.get("last_name", ""),
            "date_naissance": employee_data.get("date_naissance") or employee_data.get("birthdate", ""),
            "birth_place": employee_data.get("birth_place") or employee_data.get("lieu_naissance", ""),
            "social_security_number": employee_data.get("social_security_number")
            or employee_data.get("numero_securite_sociale", ""),
            "job_title": employee_data.get("job_title", ""),
            "hire_date": employee_data.get("hire_date", ""),
            "contract_type": employee_data.get("contract_type", "CDI"),
            "address": employee_data.get("address", ""),
        },
        "company": {
            "name": company_data.get("name") or company_data.get("raison_sociale", ""),
            "raison_sociale": company_data.get("raison_sociale") or company_data.get("name", ""),
            "siret": company_data.get("siret", ""),
            "address": company_data.get("address", ""),
            "city": company_data.get("city", ""),
            "naf_code": company_data.get("naf_code") or company_data.get("ape_code", ""),
            "ape_code": company_data.get("ape_code") or company_data.get("naf_code", ""),
            "urssaf_number": company_data.get("urssaf_number", ""),
        },
        "exit": {
            "last_working_day": exit_data.get("last_working_day", ""),
            "exit_reason": exit_data.get("exit_reason", ""),
            "exit_type": exit_data.get("exit_type", ""),
        },
    }
    if include_indemnities:
        document_data["indemnities"] = exit_data.get("calculated_indemnities", {})
    return document_data


DOCUMENT_NAME_MAP = {
    "certificat_travail": "Certificat de travail",
    "attestation_pole_emploi": "Attestation Pôle Emploi",
    "solde_tout_compte": "Solde de tout compte",
}

GENERATABLE_DOCUMENT_TYPES = ["certificat_travail", "attestation_pole_emploi", "solde_tout_compte"]


# Placeholders pour mapping row -> entité domain (optionnel, non utilisés pour l'instant)
def row_to_employee_exit_entity(row: Dict[str, Any]) -> Any:
    """Optionnel : mapping table employee_exits -> EmployeeExitEntity."""
    raise NotImplementedError("Migrer : row_to_employee_exit_entity")


def row_to_exit_document_entity(row: Dict[str, Any]) -> Any:
    """Optionnel : mapping exit_documents -> ExitDocumentEntity."""
    raise NotImplementedError("Migrer : row_to_exit_document_entity")


def row_to_checklist_item_entity(row: Dict[str, Any]) -> Any:
    """Optionnel : mapping exit_checklist_items -> ChecklistItemEntity."""
    raise NotImplementedError("Migrer : row_to_checklist_item_entity")
