"""Nettoyage complet avant suppression d'une fiche employé."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.database import supabase

logger = logging.getLogger(__name__)

_EMPLOYEE_BUCKETS = ("contracts", "piece_identite", "creation_compte")
_PAYSLIPS_BUCKET = "payslips"
_GENERATED_BUCKET = "generated_documents"
_EXIT_BUCKET = "exit_documents"
_ADVANCE_PAYMENTS_BUCKET = "advance_payments"
_SALARY_CERT_BUCKET = "salary_certificates"

_ORPHAN_TABLES = (
    "ijss_import_items",
    "ijss_received_lines",
    "employee_time_entries",
    "employee_time_entries_validations",
    "employee_badge_credentials",
    "employee_time_day_accounting",
    "shifts",
    "ijss_expected_lines",
    "salary_certificates",
    "employee_competencies",
    "employee_certifications",
)

_COUNT_SPECS: tuple[tuple[str, str], ...] = (
    ("payslips", "bulletin(s) de paie"),
    ("salary_advances", "avance(s) / acompte(s)"),
    ("salary_seizures", "saisie(s) sur salaire"),
    ("absence_requests", "demande(s) d'absence"),
    ("monthly_inputs", "saisie(s) mensuelle(s)"),
    ("shifts", "créneau(x) de planning"),
    ("employee_exits", "processus de sortie"),
    ("generated_documents", "document(s) généré(s)"),
    ("annual_reviews", "entretien(s)"),
    ("expense_reports", "note(s) de frais"),
    ("employee_time_entries", "pointage(s) badgeuse"),
    ("employee_loans", "prêt(s) salarié"),
    ("training_enrollments", "inscription(s) formation"),
    ("employee_schedules", "planning(s) horaire(s)"),
    ("payroll_simulations", "simulation(s) de paie"),
)


@dataclass
class DeletionImpact:
    employee_id: str
    employee_name: str
    counts: Dict[str, int] = field(default_factory=dict)
    summary_lines: List[str] = field(default_factory=list)
    has_user_account: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "counts": self.counts,
            "summary_lines": self.summary_lines,
            "has_user_account": self.has_user_account,
            "has_data": bool(self.summary_lines),
        }


def _count_rows(table: str, employee_id: str) -> int:
    try:
        resp = (
            supabase.table(table)
            .select("id", count="exact")
            .eq("employee_id", employee_id)
            .limit(1)
            .execute()
        )
        return int(resp.count or 0)
    except Exception:
        return 0


def get_deletion_impact(employee_id: str, company_id: str) -> DeletionImpact:
    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, user_id, company_id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    emp = emp_resp.data
    if not emp:
        return DeletionImpact(employee_id=employee_id, employee_name="")

    first = (emp.get("first_name") or "").strip()
    last = (emp.get("last_name") or "").strip()
    name = f"{first} {last}".strip() or employee_id

    counts: Dict[str, int] = {}
    summary_lines: List[str] = []
    for table, label in _COUNT_SPECS:
        n = _count_rows(table, employee_id)
        if n > 0:
            counts[table] = n
            summary_lines.append(f"{n} {label}")

    has_user = bool(emp.get("user_id") or emp.get("id"))
    if has_user:
        summary_lines.append("Compte de connexion associé")

    return DeletionImpact(
        employee_id=employee_id,
        employee_name=name,
        counts=counts,
        summary_lines=summary_lines,
        has_user_account=has_user,
    )


def _remove_storage_paths(bucket: str, paths: List[str]) -> None:
    clean = [p for p in paths if p]
    if not clean:
        return
    try:
        supabase.storage.from_(bucket).remove(clean)
    except Exception as exc:
        logger.warning("Storage remove %s: %s", bucket, exc)


def _remove_storage_folder(bucket: str, prefix: str) -> None:
    try:
        entries = supabase.storage.from_(bucket).list(prefix)
    except Exception as exc:
        logger.warning("Storage list %s/%s: %s", bucket, prefix, exc)
        return
    if not isinstance(entries, list):
        return
    paths = [f"{prefix}/{item['name']}" for item in entries if item.get("name")]
    _remove_storage_paths(bucket, paths)


def cleanup_employee_storage(company_id: str, employee_id: str) -> None:
    prefix = f"{company_id}/{employee_id}"
    for bucket in _EMPLOYEE_BUCKETS:
        _remove_storage_folder(bucket, prefix)

    try:
        payslip_rows = (
            supabase.table("payslips")
            .select("pdf_storage_path")
            .eq("employee_id", employee_id)
            .execute()
        ).data or []
        _remove_storage_paths(
            _PAYSLIPS_BUCKET,
            [r["pdf_storage_path"] for r in payslip_rows if r.get("pdf_storage_path")],
        )
    except Exception as exc:
        logger.warning("Payslip storage cleanup: %s", exc)

    try:
        doc_rows = (
            supabase.table("generated_documents")
            .select("file_url")
            .eq("employee_id", employee_id)
            .execute()
        ).data or []
        _remove_storage_paths(
            _GENERATED_BUCKET,
            [r["file_url"] for r in doc_rows if r.get("file_url")],
        )
    except Exception as exc:
        logger.warning("Generated documents storage cleanup: %s", exc)

    try:
        exit_rows = (
            supabase.table("employee_exits")
            .select("id")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .execute()
        ).data or []
        exit_ids = [str(r["id"]) for r in exit_rows]
        if exit_ids:
            exit_docs = (
                supabase.table("exit_documents")
                .select("storage_path")
                .in_("exit_id", exit_ids)
                .execute()
            ).data or []
            _remove_storage_paths(
                _EXIT_BUCKET,
                [r["storage_path"] for r in exit_docs if r.get("storage_path")],
            )
    except Exception as exc:
        logger.warning("Exit documents storage cleanup: %s", exc)

    try:
        advance_ids = [
            str(r["id"])
            for r in (
                supabase.table("salary_advances")
                .select("id")
                .eq("employee_id", employee_id)
                .execute()
            ).data
            or []
        ]
        if advance_ids:
            payments = (
                supabase.table("salary_advance_payments")
                .select("proof_file_path")
                .in_("advance_id", advance_ids)
                .execute()
            ).data or []
            _remove_storage_paths(
                _ADVANCE_PAYMENTS_BUCKET,
                [r["proof_file_path"] for r in payments if r.get("proof_file_path")],
            )
    except Exception as exc:
        logger.warning("Advance payments storage cleanup: %s", exc)

    try:
        certs = (
            supabase.table("salary_certificates")
            .select("storage_path")
            .eq("employee_id", employee_id)
            .execute()
        ).data or []
        _remove_storage_paths(
            _SALARY_CERT_BUCKET,
            [r["storage_path"] for r in certs if r.get("storage_path")],
        )
    except Exception as exc:
        logger.warning("Salary certificates storage cleanup: %s", exc)


_LEGACY_EMPLOYEE_DATA_TABLES = (
    "salary_advances",
    "salary_seizures",
    "payslips",
    "absence_requests",
    "monthly_inputs",
    "employee_schedules",
    "payroll_simulations",
    "employee_exits",
    "generated_documents",
    "employee_documents",
    "annual_reviews",
    "promotions",
    "expense_reports",
    "medical_follow_up_obligations",
    "rib_alerts",
    "recruitment_candidates",
    "cse_elected_members",
    "cse_delegation_hours",
    "cse_meeting_participants",
    "payroll_anomaly_resolutions",
    "employee_loans",
    "employee_mutuelle_types",
    "employee_leave_adjustments",
    "employee_cet_movements",
    "employee_cp_fractionnement_grants",
    "employee_cp_fractionnement_inputs",
    "employee_cp_seniority_grants",
    "employee_modulation_counters",
    "employee_modulation_movements",
    "employee_overtime_adjustments",
    "repos_compensateur_credits",
    "participation_campaign_advances",
    "participation_bulletins",
    "onboarding_checklists",
    "notifications",
    "training_enrollments",
    "employee_objectives",
    "employee_boeth_profiles",
    "employee_work_medal_cases",
    "hr_deadline_reminder_logs",
    "company_jei_exonerations",
    "cse_delegation_requests",
    "cse_delegation_payroll_entries",
)


def _delete_by_employee_id(table: str, employee_id: str) -> None:
    try:
        supabase.table(table).delete().eq("employee_id", employee_id).execute()
    except Exception as exc:
        logger.warning("Delete %s for employee %s: %s", table, employee_id, exc)


def cleanup_employee_orphan_rows(employee_id: str) -> None:
    """Filet de sécurité pour tables sans CASCADE ou FK legacy non migrée."""
    try:
        exit_ids = [
            str(r["id"])
            for r in (
                supabase.table("employee_exits")
                .select("id")
                .eq("employee_id", employee_id)
                .execute()
            ).data
            or []
        ]
        if exit_ids:
            for table in ("exit_checklist_items", "exit_documents"):
                try:
                    supabase.table(table).delete().in_("exit_id", exit_ids).execute()
                except Exception as exc:
                    logger.warning("Exit child cleanup %s: %s", table, exc)
    except Exception as exc:
        logger.warning("Exit lookup cleanup: %s", exc)

    try:
        advance_ids = [
            str(r["id"])
            for r in (
                supabase.table("salary_advances")
                .select("id")
                .eq("employee_id", employee_id)
                .execute()
            ).data
            or []
        ]
        if advance_ids:
            for table in ("salary_advance_payments", "salary_advance_repayments"):
                try:
                    supabase.table(table).delete().in_("advance_id", advance_ids).execute()
                except Exception as exc:
                    logger.warning("Advance child cleanup %s: %s", table, exc)
    except Exception as exc:
        logger.warning("Advance children cleanup: %s", exc)

    try:
        seizure_ids = [
            str(r["id"])
            for r in (
                supabase.table("salary_seizures")
                .select("id")
                .eq("employee_id", employee_id)
                .execute()
            ).data
            or []
        ]
        if seizure_ids:
            supabase.table("salary_seizure_deductions").delete().in_(
                "seizure_id", seizure_ids
            ).execute()
    except Exception as exc:
        logger.warning("Seizure deductions cleanup: %s", exc)

    for table in _LEGACY_EMPLOYEE_DATA_TABLES:
        _delete_by_employee_id(table, employee_id)

    for table in _ORPHAN_TABLES:
        _delete_by_employee_id(table, employee_id)


def cleanup_user_account_for_company(
    auth_uid: str,
    company_id: str,
    employee_id: str,
) -> bool:
    """
    Retire l'accès à la société courante.
    Retourne True si le compte Auth/profil doit aussi être supprimé.
    """
    from app.modules.users.application.service import (
        get_user_company_access_repository,
        get_user_permission_repository,
        get_user_repository,
    )

    access_repo = get_user_company_access_repository()
    perm_repo = get_user_permission_repository()
    user_repo = get_user_repository()

    perm_repo.delete_for_user_company(auth_uid, company_id)
    access_repo.delete(auth_uid, company_id)

    other_accesses = [
        a for a in access_repo.get_accesses_for_user(auth_uid) if a.get("company_id")
    ]
    if other_accesses:
        return False

    other_employees = (
        supabase.table("employees")
        .select("id")
        .eq("user_id", auth_uid)
        .neq("id", employee_id)
        .limit(1)
        .execute()
    )
    if other_employees.data:
        return False

    legacy_match = (
        supabase.table("employees")
        .select("id")
        .eq("id", auth_uid)
        .neq("id", employee_id)
        .limit(1)
        .execute()
    )
    if legacy_match.data:
        return False

    user_repo.delete(auth_uid)
    return True
