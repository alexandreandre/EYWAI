"""Réconciliation effectifs DSN ↔ base EYWAI (import mensuel)."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.user_messages import (
    _mask_nir,
    employee_workforce_gap_anomaly,
    workforce_reconciliation_summary_anomaly,
)
from app.modules.dsn_import.infrastructure import repository as repo


def _period_end_date(period: Optional[str]) -> Optional[date]:
    if not period or "-" not in period:
        return None
    try:
        year_s, month_s = period.split("-", 1)
        year, month = int(year_s), int(month_s)
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    except (ValueError, TypeError):
        return None


def _resolve_period(summary: Dict[str, Any]) -> Optional[str]:
    periods = summary.get("cumul_periods") or []
    if periods:
        return str(sorted(periods)[-1])
    for key in ("detected_period", "intended_period", "period_max", "expected_import_period"):
        val = summary.get(key)
        if val:
            return str(val)
    return None


def _employee_display_name(row: Dict[str, Any]) -> str:
    return f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "Salarié"


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _build_gap(
    *,
    gap_type: str,
    employee: Dict[str, Any],
    contract_end_date: Optional[str] = None,
    suggested_last_working_day: Optional[str] = None,
    resolution: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    employee_id = str(employee["id"])
    gap_id = f"{gap_type.split('_')[0]}:{employee_id}"
    if gap_type == "missing_from_dsn":
        gap_id = f"missing:{employee_id}"
    elif gap_type == "contract_end_in_dsn":
        gap_id = f"end:{employee_id}"
    nir = (employee.get("nir") or "").strip()
    return {
        "gap_id": gap_id,
        "employee_id": employee_id,
        "employee_name": _employee_display_name(employee),
        "nir_masked": _mask_nir(nir),
        "gap_type": gap_type,
        "suggested_last_working_day": suggested_last_working_day,
        "contract_end_date": contract_end_date,
        "resolution": resolution,
    }


def compute_workforce_gaps(
    items: List[Dict[str, Any]],
    *,
    target_company_id: Optional[str],
    import_mode: str,
    summary: Optional[Dict[str, Any]] = None,
    stored_resolutions: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Compare les salariés actifs en base aux individus de la DSN.

    Retourne (workforce_reconciliation summary, anomalies).
    """
    summary = summary or {}
    stored_resolutions = stored_resolutions or {}
    disabled: Dict[str, Any] = {
        "enabled": False,
        "company_id": target_company_id,
        "period": None,
        "gaps": [],
        "unresolved_count": 0,
        "resolved_count": 0,
        "active_without_nir_count": 0,
    }
    if (import_mode or "").strip().lower() != "monthly" or not target_company_id:
        return disabled, []

    period = _resolve_period(summary)
    period_end = _period_end_date(period)
    company_id = str(target_company_id)

    dsn_nirs: set[str] = set()
    dsn_nir_to_item: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if it.get("item_type") != "employee":
            continue
        payload = it.get("mapped_payload") or {}
        nir = (payload.get("nir") or "").strip()
        if nir:
            dsn_nirs.add(nir)
            dsn_nir_to_item[nir] = it

    active_employees = repo.list_active_employees_with_nir(company_id)
    active_without_nir = repo.list_active_employees_without_nir(company_id)
    active_by_nir = {
        (e.get("nir") or "").strip(): e for e in active_employees if (e.get("nir") or "").strip()
    }

    gaps: List[Dict[str, Any]] = []
    seen_employee_ids: set[str] = set()

    for nir, employee in active_by_nir.items():
        if nir not in dsn_nirs:
            employee_id = str(employee["id"])
            if employee_id in seen_employee_ids:
                continue
            seen_employee_ids.add(employee_id)
            resolution = stored_resolutions.get(f"missing:{employee_id}")
            gaps.append(
                _build_gap(
                    gap_type="missing_from_dsn",
                    employee=employee,
                    suggested_last_working_day=period_end.isoformat() if period_end else None,
                    resolution=resolution,
                )
            )

    if period_end:
        for nir, it in dsn_nir_to_item.items():
            if not it.get("is_existing"):
                continue
            employee = active_by_nir.get(nir)
            if not employee:
                existing_id = it.get("existing_employee_id")
                if existing_id:
                    employee = repo.find_employee_by_nir(company_id, nir)
            if not employee:
                continue
            employee_id = str(employee["id"])
            if employee_id in seen_employee_ids:
                continue
            payload = it.get("mapped_payload") or {}
            end_raw = payload.get("contract_end_date")
            end_date = _parse_iso_date(end_raw)
            if not end_date or end_date > period_end:
                continue
            seen_employee_ids.add(employee_id)
            resolution = stored_resolutions.get(f"end:{employee_id}")
            gaps.append(
                _build_gap(
                    gap_type="contract_end_in_dsn",
                    employee=employee,
                    contract_end_date=str(end_raw)[:10] if end_raw else end_date.isoformat(),
                    suggested_last_working_day=end_date.isoformat(),
                    resolution=resolution,
                )
            )

    resolved_count = sum(1 for g in gaps if g.get("resolution"))
    unresolved_count = len(gaps) - resolved_count

    workforce_summary: Dict[str, Any] = {
        "enabled": True,
        "company_id": company_id,
        "period": period,
        "gaps": gaps,
        "unresolved_count": unresolved_count,
        "resolved_count": resolved_count,
        "active_without_nir_count": len(active_without_nir),
        "dsn_employee_count": len(dsn_nirs),
        "active_db_count": len(active_employees),
    }

    anomalies: List[Dict[str, Any]] = []
    if gaps:
        company = repo.find_company_by_id(company_id) or {}
        company_name = (
            company.get("company_name") or company.get("raison_sociale") or "l'entreprise"
        )
        anomalies.append(
            workforce_reconciliation_summary_anomaly(
                company_name=company_name,
                gap_count=len(gaps),
                period=period,
            )
        )
        for gap in gaps:
            anomalies.append(employee_workforce_gap_anomaly(gap=gap))

    if active_without_nir:
        anomalies.append(
            {
                "code": "workforce_active_without_nir",
                "type": "workforce_active_without_nir",
                "message": (
                    f"{len(active_without_nir)} salarié(s) actif(s) sans NIR — "
                    "hors comparaison automatique avec la DSN."
                ),
                "hint": "Complétez le NIR sur la fiche salarié pour une réconciliation fiable.",
                "severity": "warning",
                "meta": {"count": len(active_without_nir)},
            }
        )

    return workforce_summary, anomalies


def attach_workforce_reconciliation(
    items: List[Dict[str, Any]],
    summary: Dict[str, Any],
    anomalies: List[Dict[str, Any]],
    *,
    target_company_id: Optional[str],
    import_mode: str,
) -> None:
    """Calcule et attache workforce_reconciliation au summary ; ajoute les anomalies."""
    stored = (summary.get("workforce_reconciliation") or {}).get("resolutions") or {}
    wf_summary, wf_anomalies = compute_workforce_gaps(
        items,
        target_company_id=target_company_id,
        import_mode=import_mode,
        summary=summary,
        stored_resolutions=stored,
    )
    # Réappliquer les résolutions stockées sur les gaps recalculés
    gaps = wf_summary.get("gaps") or []
    for gap in gaps:
        gap_id = gap.get("gap_id")
        if gap_id and gap_id in stored:
            gap["resolution"] = stored[gap_id]
    resolved_count = sum(1 for g in gaps if g.get("resolution"))
    wf_summary["resolved_count"] = resolved_count
    wf_summary["unresolved_count"] = len(gaps) - resolved_count
    wf_summary["resolutions"] = stored
    summary["workforce_reconciliation"] = wf_summary
    anomalies.extend(wf_anomalies)


def validate_workforce_resolutions_for_commit(
    summary: Dict[str, Any],
    resolutions: List[Dict[str, Any]],
) -> None:
    """Lève ValueError si des écarts mensuels ne sont pas tous résolus."""
    wf = summary.get("workforce_reconciliation") or {}
    if not wf.get("enabled"):
        return
    gaps = wf.get("gaps") or []
    if not gaps:
        return
    by_gap_id = {str(r.get("gap_id")): r for r in resolutions if r.get("gap_id")}
    missing = [g for g in gaps if not by_gap_id.get(g.get("gap_id"))]
    if missing:
        names = ", ".join(g.get("employee_name", "?") for g in missing[:3])
        extra = f" (+{len(missing) - 3})" if len(missing) > 3 else ""
        raise ValueError(
            f"Réconciliation effectifs incomplète : décision requise pour {len(missing)} "
            f"salarié(s) ({names}{extra})."
        )
    valid_actions = {"open_exit", "close_departure", "ignore"}
    for gap in gaps:
        gap_id = gap.get("gap_id")
        res = by_gap_id.get(gap_id) or {}
        action = res.get("action")
        if action not in valid_actions:
            raise ValueError(f"Action invalide pour {gap.get('employee_name')}.")
        if action == "ignore":
            continue
        if action in ("open_exit", "close_departure"):
            lwd = res.get("last_working_day") or gap.get("suggested_last_working_day")
            if not lwd:
                raise ValueError(
                    f"Date de dernier jour ouvré requise pour {gap.get('employee_name')}."
                )
