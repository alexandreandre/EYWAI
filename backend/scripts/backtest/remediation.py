"""Remédiations VERTES idempotentes pour le backtest paie."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client
from app.modules.payroll.backtest.models import RemediationColor, RemediationProposal

# Salariés gelés (déjà validés Cegid — jamais réécrits automatiquement)
FROZEN_EMPLOYEE_FOLDERS = frozenset({"COTTE_Leo", "BUGNY_Michel"})

RED_ACTIONS = frozenset({"drop", "delete_mass", "disable_rls", "truncate"})


class RemediationError(Exception):
    pass


class RemediationBlocked(RemediationError):
    """Action ROUGE ou salarié gelé."""


def apply_remediation(
    proposal: RemediationProposal,
    *,
    employee_ids_by_matricule: Dict[str, str],
    company_id: str,
    year: int,
    month: int,
    employee_folders: Dict[str, str],
    journal_callback=None,
) -> List[Dict[str, Any]]:
    if proposal.color == RemediationColor.ROUGE:
        raise RemediationBlocked(f"Action ROUGE bloquée: {proposal.pattern_id}")
    if proposal.color == RemediationColor.ORANGE:
        raise RemediationBlocked(
            f"Action ORANGE (code) non appliquée ici: {proposal.pattern_id}"
        )

    results: List[Dict[str, Any]] = []
    admin = get_supabase_admin_client()

    for matricule in proposal.affected_matricules:
        emp_id = employee_ids_by_matricule.get(matricule)
        folder = employee_folders.get(matricule, "")
        if folder in FROZEN_EMPLOYEE_FOLDERS:
            results.append(
                {
                    "matricule": matricule,
                    "status": "skipped_frozen",
                    "reason": f"Salarié gelé ({folder})",
                }
            )
            continue
        if not emp_id:
            results.append({"matricule": matricule, "status": "skipped", "reason": "no employee_id"})
            continue

        before = _snapshot_employee(admin, emp_id, year, month)
        try:
            if proposal.action_type == "monthly_input_participation":
                _apply_monthly_input(
                    admin,
                    emp_id,
                    company_id,
                    year,
                    month,
                    name="Participation 2025 — numéraire",
                    amount=proposal.payload.get("amount", 0),
                    is_socially_taxed=False,
                    is_taxable=True,
                )
            elif proposal.action_type == "monthly_input_acompte":
                _apply_monthly_input(
                    admin,
                    emp_id,
                    company_id,
                    year,
                    month,
                    name="Acompte participation 2025 (déjà versé)",
                    amount=-abs(proposal.payload.get("amount", 0)),
                    is_socially_taxed=False,
                    is_taxable=False,
                )
            elif proposal.action_type == "monthly_input_note_de_frais":
                _apply_monthly_input(
                    admin,
                    emp_id,
                    company_id,
                    year,
                    month,
                    name="Remboursement note de frais (participation)",
                    amount=proposal.payload.get("amount", 0),
                    is_socially_taxed=False,
                    is_taxable=False,
                )
            elif proposal.action_type == "enable_prevoyance":
                _patch_specificites(admin, emp_id, {"prevoyance": {"adhesion": True}})
            elif proposal.action_type == "enable_hors_hs":
                _patch_specificites(
                    admin, emp_id, {"salaire_hors_hs_structurelles": True}
                )
            elif proposal.action_type == "set_classification":
                coeff = proposal.payload.get("coefficient")
                if coeff:
                    _patch_classification(admin, emp_id, int(coeff))
            elif proposal.action_type == "align_pointage_planning":
                _align_pointage_planning(admin, emp_id, year, month)
            else:
                results.append(
                    {
                        "matricule": matricule,
                        "status": "skipped",
                        "reason": f"action inconnue: {proposal.action_type}",
                    }
                )
                continue

            after = _snapshot_employee(admin, emp_id, year, month)
            entry = {
                "matricule": matricule,
                "employee_id": emp_id,
                "status": "applied",
                "action_type": proposal.action_type,
                "pattern_id": proposal.pattern_id,
            }
            if journal_callback:
                journal_callback(
                    {
                        "action": proposal.action_type,
                        "matricule": matricule,
                        "employee_id": emp_id,
                        "before": before,
                        "after": after,
                    }
                )
            results.append(entry)
        except Exception as exc:
            results.append(
                {
                    "matricule": matricule,
                    "status": "error",
                    "error": str(exc),
                }
            )
    return results


def _snapshot_employee(admin, employee_id: str, year: int, month: int) -> Dict[str, Any]:
    emp = (
        admin.table("employees")
        .select("specificites_paie, classification_conventionnelle")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    mi = (
        admin.table("monthly_inputs")
        .select("name, amount")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
    sched = (
        admin.table("employee_schedules")
        .select("actual_hours, planned_calendar")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .maybe_single()
        .execute()
    )
    return {
        "specificites_paie": (emp.data or {}).get("specificites_paie"),
        "classification": (emp.data or {}).get("classification_conventionnelle"),
        "monthly_inputs": mi.data or [],
        "schedule": sched.data,
    }


def _apply_monthly_input(
    admin,
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    *,
    name: str,
    amount: float,
    is_socially_taxed: bool,
    is_taxable: bool,
) -> None:
    admin.table("monthly_inputs").delete().eq("employee_id", employee_id).eq(
        "year", year
    ).eq("month", month).eq("name", name).execute()
    if amount == 0:
        return
    admin.table("monthly_inputs").insert(
        {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": year,
            "month": month,
            "name": name,
            "description": name,
            "amount": round(float(amount), 2),
            "is_socially_taxed": is_socially_taxed,
            "is_taxable": is_taxable,
        }
    ).execute()


def _patch_specificites(admin, employee_id: str, patch: Dict[str, Any]) -> None:
    res = (
        admin.table("employees")
        .select("specificites_paie")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    current = (res.data or {}).get("specificites_paie") or {}
    if isinstance(current, str):
        current = json.loads(current)
    merged = {**current, **patch}
    if "prevoyance" in patch and isinstance(current.get("prevoyance"), dict):
        merged["prevoyance"] = {**current["prevoyance"], **patch["prevoyance"]}
    admin.table("employees").update({"specificites_paie": merged}).eq(
        "id", employee_id
    ).execute()


def _patch_classification(admin, employee_id: str, coefficient: int) -> None:
    res = (
        admin.table("employees")
        .select("classification_conventionnelle")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    current = (res.data or {}).get("classification_conventionnelle") or {}
    if isinstance(current, str):
        current = json.loads(current)
    current["coefficient"] = coefficient
    current["classe_emploi"] = str(coefficient)
    admin.table("employees").update(
        {"classification_conventionnelle": current}
    ).eq("id", employee_id).execute()


def _align_pointage_planning(admin, employee_id: str, year: int, month: int) -> None:
    """Copie le planning (prevu) vers le réel pour éviter absences fictives."""
    res = (
        admin.table("employee_schedules")
        .select("id, planned_calendar, actual_hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .maybe_single()
        .execute()
    )
    row = res.data
    if not row:
        return
    planned = row.get("planned_calendar") or {}
    if not planned:
        return
    admin.table("employee_schedules").update(
        {"actual_hours": planned}
    ).eq("id", row["id"]).execute()
