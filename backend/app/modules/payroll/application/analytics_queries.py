"""Requêtes applicatives — Analytics Paie."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from app.modules.payslips.application.anomalies_report import build_payslips_anomalies_report
from app.modules.payroll.infrastructure.analytics_repository import (
    payroll_analytics_repository as repo,
)
from app.modules.payroll.schemas.analytics_responses import (
    ItemsAIntegrer,
    PayrollAnalyticsBreakdown,
    PayrollAnalyticsSummary,
    PayrollAnalyticsTrends,
    PayrollBreakdownItem,
    PayrollPeriodItem,
    PayrollPeriodsResponse,
    PayrollTrendPoint,
)


def _parse_period(period: str) -> Tuple[int, int]:
    parts = period.strip().split("-")
    if len(parts) != 2:
        raise ValueError("Période invalide (attendu YYYY-MM).")
    return int(parts[0]), int(parts[1])


def _period_key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    m = month + delta
    y = year
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return y, m


def _iter_months(end_year: int, end_month: int, count: int) -> List[Tuple[int, int, str]]:
    y, m = end_year, end_month
    out: List[Tuple[int, int, str]] = []
    for _ in range(count):
        out.append((y, m, _period_key(y, m)))
        y, m = _shift_month(y, m, -1)
    out.reverse()
    return out


def _extract_amounts(payslip_data: Any) -> Dict[str, float]:
    pd = payslip_data if isinstance(payslip_data, dict) else {}
    pied = pd.get("pied_de_page") if isinstance(pd.get("pied_de_page"), dict) else {}
    sc = pd.get("structure_cotisations") if isinstance(pd.get("structure_cotisations"), dict) else {}
    lines = sc.get("cotisations") if isinstance(sc.get("cotisations"), list) else []
    cot_sal = 0.0
    cot_pat = 0.0
    for line in lines:
        if not isinstance(line, dict):
            continue
        cot_sal += float(line.get("montant_salarial") or 0)
        cot_pat += float(line.get("montant_patronal") or 0)
    return {
        "brut": float(pd.get("salaire_brut") or 0),
        "net": float(pd.get("net_a_payer") or 0),
        "cout_employeur": float(pied.get("cout_total_employeur") or 0),
        "cotisations_salariales": cot_sal,
        "cotisations_patronales": cot_pat,
    }


def _employee_ids_for_teams(
    employees: List[Dict[str, Any]], team_ids: Optional[List[str]]
) -> Optional[Set[str]]:
    if not team_ids:
        return None
    sel = {str(t) for t in team_ids if t}
    return {
        str(e["id"])
        for e in employees
        if e.get("id") and str(e.get("team_id") or "") in sel
    }


def _filter_payslips_by_teams(
    payslips: List[Dict[str, Any]],
    allowed_ids: Optional[Set[str]],
) -> List[Dict[str, Any]]:
    if allowed_ids is None:
        return payslips
    return [p for p in payslips if str(p.get("employee_id") or "") in allowed_ids]


def _aggregate_payslips(
    payslips: List[Dict[str, Any]], *, validated_only: bool = False
) -> Dict[str, float]:
    totals = {
        "brut": 0.0,
        "net": 0.0,
        "cout_employeur": 0.0,
        "cotisations_salariales": 0.0,
        "cotisations_patronales": 0.0,
    }
    paid_ids: Set[str] = set()
    for row in payslips:
        if validated_only and str(row.get("status") or "") != "valide":
            continue
        amounts = _extract_amounts(row.get("payslip_data"))
        for k in totals:
            if k in amounts:
                totals[k] += amounts[k]
        eid = str(row.get("employee_id") or "")
        if eid:
            paid_ids.add(eid)
    totals["effectif_paye"] = float(len(paid_ids))
    return totals


def _pct_delta(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / previous) * 100.0, 2)


def _cycle_status(
    *,
    is_closed: bool,
    nb_valides: int,
    nb_attendus: int,
) -> Literal["brouillon", "en_cours", "clos"]:
    if is_closed:
        return "clos"
    if nb_valides > 0:
        return "en_cours"
    return "brouillon"


def get_payroll_analytics_summary(
    company_id: str,
    period: str,
    team_ids: Optional[List[str]] = None,
) -> dict:
    year, month = _parse_period(period)
    employees = repo.fetch_active_employees(company_id)
    allowed = _employee_ids_for_teams(employees, team_ids)
    if team_ids and allowed is not None:
        employees = [e for e in employees if str(e.get("id") or "") in allowed]

    effectif_actif = len(employees)
    payslips = _filter_payslips_by_teams(
        repo.fetch_payslips_for_company(company_id, year=year, month=month),
        allowed,
    )
    prev_y, prev_m = _shift_month(year, month, -1)
    prev_payslips = _filter_payslips_by_teams(
        repo.fetch_payslips_for_company(company_id, year=prev_y, month=prev_m),
        allowed,
    )

    valides = [p for p in payslips if str(p.get("status") or "") == "valide"]
    nb_valides = len(valides)
    nb_attendus = effectif_actif

    cur = _aggregate_payslips(payslips, validated_only=True)
    prev = _aggregate_payslips(prev_payslips, validated_only=True)

    anomalies = build_payslips_anomalies_report(company_id, year, month)
    bloquants = 0
    warnings = 0
    if team_ids and allowed is not None:
        for a in anomalies.anomalies:
            if str(a.employee_id) in allowed:
                if a.severite == "bloquant":
                    bloquants += 1
                else:
                    warnings += 1
    else:
        for a in anomalies.anomalies:
            if a.severite == "bloquant":
                bloquants += 1
            else:
                warnings += 1

    ndf = repo.count_pending_expenses(company_id)
    absences = repo.count_pending_absences(company_id)

    active_ids = {str(e["id"]) for e in employees if e.get("id")}
    mi_count = repo.count_monthly_inputs(active_ids, year, month)
    adv_count = repo.count_active_advances(active_ids)

    is_closed = repo.is_period_closed(company_id, year, month)
    items = ItemsAIntegrer(
        ndf=ndf,
        absences=absences,
        primes=mi_count,
        avances=adv_count,
        total=ndf + absences + mi_count + adv_count,
    )

    closed_at = None
    for run in repo.fetch_payroll_runs(company_id, year):
        if run.get("month") == month and str(run.get("status")) == "closed":
            closed_at = run.get("closed_at")
            if closed_at and hasattr(closed_at, "isoformat"):
                closed_at = closed_at.isoformat()
            else:
                closed_at = str(closed_at) if closed_at else None
            break

    summary = PayrollAnalyticsSummary(
        period=period,
        statut_cycle=_cycle_status(
            is_closed=is_closed,
            nb_valides=nb_valides,
            nb_attendus=nb_attendus,
        ),
        nb_bulletins_valides=nb_valides,
        nb_bulletins_attendus=nb_attendus,
        anomalies_bloquantes=bloquants,
        anomalies_warnings=warnings,
        masse_brute=round(cur["brut"], 2),
        cout_employeur_total=round(cur["cout_employeur"], 2),
        net_verse=round(cur["net"], 2),
        effectif_paye=int(cur["effectif_paye"]),
        effectif_actif=effectif_actif,
        delta_brut_m1_pct=_pct_delta(cur["brut"], prev["brut"]),
        delta_cout_m1_pct=_pct_delta(cur["cout_employeur"], prev["cout_employeur"]),
        items_a_integrer=items,
        cycle_closed_at=closed_at,
    )
    return summary.model_dump()


def get_payroll_analytics_trends(
    company_id: str,
    *,
    months: int = 12,
    end_period: Optional[str] = None,
    team_ids: Optional[List[str]] = None,
) -> dict:
    today = date.today()
    if end_period:
        end_y, end_m = _parse_period(end_period)
    else:
        end_y, end_m = today.year, today.month

    months = max(1, min(months, 24))
    employees = repo.fetch_active_employees(company_id)
    allowed = _employee_ids_for_teams(employees, team_ids)

    all_payslips = repo.fetch_payslips_for_company(company_id)
    if allowed is not None:
        all_payslips = _filter_payslips_by_teams(all_payslips, allowed)

    by_period: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in all_payslips:
        y, m = p.get("year"), p.get("month")
        if y is None or m is None:
            continue
        key = _period_key(int(y), int(m))
        by_period[key].append(p)

    points: List[PayrollTrendPoint] = []
    for y, m, key in _iter_months(end_y, end_m, months):
        rows = by_period.get(key, [])
        agg = _aggregate_payslips(rows, validated_only=True)
        is_closed = repo.is_period_closed(company_id, y, m)
        points.append(
            PayrollTrendPoint(
                period=key,
                masse_brute=round(agg["brut"], 2),
                cotisations_salariales=round(agg["cotisations_salariales"], 2),
                cotisations_patronales=round(agg["cotisations_patronales"], 2),
                net_verse=round(agg["net"], 2),
                cout_employeur=round(agg["cout_employeur"], 2),
                effectif_paye=int(agg["effectif_paye"]),
                is_closed=is_closed,
            )
        )

    return PayrollAnalyticsTrends(
        end_period=_period_key(end_y, end_m),
        months=months,
        points=points,
    ).model_dump()


def get_payroll_analytics_breakdown(
    company_id: str,
    period: str,
    group_by: Literal["team", "service", "contract_type"] = "team",
    team_ids: Optional[List[str]] = None,
) -> dict:
    year, month = _parse_period(period)
    employees = repo.fetch_active_employees(company_id)
    allowed = _employee_ids_for_teams(employees, team_ids)
    if allowed is not None:
        employees = [e for e in employees if str(e.get("id") or "") in allowed]

    emp_meta: Dict[str, Dict[str, Any]] = {
        str(e["id"]): e for e in employees if e.get("id")
    }
    teams = {str(t["id"]): str(t.get("name") or "Équipe") for t in repo.fetch_teams(company_id)}
    services = repo.fetch_services(company_id)

    payslips = _filter_payslips_by_teams(
        repo.fetch_payslips_for_company(company_id, year=year, month=month),
        allowed,
    )
    valides = [p for p in payslips if str(p.get("status") or "") == "valide"]

    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"masse_brute": 0.0, "cout_employeur": 0.0, "employees": set()}
    )

    for p in valides:
        eid = str(p.get("employee_id") or "")
        meta = emp_meta.get(eid)
        if not meta:
            continue
        amounts = _extract_amounts(p.get("payslip_data"))
        if group_by == "team":
            tid = str(meta.get("team_id") or "")
            key = tid or "__none__"
            label = teams.get(tid, "Sans équipe") if tid else "Sans équipe"
        elif group_by == "service":
            sid = str(meta.get("service_id") or "")
            key = sid or "__none__"
            label = services.get(sid, "Sans service") if sid else "Sans service"
        else:
            ctype = str(meta.get("contract_type") or "Non défini")
            key = ctype
            label = ctype
        buckets[key]["label"] = label
        buckets[key]["masse_brute"] += amounts["brut"]
        buckets[key]["cout_employeur"] += amounts["cout_employeur"]
        buckets[key]["employees"].add(eid)

    items: List[PayrollBreakdownItem] = []
    total = 0.0
    for key, data in sorted(buckets.items(), key=lambda x: (-x[1]["masse_brute"], x[1].get("label", ""))):
        mb = round(data["masse_brute"], 2)
        total += mb
        items.append(
            PayrollBreakdownItem(
                key=key,
                label=str(data.get("label") or key),
                masse_brute=mb,
                cout_employeur=round(data["cout_employeur"], 2),
                effectif=len(data["employees"]),
            )
        )

    return PayrollAnalyticsBreakdown(
        period=period,
        group_by=group_by,
        items=items,
        total_masse_brute=round(total, 2),
    ).model_dump()


def get_payroll_periods(company_id: str, year: int) -> dict:
    runs = repo.fetch_payroll_runs(company_id, year)
    run_by_month = {int(r["month"]): r for r in runs if r.get("month")}

    periods: List[PayrollPeriodItem] = []
    for m in range(1, 13):
        run = run_by_month.get(m)
        status: Literal["open", "closed", "locked"] = "open"
        closed_at = None
        closed_by = None
        if run:
            raw = str(run.get("status") or "open")
            if raw in ("closed", "locked", "open"):
                status = raw  # type: ignore[assignment]
            closed_at = run.get("closed_at")
            if closed_at and hasattr(closed_at, "isoformat"):
                closed_at = closed_at.isoformat()
            elif closed_at:
                closed_at = str(closed_at)
            closed_by = run.get("closed_by")
            if closed_by:
                closed_by = str(closed_by)

        periods.append(
            PayrollPeriodItem(
                year=year,
                month=m,
                period=_period_key(year, m),
                status=status,
                closed_at=closed_at,
                closed_by=closed_by,
            )
        )

    return PayrollPeriodsResponse(year=year, periods=periods).model_dump()
