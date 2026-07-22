"""Réconciliation effectifs DSN ↔ base EYWAI (import mensuel)."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.modules.dsn_import.domain.employee_dsn_situation import (
    DsnSituation,
    DsnSituationSignals,
    classify_dsn_situation,
)
from app.modules.dsn_import.domain.normalize import nir_match_key
from app.modules.dsn_import.domain.user_messages import (
    _mask_nir,
    employee_dsn_situation_advisory,
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


def _period_start_date(period: Optional[str]) -> Optional[date]:
    if not period or "-" not in period:
        return None
    try:
        year_s, month_s = period.split("-", 1)
        year, month = int(year_s), int(month_s)
        return date(year, month, 1)
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


def _normalize_nir(nir: Optional[str]) -> str:
    """Clé de rapprochement NIR : réduit la base (15) et la DSN (13) au même repère."""
    return nir_match_key(nir)


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _employee_in_payroll_scope(
    employee: Dict[str, Any],
    period_start: Optional[date],
    period_end: Optional[date],
) -> bool:
    """Salarié susceptible d'apparaître dans la DSN du mois (embauché et pas encore parti)."""
    hire = _parse_iso_date(employee.get("hire_date"))
    end = _parse_iso_date(employee.get("contract_end_date"))
    if period_end and hire and hire > period_end:
        return False
    if period_start and end and end < period_start:
        return False
    return True


def _business_days_in_period(start: date, end: date) -> int:
    if end < start:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _absence_business_days_in_period(
    nir_items: List[Dict[str, Any]],
    period_start: date,
    period_end: date,
) -> int:
    """Jours ouvrés de la période couverts par un arrêt/suspension (items 'absence')."""
    covered: set[date] = set()
    for it in nir_items:
        if it.get("item_type") != "absence":
            continue
        payload = it.get("mapped_payload") or {}
        for raw in payload.get("selected_days") or []:
            d = _parse_iso_date(raw)
            if d and period_start <= d <= period_end and d.weekday() < 5:
                covered.add(d)
    return len(covered)


def _period_totals_for_nir(
    nir_items: List[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[float]]:
    """(brut, net_imposable) du mois depuis l'item 'cumul', s'il existe."""
    for it in nir_items:
        if it.get("item_type") != "cumul":
            continue
        totals = (it.get("mapped_payload") or {}).get("month_totals") or {}
        brut = totals.get("brut")
        net = totals.get("net_imposable")
        return (
            float(brut) if brut is not None else None,
            float(net) if net is not None else None,
        )
    return None, None


def _fin_contrat_signal(
    nir_items: List[Dict[str, Any]],
) -> Tuple[bool, Optional[date]]:
    """(has_fin_contrat, dernier jour ouvré) depuis l'item 'exit' (bloc DSN G62)."""
    for it in nir_items:
        if it.get("item_type") != "exit":
            continue
        payload = it.get("mapped_payload") or {}
        return True, _parse_iso_date(payload.get("last_working_day"))
    return False, None


def _build_situation_signals(
    nir_items: List[Dict[str, Any]],
    period_start: date,
    period_end: date,
) -> DsnSituationSignals:
    has_fin, fin_lwd = _fin_contrat_signal(nir_items)
    brut, net = _period_totals_for_nir(nir_items)
    return DsnSituationSignals(
        period_start=period_start,
        period_end=period_end,
        working_days_in_period=_business_days_in_period(period_start, period_end),
        present_in_dsn=True,
        has_fin_contrat=has_fin,
        fin_contrat_last_working_day=fin_lwd,
        exit_last_working_day=None,
        absence_days_in_period=_absence_business_days_in_period(
            nir_items, period_start, period_end
        ),
        period_brut=brut,
        period_net=net,
    )


def _build_advisories(
    *,
    active_by_nir: Dict[str, Dict[str, Any]],
    dsn_nirs: set,
    items_by_nir: Dict[str, List[Dict[str, Any]]],
    seen_employee_ids: set,
    period: Optional[str],
    period_start: Optional[date],
    period_end: Optional[date],
) -> List[Dict[str, Any]]:
    """Recommandations non bloquantes pour les salariés présents à la situation atypique.

    Couvre les catégories que les écarts effectifs ne traitent pas : absence prolongée
    et versement postérieur au départ. Les départs (absent de la DSN, fin de contrat)
    restent gérés par les écarts bloquants.
    """
    advisories: List[Dict[str, Any]] = []
    if not (period_start and period_end):
        return advisories
    for nir, employee in active_by_nir.items():
        if nir not in dsn_nirs:
            continue  # absent de la DSN -> déjà traité comme écart 'missing_from_dsn'
        employee_id = str(employee["id"])
        if employee_id in seen_employee_ids:
            continue  # déjà un écart bloquant (ex. fin de contrat)
        if not _employee_in_payroll_scope(employee, period_start, period_end):
            continue
        signals = _build_situation_signals(
            items_by_nir.get(nir, []), period_start, period_end
        )
        result = classify_dsn_situation(signals)
        if result.situation not in (
            DsnSituation.PROLONGED_ABSENCE,
            DsnSituation.POST_EXIT_PAYMENT,
        ):
            continue
        advisories.append(
            {
                "advisory_id": f"situation:{employee_id}",
                "employee_id": employee_id,
                "employee_name": _employee_display_name(employee),
                "nir_masked": _mask_nir((employee.get("nir") or "").strip()),
                "situation": result.situation.value,
                "recommendation": result.recommendation,
                "evidence": result.evidence,
                "period": period,
            }
        )
    return advisories


def _classify_missing_from_dsn_gap(
    employee: Dict[str, Any],
    period_start: Optional[date],
) -> Tuple[str, str]:
    """
    Retourne (gap_type, likely_scenario) pour un salarié absent de la DSN.
    """
    hire = _parse_iso_date(employee.get("hire_date"))
    if period_start and hire and hire >= period_start:
        return "new_hire_not_in_dsn", "new_hire"
    if hire:
        return "missing_from_dsn", "departure"
    return "missing_from_dsn", "unknown"


def _build_gap(
    *,
    gap_type: str,
    employee: Dict[str, Any],
    period: Optional[str] = None,
    contract_end_date: Optional[str] = None,
    suggested_last_working_day: Optional[str] = None,
    likely_scenario: Optional[str] = None,
    resolution: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    employee_id = str(employee["id"])
    if gap_type in ("missing_from_dsn", "new_hire_not_in_dsn"):
        gap_id = f"missing:{employee_id}"
    elif gap_type == "contract_end_in_dsn":
        gap_id = f"end:{employee_id}"
    else:
        gap_id = f"{gap_type.split('_')[0]}:{employee_id}"
    nir = (employee.get("nir") or "").strip()
    hire_raw = employee.get("hire_date")
    hire_iso = str(hire_raw)[:10] if hire_raw else None
    return {
        "gap_id": gap_id,
        "employee_id": employee_id,
        "employee_name": _employee_display_name(employee),
        "nir_masked": _mask_nir(nir),
        "gap_type": gap_type,
        "hire_date": hire_iso,
        "period": period,
        "likely_scenario": likely_scenario,
        "suggested_last_working_day": suggested_last_working_day,
        "contract_end_date": contract_end_date,
        "resolution": resolution,
    }


def _count_gaps_by_type(gaps: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "new_hire_not_in_dsn": 0,
        "missing_from_dsn": 0,
        "contract_end_in_dsn": 0,
    }
    for gap in gaps:
        gap_type = gap.get("gap_type")
        if gap_type in counts:
            counts[str(gap_type)] += 1
    return counts


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
        "excluded_out_of_scope_count": 0,
        "gap_counts_by_type": {
            "new_hire_not_in_dsn": 0,
            "missing_from_dsn": 0,
            "contract_end_in_dsn": 0,
        },
        "advisories": [],
    }
    if (import_mode or "").strip().lower() != "monthly" or not target_company_id:
        return disabled, []

    period = _resolve_period(summary)
    period_start = _period_start_date(period)
    period_end = _period_end_date(period)
    company_id = str(target_company_id)

    dsn_nirs: set[str] = set()
    dsn_nir_to_item: Dict[str, Dict[str, Any]] = {}
    items_by_nir: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        payload = it.get("mapped_payload") or {}
        nir = _normalize_nir(payload.get("nir"))
        if not nir:
            continue
        items_by_nir.setdefault(nir, []).append(it)
        if it.get("item_type") == "employee":
            dsn_nirs.add(nir)
            dsn_nir_to_item[nir] = it

    active_employees = repo.list_active_employees_with_nir(company_id)
    active_without_nir = repo.list_active_employees_without_nir(company_id)
    active_by_nir = {
        _normalize_nir(e.get("nir")): e
        for e in active_employees
        if _normalize_nir(e.get("nir"))
    }

    gaps: List[Dict[str, Any]] = []
    seen_employee_ids: set[str] = set()
    excluded_out_of_scope_count = 0

    for nir, employee in active_by_nir.items():
        if nir in dsn_nirs:
            continue
        employee_id = str(employee["id"])
        if employee_id in seen_employee_ids:
            continue
        if not _employee_in_payroll_scope(employee, period_start, period_end):
            excluded_out_of_scope_count += 1
            continue
        seen_employee_ids.add(employee_id)
        gap_type, likely_scenario = _classify_missing_from_dsn_gap(employee, period_start)
        resolution = stored_resolutions.get(f"missing:{employee_id}")
        suggested_lwd = None
        if gap_type == "missing_from_dsn" and period_end:
            suggested_lwd = period_end.isoformat()
        gaps.append(
            _build_gap(
                gap_type=gap_type,
                employee=employee,
                period=period,
                likely_scenario=likely_scenario,
                suggested_last_working_day=suggested_lwd,
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
                    period=period,
                    likely_scenario="departure",
                    contract_end_date=str(end_raw)[:10] if end_raw else end_date.isoformat(),
                    suggested_last_working_day=end_date.isoformat(),
                    resolution=resolution,
                )
            )

    advisories = _build_advisories(
        active_by_nir=active_by_nir,
        dsn_nirs=dsn_nirs,
        items_by_nir=items_by_nir,
        seen_employee_ids=seen_employee_ids,
        period=period,
        period_start=period_start,
        period_end=period_end,
    )

    resolved_count = sum(1 for g in gaps if g.get("resolution"))
    unresolved_count = len(gaps) - resolved_count
    gap_counts_by_type = _count_gaps_by_type(gaps)

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
        "excluded_out_of_scope_count": excluded_out_of_scope_count,
        "gap_counts_by_type": gap_counts_by_type,
        "advisories": advisories,
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
                gap_counts_by_type=gap_counts_by_type,
            )
        )
        for gap in gaps:
            anomalies.append(employee_workforce_gap_anomaly(gap=gap))

    for advisory in advisories:
        anomalies.append(employee_dsn_situation_advisory(advisory=advisory))

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


def workforce_blocks_commit(summary: Dict[str, Any]) -> bool:
    """True tant que des écarts effectifs mensuels n'ont pas de décision enregistrée."""
    wf = summary.get("workforce_reconciliation") or {}
    if not wf.get("enabled"):
        return False
    gaps = wf.get("gaps") or []
    if not gaps:
        return False
    stored = wf.get("resolutions") or {}
    for gap in gaps:
        gap_id = gap.get("gap_id")
        if not gap_id or gap_id not in stored:
            return True
    return False


def resolve_monthly_target_company_id(
    import_mode: str,
    target_company_id: Optional[str],
    summary: Dict[str, Any],
) -> Optional[str]:
    """Résout l'entreprise cible pour la réconciliation (mensuel)."""
    if target_company_id:
        return str(target_company_id)
    if (import_mode or "").strip().lower() != "monthly":
        return None
    siret = summary.get("siret")
    if not siret:
        sirets = summary.get("sirets") or []
        siret = sirets[0] if sirets else None
    if not siret:
        return None
    company = repo.find_company_by_siret(str(siret).replace(" ", ""))
    return str(company["id"]) if company else None


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
    valid_actions = {
        "open_exit",
        "close_departure",
        "ignore",
        "acknowledge_new_hire",
        "delete_permanently",
    }
    for gap in gaps:
        gap_id = gap.get("gap_id")
        res = by_gap_id.get(gap_id) or {}
        action = res.get("action")
        if action not in valid_actions:
            raise ValueError(f"Action invalide pour {gap.get('employee_name')}.")
        if action in ("ignore", "acknowledge_new_hire", "delete_permanently"):
            if action == "delete_permanently" and gap.get("gap_type") != "missing_from_dsn":
                raise ValueError(
                    f"La suppression définitive n'est pas autorisée pour {gap.get('employee_name')}."
                )
            continue
        if action in ("open_exit", "close_departure"):
            lwd = res.get("last_working_day") or gap.get("suggested_last_working_day")
            if not lwd:
                raise ValueError(
                    f"Date de dernier jour ouvré requise pour {gap.get('employee_name')}."
                )
