"""Requêtes applicatives — résolution KPIs paie (bulletins vs DSN)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.modules.dashboard.application.dto import MONTH_NAMES_FR
from app.modules.dsn_import.infrastructure import payroll_totals_repository as dsn_totals_repo
from app.modules.payroll.domain.payroll_kpi_resolver import (
    DsnPeriodTotals,
    PayrollPeriodSnapshot,
    PayslipPeriodTotals,
    aggregate_payslips_by_period,
    build_period_series,
    dsn_row_to_totals,
    primary_source,
    resolve_period_snapshot,
    series_has_mixed_sources,
)


@dataclass
class PayrollDashboardPayload:
    last_month: PayrollPeriodSnapshot
    series_12: List[PayrollPeriodSnapshot]
    has_mixed_sources: bool
    primary_source: str
    dsn_sync_mode: str


def _fetch_payslips(company_id: str) -> List[Dict[str, Any]]:
    client = get_supabase_admin_client()
    resp = (
        client.table("payslips")
        .select("month, year, payslip_data")
        .eq("company_id", company_id)
        .execute()
    )
    return resp.data or []


def _fetch_company_dsn_sync_mode(company_id: str) -> str:
    client = get_supabase_admin_client()
    resp = (
        client.table("companies")
        .select("dsn_sync_mode")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    row = resp.data if resp and resp.data else {}
    return str((row or {}).get("dsn_sync_mode") or "native").strip().lower()


def _dsn_by_period(company_id: str) -> Dict[str, DsnPeriodTotals]:
    rows = dsn_totals_repo.list_by_company(company_id, limit=36)
    return {str(r["period"]): dsn_row_to_totals(r) for r in rows if r.get("period")}


def _month_keys_before_today(*, count: int = 24) -> List[str]:
    today = date.today()
    first_of_current = today.replace(day=1)
    keys: List[str] = []
    cursor = first_of_current - timedelta(days=1)
    for _ in range(count):
        keys.append(f"{cursor.year}-{cursor.month:02d}")
        cursor = cursor.replace(day=1) - timedelta(days=1)
    keys.reverse()
    return keys


def resolve_company_payroll_kpi(
    company_id: str,
    period: str,
    *,
    payslips: Optional[List[Dict[str, Any]]] = None,
    dsn_sync_mode: Optional[str] = None,
) -> PayrollPeriodSnapshot:
    mode = dsn_sync_mode or _fetch_company_dsn_sync_mode(company_id)
    if payslips is None:
        payslips = _fetch_payslips(company_id)
    payslip_map = aggregate_payslips_by_period(payslips)
    dsn_map = _dsn_by_period(company_id)
    return resolve_period_snapshot(
        period,
        payslip_totals=payslip_map.get(period, PayslipPeriodTotals()),
        dsn_totals=dsn_map.get(period, DsnPeriodTotals()),
        dsn_sync_mode=mode,
    )


def resolve_company_payroll_series(
    company_id: str,
    *,
    months: int = 24,
    payslips: Optional[List[Dict[str, Any]]] = None,
    dsn_sync_mode: Optional[str] = None,
) -> List[PayrollPeriodSnapshot]:
    mode = dsn_sync_mode or _fetch_company_dsn_sync_mode(company_id)
    if payslips is None:
        payslips = _fetch_payslips(company_id)
    keys = _month_keys_before_today(count=months)
    payslip_map = aggregate_payslips_by_period(payslips)
    dsn_map = _dsn_by_period(company_id)
    return build_period_series(keys, payslip_map, dsn_map, mode)


def resolve_company_payroll_dashboard(
    company_id: str,
    *,
    payslips: Optional[List[Dict[str, Any]]] = None,
) -> PayrollDashboardPayload:
    mode = _fetch_company_dsn_sync_mode(company_id)
    series = resolve_company_payroll_series(
        company_id, months=24, payslips=payslips, dsn_sync_mode=mode
    )
    series_12 = series[-12:]
    last_month = series[-1] if series else resolve_period_snapshot(
        date.today().replace(day=1).strftime("%Y-%m"),
        payslip_totals=PayslipPeriodTotals(),
        dsn_totals=DsnPeriodTotals(),
        dsn_sync_mode=mode,
    )
    return PayrollDashboardPayload(
        last_month=last_month,
        series_12=series_12,
        has_mixed_sources=series_has_mixed_sources(series_12),
        primary_source=primary_source(series_12),
        dsn_sync_mode=mode,
    )


def snapshot_to_evolution_row(snapshot: PayrollPeriodSnapshot) -> Dict[str, Any]:
    charges = snapshot.employee_charges + snapshot.employer_charges
    return {
        "month": snapshot.period,
        "masse_salariale_brute": round(snapshot.gross, 2),
        "net_verse": round(snapshot.net, 2),
        "charges_totales": round(charges, 2),
        "cout_total_employeur": round(snapshot.employer_cost, 2),
        "payroll_source": snapshot.source,
        "payroll_source_label": snapshot.source_label,
        "payroll_partial": snapshot.partial,
    }


def chart_point_from_snapshot(snapshot: PayrollPeriodSnapshot) -> Dict[str, Any]:
    try:
        _y, m = snapshot.period.split("-")
        month_num = int(m)
        name = MONTH_NAMES_FR.get(month_num, m)
    except (ValueError, IndexError):
        name = snapshot.period
    net = round(snapshot.net, 2)
    cost = round(snapshot.employer_cost, 2)
    if snapshot.source == "dsn" and cost <= 0:
        charges = 0.0
    else:
        charges = round(max(cost - net, 0), 2)
    return {
        "name": name,
        "Net_Verse": net,
        "Charges": charges,
        "source": snapshot.source,
        "period": snapshot.period,
    }


def enrich_consolidated_with_dsn(
    payload: Dict[str, Any],
    company_ids: List[str],
    period: str,
) -> Dict[str, Any]:
    """Fallback DSN pour filiales transition/external sans bulletins dans le snapshot RPC."""
    if not payload or not period:
        return payload

    client = get_supabase_admin_client()
    modes_resp = (
        client.table("companies")
        .select("id, dsn_sync_mode")
        .in_("id", company_ids)
        .execute()
    )
    modes = {
        str(r["id"]): str(r.get("dsn_sync_mode") or "native").lower()
        for r in (modes_resp.data or [])
    }

    by_company = list(payload.get("by_company") or [])
    sources_seen: set = set()
    for row in by_company:
        cid = str(row.get("company_id") or row.get("id") or "")
        if not cid:
            continue
        if float(row.get("gross_salary") or 0) > 0:
            row["payroll_source"] = "payslip"
            sources_seen.add("payslip")
            continue
        snap = resolve_company_payroll_kpi(
            cid, period, dsn_sync_mode=modes.get(cid, "native")
        )
        if snap.source == "dsn" and snap.gross > 0:
            row["gross_salary"] = snap.gross
            row["net_salary"] = snap.net
            row["payroll_source"] = "dsn"
            row["payroll_source_label"] = snap.source_label
            row["payroll_partial"] = snap.partial
            sources_seen.add("dsn")
        else:
            row["payroll_source"] = snap.source
            if snap.source != "none":
                sources_seen.add(snap.source)

    totals = dict(payload.get("totals") or {})
    totals["total_gross_salary"] = sum(float(c.get("gross_salary") or 0) for c in by_company)
    totals["total_net_salary"] = sum(float(c.get("net_salary") or 0) for c in by_company)
    if by_company:
        totals["average_gross_per_company"] = totals["total_gross_salary"] / len(by_company)

    metadata = dict(payload.get("metadata") or {})
    metadata["has_mixed_sources"] = len(sources_seen) > 1

    return {**payload, "by_company": by_company, "totals": totals, "metadata": metadata}
