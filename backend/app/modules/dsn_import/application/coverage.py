"""Calcul de couverture DSN par entreprise (mois importés, trous, alertes)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from app.modules.dsn_import.infrastructure import repository as repo

DSN_SYNC_MODES_ALERTING = frozenset({"external", "transition"})
GRACE_DAYS_AFTER_PAYDAY = 5
DEFAULT_PAY_DAY = 25


def _parse_period(period: str) -> Optional[Tuple[int, int]]:
    if not period or len(period) < 7:
        return None
    try:
        y, m = period.split("-", 1)
        return int(y), int(m)
    except ValueError:
        return None


def _period_str(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _month_range(start: Tuple[int, int], end: Tuple[int, int]) -> List[str]:
    """Liste inclusive YYYY-MM entre start et end."""
    sy, sm = start
    ey, em = end
    out: List[str] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(_period_str(y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _approx_pay_day(company: Dict[str, Any]) -> int:
    occ = company.get("paie_occurrence")
    if occ is None:
        return DEFAULT_PAY_DAY
    try:
        occ_i = int(occ)
    except (TypeError, ValueError):
        return DEFAULT_PAY_DAY
    if occ_i == -1:
        return 28
    if occ_i == -2:
        return 27
    if 1 <= occ_i <= 28:
        return occ_i
    return DEFAULT_PAY_DAY


def _add_business_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def expected_last_period(
    company: Dict[str, Any],
    reference: Optional[date] = None,
) -> str:
    """Dernier mois de paie dont la DSN est attendue (YYYY-MM)."""
    ref = reference or date.today()
    pay_day = _approx_pay_day(company)
    try:
        pay_date = date(ref.year, ref.month, min(pay_day, monthrange(ref.year, ref.month)[1]))
    except ValueError:
        pay_date = date(ref.year, ref.month, DEFAULT_PAY_DAY)
    deadline = _add_business_days(pay_date, GRACE_DAYS_AFTER_PAYDAY)
    if ref >= deadline:
        return _period_str(ref.year, ref.month)
    prev_month = ref.month - 1
    prev_year = ref.year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    return _period_str(prev_year, prev_month)


def _batch_company_id(batch: Dict[str, Any], company: Dict[str, Any]) -> bool:
    summary = batch.get("summary") or {}
    report = summary.get("commit_report") or {}
    target = report.get("target_company_id")
    if target and str(target) == str(company.get("id")):
        return True
    companies_map = report.get("companies") or {}
    siret = (company.get("siret") or "").replace(" ", "")
    if siret and siret in companies_map:
        return True
    batch_siren = (batch.get("siren") or "").replace(" ", "")
    company_siren = (company.get("siren") or "").replace(" ", "")
    if batch_siren and company_siren and batch_siren == company_siren:
        if not target and not companies_map:
            return True
    return False


def _periods_from_batch(batch: Dict[str, Any]) -> Set[str]:
    summary = batch.get("summary") or {}
    periods: Set[str] = set()
    for key in ("periods_committed", "cumul_periods"):
        raw = summary.get(key)
        if isinstance(raw, list):
            periods.update(str(p) for p in raw if p)
    pmin = batch.get("period_min")
    pmax = batch.get("period_max") or pmin
    if pmin:
        start = _parse_period(str(pmin))
        end = _parse_period(str(pmax)) if pmax else start
        if start and end:
            periods.update(_month_range(start, end))
    return periods


def _gaps_in_year(months_covered: Set[str], year: int, through_period: str) -> List[str]:
    end = _parse_period(through_period)
    if not end:
        return []
    start = (year, 1)
    if end[0] != year:
        end = (year, 12)
    all_months = set(_month_range(start, end))
    return sorted(all_months - months_covered)


def compute_coverage(
    company: Dict[str, Any],
    batches: Optional[List[Dict[str, Any]]] = None,
    reference: Optional[date] = None,
    revoked_periods: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Calcule la couverture DSN pour une entreprise."""
    ref = reference or date.today()
    company_id = str(company.get("id") or "")
    sync_mode = (company.get("dsn_sync_mode") or "native").strip().lower()
    if sync_mode not in ("external", "native", "transition"):
        sync_mode = "native"

    if batches is None:
        batches = repo.list_committed_batches(limit=500)
    if revoked_periods is None:
        revoked_periods = repo.list_revoked_periods(company_id)
    revoked_set = set(revoked_periods or [])

    linked = [b for b in batches if b.get("status") == "committed" and _batch_company_id(b, company)]

    months_covered: Set[str] = set()
    batch_history: List[Dict[str, Any]] = []
    last_import_at: Optional[str] = None
    last_period: Optional[str] = None

    for batch in sorted(linked, key=lambda b: b.get("created_at") or ""):
        periods = _periods_from_batch(batch)
        months_covered.update(periods)
        created = batch.get("created_at")
        if created and (last_import_at is None or created > last_import_at):
            last_import_at = created
        if periods:
            batch_max = max(periods)
            if last_period is None or batch_max > last_period:
                last_period = batch_max
        batch_history.append(
            {
                "batch_id": str(batch.get("id")),
                "created_at": created,
                "period_min": batch.get("period_min"),
                "period_max": batch.get("period_max"),
                "import_mode": (batch.get("summary") or {}).get("import_mode"),
                "periods": sorted(periods),
            }
        )

    if revoked_set:
        months_covered -= revoked_set

    months_sorted = sorted(months_covered)
    expected = expected_last_period(company, ref)
    year = ref.year
    gaps = _gaps_in_year(months_covered, year, expected) if months_covered else []

    if sync_mode == "native" and not months_covered:
        status = "not_applicable"
    elif not months_covered:
        status = "never"
    elif expected in months_covered and not gaps:
        status = "ok"
    elif expected not in months_covered:
        exp_date = _parse_period(expected)
        if exp_date:
            exp_end = date(exp_date[0], exp_date[1], monthrange(exp_date[0], exp_date[1])[1])
            pay_day = _approx_pay_day(company)
            try:
                pay_date = date(exp_date[0], exp_date[1], min(pay_day, monthrange(exp_date[0], exp_date[1])[1]))
            except ValueError:
                pay_date = exp_end
            deadline = _add_business_days(pay_date, GRACE_DAYS_AFTER_PAYDAY)
            if ref < deadline:
                status = "late"
            else:
                status = "missing"
        else:
            status = "missing"
    elif gaps:
        status = "missing"
    else:
        status = "ok"

    timeline: List[Dict[str, Any]] = []
    for m in range(1, 13):
        period = _period_str(year, m)
        if m > ref.month and year == ref.year:
            state = "future"
        elif period in months_covered:
            state = "covered"
        elif period <= expected:
            state = "missing"
        else:
            state = "future"
        timeline.append({"period": period, "month": m, "state": state})

    alerts = _build_coverage_alerts(
        sync_mode=sync_mode,
        status=status,
        expected=expected,
        gaps=gaps,
        months_covered=months_sorted,
    )

    return {
        "company_id": company_id,
        "dsn_sync_mode": sync_mode,
        "status": status,
        "expected_last_period": expected,
        "last_period": last_period,
        "last_import_at": last_import_at,
        "months_covered": months_sorted,
        "gaps": gaps,
        "timeline": timeline,
        "batch_count": len(linked),
        "recent_batches": batch_history[-12:],
        "alerts": alerts,
    }


def _build_coverage_alerts(
    *,
    sync_mode: str,
    status: str,
    expected: str,
    gaps: List[str],
    months_covered: List[str],
) -> List[Dict[str, Any]]:
    if sync_mode == "native":
        return []
    alerts: List[Dict[str, Any]] = []
    if status == "never":
        alerts.append(
            {
                "code": "dsn_never_imported",
                "severity": "critical",
                "label": "Aucune DSN importée pour cette entreprise",
            }
        )
    elif gaps and months_covered:
        alerts.append(
            {
                "code": "dsn_onboarding_incomplete",
                "severity": "warning",
                "label": f"Trous dans la couverture DSN ({len(gaps)} mois manquant(s))",
                "gaps": gaps,
            }
        )
    elif status == "missing":
        alerts.append(
            {
                "code": "dsn_month_missing",
                "severity": "warning",
                "label": f"DSN de {expected} non importée",
                "expected_period": expected,
            }
        )
    elif status == "late":
        alerts.append(
            {
                "code": "dsn_month_late",
                "severity": "info",
                "label": f"DSN de {expected} en attente (délai de grâce)",
                "expected_period": expected,
            }
        )
    return alerts


def compute_admin_late_summary(
    companies: List[Dict[str, Any]],
    batches: Optional[List[Dict[str, Any]]] = None,
    revoked_by_company: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """Résumé admin : entreprises en retard DSN + statut par entreprise."""
    if batches is None:
        batches = repo.list_committed_batches(limit=500)
    if revoked_by_company is None:
        company_ids = [str(c.get("id")) for c in companies if c.get("id")]
        revoked_by_company = repo.list_revoked_periods_by_company(company_ids)
    late: List[Dict[str, Any]] = []
    all_companies: List[Dict[str, Any]] = []
    for company in companies:
        mode = (company.get("dsn_sync_mode") or "native").strip().lower()
        cid = str(company.get("id") or "")
        cov = compute_coverage(
            company,
            batches=batches,
            revoked_periods=revoked_by_company.get(cid, []),
        )
        all_companies.append(
            {
                "company_id": str(company.get("id")),
                "company_name": company.get("company_name"),
                "status": cov["status"],
                "dsn_sync_mode": mode,
            }
        )
        if mode not in DSN_SYNC_MODES_ALERTING:
            continue
        if cov["status"] in ("missing", "never", "late"):
            late.append(
                {
                    "company_id": str(company.get("id")),
                    "company_name": company.get("company_name"),
                    "status": cov["status"],
                    "expected_last_period": cov["expected_last_period"],
                    "last_period": cov["last_period"],
                    "gaps_count": len(cov["gaps"]),
                }
            )
    late.sort(key=lambda x: (x["status"] != "missing", x.get("expected_last_period") or ""))
    return {"late_count": len(late), "companies": late, "all_companies": all_companies}


def _reference_for_matrix_year(year: int) -> date:
    """Date de référence pour calculer couverture / timeline d'une année civile."""
    today = date.today()
    if year < today.year:
        return date(year, 12, 31)
    if year > today.year:
        return date(year, 1, 1)
    return today


def compute_admin_coverage_matrix(
    companies: List[Dict[str, Any]],
    *,
    year: int,
    batches: Optional[List[Dict[str, Any]]] = None,
    revoked_by_company: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """Matrice admin : couverture mois par mois pour toutes les entreprises."""
    if batches is None:
        batches = repo.list_committed_batches(limit=500)
    if revoked_by_company is None:
        company_ids = [str(c.get("id")) for c in companies if c.get("id")]
        revoked_by_company = repo.list_revoked_periods_by_company(company_ids)
    ref = _reference_for_matrix_year(year)
    rows: List[Dict[str, Any]] = []
    for company in companies:
        cid = str(company.get("id") or "")
        cov = compute_coverage(
            company,
            batches=batches,
            reference=ref,
            revoked_periods=revoked_by_company.get(cid, []),
        )
        status = cov["status"]
        if status == "not_applicable" and not cov.get("months_covered"):
            status = "missing"
        rows.append(
            {
                "company_id": str(company.get("id")),
                "company_name": company.get("company_name"),
                "group_name": company.get("group_name"),
                "siret": company.get("siret"),
                "dsn_sync_mode": cov["dsn_sync_mode"],
                "status": status,
                "expected_last_period": cov["expected_last_period"],
                "last_period": cov["last_period"],
                "last_import_at": cov["last_import_at"],
                "gaps_count": len(cov["gaps"]),
                "months_covered": cov["months_covered"],
                "timeline": cov["timeline"],
            }
        )
    rows.sort(key=lambda r: (r.get("group_name") or "", r.get("company_name") or ""))
    return {"year": year, "companies": rows}


def merge_dsn_alerts_into_overview(
    existing_alerts: List[Dict[str, Any]],
    coverage: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Fusionne les alertes DSN dans la liste overview (RH)."""
    out = list(existing_alerts)
    for alert in coverage.get("alerts") or []:
        code = alert.get("code")
        if code == "dsn_month_late":
            continue
        rh_alert = dict(alert)
        if code == "dsn_month_missing":
            period = alert.get("expected_period", "")
            rh_alert["label"] = (
                f"La DSN de {period} n'a pas encore été importée dans EYWAI. "
                "Vos cumuls de paie peuvent être incomplets. "
                "Contactez votre administrateur EYWAI."
            )
            rh_alert["action"] = "contact_admin"
        elif code == "dsn_never_imported":
            rh_alert["label"] = (
                "Aucune DSN n'a été importée pour cette entreprise. "
                "Contactez votre administrateur EYWAI pour initialiser le dossier paie."
            )
            rh_alert["action"] = "contact_admin"
        elif code == "dsn_onboarding_incomplete":
            rh_alert["action"] = "contact_admin"
        out.append(rh_alert)
    return out
