"""
Lecture Supabase pour comparaison N vs N-1 et tendances.
"""

from __future__ import annotations

from typing import Any

from app.core.database import supabase


def _net_from_payslip_data(data: Any) -> float:
    if not isinstance(data, dict):
        return 0.0
    v = data.get("net_a_payer")
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def fetch_previous_validated_payslip(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> dict[str, Any] | None:
    """
    Dernier bulletin validé strictement avant (year, month).
    """
    r = (
        supabase.table("payslips")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("status", "valide")
        .or_(f"year.lt.{year},and(year.eq.{year},month.lt.{month})")
        .order("year", desc=True)
        .order("month", desc=True)
        .limit(1)
        .execute()
    )
    rows = r.data if r else None
    if not rows:
        return None
    return rows[0] if isinstance(rows, list) else rows


def fetch_validated_payslips_strictly_before(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Bulletins validés avant la période (year, month), du plus récent au plus ancien."""
    r = (
        supabase.table("payslips")
        .select("id, year, month, payslip_data")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("status", "valide")
        .or_(f"year.lt.{year},and(year.eq.{year},month.lt.{month})")
        .order("year", desc=True)
        .order("month", desc=True)
        .limit(limit)
        .execute()
    )
    return (r.data or []) if r else []


def fetch_employee_statut(employee_id: str) -> str | None:
    r = (
        supabase.table("employees")
        .select("statut")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not r or not r.data:
        return None
    st = r.data.get("statut")
    return str(st) if st is not None else None


def fetch_recent_nets_asc_for_r10(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    current_payslip_data: dict[str, Any],
) -> list[float]:
    """
    Jusqu'à 4 nets chronologiques [n-3, n-2, n-1, n] pour R10.
    n = bulletin courant (tout statut) ; mois précédents = validés uniquement.
    """
    prev_rows = fetch_validated_payslips_strictly_before(
        employee_id, company_id, year, month, limit=3
    )
    triple = list(reversed(prev_rows))
    tuples: list[tuple[int, int, float]] = []
    for row in triple:
        tuples.append(
            (
                int(row["year"]),
                int(row["month"]),
                _net_from_payslip_data(row.get("payslip_data")),
            )
        )
    tuples.append((year, month, _net_from_payslip_data(current_payslip_data)))
    tuples.sort(key=lambda x: (x[0], x[1]))
    nets = [t[2] for t in tuples]
    return nets[-4:] if len(nets) >= 4 else nets


def update_payslip_data_alerts_status(
    payslip_id: str,
    rule_id: str,
    status: str,
    user_id: str,
    comment: str | None,
) -> dict[str, Any]:
    """Fusionne alerts_status dans payslip_data."""
    r = (
        supabase.table("payslips")
        .select("payslip_data")
        .eq("id", payslip_id)
        .single()
        .execute()
    )
    row = r.data if r else None
    if not row:
        raise ValueError("Bulletin introuvable")
    pd = row.get("payslip_data") or {}
    if not isinstance(pd, dict):
        pd = {}
    from datetime import datetime, timezone

    statuses = pd.get("alerts_status")
    if not isinstance(statuses, dict):
        statuses = {}
    statuses[rule_id] = {
        "status": status,
        "by": user_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "comment": comment,
    }
    pd["alerts_status"] = statuses
    upd = (
        supabase.table("payslips")
        .update({"payslip_data": pd})
        .eq("id", payslip_id)
        .execute()
    )
    rows = upd.data if upd else None
    if not rows:
        raise ValueError("Mise à jour impossible")
    return rows[0] if isinstance(rows, list) else rows


def mark_payslip_validated(payslip_id: str, user_id: str) -> dict[str, Any]:
    from datetime import datetime, timezone

    from app.modules.payslips.infrastructure.anomaly_cleanup import (
        strip_engine_alerts_from_payslip_data,
    )

    now = datetime.now(timezone.utc).isoformat()
    current = (
        supabase.table("payslips")
        .select("payslip_data")
        .eq("id", payslip_id)
        .maybe_single()
        .execute()
    )
    payload: dict[str, Any] = {
        "status": "valide",
        "validated_at": now,
        "validated_by": user_id,
    }
    pdata = current.data.get("payslip_data") if current and current.data else None
    if isinstance(pdata, dict):
        cleaned = strip_engine_alerts_from_payslip_data(pdata)
        if cleaned != pdata:
            payload["payslip_data"] = cleaned

    upd = (
        supabase.table("payslips")
        .update(payload)
        .eq("id", payslip_id)
        .execute()
    )
    rows = upd.data if upd else None
    if not rows:
        raise ValueError("Validation impossible")
    return rows[0] if isinstance(rows, list) else rows
