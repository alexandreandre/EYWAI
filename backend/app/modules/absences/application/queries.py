"""
Queries (cas d'usage lecture) du module absences.

Utilise domain (règles) et infrastructure (repository, providers, queries).
Retourne des dicts / listes de dicts compatibles avec les schémas de réponse API.
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from typing import List
from uuid import uuid4

from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    calculate_acquired_rtt,
)
from app.modules.absences.infrastructure.providers import (
    evenement_familial_provider,
    storage_provider,
)
from app.modules.absences.infrastructure.queries import (
    get_employee_hire_date,
    get_employees_hire_dates_batch,
    get_planned_calendar,
    get_repos_credits_by_employee_year,
    get_salary_certificate_record,
    resolve_employee_id_for_user,
)
from app.modules.absences.infrastructure.repository import absence_repository

BUCKET_LEAVE_ATTACHMENTS = "leave_attachments"
BUCKET_SALARY_CERTIFICATES = "salary_certificates"


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
        print(f"[WARNING] Erreur URLs signées: {e}", file=sys.stderr)


def get_upload_url_signed(user_id: str, filename: str) -> dict:
    """Génère une URL signée pour l'upload d'un justificatif. Retourne {"path": ..., "signedURL": ...}."""
    _root, extension = (
        filename.rsplit(".", 1) if "." in filename else (filename, "")
    )
    if "." in filename and extension:
        extension = f".{extension}"
    else:
        extension = ""
    unique_filename = f"{datetime.now().isoformat()}-{uuid4().hex}{extension}"
    path = f"{user_id}/{unique_filename}"
    url = storage_provider.create_signed_upload_url(
        path, BUCKET_LEAVE_ATTACHMENTS
    )
    return {"path": path, "signedURL": url}


def get_absence_requests(status: str | None = None) -> List[dict]:
    """Liste des demandes (optionnellement filtrées par status), enrichies employé + soldes + URLs signées."""
    requests = absence_repository.list_by_status(status)
    if not requests:
        return []

    employee_ids = list({req["employee"]["id"] for req in requests})
    today = date.today()
    hire_dates = get_employees_hire_dates_batch(employee_ids)
    validated_reqs = absence_repository.list_validated_for_employees(
        employee_ids
    )
    repos_credits_by_emp = get_repos_credits_by_employee_year(
        employee_ids, today.year
    )

    balances_map: dict[str, List[dict]] = {}
    for emp_id in employee_ids:
        if emp_id not in hire_dates:
            continue
        hire_date = hire_dates[emp_id]
        cp_acquis = calculate_acquired_cp(hire_date, today)
        rtt_acquis = calculate_acquired_rtt(hire_date, today)
        emp_validated = [r for r in validated_reqs if r["employee_id"] == emp_id]
        cp_pris = sum(
            r.get("jours_payes") if r.get("jours_payes") is not None else len(r.get("selected_days", []))
            for r in emp_validated
            if r["type"] == "conge_paye"
        )
        rtt_pris = sum(
            len(r["selected_days"]) for r in emp_validated if r["type"] == "rtt"
        )
        repos_pris = sum(
            len(r["selected_days"])
            for r in emp_validated
            if r["type"] == "repos_compensateur"
        )
        repos_acquis = repos_credits_by_emp.get(emp_id, 0.0)
        balances_map[emp_id] = [
            {"type": "Congés Payés", "acquired": cp_acquis, "taken": cp_pris, "remaining": cp_acquis - cp_pris},
            {"type": "RTT", "acquired": rtt_acquis, "taken": rtt_pris, "remaining": rtt_acquis - rtt_pris},
            {"type": "Repos compensateur", "acquired": repos_acquis, "taken": repos_pris, "remaining": repos_acquis - repos_pris},
            {"type": "Événement familial", "acquired": 0, "taken": 0, "remaining": "selon événement"},
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
    return requests


def get_absences_for_employee(employee_id: str) -> List[dict]:
    """Historique des demandes pour un employé, avec URLs signées des justificatifs."""
    data = absence_repository.list_by_employee_id(employee_id)
    if not data:
        return []
    _enrich_with_signed_urls(data)
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
            print(f"[WARNING] Erreur URL signée: {e}", file=sys.stderr)
    return data


def get_my_absence_balances(employee_id: str) -> List[dict]:
    """Soldes (CP, RTT, repos, événement familial, sans solde) pour un employé. Raises LookupError si pas de hire_date."""
    today = date.today()
    hire_date_raw = get_employee_hire_date(employee_id)
    if not hire_date_raw:
        raise LookupError("Date d'embauche non trouvée pour l'employé.")
    hire_date = (
        date.fromisoformat(hire_date_raw)
        if isinstance(hire_date_raw, str)
        else hire_date_raw
    )

    cp_acquis = calculate_acquired_cp(hire_date, today)
    rtt_acquis = calculate_acquired_rtt(hire_date, today)
    validated_list = absence_repository.list_validated_for_employees(
        [employee_id]
    )
    cp_pris = sum(
        r.get("jours_payes") if r.get("jours_payes") is not None else len(r.get("selected_days", []))
        for r in validated_list
        if r.get("type") == "conge_paye"
    )
    rtt_pris = sum(len(r["selected_days"]) for r in validated_list if r.get("type") == "rtt")
    ss_pris = sum(len(r["selected_days"]) for r in validated_list if r.get("type") == "sans_solde")
    repos_pris = sum(
        len(r["selected_days"])
        for r in validated_list
        if r.get("type") == "repos_compensateur"
    )
    cp_restant = cp_acquis - cp_pris
    rtt_restant = rtt_acquis - rtt_pris
    repos_credits = get_repos_credits_by_employee_year([employee_id], today.year)
    repos_acquis = repos_credits.get(employee_id, 0.0)
    repos_restant = repos_acquis - repos_pris

    return [
        {"type": "Congés Payés", "acquired": cp_acquis, "taken": cp_pris, "remaining": cp_restant},
        {"type": "RTT", "acquired": rtt_acquis, "taken": rtt_pris, "remaining": rtt_restant},
        {"type": "Repos compensateur", "acquired": repos_acquis, "taken": repos_pris, "remaining": repos_restant},
        {"type": "Événement familial", "acquired": 0, "taken": 0, "remaining": "selon événement"},
        {"type": "Congé sans solde", "acquired": 0, "taken": ss_pris, "remaining": "N/A"},
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
    return data


def get_my_absences_page_data(
    employee_id: str, year: int, month: int
) -> dict:
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

    cp_acquis = calculate_acquired_cp(hire_date, today)
    rtt_acquis = calculate_acquired_rtt(hire_date, today)
    validated_requests = absence_repository.list_validated_for_employees(
        [employee_id]
    )
    cp_pris = sum(
        req.get("jours_payes") if req.get("jours_payes") is not None else len(req.get("selected_days", []))
        for req in validated_requests
        if req["type"] == "conge_paye"
    )
    rtt_pris = sum(len(req["selected_days"]) for req in validated_requests if req["type"] == "rtt")
    ss_pris = sum(len(req["selected_days"]) for req in validated_requests if req["type"] == "sans_solde")
    repos_pris = sum(
        len(req["selected_days"])
        for req in validated_requests
        if req["type"] == "repos_compensateur"
    )
    repos_credits = get_repos_credits_by_employee_year([employee_id], today.year)
    repos_acquis = repos_credits.get(employee_id, 0.0)

    balances_data = [
        {"type": "Congés Payés", "acquired": cp_acquis, "taken": cp_pris, "remaining": cp_acquis - cp_pris},
        {"type": "RTT", "acquired": rtt_acquis, "taken": rtt_pris, "remaining": rtt_acquis - rtt_pris},
        {"type": "Repos compensateur", "acquired": repos_acquis, "taken": repos_pris, "remaining": repos_acquis - repos_pris},
        {"type": "Événement familial", "acquired": 0, "taken": 0, "remaining": "selon événement"},
        {"type": "Congé sans solde", "acquired": 0, "taken": ss_pris, "remaining": "N/A"},
    ]

    calendar_data = get_planned_calendar(employee_id, year, month)
    history_data = absence_repository.list_by_employee_id(employee_id)
    if history_data:
        _enrich_with_signed_urls(history_data)

    return {
        "balances": balances_data,
        "calendar_days": calendar_data,
        "history": history_data,
    }


def get_my_evenements_familiaux(user_id: str) -> List[dict]:
    """Événements familiaux disponibles pour l'utilisateur (résolution employee_id via user_id)."""
    employee_id = resolve_employee_id_for_user(user_id)
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
        print(f"[WARNING] Erreur URL signée (view): {e}", file=sys.stderr)
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
        print(f"[WARNING] Erreur URL signée (download): {e}", file=sys.stderr)
    return cert_data


def download_salary_certificate(absence_id: str) -> tuple[bytes, str] | None:
    """Contenu PDF et filename de l'attestation pour une absence. None si pas trouvée."""
    cert = get_salary_certificate_record(absence_id)
    if not cert:
        return None
    storage_path = cert["storage_path"]
    filename = cert["filename"]
    file_resp = storage_provider.download(
        BUCKET_SALARY_CERTIFICATES, storage_path
    )
    if isinstance(file_resp, dict) and file_resp.get("error"):
        return None
    return (file_resp, filename)
