"""
Requêtes Supabase pour le dashboard.

Toute lecture DB du module : employees, absence_requests, expense_reports, payslips.
Client Supabase via app.core.database (aucune dépendance legacy).
"""

from __future__ import annotations

from datetime import date
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
    """Fiches de paie (year, month, payslip_data) pour agrégation coûts / nets et HS."""
    client = _get_client()
    resp = (
        client.table("payslips")
        .select("year, month, payslip_data")
        .eq("company_id", company_id)
        .execute()
    )
    return list(resp.data or [])


def count_employees_missing_iban(company_id: str) -> int:
    """Salariés actifs sans IBAN renseigné (alerte paie)."""
    try:
        client = _get_client()
        resp = (
            client.table("employees")
            .select("id, iban")
            .eq("company_id", company_id)
            .eq("employment_status", "actif")
            .execute()
        )
        n = 0
        for row in resp.data or []:
            iban = row.get("iban")
            if iban is None or (isinstance(iban, str) and not iban.strip()):
                n += 1
        return n
    except Exception:
        return 0


def count_monthly_inputs_for_company(company_id: str, year: int, month: int) -> int:
    """Nombre de primes / variables mensuelles saisies pour le mois (employés de l'entreprise)."""
    try:
        client = _get_client()
        emp_resp = (
            client.table("employees")
            .select("id")
            .eq("company_id", company_id)
            .execute()
        )
        emp_set = {str(r["id"]) for r in (emp_resp.data or []) if r.get("id")}
        if not emp_set:
            return 0
        r2 = (
            client.table("monthly_inputs")
            .select("employee_id")
            .eq("year", year)
            .eq("month", month)
            .execute()
        )
        return sum(1 for row in (r2.data or []) if str(row.get("employee_id") or "") in emp_set)
    except Exception:
        return 0


def salary_advances_summary_for_company(company_id: str, ref_year: int, ref_month: int) -> tuple[int, float, int, float]:
    """
    (pending_count, pending_requested_sum_eur, advances_created_in_month_count, advances_created_in_month_sum_eur)
    """
    try:
        client = _get_client()
        emp_resp = (
            client.table("employees")
            .select("id")
            .eq("company_id", company_id)
            .execute()
        )
        emp_ids = [str(r["id"]) for r in (emp_resp.data or []) if r.get("id")]
        if not emp_ids:
            return 0, 0.0, 0, 0.0
        rows: list = []
        chunk = 80
        for i in range(0, len(emp_ids), chunk):
            part = emp_ids[i : i + chunk]
            resp = (
                client.table("salary_advances")
                .select("id, status, requested_amount, created_at")
                .in_("employee_id", part)
                .execute()
            )
            rows.extend(resp.data or [])
        pending_count = 0
        pending_sum = 0.0
        month_count = 0
        month_sum = 0.0
        for row in rows:
            try:
                amt = float(row.get("requested_amount") or 0)
            except (TypeError, ValueError):
                amt = 0.0
            st = row.get("status") or ""
            if st == "pending":
                pending_count += 1
                pending_sum += amt
            created = row.get("created_at")
            if created:
                try:
                    if isinstance(created, str):
                        d = date.fromisoformat(created[:10])
                    else:
                        continue
                    if d.year == ref_year and d.month == ref_month:
                        month_count += 1
                        month_sum += amt
                except (ValueError, TypeError):
                    continue
        return pending_count, round(pending_sum, 2), month_count, round(month_sum, 2)
    except Exception:
        return 0, 0.0, 0, 0.0


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
