"""
Requêtes (cas d'usage lecture) du module employee_exits.

Délèguent à domain + infrastructure. Comportement identique au router legacy.
"""
from app.core.logging import get_logger, log_app_debug

logger = get_logger("modules.employee_exits.application.queries")

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.application.service import (
    enrich_exit_with_documents_and_checklist,
)
from app.modules.employee_exits.infrastructure.mappers import (
    build_document_data_from_exit,
)
from app.modules.payroll.documents.attestation_employeur_salary_history import (
    get_salary_history,
)
from app.modules.employee_exits.infrastructure.providers import (
    get_exit_storage_provider,
    get_indemnity_calculator,
)
from app.modules.employee_exits.infrastructure.queries import (
    get_company_by_id,
    get_employee_by_id as infra_get_employee_by_id,
    get_employee_full,
)
from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitDocumentRepository,
    ExitChecklistRepository,
)
from app.modules.employees.application.queries import employee_has_work_contract
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.employee_exits.domain.notice_period import compute_notice_period
from app.modules.employee_exits.domain.rules import exit_block_reason
from app.modules.collective_agreements.rules.repository import CCRulesRepository


def get_employee_company_id(employee_id: str, supabase_client: Any = None) -> str:
    """Retourne le company_id d'un employé. Lève EmployeeExitApplicationError(404) si non trouvé."""
    sb = supabase_client or supabase
    employee = infra_get_employee_by_id(employee_id, sb)
    if not employee:
        raise EmployeeExitApplicationError(404, "Employé non trouvé")
    return str(employee["company_id"])


def list_exit_eligible_employees(
    company_id: str,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Salariés actifs avec contrat de travail, éligibles à un nouveau départ."""
    _ = supabase_client  # réservé pour tests / injection future
    repo = EmployeeRepository()
    rows = repo.get_summary_by_company(company_id, active_only=True)
    eligible: List[Dict[str, Any]] = []
    for employee in rows:
        has_contract = employee_has_work_contract(str(employee["id"]), company_id)
        if exit_block_reason(employee, has_work_contract=has_contract) is not None:
            continue
        eligible.append(
            {
                "id": str(employee["id"]),
                "first_name": employee.get("first_name") or "",
                "last_name": employee.get("last_name") or "",
                "job_title": employee.get("job_title"),
            }
        )
    return eligible


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _resolve_employee_collective_agreement(
    employee: Dict[str, Any],
    company_id: str,
    supabase_client: Any,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Retourne (agreement_id, idcc, name) pour l'employé ou l'entreprise."""
    sb = supabase_client
    agreement_id = employee.get("collective_agreement_id")
    if not agreement_id:
        try:
            company_cc = (
                sb.table("company_collective_agreements")
                .select("collective_agreement_id")
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
            if company_cc.data:
                agreement_id = company_cc.data[0].get("collective_agreement_id")
        except Exception:
            agreement_id = None

    if not agreement_id:
        return None, None, None

    try:
        catalog = (
            sb.table("collective_agreements_catalog")
            .select("id, idcc, name")
            .eq("id", agreement_id)
            .maybe_single()
            .execute()
        )
        if catalog and catalog.data:
            row = catalog.data
            return (
                str(row.get("id") or agreement_id),
                str(row["idcc"]) if row.get("idcc") is not None else None,
                str(row.get("name") or "").strip() or None,
            )
    except Exception:
        pass
    return str(agreement_id), None, None


def get_notice_period_preview(
    employee_id: str,
    company_id: str,
    exit_type: str,
    reference_date: date,
    *,
    is_gross_misconduct: bool = False,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Prévisualise le préavis applicable pour un collaborateur et un type de départ."""
    sb = supabase_client or supabase
    employee = get_employee_full(employee_id, sb)
    if not employee:
        raise EmployeeExitApplicationError(404, "Employé non trouvé")
    if str(employee.get("company_id")) != str(company_id):
        raise EmployeeExitApplicationError(404, "Employé non trouvé")

    agreement_id, idcc, agreement_name = _resolve_employee_collective_agreement(
        employee, company_id, sb
    )
    cc_rules: Optional[Dict[str, Any]] = None
    if agreement_id or idcc:
        rules_repo = CCRulesRepository(sb)
        rules_row = None
        if agreement_id:
            rules_row = rules_repo.get_rules_by_agreement_id(agreement_id)
        if not rules_row and idcc:
            rules_row = rules_repo.get_rules_by_idcc(idcc)
        if rules_row and isinstance(rules_row.get("rules"), dict):
            cc_rules = rules_row["rules"]

    result = compute_notice_period(
        exit_type=exit_type,
        hire_date=_parse_iso_date(employee.get("hire_date")),
        reference_date=reference_date,
        statut=employee.get("statut"),
        is_gross_misconduct=is_gross_misconduct,
        collective_agreement_name=agreement_name,
        collective_agreement_idcc=idcc,
        cc_rules=cc_rules,
    )
    return {
        "employee_id": str(employee_id),
        "exit_type": exit_type,
        "reference_date": reference_date.isoformat(),
        "notice_period_days": result.days,
        "source": result.source,
        "label": result.label,
        "detail": result.detail,
        "warnings": list(result.warnings),
        "applicable": result.applicable,
        "collective_agreement_name": result.collective_agreement_name,
        "collective_agreement_idcc": result.collective_agreement_idcc,
        "seniority_months": result.seniority_months,
        "employee_category": result.employee_category,
        "has_collective_agreement": bool(agreement_id or agreement_name or idcc),
    }


def list_employee_exits(
    company_id: str,
    status: Optional[str] = None,
    exit_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Liste les sorties enrichies (documents, checklist, completion_rate)."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    rows = exit_repo.list(
        company_id,
        status=status,
        exit_type=exit_type,
        employee_id=employee_id,
    )
    enriched = []
    for exit_record in rows:
        enrich_exit_with_documents_and_checklist(exit_record, 3600, sb)
        enriched.append(exit_record)
    return enriched


def get_employee_exit(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Récupère une sortie par id avec documents et checklist."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    exit_record = exit_repo.get_with_employee(
        exit_id, company_id, "id, first_name, last_name, email, job_title, hire_date"
    )
    if not exit_record:
        raise EmployeeExitApplicationError(404, "Départ non trouvé")
    enrich_exit_with_documents_and_checklist(exit_record, 3600, sb)
    try:
        from app.modules.employee_loans.infrastructure.payroll_queries import (
            get_employee_outstanding_loans,
        )

        employee_id = exit_record.get("employee_id")
        if employee_id:
            exit_record["outstanding_loans"] = get_employee_outstanding_loans(
                str(employee_id)
            )
    except Exception as exc:
        log_app_debug(logger, f"Prêts employeur non chargés pour sortie: {exc}")
    return exit_record


def calculate_exit_indemnities(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Calcule les indemnités et met à jour l'enregistrement sortie. Retourne le dict indemnités."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    calculator = get_indemnity_calculator()
    exit_data = exit_repo.get_with_employee(
        exit_id,
        company_id,
        "id, first_name, last_name, hire_date, salaire_de_base, job_title, contract_type, company_id, specificites_paie",
    )
    if not exit_data:
        raise EmployeeExitApplicationError(404, "Départ non trouvé")
    employee_data = exit_data.get("employees") or {}
    try:
        indemnities = calculator.calculate(employee_data, exit_data, sb)
    except ImportError as e:
        raise EmployeeExitApplicationError(
            500, f"Module de calcul non disponible: {str(e)}"
        )
    except Exception as e:
        logger.warning(f'✗ Erreur calcul: {e}')
        raise EmployeeExitApplicationError(
            500, f"Erreur lors du calcul des indemnités: {str(e)}"
        )
    exit_repo.update(
        exit_id,
        company_id,
        {
            "calculated_indemnities": indemnities,
            "remaining_vacation_days": indemnities.get("indemnite_conges", {}).get(
                "jours_restants", 0
            ),
            "final_net_amount": indemnities.get("total_net_indemnities", 0),
        },
    )
    return indemnities


def get_document_upload_url(
    exit_id: str,
    company_id: str,
    filename: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Génère une URL signée pour upload. Retourne upload_url, storage_path, expires_in."""
    sb = supabase_client or supabase
    exit_repo = EmployeeExitRepository(sb)
    if not exit_repo.get_by_id(exit_id, company_id):
        raise EmployeeExitApplicationError(404, "Départ non trouvé")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage_path = f"exits/{exit_id}/{ts}_{filename}"
    try:
        upload_url = get_exit_storage_provider(sb).create_signed_upload_url(
            storage_path
        )
        return {
            "upload_url": upload_url,
            "storage_path": storage_path,
            "expires_in": 3600,
        }
    except Exception as e:
        logger.warning(f'✗ Erreur génération URL upload: {e}')
        raise EmployeeExitApplicationError(500, f"Erreur génération URL: {str(e)}")


def list_exit_documents(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Liste les documents d'une sortie avec download_url."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    storage = get_exit_storage_provider(sb)
    documents = doc_repo.list_by_exit(exit_id, company_id)
    for doc in documents:
        try:
            doc["download_url"] = storage.create_signed_url(doc["storage_path"], 3600)
        except Exception:
            doc["download_url"] = None
    return documents


EDIT_HISTORY_META_KEY = "_edit_history"


def _coerce_edit_history(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    return []


def _stored_edit_history(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lit l'historique depuis la colonne dédiée ou document_data._edit_history."""
    history = _coerce_edit_history(doc.get("edit_history"))
    if history:
        return history
    document_data = doc.get("document_data")
    if isinstance(document_data, dict):
        return _coerce_edit_history(document_data.get(EDIT_HISTORY_META_KEY))
    return []


def _strip_edit_history_meta(document_data: Any) -> Any:
    if not isinstance(document_data, dict):
        return document_data
    if EDIT_HISTORY_META_KEY not in document_data:
        return document_data
    return {k: v for k, v in document_data.items() if k != EDIT_HISTORY_META_KEY}


def document_edit_history_entries(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Historique persisté, avec repli sur last_edited_* pour les anciens enregistrements."""
    history = _stored_edit_history(doc)
    if history:
        return history
    if doc.get("manually_edited") and doc.get("last_edited_at"):
        return [
            {
                "version": doc.get("version", 1),
                "edited_by": doc.get("last_edited_by"),
                "edited_at": doc.get("last_edited_at"),
                "changes_summary": "Document modifié",
            }
        ]
    return []


def _enrich_attestation_document_data(
    document_data: Dict[str, Any],
    employee_data: Dict[str, Any],
    exit_data: Dict[str, Any],
    supabase_client: Any,
) -> Dict[str, Any]:
    """Pré-remplit salary_history et primes_lines si absents."""
    if document_data.get("salary_history"):
        return document_data
    employee_id = str(employee_data.get("id") or exit_data.get("employee_id") or "")
    history = get_salary_history(
        employee_id=employee_id,
        employee_data=employee_data,
        end_date=exit_data.get("last_working_day"),
        supabase_client=supabase_client,
    )
    enriched = dict(document_data)
    enriched["salary_history"] = history.get("months") or []
    enriched["salary_month_count"] = history.get("month_count", 25)
    enriched["primes_lines"] = history.get("primes_lines") or []
    if not enriched.get("indemnities") and exit_data.get("calculated_indemnities"):
        enriched["indemnities"] = exit_data.get("calculated_indemnities")
    return enriched


def get_exit_document_details(
    exit_id: str,
    document_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Détails complets d'un document avec document_data (éditable) et download_url."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    exit_repo = EmployeeExitRepository(sb)
    storage = get_exit_storage_provider(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    document_data = doc.get("document_data") or doc.get("generation_data")
    if not document_data:
        exit_data = exit_repo.get_by_id(exit_id, company_id)
        if not exit_data:
            raise EmployeeExitApplicationError(404, "Départ non trouvé")
        emp_id = exit_data.get("employee_id")
        employee_data = get_employee_full(str(emp_id), sb) if emp_id else {}
        company_data = get_company_by_id(company_id, sb) or {}
        document_data = build_document_data_from_exit(
            employee_data,
            company_data,
            exit_data,
            include_indemnities=(
                doc.get("document_type")
                in ("solde_tout_compte", "attestation_pole_emploi")
            ),
        )
    if doc.get("document_type") == "attestation_pole_emploi":
        exit_data = exit_repo.get_by_id(exit_id, company_id) or {}
        emp_id = exit_data.get("employee_id")
        employee_data = (
            get_employee_full(str(emp_id), sb) if emp_id else {}
        )
        document_data = _enrich_attestation_document_data(
            document_data if isinstance(document_data, dict) else {},
            employee_data,
            exit_data,
            sb,
        )
    edit_history = document_edit_history_entries(doc)
    download_url = None
    if doc.get("storage_path"):
        try:
            download_url = storage.create_signed_url(doc["storage_path"], 3600)
        except Exception as e:
            logger.warning(f'⚠ Erreur génération URL signée: {e}')
    result = dict(doc)
    result["document_data"] = _strip_edit_history_meta(document_data)
    result["edit_history"] = edit_history if edit_history else None
    result["download_url"] = download_url
    result.setdefault("version", 1)
    result.setdefault("manually_edited", False)
    result.setdefault("last_edited_by", None)
    result.setdefault("last_edited_at", None)
    return result


def get_document_edit_history(
    exit_id: str,
    document_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Historique des modifications d'un document (métadonnées)."""
    sb = supabase_client or supabase
    doc_repo = ExitDocumentRepository(sb)
    doc = doc_repo.get_by_id(document_id, exit_id, company_id)
    if not doc:
        raise EmployeeExitApplicationError(404, "Document non trouvé")
    history = document_edit_history_entries(doc)
    return {
        "document_id": document_id,
        "total_versions": doc.get("version", 1),
        "history": history,
    }


def get_exit_checklist(
    exit_id: str,
    company_id: str,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Récupère la checklist d'une sortie (ordre display_order)."""
    sb = supabase_client or supabase
    checklist_repo = ExitChecklistRepository(sb)
    return checklist_repo.list_by_exit(exit_id, company_id)
