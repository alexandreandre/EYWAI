"""Application du montant IJSS validé sur le bulletin (regénération ciblée)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.ijss_tracking.infrastructure import repository as repo

logger = get_logger("modules.ijss_tracking.apply")


def _resolve_brut_amount(
    expected: Dict[str, Any],
    period_id: str,
    manual_amount: Optional[float],
    manual_source: Optional[str],
) -> tuple[float, str]:
    """CPAM matched > banque matched > montant manuel > déjà validé."""
    if manual_amount is not None and manual_amount >= 0:
        return round(float(manual_amount), 2), manual_source or "manual"

    existing = expected.get("ijss_brut_validated")
    if existing is not None and float(existing) >= 0:
        return round(float(existing), 2), str(
            expected.get("validation_source") or "manual"
        )

    received = repo.list_received_lines(period_id)
    emp_id = str(expected.get("employee_id") or "")
    cpam = sum(
        float(line.get("amount") or 0)
        for line in received
        if str(line.get("employee_id") or "") == emp_id
        and line.get("source") == "cpam_decompte"
        and line.get("match_status") == "matched"
    )
    if cpam > 0:
        return round(cpam, 2), "cpam_decompte"

    bank = sum(
        float(line.get("amount") or 0)
        for line in received
        if str(line.get("employee_id") or "") == emp_id
        and line.get("source") == "bank_transfer"
        and line.get("match_status") == "matched"
    )
    if bank > 0:
        return round(bank, 2), "bank_transfer"

    raise ValueError(
        "Aucun montant CPAM/banque rapproché — saisissez un montant brut manuellement."
    )


def validate_expected_line_brut(
    company_id: str,
    expected_line_id: str,
    user_id: str,
    amount: Optional[float] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    expected = repo.get_expected_line(company_id, expected_line_id)
    if not expected:
        raise LookupError("Ligne attendue introuvable.")
    period = repo.get_period(company_id, str(expected["period_id"]))
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    brut, validation_source = _resolve_brut_amount(
        expected, str(period["id"]), amount, source
    )
    now = datetime.now(timezone.utc).isoformat()
    updated = repo.update_expected_line(
        expected_line_id,
        {
            "ijss_brut_validated": brut,
            "validation_source": validation_source,
            "validated_at": now,
            "validated_by": user_id,
        },
    )
    from app.modules.ijss_tracking.application.service import _recompute_period

    _recompute_period(period)
    return updated or expected


def apply_validated_ijss_to_payslip(
    company_id: str,
    expected_line_id: str,
    user_id: str,
) -> Dict[str, Any]:
    expected = repo.get_expected_line(company_id, expected_line_id)
    if not expected:
        raise LookupError("Ligne attendue introuvable.")
    period = repo.get_period(company_id, str(expected["period_id"]))
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    brut = expected.get("ijss_brut_validated")
    if brut is None:
        raise ValueError("Validez d'abord le montant brut CPAM pour cette ligne.")

    brut_f = round(float(brut), 2)
    employee_id = str(expected.get("employee_id") or "")
    year = int(period["period_year"])
    month = int(period["period_month"])

    emp_res = (
        get_supabase_admin_client()
        .table("employees")
        .select("statut, is_forfait_jour")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    emp = emp_res.data or {}
    statut = emp.get("statut") or ""
    from app.shared.domain.employment_rules import is_forfait_jour

    ijss_tracking_meta = {
        "expected_line_id": expected_line_id,
        "brut_validated": brut_f,
        "brut_theorique": float(expected.get("ijss_theorique") or 0),
        "source": expected.get("validation_source") or "manual",
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "applied_by": user_id,
    }

    if is_forfait_jour(statut, emp.get("is_forfait_jour")):
        from app.modules.payroll.documents.payslip_generator_forfait import (
            process_payslip_generation_forfait,
        )

        result = process_payslip_generation_forfait(
            employee_id,
            year,
            month,
            ijss_brut_override=brut_f,
            ijss_tracking_meta=ijss_tracking_meta,
        )
    else:
        from app.modules.payroll.documents.payslip_generator import (
            process_payslip_generation,
        )

        result = process_payslip_generation(
            employee_id,
            year,
            month,
            ijss_brut_override=brut_f,
            ijss_tracking_meta=ijss_tracking_meta,
        )

    payslip_id = result.get("payslip_id") if isinstance(result, dict) else None
    now = datetime.now(timezone.utc).isoformat()
    repo.update_expected_line(
        expected_line_id,
        {
            "applied_to_payslip_at": now,
            "applied_ijss_brut": brut_f,
            "payslip_id": payslip_id or expected.get("payslip_id"),
        },
    )
    from app.modules.ijss_tracking.application.service import _recompute_period

    _recompute_period(period)
    return {
        "expected_line_id": expected_line_id,
        "applied_ijss_brut": brut_f,
        "payslip_id": payslip_id,
        "employee_id": employee_id,
    }


def apply_all_validated_for_period(
    company_id: str, period_id: str, user_id: str
) -> Dict[str, Any]:
    period = repo.get_period(company_id, period_id)
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    applied: list[Dict[str, Any]] = []
    errors: list[str] = []
    for exp in repo.list_expected_lines(period_id):
        if exp.get("ijss_brut_validated") is None:
            continue
        if exp.get("applied_to_payslip_at"):
            continue
        st = exp.get("line_status") or "pending"
        if st not in ("ok", "justified", "partial"):
            continue
        try:
            applied.append(
                apply_validated_ijss_to_payslip(
                    company_id, str(exp["id"]), user_id
                )
            )
        except Exception as exc:
            errors.append(f"{exp.get('employee_id')}: {exc}")

    return {"applied_count": len(applied), "applied": applied, "errors": errors}
