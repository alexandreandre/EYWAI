"""
Requêtes Supabase complexes pour saisies et avances.

Listes enrichies (jointures, agrégations), saisies/avances par période,
salaire journalier, avances restant à rembourser. Comportement identique au legacy.
"""
import traceback
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.saisies_avances.domain.rules import (
    MAX_ADVANCE_DAYS,
    compute_advance_available_from_figures,
    remaining_to_pay_value,
)


def get_employee_company_id(employee_id: str) -> Optional[str]:
    """Récupère le company_id d'un employé."""
    r = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    return r.data.get("company_id") if r.data else None


def list_seizures_with_employee(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Liste des saisies avec jointure employee et champ employee_name."""
    q = supabase.table("salary_seizures").select(
        "*, employee:employees(id, first_name, last_name)"
    )
    if employee_id:
        q = q.eq("employee_id", employee_id)
    if status:
        q = q.eq("status", status)
    r = q.order("created_at", desc=True).execute()
    seizures = r.data or []
    for s in seizures:
        if "employee" in s and isinstance(s["employee"], dict):
            emp = s["employee"]
            s["employee_name"] = (
                f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
            )
    return seizures


def list_advances_with_employee_and_remaining_to_pay(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Liste des avances enrichie employee_name et remaining_to_pay.
    Comportement identique au router legacy (batch employees + batch payments).
    """
    q = supabase.table("salary_advances").select("*")
    if employee_id:
        q = q.eq("employee_id", employee_id)
    if status:
        q = q.eq("status", status)
    r = q.order("created_at", desc=True).execute()
    advances = r.data or []

    employee_ids = list(set(a.get("employee_id") for a in advances if a.get("employee_id")))
    employees_map: Dict[str, str] = {}
    if employee_ids:
        try:
            ids_norm = [str(eid) for eid in employee_ids]
            emp_res = (
                supabase.table("employees")
                .select("id, first_name, last_name")
                .in_("id", ids_norm)
                .execute()
            )
            if emp_res.data:
                for emp in emp_res.data:
                    eid = emp.get("id")
                    fn, ln = emp.get("first_name", ""), emp.get("last_name", "")
                    full = f"{fn} {ln}".strip()
                    if full:
                        sid = str(eid)
                        employees_map[sid] = full
                        if eid != sid:
                            employees_map[eid] = full
        except Exception as e:
            traceback.print_exc()
            print(f"Erreur récupération noms employés: {e}")

    advance_ids = [a.get("id") for a in advances if a.get("id")]
    payments_map: Dict[str, Decimal] = {}
    if advance_ids:
        try:
            aids_str = [str(aid) for aid in advance_ids]
            pay_res = (
                supabase.table("salary_advance_payments")
                .select("advance_id, payment_amount")
                .in_("advance_id", aids_str)
                .execute()
            )
            if pay_res.data:
                for p in pay_res.data:
                    aid_raw = p.get("advance_id")
                    if not aid_raw:
                        continue
                    key = str(aid_raw).strip()
                    amt = Decimal(str(p.get("payment_amount", 0)))
                    payments_map[key] = payments_map.get(key, Decimal("0")) + amt
        except Exception as e:
            traceback.print_exc()
            print(f"Erreur récupération paiements: {e}")

    for advance in advances:
        try:
            eid = advance.get("employee_id")
            advance["employee_name"] = employees_map.get(str(eid)) or (
                employees_map.get(eid) if eid else None
            )
            aid = advance.get("id")
            aid_key = str(aid) if aid else None
            approved_raw = advance.get("approved_amount")
            approved = Decimal("0")
            if approved_raw is not None and approved_raw != "":
                try:
                    if isinstance(approved_raw, (int, float)):
                        approved = Decimal(str(float(approved_raw)))
                    else:
                        sv = str(approved_raw).strip()
                        if sv:
                            approved = Decimal(sv)
                except (ValueError, TypeError, Exception):
                    approved = Decimal("0")
            total_paid = payments_map.get(aid_key, Decimal("0")) if aid_key else Decimal("0")
            advance["remaining_to_pay"] = remaining_to_pay_value(approved, total_paid)
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR GET ADVANCES] {advance.get('id')}: {e}")
            if "employee_name" not in advance:
                advance["employee_name"] = None
            advance["remaining_to_pay"] = 0.0

    return advances


def get_seizures_for_period(
    employee_id: str, year: int, month: int
) -> List[Dict[str, Any]]:
    """Saisies actives pour une période (dates dans la période)."""
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1) - date.resolution
    else:
        period_end = date(year, month + 1, 1) - date.resolution
    r = (
        supabase.table("salary_seizures")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("status", "active")
        .lte("start_date", period_end)
        .or_(f"end_date.is.null,end_date.gte.{period_start}")
        .execute()
    )
    return r.data or []


def get_advances_to_repay(
    employee_id: str, year: int, month: int
) -> List[Dict[str, Any]]:
    """Avances à rembourser (approved/paid, remaining_amount > 0, avec au moins un paiement)."""
    r = (
        supabase.table("salary_advances")
        .select("*")
        .eq("employee_id", employee_id)
        .in_("status", ["approved", "paid"])
        .gt("remaining_amount", 0)
        .execute()
    )
    advances = r.data or []
    result = []
    for advance in advances:
        advance_id = advance.get("id")
        pay_r = (
            supabase.table("salary_advance_payments")
            .select("id")
            .eq("advance_id", advance_id)
            .limit(1)
            .execute()
        )
        if advance.get("status") == "paid" or (pay_r.data and len(pay_r.data) > 0):
            result.append(advance)
    return result


def get_daily_salary_for_employee(employee_id: str) -> Decimal:
    """Salaire journalier : dernier bulletin net_a_payer/30 ou salaire_de_base/30."""
    r = (
        supabase.table("payslips")
        .select("payslip_data, year, month")
        .eq("employee_id", employee_id)
        .order("year", desc=True)
        .order("month", desc=True)
        .limit(1)
        .execute()
    )
    if r.data:
        payslip_data = r.data[0].get("payslip_data", {})
        net = Decimal(str(payslip_data.get("net_a_payer", 0)))
        return net / Decimal("30")
    emp_r = (
        supabase.table("employees")
        .select("salaire_de_base")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    if emp_r.data:
        sb = emp_r.data.get("salaire_de_base", {})
        if isinstance(sb, dict):
            base = Decimal(str(sb.get("valeur", 0)))
        else:
            base = Decimal(str(sb))
        return base / Decimal("30")
    return Decimal("0")


def get_outstanding_advances_sum(employee_id: str) -> Decimal:
    """Somme des remaining_amount des avances status=paid et remaining_amount > 0."""
    r = (
        supabase.table("salary_advances")
        .select("remaining_amount")
        .eq("employee_id", employee_id)
        .eq("status", "paid")
        .gt("remaining_amount", 0)
        .execute()
    )
    return sum(
        Decimal(str(a.get("remaining_amount", 0))) for a in (r.data or [])
    )


def get_days_worked_for_month(year: int, month: int) -> Decimal:
    """Jours travaillés : jour du mois si mois en cours, sinon 15."""
    today = date.today()
    if today.month == month and today.year == year:
        return Decimal(str(today.day))
    return Decimal("15")


def build_advance_available(
    employee_id: str, year: int, month: int
) -> Dict[str, Any]:
    """
    Construit le montant disponible pour une avance (données + règle pure).
    Retourne un dict avec daily_salary, days_worked, outstanding_advances, available_amount, max_advance_days.
    """
    daily_salary = get_daily_salary_for_employee(employee_id)
    days_worked = get_days_worked_for_month(year, month)
    total_outstanding = get_outstanding_advances_sum(employee_id)
    available_amount, _ = compute_advance_available_from_figures(
        daily_salary, days_worked, total_outstanding, MAX_ADVANCE_DAYS
    )
    return {
        "daily_salary": daily_salary,
        "days_worked": days_worked,
        "outstanding_advances": total_outstanding,
        "available_amount": available_amount,
        "max_advance_days": MAX_ADVANCE_DAYS,
    }


def list_salary_seizure_deductions_by_payslip(payslip_id: str) -> List[Dict[str, Any]]:
    """Prélèvements appliqués sur un bulletin."""
    r = (
        supabase.table("salary_seizure_deductions")
        .select("*")
        .eq("payslip_id", payslip_id)
        .order("created_at", desc=True)
        .execute()
    )
    return r.data or []


def list_salary_advance_repayments_by_payslip(payslip_id: str) -> List[Dict[str, Any]]:
    """Remboursements d'avances appliqués sur un bulletin."""
    r = (
        supabase.table("salary_advance_repayments")
        .select("*")
        .eq("payslip_id", payslip_id)
        .order("created_at", desc=True)
        .execute()
    )
    return r.data or []


def get_payment_with_advance(payment_id: str) -> Optional[Dict[str, Any]]:
    """Paiement avec jointure advance (id, approved_amount, remaining_amount)."""
    r = (
        supabase.table("salary_advance_payments")
        .select("*, advance:salary_advances(id, approved_amount, remaining_amount)")
        .eq("id", payment_id)
        .single()
        .execute()
    )
    return r.data if r.data else None


def get_proof_file_path(payment_id: str) -> Optional[str]:
    """Chemin du fichier preuve pour un paiement."""
    r = (
        supabase.table("salary_advance_payments")
        .select("proof_file_path")
        .eq("id", payment_id)
        .single()
        .execute()
    )
    return r.data.get("proof_file_path") if r.data else None
