"""Service applicatif suivi IJSS."""

from __future__ import annotations

import calendar as cal_mod
import hashlib
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.ijss_tracking.domain.enums import IJSS_ELIGIBLE_ABSENCE_TYPES
from app.modules.ijss_tracking.domain.reconciliation import (
    aggregate_line_status,
    aggregate_period_status,
    match_received_to_employee,
)
from app.modules.ijss_tracking.infrastructure import repository as repo
from app.modules.ijss_tracking.infrastructure.parsers.bank_recap_parser import (
    parse_bank_recap_file,
)
from app.modules.ijss_tracking.infrastructure.parsers.cpam_decompte_parser import (
    parse_cpam_decompte_file,
)
from app.shared.utils.export import generate_xlsx

logger = get_logger("modules.ijss_tracking.service")


def _parse_day(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value[:10])
    return None


def _period_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = cal_mod.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _absence_overlaps_month(absence: Dict[str, Any], year: int, month: int) -> bool:
    start, end = _period_bounds(year, month)
    for raw in absence.get("selected_days") or []:
        d = _parse_day(raw)
        if d and start <= d <= end:
            return True
    return False


def _pick_absence_for_period(
    absences: List[Dict[str, Any]], year: int, month: int
) -> Optional[Dict[str, Any]]:
    overlapping = [a for a in absences if _absence_overlaps_month(a, year, month)]
    if not overlapping:
        return None
    overlapping.sort(
        key=lambda a: min(
            _parse_day(d) or date(9999, 12, 31) for d in (a.get("selected_days") or [])
        )
    )
    return overlapping[0]


def _fetch_employees(company_id: str) -> List[Dict[str, Any]]:
    resp = (
        get_supabase_admin_client()
        .table("employees")
        .select("id, first_name, last_name, nir")
        .eq("company_id", company_id)
        .execute()
    )
    return resp.data or []


def _sum_received_for_employee(
    received_lines: List[Dict[str, Any]], employee_id: str, source: str
) -> float:
    total = 0.0
    for line in received_lines:
        if str(line.get("employee_id") or "") != employee_id:
            continue
        if line.get("source") != source:
            continue
        if line.get("match_status") == "matched":
            total += float(line.get("amount") or 0)
    return round(total, 2)


def _recompute_period(period: Dict[str, Any]) -> Dict[str, Any]:
    period_id = str(period["id"])
    expected = repo.list_expected_lines(period_id)
    received = repo.list_received_lines(period_id)
    threshold = float(period.get("variance_threshold") or 1.0)
    line_statuses: List[str] = []
    expected_total = 0.0

    for exp in expected:
        emp_id = str(exp.get("employee_id") or "")
        exp_amt = float(exp.get("ijss_subrogees_bulletin") or exp.get("ijss_theorique") or 0)
        expected_total += exp_amt
        cpam = _sum_received_for_employee(received, emp_id, "cpam_decompte")
        bank = _sum_received_for_employee(received, emp_id, "bank_transfer")
        notes = repo.list_notes_for_expected(str(exp["id"]))
        status = aggregate_line_status(
            expected_amount=exp_amt,
            cpam_amount=cpam,
            bank_amount=bank,
            threshold=threshold,
            has_justification=bool(notes),
        )
        line_statuses.append(status)
        get_supabase_admin_client().table("ijss_expected_lines").update(
            {"line_status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", exp["id"]).execute()

    cpam_total = round(
        sum(float(l.get("amount") or 0) for l in received if l.get("source") == "cpam_decompte"),
        2,
    )
    bank_total = round(
        sum(float(l.get("amount") or 0) for l in received if l.get("source") == "bank_transfer"),
        2,
    )
    variance = round(expected_total - cpam_total, 2)
    period_status = aggregate_period_status(line_statuses) if line_statuses else "open"

    updated = repo.update_period(
        period_id,
        {
            "expected_total": round(expected_total, 2),
            "received_cpam_total": cpam_total,
            "received_bank_total": bank_total,
            "variance_total": variance,
            "status": period_status,
        },
    )
    return updated or period


def get_period_dashboard(
    company_id: str, year: int, month: int
) -> Dict[str, Any]:
    period = repo.get_or_create_period(company_id, year, month)
    if not period:
        raise RuntimeError("Impossible de créer la période IJSS.")
    period = _recompute_period(period)
    expected = repo.list_expected_lines(str(period["id"]))
    received = repo.list_received_lines(str(period["id"]))
    employees = _fetch_employees(company_id)
    emp_map = {str(e["id"]): e for e in employees}

    rows: List[Dict[str, Any]] = []
    counts = {"ok": 0, "variance": 0, "pending": 0}

    for exp in expected:
        emp_id = str(exp.get("employee_id") or "")
        emp = emp_map.get(emp_id, {})
        cpam = _sum_received_for_employee(received, emp_id, "cpam_decompte")
        bank = _sum_received_for_employee(received, emp_id, "bank_transfer")
        st = exp.get("line_status") or "pending"
        if st in ("ok", "justified"):
            counts["ok"] += 1
        elif st in ("variance", "partial"):
            counts["variance"] += 1
        else:
            counts["pending"] += 1
        rows.append(
            {
                "expected_line_id": exp.get("id"),
                "employee_id": emp_id,
                "employee_name": f"{emp.get('last_name', '')} {emp.get('first_name', '')}".strip(),
                "absence_request_id": exp.get("absence_request_id"),
                "ijss_theorique": float(exp.get("ijss_theorique") or 0),
                "ijss_subrogees_bulletin": float(exp.get("ijss_subrogees_bulletin") or 0),
                "ijss_brut_validated": float(exp["ijss_brut_validated"])
                if exp.get("ijss_brut_validated") is not None
                else None,
                "validation_source": exp.get("validation_source"),
                "applied_to_payslip_at": exp.get("applied_to_payslip_at"),
                "applied_ijss_brut": float(exp["applied_ijss_brut"])
                if exp.get("applied_ijss_brut") is not None
                else None,
                "received_cpam": cpam,
                "received_bank": bank,
                "line_status": st,
                "subrogation_active": bool(exp.get("subrogation_active")),
            }
        )

    rows.sort(key=lambda r: (0 if r["line_status"] in ("variance", "partial") else 1, r["employee_name"]))

    unmatched_received: List[Dict[str, Any]] = []
    for line in received:
        match_status = line.get("match_status") or "unmatched"
        if match_status == "matched" and line.get("employee_id"):
            continue
        unmatched_received.append(
            {
                "id": str(line.get("id") or ""),
                "source": str(line.get("source") or ""),
                "amount": float(line.get("amount") or 0),
                "employee_name_raw": line.get("employee_name_raw"),
                "employee_nir": line.get("employee_nir"),
                "payment_date": line.get("payment_date"),
            }
        )
    unmatched_received.sort(key=lambda u: (-u["amount"], u.get("employee_name_raw") or ""))

    return {
        "period": period,
        "summary": counts,
        "rows": rows,
        "unmatched_received": unmatched_received,
    }


def sync_expected_lines(company_id: str, period_id: str) -> Dict[str, Any]:
    period = repo.get_period(company_id, period_id)
    if not period:
        raise LookupError("Période introuvable.")
    if period.get("status") == "closed":
        raise ValueError("Période clôturée — resynchronisation impossible.")

    year = int(period["period_year"])
    month = int(period["period_month"])
    client = get_supabase_admin_client()

    payslips = (
        client.table("payslips")
        .select("id, employee_id, payslip_data, year, month")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .execute()
    ).data or []

    created = 0
    for ps in payslips:
        pdata = ps.get("payslip_data") or {}
        sn = pdata.get("synthese_net") or {}
        ijss = float(sn.get("ijss_subrogees") or 0)
        if ijss <= 0 and not sn.get("subrogation_active"):
            continue
        bloc = pdata.get("bloc_maintien") or {}
        ijss_block = bloc.get("ijss") or {}
        ijss_theo = float(ijss_block.get("ijss_theorique") or ijss)
        nb_jours = int(ijss_block.get("nb_jours_indemnises") or 0)

        absences = (
            client.table("absence_requests")
            .select("id, subrogation_active, selected_days")
            .eq("employee_id", ps["employee_id"])
            .eq("status", "validated")
            .in_("type", list(IJSS_ELIGIBLE_ABSENCE_TYPES))
            .execute()
        ).data or []
        matched_absence = _pick_absence_for_period(absences, year, month)
        absence_id = matched_absence["id"] if matched_absence else None
        subrogation = bool(
            sn.get("subrogation_active")
            if sn.get("subrogation_active") is not None
            else (
                matched_absence.get("subrogation_active")
                if matched_absence
                else True
            )
        )

        repo.upsert_expected_line(
            {
                "company_id": company_id,
                "period_id": period_id,
                "employee_id": ps["employee_id"],
                "absence_request_id": absence_id,
                "payslip_id": ps.get("id"),
                "period_year": year,
                "period_month": month,
                "ijss_theorique": ijss_theo,
                "ijss_subrogees_bulletin": ijss,
                "nb_jours_indemnises": nb_jours,
                "subrogation_active": subrogation,
                "calculation_snapshot": {"bloc_maintien": bloc, "synthese_net": sn},
            }
        )
        created += 1

    period = _recompute_period(period)
    return {"synced_count": created, "period": period}


def close_period(company_id: str, period_id: str, user_id: str) -> Dict[str, Any]:
    period = repo.get_period(company_id, period_id)
    if not period:
        raise LookupError("Période introuvable.")
    period = _recompute_period(period)
    expected = repo.list_expected_lines(period_id)
    open_variances = [
        e for e in expected if e.get("line_status") in ("variance", "partial", "pending")
    ]
    if open_variances:
        raise ValueError(
            f"{len(open_variances)} ligne(s) avec écart ou en attente — justifiez ou rapprochez avant clôture."
        )
    updated = repo.update_period(
        period_id,
        {
            "status": "closed",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "closed_by": user_id,
        },
    )
    return {"period": updated, "message": "Période clôturée."}


def match_received_line_manual(
    company_id: str,
    line_id: str,
    employee_id: str,
    expected_line_id: Optional[str] = None,
) -> Dict[str, Any]:
    line = repo.get_received_line(company_id, line_id)
    if not line:
        raise LookupError("Ligne reçue introuvable.")
    fields: Dict[str, Any] = {
        "employee_id": employee_id,
        "match_confidence": "manual",
        "match_status": "matched",
    }
    if expected_line_id:
        fields["expected_line_id"] = expected_line_id
    updated = repo.update_received_line(line_id, fields)
    period_id = line.get("period_id")
    if period_id:
        period = repo.get_period(company_id, str(period_id))
        if period:
            _recompute_period(period)
    return {"line": updated}


def justify_variance(
    company_id: str,
    expected_line_id: str,
    content: str,
    user_id: str,
    received_line_id: Optional[str] = None,
) -> Dict[str, Any]:
    note_id = repo.insert_note(
        {
            "company_id": company_id,
            "expected_line_id": expected_line_id,
            "received_line_id": received_line_id,
            "note_type": "justification",
            "content": content,
            "created_by": user_id,
        }
    )
    client = get_supabase_admin_client()
    exp_resp = (
        client.table("ijss_expected_lines")
        .select("period_id, company_id")
        .eq("id", expected_line_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if exp_resp.data:
        period = repo.get_period(company_id, str(exp_resp.data[0]["period_id"]))
        if period:
            _recompute_period(period)
    return {"note_id": note_id, "message": "Écart justifié."}


def get_absence_ijss_status(company_id: str, absence_id: str) -> Dict[str, Any]:
    client = get_supabase_admin_client()
    exp = (
        client.table("ijss_expected_lines")
        .select("*")
        .eq("company_id", company_id)
        .eq("absence_request_id", absence_id)
        .order("period_year", desc=True)
        .order("period_month", desc=True)
        .limit(1)
        .execute()
    )
    if not exp.data:
        return {"status": "pending", "absence_request_id": absence_id}
    line = exp.data[0]
    brut_val = line.get("ijss_brut_validated")
    applied_brut = line.get("applied_ijss_brut")
    return {
        "status": line.get("line_status") or "pending",
        "absence_request_id": absence_id,
        "expected_line_id": line.get("id"),
        "ijss_subrogees_bulletin": float(line.get("ijss_subrogees_bulletin") or 0),
        "ijss_brut_validated": float(brut_val) if brut_val is not None else None,
        "applied_to_payslip_at": line.get("applied_to_payslip_at"),
        "applied_ijss_brut": float(applied_brut) if applied_brut is not None else None,
    }


def parse_import_file(
    company_id: str,
    period_id: str,
    batch_type: str,
    filename: str,
    content: bytes,
    user_id: str,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    file_hash = hashlib.sha256(content).hexdigest()
    if repo.batch_exists_by_hash(company_id, file_hash):
        raise ValueError("Ce fichier a déjà été importé (hash identique).")

    if batch_type == "bank_recap":
        parsed = parse_bank_recap_file(filename, content, column_mapping)
        source = "bank_transfer"
    elif batch_type == "cpam_decompte_file":
        parsed = parse_cpam_decompte_file(filename, content, column_mapping)
        source = "cpam_decompte"
    else:
        raise ValueError(f"Type d'import non supporté : {batch_type}")

    batch_id = repo.insert_batch(
        {
            "company_id": company_id,
            "period_id": period_id,
            "batch_type": batch_type,
            "status": "previewed",
            "file_name": filename,
            "file_hash": file_hash,
            "summary": {"line_count": parsed["line_count"]},
            "preview": parsed,
            "uploaded_by": user_id,
        }
    )
    if not batch_id:
        raise RuntimeError("Création du batch import échouée.")

    period = repo.get_period(company_id, period_id)
    if not period:
        raise LookupError("Période introuvable.")
    employees = _fetch_employees(company_id)
    expected = repo.list_expected_lines(period_id)

    items: List[Dict[str, Any]] = []
    for line in parsed["lines"]:
        match = match_received_to_employee(
            employee_name_raw=line.get("employee_name_raw") or "",
            employee_nir=line.get("employee_nir"),
            amount=float(line.get("amount") or 0),
            employees=employees,
            expected_lines=expected,
        )
        mapped = {**line, "source": source}
        if match:
            mapped["employee_id"] = match.employee_id
            mapped["match_confidence"] = match.confidence
            mapped["match_reason"] = match.reason
        items.append(
            {
                "batch_id": batch_id,
                "row_index": line["row_index"],
                "raw_payload": line.get("raw") or {},
                "mapped_payload": mapped,
                "match_status": "matched" if match else "unmatched",
                "employee_id": match.employee_id if match else None,
                "anomalies": [],
            }
        )
    repo.insert_import_items(items)

    if parsed.get("detected_mapping"):
        repo.upsert_import_profile(company_id, batch_type, parsed["detected_mapping"])

    return {
        "batch_id": batch_id,
        "preview": parsed,
        "items_preview": items,
        "detected_mapping": parsed.get("detected_mapping"),
    }


def commit_import_batch(company_id: str, batch_id: str) -> Dict[str, Any]:
    batch = repo.get_batch(company_id, batch_id)
    if not batch:
        raise LookupError("Batch introuvable.")
    if batch.get("status") == "committed":
        raise ValueError("Batch déjà validé.")
    period_id = str(batch.get("period_id") or "")
    period = repo.get_period(company_id, period_id) if period_id else None
    if period and period.get("status") == "closed":
        raise ValueError("Période clôturée.")

    items = repo.list_import_items(batch_id)
    batch_type = batch.get("batch_type")
    source = "bank_transfer" if batch_type == "bank_recap" else "cpam_decompte"
    committed = 0

    for item in items:
        mapped = item.get("mapped_payload") or {}
        if item.get("match_status") == "skipped":
            continue
        repo.insert_received_line(
            {
                "company_id": company_id,
                "period_id": period_id or None,
                "import_batch_id": batch_id,
                "source": source,
                "amount": float(mapped.get("amount") or 0),
                "payment_date": mapped.get("payment_date"),
                "period_start": mapped.get("period_start"),
                "period_end": mapped.get("period_end"),
                "employee_id": item.get("employee_id"),
                "employee_nir": mapped.get("employee_nir"),
                "employee_name_raw": mapped.get("employee_name_raw"),
                "bank_reference": mapped.get("bank_reference"),
                "match_confidence": mapped.get("match_confidence") or "none",
                "match_status": "matched" if item.get("employee_id") else "unmatched",
            }
        )
        committed += 1

    repo.update_batch(batch_id, {"status": "committed", "summary": {"committed_lines": committed}})
    if period:
        _recompute_period(period)
    return {"committed_lines": committed, "batch_id": batch_id}


def sync_cpam_from_net_entreprises(
    company_id: str, period_id: str, user_id: str
) -> Dict[str, Any]:
    """Synchronise les décomptes CPAM via Net-Entreprises (API ou repli)."""
    from app.modules.net_entreprises.application.ij_decomptes_service import (
        fetch_and_stage_ij_decomptes,
    )

    period = repo.get_period(company_id, period_id)
    if not period:
        raise LookupError("Période introuvable.")
    period_str = f"{period['period_year']}-{period['period_month']:02d}"
    return fetch_and_stage_ij_decomptes(
        company_id=company_id,
        period_id=period_id,
        period=period_str,
        user_id=user_id,
    )


def export_audit_excel(company_id: str, period_id: str) -> bytes:
    dashboard = get_period_dashboard(
        company_id,
        int(repo.get_period(company_id, period_id)["period_year"]),
        int(repo.get_period(company_id, period_id)["period_month"]),
    )
    headers = [
        "Salarié",
        "IJSS théorique",
        "IJSS bulletin",
        "Décompte CPAM",
        "Virement banque",
        "Statut",
    ]
    data = []
    for row in dashboard["rows"]:
        data.append(
            {
                "Salarié": row["employee_name"],
                "IJSS théorique": row["ijss_theorique"],
                "IJSS bulletin": row["ijss_subrogees_bulletin"],
                "Décompte CPAM": row["received_cpam"],
                "Virement banque": row["received_bank"],
                "Statut": row["line_status"],
            }
        )
    return generate_xlsx(data, headers, sheet_name="Suivi IJSS")


def validate_expected_line(
    company_id: str,
    expected_line_id: str,
    user_id: str,
    amount: Optional[float] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    from app.modules.ijss_tracking.application.apply_to_payslip import (
        validate_expected_line_brut,
    )

    return validate_expected_line_brut(
        company_id, expected_line_id, user_id, amount, source
    )


def apply_ijss_to_payslip(
    company_id: str, expected_line_id: str, user_id: str
) -> Dict[str, Any]:
    from app.modules.ijss_tracking.application.apply_to_payslip import (
        apply_validated_ijss_to_payslip,
    )

    return apply_validated_ijss_to_payslip(company_id, expected_line_id, user_id)


def apply_all_validated(company_id: str, period_id: str, user_id: str) -> Dict[str, Any]:
    from app.modules.ijss_tracking.application.apply_to_payslip import (
        apply_all_validated_for_period,
    )

    return apply_all_validated_for_period(company_id, period_id, user_id)
