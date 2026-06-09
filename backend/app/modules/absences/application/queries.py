"""
Queries (cas d'usage lecture) du module absences.

Utilise domain (règles) et infrastructure (repository, providers, queries).
Retourne des dicts / listes de dicts compatibles avec les schémas de réponse API.
"""

from __future__ import annotations
from app.core.logging import get_logger, log_app_debug

logger = get_logger("modules.absences.application.queries")

import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.database import supabase
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    calculate_acquired_rtt,
    compute_absence_balances,
    compute_cp_balances_for_bulletin,
    count_absence_days_taken,
    requires_salary_certificate,
    validate_conge_paye_request_days,
)
from app.modules.absences.infrastructure.providers import (
    evenement_familial_provider,
    storage_provider,
)
from app.modules.absences.application.service import resolve_employee_id_for_user
from app.modules.absences.infrastructure.queries import (
    get_employee_hire_date,
    get_employees_hire_dates_batch,
    get_planned_calendar,
    get_repos_credits_by_employee_year,
    get_salary_certificate_record,
)
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.maintenance_settings.application.queries import get_maintenance_settings
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.maintien_salaire_service import (
    calculer_maintien,
    calculer_regularisation_at,
)
from app.modules.users.schemas.responses import User

BUCKET_LEAVE_ATTACHMENTS = "leave_attachments"
BUCKET_SALARY_CERTIFICATES = "salary_certificates"


def _enrich_absence_certificate_fields(row: dict) -> None:
    """Ajoute certificate_status et certificate_id (attestation IJSS / salaire)."""
    atype = row.get("type") or ""
    status = row.get("status") or ""
    aid = row.get("id")
    if not requires_salary_certificate(atype):
        row["certificate_status"] = "not_required"
        row["certificate_id"] = None
        return
    cert = get_salary_certificate_record(aid) if aid else None
    if cert and cert.get("id"):
        row["certificate_status"] = "generated"
        row["certificate_id"] = str(cert["id"])
        return
    if status == "validated":
        row["certificate_status"] = "pending"
        row["certificate_id"] = None
        return
    row["certificate_status"] = None
    row["certificate_id"] = None


def _enrich_with_signed_urls(
    items: List[dict],
    path_key: str = "attachment_url",
    bucket: str = BUCKET_LEAVE_ATTACHMENTS,
) -> None:
    """Remplace les chemins par les URLs signées (modifie items en place)."""
    paths = [it[path_key] for it in items if it.get(path_key)]
    if not paths:
        return
    try:
        url_map = storage_provider.create_signed_urls(
            paths, bucket, expiry_seconds=3600
        )
        for it in items:
            if it.get(path_key) in url_map:
                it[path_key] = url_map[it[path_key]]
    except Exception as e:
        logger.warning(f'[WARNING] Erreur URLs signées: {e}')


def get_upload_url_signed(user_id: str, filename: str) -> dict:
    """Génère une URL signée pour l'upload d'un justificatif. Retourne {"path": ..., "signedURL": ...}."""
    _root, extension = filename.rsplit(".", 1) if "." in filename else (filename, "")
    if "." in filename and extension:
        extension = f".{extension}"
    else:
        extension = ""
    unique_filename = f"{datetime.now().isoformat()}-{uuid4().hex}{extension}"
    path = f"{user_id}/{unique_filename}"
    url = storage_provider.create_signed_upload_url(path, BUCKET_LEAVE_ATTACHMENTS)
    return {"path": path, "signedURL": url}


def get_absence_requests(
    status: str | None = None, *, company_id: str
) -> List[dict]:
    """Liste des demandes pour une entreprise, enrichies employé + soldes + URLs signées."""
    requests = absence_repository.list_by_status(status, company_id=company_id)
    if not requests:
        return []

    employee_ids = list({req["employee"]["id"] for req in requests})
    today = date.today()
    hire_dates = get_employees_hire_dates_batch(employee_ids)
    validated_reqs = absence_repository.list_validated_for_employees(employee_ids)
    repos_credits_by_emp = get_repos_credits_by_employee_year(employee_ids, today.year)

    balances_map: dict[str, List[dict]] = {}
    for emp_id in employee_ids:
        if emp_id not in hire_dates:
            continue
        hire_date = hire_dates[emp_id]
        emp_validated = [r for r in validated_reqs if r["employee_id"] == emp_id]
        soldes = compute_absence_balances(
            hire_date,
            emp_validated,
            today,
            repos_acquis=repos_credits_by_emp.get(emp_id, 0.0),
        )
        cp = soldes["conges_payes"]
        rtt = soldes["rtt"]
        repos = soldes["repos_compensateur"]
        balances_map[emp_id] = [
            {
                "type": "Congés Payés",
                "acquired": cp["acquis"],
                "taken": cp["pris"],
                "remaining": cp["solde"],
            },
            {
                "type": "RTT",
                "acquired": rtt["acquis"],
                "taken": rtt["pris"],
                "remaining": rtt["solde"],
            },
            {
                "type": "Repos compensateur",
                "acquired": repos["acquis"],
                "taken": repos["pris"],
                "remaining": repos["solde"],
            },
            {
                "type": "Événement familial",
                "acquired": 0,
                "taken": 0,
                "remaining": "selon événement",
            },
        ]

    for req in requests:
        emp_id = req["employee"]["id"]
        req["employee"]["balances"] = balances_map.get(emp_id, [])
        if req.get("type") == "evenement_familial" and req.get("event_subtype"):
            hire_date = hire_dates.get(emp_id)
            solde_data = evenement_familial_provider.get_solde_evenement(
                emp_id, req["event_subtype"], hire_date
            )
            req["event_familial_cycles_consumed"] = solde_data.get(
                "cycles_completed", 0
            )

    _enrich_with_signed_urls(requests)
    for req in requests:
        _enrich_absence_certificate_fields(req)
    return requests


def get_absences_for_employee(employee_id: str) -> List[dict]:
    """Historique des demandes pour un employé, avec URLs signées des justificatifs."""
    data = absence_repository.list_by_employee_id(employee_id)
    if not data:
        return []
    _enrich_with_signed_urls(data)
    for row in data:
        _enrich_absence_certificate_fields(row)
    return data


def update_absence_request_signed_url_single(request_id: str) -> dict | None:
    """Met à jour une demande avec l'URL signée du justificatif si présent. Retourne la demande ou None."""
    data = absence_repository.get_by_id(request_id)
    if not data:
        return None
    if data.get("attachment_url"):
        try:
            url = storage_provider.create_signed_url(
                data["attachment_url"],
                BUCKET_LEAVE_ATTACHMENTS,
                expiry_seconds=3600,
            )
            if url:
                data["attachment_url"] = url
        except Exception as e:
            logger.warning(f'[WARNING] Erreur URL signée: {e}')
    _enrich_absence_certificate_fields(data)
    return data


def get_absence_request_detail(
    user_id: str, company_id: str, absence_id: str
) -> dict:
    """Détail d'une absence pour le collaborateur connecté (avec statut attestation IJSS)."""
    employee_id = resolve_employee_id_for_user(user_id, company_id)
    if not employee_id:
        raise LookupError("Profil collaborateur sans employé associé.")
    row = absence_repository.get_by_id(absence_id)
    if not row:
        raise LookupError("Demande non trouvée.")
    if str(row.get("employee_id")) != str(employee_id):
        raise PermissionError("Accès refusé à cette absence.")
    enriched = update_absence_request_signed_url_single(absence_id)
    if enriched is None:
        raise LookupError("Demande non trouvée.")
    return enriched


def _parse_hire_date(employee_id: str) -> date | None:
    hire_date_raw = get_employee_hire_date(employee_id)
    if not hire_date_raw:
        return None
    return (
        date.fromisoformat(hire_date_raw)
        if isinstance(hire_date_raw, str)
        else hire_date_raw
    )


def assert_employee_conge_paye_request_allowed(
    employee_id: str, selected_days: list
) -> None:
    """
    Vérifie qu'une demande CP salarié ne dépasse pas le solde disponible
    (validés + pending). Lève ValueError ou LookupError.
    """
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        raise LookupError("Date d'embauche non trouvée pour l'employé.")
    parsed_days: list[date] = []
    for day in selected_days:
        if isinstance(day, date):
            parsed_days.append(day)
        elif isinstance(day, str):
            parsed_days.append(date.fromisoformat(day[:10]))
    employee_requests = absence_repository.list_by_employee_id(employee_id)
    validate_conge_paye_request_days(hire_date, employee_requests, parsed_days)


def get_absence_balances_at_date(
    employee_id: str, ref_date: date
) -> dict[str, dict[str, float]] | None:
    """Soldes CP / RTT / repos à une date de référence (même logique que la page Absences)."""
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return None
    validated_list = absence_repository.list_validated_for_employees([employee_id])
    repos_credits = get_repos_credits_by_employee_year([employee_id], ref_date.year)
    repos_acquis = repos_credits.get(employee_id, 0.0)
    return compute_absence_balances(
        hire_date,
        validated_list,
        ref_date,
        repos_acquis=repos_acquis,
    )


def get_absence_balances_for_payslip(
    employee_id: str, year: int, month: int
) -> dict[str, object] | None:
    """Soldes affichés sur le bulletin : calcul à la fin du mois de paie."""
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return None
    _, last_day = calendar.monthrange(year, month)
    ref_date = date(year, month, last_day)
    validated_list = absence_repository.list_validated_for_employees([employee_id])
    repos_credits = get_repos_credits_by_employee_year([employee_id], ref_date.year)
    repos_acquis = repos_credits.get(employee_id, 0.0)
    cp_lines = compute_cp_balances_for_bulletin(hire_date, validated_list, ref_date)
    autres = compute_absence_balances(
        hire_date,
        validated_list,
        ref_date,
        repos_acquis=repos_acquis,
    )
    return {
        "date_reference": ref_date.strftime("%d/%m/%Y"),
        "conges_payes": cp_lines["periode_courante"],
        "conges_payes_periode_precedente": cp_lines["periode_precedente"],
        "rtt": autres["rtt"],
        "repos_compensateur": autres["repos_compensateur"],
    }


def get_my_absence_balances(employee_id: str) -> List[dict]:
    """Soldes (CP, RTT, repos, événement familial, sans solde) pour un employé. Raises LookupError si pas de hire_date."""
    today = date.today()
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        raise LookupError("Date d'embauche non trouvée pour l'employé.")

    validated_list = absence_repository.list_validated_for_employees([employee_id])
    balances = compute_absence_balances(
        hire_date,
        validated_list,
        today,
        repos_acquis=get_repos_credits_by_employee_year([employee_id], today.year).get(
            employee_id, 0.0
        ),
    )
    cp = balances["conges_payes"]
    rtt = balances["rtt"]
    repos = balances["repos_compensateur"]
    ss_pris = count_absence_days_taken(validated_list, "sans_solde", today)

    return [
        {
            "type": "Congés Payés",
            "acquired": cp["acquis"],
            "taken": cp["pris"],
            "remaining": cp["solde"],
        },
        {
            "type": "RTT",
            "acquired": rtt["acquis"],
            "taken": rtt["pris"],
            "remaining": rtt["solde"],
        },
        {
            "type": "Repos compensateur",
            "acquired": repos["acquis"],
            "taken": repos["pris"],
            "remaining": repos["solde"],
        },
        {
            "type": "Événement familial",
            "acquired": 0,
            "taken": 0,
            "remaining": "selon événement",
        },
        {
            "type": "Congé sans solde",
            "acquired": 0,
            "taken": ss_pris,
            "remaining": "N/A",
        },
    ]


def get_my_monthly_calendar(employee_id: str, year: int, month: int) -> List[dict]:
    """Calendrier planifié du mois pour un employé (liste des jours)."""
    return get_planned_calendar(employee_id, year, month)


def get_my_absences_history(employee_id: str) -> List[dict]:
    """Historique des demandes pour un employé avec URLs signées des justificatifs."""
    data = absence_repository.list_by_employee_id(employee_id)
    if not data:
        return []
    _enrich_with_signed_urls(data)
    for row in data:
        _enrich_absence_certificate_fields(row)
    return data


def get_my_absences_page_data(employee_id: str, year: int, month: int) -> dict:
    """Soldes + calendrier + historique pour la page absences. Keys: balances, calendar_days, history."""
    today = date.today()
    hire_date_raw = get_employee_hire_date(employee_id)
    if not hire_date_raw:
        raise LookupError("Date d'embauche non trouvée.")
    hire_date = (
        date.fromisoformat(hire_date_raw)
        if isinstance(hire_date_raw, str)
        else hire_date_raw
    )

    validated_requests = absence_repository.list_validated_for_employees([employee_id])
    repos_credits = get_repos_credits_by_employee_year([employee_id], today.year)
    soldes = compute_absence_balances(
        hire_date,
        validated_requests,
        today,
        repos_acquis=repos_credits.get(employee_id, 0.0),
    )
    cp = soldes["conges_payes"]
    rtt = soldes["rtt"]
    repos = soldes["repos_compensateur"]
    ss_pris = count_absence_days_taken(validated_requests, "sans_solde", today)

    balances_data = [
        {
            "type": "Congés Payés",
            "acquired": cp["acquis"],
            "taken": cp["pris"],
            "remaining": cp["solde"],
        },
        {
            "type": "RTT",
            "acquired": rtt["acquis"],
            "taken": rtt["pris"],
            "remaining": rtt["solde"],
        },
        {
            "type": "Repos compensateur",
            "acquired": repos["acquis"],
            "taken": repos["pris"],
            "remaining": repos["solde"],
        },
        {
            "type": "Événement familial",
            "acquired": 0,
            "taken": 0,
            "remaining": "selon événement",
        },
        {
            "type": "Congé sans solde",
            "acquired": 0,
            "taken": ss_pris,
            "remaining": "N/A",
        },
    ]

    calendar_data = get_planned_calendar(employee_id, year, month)
    history_data = absence_repository.list_by_employee_id(employee_id)
    if history_data:
        _enrich_with_signed_urls(history_data)
        for row in history_data:
            _enrich_absence_certificate_fields(row)

    return {
        "balances": balances_data,
        "calendar_days": calendar_data,
        "history": history_data,
    }


def get_my_evenements_familiaux(user_id: str, company_id: str) -> List[dict]:
    """Événements familiaux disponibles pour l'utilisateur (résolution employee_id via user_id)."""
    employee_id = resolve_employee_id_for_user(user_id, company_id)
    if not employee_id:
        return []
    return evenement_familial_provider.get_events_disponibles(employee_id)


def get_salary_certificate_info(absence_id: str) -> dict | None:
    """Infos attestation pour une absence (view_url, download_url ajoutés à cert_data). None si pas trouvée."""
    if not absence_repository.get_by_id(absence_id):
        return None
    cert_data = get_salary_certificate_record(absence_id)
    if not cert_data:
        return None
    cert_data = dict(cert_data)
    try:
        url = storage_provider.create_signed_url(
            cert_data["storage_path"],
            BUCKET_SALARY_CERTIFICATES,
            expiry_seconds=3600,
        )
        if url:
            cert_data["view_url"] = url
    except Exception as e:
        logger.warning(f'[WARNING] Erreur URL signée (view): {e}')
    try:
        url = storage_provider.create_signed_url(
            cert_data["storage_path"],
            BUCKET_SALARY_CERTIFICATES,
            expiry_seconds=3600,
            download=True,
        )
        if url:
            cert_data["download_url"] = url
    except Exception as e:
        logger.warning(f'[WARNING] Erreur URL signée (download): {e}')
    return cert_data


def download_salary_certificate(absence_id: str) -> tuple[bytes, str] | None:
    """Contenu PDF et filename de l'attestation pour une absence. None si pas trouvée."""
    cert = get_salary_certificate_record(absence_id)
    if not cert:
        return None
    storage_path = cert["storage_path"]
    filename = cert["filename"]
    file_resp = storage_provider.download(BUCKET_SALARY_CERTIFICATES, storage_path)
    if isinstance(file_resp, dict) and file_resp.get("error"):
        return None
    return (file_resp, filename)


def _parse_absence_day(d: Any) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    s = str(d)[:10]
    return date.fromisoformat(s)


def _company_payload_for_contexte(company_row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "entreprise": {
            "identification": {
                "raison_sociale": company_row.get("name")
                or company_row.get("legal_name")
                or "",
                "siret": str(company_row.get("siret") or ""),
                "adresse": company_row.get("address")
                or company_row.get("headquarters_address")
                or "",
            },
            "parametres_paie": {
                "effectif": int(
                    company_row.get("effectif")
                    or company_row.get("employee_count")
                    or 0
                ),
            },
        }
    }


def _employee_payload_for_contexte(emp: Dict[str, Any]) -> Dict[str, Any]:
    sdb = emp.get("salaire_de_base") or {}
    if isinstance(sdb, dict):
        salaire_base = float(sdb.get("valeur") or 0)
    else:
        salaire_base = float(emp.get("salaire_base_mensuel") or 0)
    return {
        "first_name": emp.get("first_name") or "",
        "last_name": emp.get("last_name") or "",
        "nir": emp.get("nir") or "",
        "statut": emp.get("statut") or "Non-Cadre",
        "emploi": emp.get("job_title") or "",
        "type_contrat": emp.get("contract_type") or "",
        "date_conclusion_contrat": emp.get("date_conclusion_contrat") or "",
        "date_debut_execution": emp.get("date_debut_execution") or "",
        "date_naissance": emp.get("date_naissance") or "",
        "duree_hebdomadaire": float(emp.get("duree_hebdomadaire") or 35),
        "date_entree": emp.get("hire_date") or "",
        "salaire_base": salaire_base,
        "taux_prelevement_source": float(emp.get("taux_prelevement_source") or 0),
        "prevoyance": emp.get("prevoyance") or "NON",
        "is_temps_partiel": bool(emp.get("is_temps_partiel")),
        "avantages_en_nature": emp.get("avantages_en_nature") or {},
        "convention_collective": emp.get("convention_collective") or {},
        "classification_conventionnelle": emp.get("classification_conventionnelle")
        or {},
        "mutuelle": emp.get("mutuelle") or {},
        "titres_restaurant": emp.get("titres_restaurant") or {},
        "transport": emp.get("transport") or {},
        "is_alsace_moselle": bool(emp.get("is_alsace_moselle", False)),
    }


def _infer_subrogation_active(
    settings_dict: Dict[str, Any],
    arret_type: str,
    override: Optional[bool],
) -> bool:
    if override is not None:
        return bool(override)
    mode = settings_dict.get("subrogation_mode") or "automatic"
    at_mp_types = {
        "accident_travail",
        "maladie_professionnelle",
        "accident_trajet",
        "rechute_at",
    }
    if mode == "at_mp_only":
        return arret_type in at_mp_types
    if mode == "per_case":
        return True
    return True


def get_absence_maintenance_preview(
    absence_id: str,
    current_user: User,
    subrogation_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Aperçu moteur maintien pour une absence (arrêt qualifié).
    Contrôle : entreprise active = company de l'employé ; accès RH ou titulaire de la demande.
    """
    active_cid = current_user.active_company_id
    if not active_cid:
        raise ValueError(
            "Sélectionnez une entreprise active pour afficher l'aperçu maintien."
        )

    absence = absence_repository.get_by_id(absence_id)
    if not absence:
        raise LookupError("Absence introuvable.")

    arret_type = absence.get("arret_type")
    if arret_type is None or not str(arret_type).strip():
        raise ValueError(
            "Veuillez qualifier le type d'arrêt avant de calculer le maintien"
        )
    arret_type = str(arret_type).strip()

    emp_res = (
        supabase.table("employees")
        .select("*")
        .eq("id", absence["employee_id"])
        .maybe_single()
        .execute()
    )
    employee_row = emp_res.data if emp_res else None
    if not employee_row:
        raise LookupError("Absence introuvable.")
    emp_company = str(employee_row.get("company_id") or "")
    if emp_company != str(active_cid):
        raise LookupError("Absence introuvable.")

    my_employee_id = resolve_employee_id_for_user(
        str(current_user.id), str(active_cid)
    )
    is_owner = my_employee_id == absence.get("employee_id")
    can_rh = current_user.has_rh_access_in_company(str(active_cid))
    if not (is_owner or can_rh or current_user.is_platform_admin):
        raise LookupError("Absence introuvable.")

    co_res = (
        supabase.table("companies")
        .select("*")
        .eq("id", emp_company)
        .maybe_single()
        .execute()
    )
    company_row = (co_res.data if co_res else None) or {}

    days_raw = absence.get("selected_days") or []
    if not days_raw:
        raise ValueError("Aucune date renseignée pour cette absence.")
    parsed_days = sorted(_parse_absence_day(d) for d in days_raw)
    date_debut_periode = parsed_days[0]
    date_fin_periode = parsed_days[-1]

    settings_model = get_maintenance_settings(emp_company)
    settings_dict = settings_model.model_dump(mode="json")

    sub_active = _infer_subrogation_active(settings_dict, arret_type, subrogation_active)

    temps_travail_row = (
        employee_row.get("temps_travail")
        if isinstance(employee_row.get("temps_travail"), dict)
        else {}
    )
    arret_data: Dict[str, Any] = {
        "arret_type": arret_type,
        "date_debut": date_debut_periode.isoformat(),
        "date_fin": date_fin_periode.isoformat(),
        "subrogation_active": sub_active,
        "nombre_enfants": int(absence.get("nombre_enfants") or 0),
        "is_temps_partiel": bool(
            absence.get("is_temps_partiel")
            if absence.get("is_temps_partiel") is not None
            else employee_row.get("is_temps_partiel")
            or temps_travail_row.get("is_temps_partiel")
            or False
        ),
        "quotite_temps_partiel": float(
            absence.get("quotite_temps_partiel")
            or temps_travail_row.get("quotite")
            or 1.0
        ),
        "historique_arrets_annee": absence.get("historique_arrets_annee") or [],
        "date_dernier_arret": absence.get("date_dernier_arret"),
        "salaire_periode_reelle": float(absence.get("salaire_periode_reelle") or 0.0),
    }

    employee_map = _employee_payload_for_contexte(employee_row)
    company_map = _company_payload_for_contexte(company_row)

    contexte = ChargerContexte(employee_map, company_map, {})
    result = calculer_maintien(
        arret_data,
        contexte,
        settings_dict,
        date_debut_periode,
        date_fin_periode,
    )

    result = dict(result)
    result["subrogation_mode"] = settings_dict.get("subrogation_mode", "automatic")
    return result


def get_absence_regularisation_at(
    absence_id: str,
    current_user: User,
) -> Dict[str, Any]:
    """
    Delta IJSS / maintien entre calcul maladie simple et AT (même absence, dates identiques).
    Réservé aux profils RH sur l'entreprise active ; l'absence doit être qualifiée AT (post-requalification).
    """
    active_cid = current_user.active_company_id
    if not active_cid:
        raise ValueError(
            "Sélectionnez une entreprise active pour la régularisation AT."
        )
    if not current_user.is_platform_admin and not current_user.has_rh_access_in_company(
        str(active_cid)
    ):
        raise PermissionError(
            "Accès réservé aux profils RH pour la régularisation AT."
        )

    absence = absence_repository.get_by_id(absence_id)
    if not absence:
        raise LookupError("Absence introuvable.")

    arret_type = str(absence.get("arret_type") or "").strip()
    if arret_type != "accident_travail":
        raise ValueError(
            "La régularisation AT s'applique uniquement si le type d'arrêt est "
            "« accident_travail » (après requalification)."
        )

    emp_res = (
        supabase.table("employees")
        .select("*")
        .eq("id", absence["employee_id"])
        .maybe_single()
        .execute()
    )
    employee_row = emp_res.data if emp_res else None
    if not employee_row:
        raise LookupError("Absence introuvable.")
    emp_company = str(employee_row.get("company_id") or "")
    if emp_company != str(active_cid):
        raise LookupError("Absence introuvable.")

    co_res = (
        supabase.table("companies")
        .select("*")
        .eq("id", emp_company)
        .maybe_single()
        .execute()
    )
    company_row = (co_res.data if co_res else None) or {}

    days_raw = absence.get("selected_days") or []
    if not days_raw:
        raise ValueError("Aucune date renseignée pour cette absence.")
    parsed_days = sorted(_parse_absence_day(d) for d in days_raw)
    date_debut_periode = parsed_days[0]
    date_fin_periode = parsed_days[-1]

    settings_model = get_maintenance_settings(emp_company)
    settings_dict = settings_model.model_dump(mode="json")

    sub_active = _infer_subrogation_active(settings_dict, arret_type, None)

    temps_travail_row = (
        employee_row.get("temps_travail")
        if isinstance(employee_row.get("temps_travail"), dict)
        else {}
    )
    arret_data: Dict[str, Any] = {
        "arret_type": arret_type,
        "date_debut": date_debut_periode.isoformat(),
        "date_fin": date_fin_periode.isoformat(),
        "subrogation_active": sub_active,
        "nombre_enfants": int(absence.get("nombre_enfants") or 0),
        "is_temps_partiel": bool(
            absence.get("is_temps_partiel")
            if absence.get("is_temps_partiel") is not None
            else employee_row.get("is_temps_partiel")
            or temps_travail_row.get("is_temps_partiel")
            or False
        ),
        "quotite_temps_partiel": float(
            absence.get("quotite_temps_partiel")
            or temps_travail_row.get("quotite")
            or 1.0
        ),
        "historique_arrets_annee": absence.get("historique_arrets_annee") or [],
        "date_dernier_arret": absence.get("date_dernier_arret"),
        "salaire_periode_reelle": float(absence.get("salaire_periode_reelle") or 0.0),
    }

    employee_map = _employee_payload_for_contexte(employee_row)
    company_map = _company_payload_for_contexte(company_row)

    contexte = ChargerContexte(employee_map, company_map, {})

    return calculer_regularisation_at(arret_data, contexte, settings_dict)
