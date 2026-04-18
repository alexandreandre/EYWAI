"""
Cas d'usage comparaison N vs N-1, tendance, acquittements, validation.
"""

from __future__ import annotations

from typing import Any

from app.modules.payslips.application.dto import (
    PayslipBadRequestError,
    PayslipCriticalActiveError,
    PayslipForbiddenError,
    PayslipNotFoundError,
    UserContext,
)
from app.modules.payslips.application.queries import get_payslip_details
from app.modules.payslips.domain.comparison_engine import (
    _extract_values,
    compute_comparison,
    comparison_result_to_dict,
)
from app.modules.payslips.domain.rules import (
    can_edit_or_restore_payslip,
    can_view_payslip,
    is_forfait_jour,
)
from app.modules.payslips.infrastructure.comparison_queries import (
    fetch_employee_statut,
    fetch_previous_validated_payslip,
    fetch_recent_nets_asc_for_r10,
    fetch_validated_payslips_strictly_before,
    mark_payslip_validated,
    update_payslip_data_alerts_status,
)
from app.modules.payslips.infrastructure.readers import payslip_meta_reader


def _ensure_view_detail(detail: dict[str, Any] | None, ctx: UserContext) -> dict[str, Any]:
    if not detail:
        raise PayslipNotFoundError("Bulletin non trouvé")
    if detail.get("employee_id") != ctx.user_id and not detail.get("company_id"):
        raise PayslipBadRequestError("Bulletin sans entreprise associée")
    if not can_view_payslip(
        detail,
        ctx.user_id,
        ctx.is_super_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Accès refusé: vous n'avez pas les permissions pour consulter ce bulletin"
        )
    return detail


def _ensure_edit_meta(meta: dict[str, Any] | None, ctx: UserContext) -> dict[str, Any]:
    if not meta:
        raise PayslipNotFoundError("Bulletin non trouvé")
    company_id = meta.get("company_id")
    if not company_id:
        raise PayslipBadRequestError("Bulletin sans entreprise associée")
    if not can_edit_or_restore_payslip(
        meta,
        ctx.is_super_admin,
        ctx.has_rh_access_in_company,
        ctx.active_company_id,
    ):
        raise PayslipForbiddenError(
            "Vous n'avez pas les permissions pour cette action sur les bulletins"
        )
    return meta


def _extract_totals(payslip_data: dict[str, Any]) -> dict[str, float]:
    v = _extract_values(payslip_data)
    return {
        "salaire_brut": v["salaire_brut"],
        "net_a_payer": v["net_a_payer"],
        "total_cotisations": v["total_cotisations_salariales"],
    }


def get_payslip_comparison_for_user(payslip_id: str, ctx: UserContext) -> dict[str, Any]:
    detail = _ensure_view_detail(get_payslip_details(payslip_id), ctx)
    emp_id = str(detail["employee_id"])
    comp_id = str(detail["company_id"])
    year = int(detail["year"])
    month = int(detail["month"])
    pd = detail.get("payslip_data") or {}
    if not isinstance(pd, dict):
        pd = {}

    prev = fetch_previous_validated_payslip(emp_id, comp_id, year, month)
    prev_data = None
    if prev and isinstance(prev.get("payslip_data"), dict):
        prev_data = prev["payslip_data"]

    statut = fetch_employee_statut(emp_id)
    recent_nets = fetch_recent_nets_asc_for_r10(emp_id, comp_id, year, month, pd)

    ctx_engine: dict[str, Any] = {
        "bulletin_n_id": payslip_id,
        "month_n": month,
        "year_n": year,
        "bulletin_n1_id": str(prev["id"]) if prev else None,
        "month_n1": int(prev["month"]) if prev else None,
        "year_n1": int(prev["year"]) if prev else None,
        "is_forfait_jour": is_forfait_jour(statut),
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": recent_nets,
    }

    result = compute_comparison(pd, prev_data, ctx_engine)
    return comparison_result_to_dict(result)


def get_payslip_trend_for_user(payslip_id: str, ctx: UserContext) -> dict[str, Any]:
    detail = _ensure_view_detail(get_payslip_details(payslip_id), ctx)
    emp_id = str(detail["employee_id"])
    comp_id = str(detail["company_id"])
    year = int(detail["year"])
    month = int(detail["month"])

    rows = fetch_validated_payslips_strictly_before(emp_id, comp_id, year, month, limit=12)
    asc_rows = list(reversed(rows))

    months_out: list[dict[str, Any]] = []
    prev_pd: dict[str, Any] | None = None
    prev_id: str | None = None
    prev_my: tuple[int, int] | None = None
    fj = is_forfait_jour(fetch_employee_statut(emp_id))

    for row in asc_rows:
        pid = str(row["id"])
        y = int(row["year"])
        m = int(row["month"])
        pdata = row.get("payslip_data") or {}
        if not isinstance(pdata, dict):
            pdata = {}
        totals = _extract_totals(pdata)
        alerts_dicts: list[dict[str, Any]] = []
        if prev_pd is not None and prev_id is not None and prev_my is not None:
            ctx_engine = {
                "bulletin_n_id": pid,
                "month_n": m,
                "year_n": y,
                "bulletin_n1_id": prev_id,
                "month_n1": prev_my[1],
                "year_n1": prev_my[0],
                "is_forfait_jour": fj,
                "has_contract_change": False,
                "has_declared_advance": None,
                "recent_nets_asc": [],
            }
            comp = compute_comparison(pdata, prev_pd, ctx_engine)
            alerts_dicts = comparison_result_to_dict(comp)["alerts"]

        months_out.append(
            {
                "month": m,
                "year": y,
                "payslip_id": pid,
                "salaire_brut": totals["salaire_brut"],
                "net_a_payer": totals["net_a_payer"],
                "total_cotisations": totals["total_cotisations"],
                "alerts": alerts_dicts,
            }
        )
        prev_pd = pdata
        prev_id = pid
        prev_my = (y, m)

    return {"employee_id": emp_id, "months": months_out}


def acquit_payslip_alert_for_user(
    payslip_id: str,
    rule_id: str,
    ctx: UserContext,
    comment: str | None,
) -> dict[str, Any]:
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    _ensure_edit_meta(meta, ctx)
    return update_payslip_data_alerts_status(
        payslip_id, rule_id, "acquittee", ctx.user_id, comment
    )


def ignore_payslip_alert_for_user(
    payslip_id: str,
    rule_id: str,
    ctx: UserContext,
    comment: str | None,
) -> dict[str, Any]:
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    _ensure_edit_meta(meta, ctx)
    return update_payslip_data_alerts_status(
        payslip_id, rule_id, "ignoree", ctx.user_id, comment
    )


def validate_payslip_for_user(payslip_id: str, ctx: UserContext) -> None:
    meta = payslip_meta_reader.get_payslip_meta(payslip_id)
    _ensure_edit_meta(meta, ctx)
    detail = get_payslip_details(payslip_id)
    if not detail:
        raise PayslipNotFoundError("Bulletin non trouvé")
    emp_id = str(detail["employee_id"])
    comp_id = str(detail["company_id"])
    year = int(detail["year"])
    month = int(detail["month"])
    pd = detail.get("payslip_data") or {}
    if not isinstance(pd, dict):
        pd = {}

    prev = fetch_previous_validated_payslip(emp_id, comp_id, year, month)
    prev_data = None
    if prev and isinstance(prev.get("payslip_data"), dict):
        prev_data = prev["payslip_data"]

    statut = fetch_employee_statut(emp_id)
    recent_nets = fetch_recent_nets_asc_for_r10(emp_id, comp_id, year, month, pd)

    ctx_engine: dict[str, Any] = {
        "bulletin_n_id": payslip_id,
        "month_n": month,
        "year_n": year,
        "bulletin_n1_id": str(prev["id"]) if prev else None,
        "month_n1": int(prev["month"]) if prev else None,
        "year_n1": int(prev["year"]) if prev else None,
        "is_forfait_jour": is_forfait_jour(statut),
        "has_contract_change": False,
        "has_declared_advance": None,
        "recent_nets_asc": recent_nets,
    }
    result = compute_comparison(pd, prev_data, ctx_engine)
    active_crit = [
        {
            "rule_id": a.rule_id,
            "message": a.message,
            "field": a.field,
        }
        for a in result.alerts
        if a.level == "CRITIQUE" and a.status == "active"
    ]
    if active_crit:
        raise PayslipCriticalActiveError(active_crit)

    mark_payslip_validated(payslip_id, ctx.user_id)
