"""
Requêtes Supabase pour le dashboard.

Toute lecture DB du module : employees, absence_requests, expense_reports, payslips.
Client Supabase via app.core.database (aucune dépendance legacy).
"""
from __future__ import annotations

from typing import List

from app.core.database import get_supabase_client


def _get_client():
    """Client Supabase (app.core.database)."""
    return get_supabase_client()


def fetch_employees_for_dashboard(company_id: str) -> List[dict]:
    """Employés avec champs nécessaires au dashboard et au team pulse."""
    client = _get_client()
    resp = (
        client.table("employees")
        .select(
            "id, first_name, last_name, hire_date, date_naissance, "
            "salaire_de_base, contract_type"
        )
        .eq("company_id", company_id)
        .execute()
    )
    return list(resp.data or [])


def fetch_absences_validated_today(company_id: str, today_iso: str) -> List[dict]:
    """Absences validées dont selected_days contient today_iso, avec jointure employee."""
    client = _get_client()
    resp = (
        client.table("absence_requests")
        .select("type, employee:employees(id, first_name, last_name, company_id)")
        .eq("status", "validated")
        .eq("company_id", company_id)
        .contains("selected_days", [today_iso])
        .execute()
    )
    return list(resp.data or [])


def fetch_absence_requests_for_absenteeism(company_id: str) -> List[dict]:
    """Absences validées avec employee_id et selected_days pour calcul du taux."""
    client = _get_client()
    resp = (
        client.table("absence_requests")
        .select("employee_id, type, selected_days, status")
        .eq("status", "validated")
        .eq("company_id", company_id)
        .execute()
    )
    return list(resp.data or [])


def fetch_payslips_by_company(company_id: str) -> List[dict]:
    """Fiches de paie (month, payslip_data) pour agrégation coûts / nets."""
    client = _get_client()
    resp = (
        client.table("payslips")
        .select("month, payslip_data")
        .eq("company_id", company_id)
        .execute()
    )
    return list(resp.data or [])


def get_pending_absence_requests_count(company_id: str) -> int:
    """Nombre de demandes d'absence en attente."""
    client = _get_client()
    resp = (
        client.table("absence_requests")
        .select("id", count="exact")
        .eq("status", "pending")
        .eq("company_id", company_id)
        .execute()
    )
    return resp.count or 0


def get_pending_expense_reports_count(company_id: str) -> int:
    """Nombre de notes de frais en attente."""
    client = _get_client()
    resp = (
        client.table("expense_reports")
        .select("id", count="exact")
        .eq("status", "pending")
        .eq("company_id", company_id)
        .execute()
    )
    return resp.count or 0


def fetch_employees_for_residence_permit_stats(company_id: str) -> List[dict]:
    """Employés soumis au titre de séjour, actifs ou en_sortie (pour stats)."""
    client = _get_client()
    resp = (
        client.table("employees")
        .select(
            "id, is_subject_to_residence_permit, "
            "residence_permit_expiry_date, employment_status"
        )
        .eq("company_id", company_id)
        .eq("is_subject_to_residence_permit", True)
        .in_("employment_status", ["actif", "en_sortie"])
        .execute()
    )
    return list(resp.data or [])
