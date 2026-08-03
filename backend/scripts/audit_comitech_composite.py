#!/usr/bin/env python3
"""Audit configuration Comitech Composite en base."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

env_file = BACKEND_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from app.core.database import supabase
from app.modules.repos_compensateur.application.contingent_queries import (
    get_contingent_overview,
)
from comitech_participation_data import COMITECH_PARTICIPATION_2025
from setup_comitech_composite import COMITECH_MEDICAL_REGISTRY, resolve_employee
from scripts.donnees_nominatives import charger_ou_vide


def _noms_audites() -> list[str]:
    """Echantillon de salaries a auditer — noms lus hors depot Git."""
    return list((charger_ou_vide("comitech", "backtest-heures") or {}).get("heures", []))[:4]


def _nom_temoin() -> str:
    noms = _noms_audites()
    return noms[0] if noms else "\x00"


CID = "12cd8c71-da13-43f9-9151-475c4d5e8812"


def main() -> int:
    report: dict = {"company_id": CID}

    co = (
        supabase.table("companies")
        .select("company_name, siret, idcc, dsn_sync_mode, group_id, settings")
        .eq("id", CID)
        .maybe_single()
        .execute()
        .data
    )
    report["company"] = co

    def rows(table: str, cols: str = "*"):
        return (
            supabase.table(table).select(cols).eq("company_id", CID).execute().data
            or []
        )

    report["collective_agreement"] = rows("company_collective_agreements", "id")
    report["cet"] = rows(
        "company_cet_settings",
        "cet_enabled, validation_mode, allow_deposit_hs, allow_deposit_cp",
    )
    report["cse"] = rows("company_cse_settings", "cse_status, carence_valid_until")
    report["contingent"] = rows("company_overtime_contingent_settings", "*")
    report["cp_seniority"] = rows("company_cp_seniority_settings", "preset, enabled")
    report["mutuelle_catalog"] = rows("company_mutuelle_types", "libelle, is_active")
    report["bonus_types"] = [
        b["libelle"] for b in rows("company_bonus_types", "libelle")
    ]

    emps = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, duree_hebdomadaire, employment_status, specificites_paie"
        )
        .eq("company_id", CID)
        .execute()
        .data
        or []
    )
    report["employees_total"] = len(emps)

    not39 = []
    for e in emps:
        st = e.get("employment_status") or "actif"
        if st not in ("actif", "active", "en_onboarding"):
            continue
        dh = e.get("duree_hebdomadaire")
        if dh is None or abs(float(dh) - 39) > 0.01:
            not39.append(f"{e['last_name']} {e['first_name']}: {dh}")
    report["employees_not_39h"] = not39

    med = (
        supabase.table("medical_follow_up_obligations")
        .select("id", count="exact")
        .eq("company_id", CID)
        .eq("status", "realisee")
        .execute()
    )
    report["medical_visits_realisees"] = med.count

    med_spst = (
        supabase.table("medical_follow_up_obligations")
        .select("employee_id")
        .eq("company_id", CID)
        .ilike("justification", "%Registre SPST%")
        .execute()
        .data
        or []
    )
    report["medical_spst_import"] = len(med_spst)

    today_iso = date.today().isoformat()
    phantom_types = ("aptitude_sir_avant_affectation", "mi_carriere_45")
    all_med = (
        supabase.table("medical_follow_up_obligations")
        .select(
            "employee_id, visit_type, due_date, status, completed_date"
        )
        .eq("company_id", CID)
        .neq("status", "annulee")
        .execute()
        .data
        or []
    )
    report["medical_phantom_overdue"] = sum(
        1
        for o in all_med
        if o.get("visit_type") in phantom_types
        and o.get("status") in ("a_faire", "planifiee")
        and o.get("due_date")
        and o["due_date"] < today_iso
    )
    report["medical_sir_vip_overdue"] = sum(
        1
        for o in all_med
        if o.get("visit_type") in ("sir", "vip")
        and o.get("status") in ("a_faire", "planifiee")
        and o.get("due_date")
        and o["due_date"] < today_iso
    )

    registry_checks: list[dict[str, Any]] = []
    for row in COMITECH_MEDICAL_REGISTRY:
        emp = resolve_employee(emps, row.last_name, row.first_hint, row.last_name_aliases)
        label = f"{row.last_name} {row.first_hint or ''}".strip()
        if not emp:
            registry_checks.append({"employee": label, "ok": False, "reason": "missing"})
            continue
        emp_obs = [o for o in all_med if o["employee_id"] == emp["id"]]
        active = [
            o
            for o in emp_obs
            if o.get("status") in ("a_faire", "planifiee")
        ]
        realised = [
            o
            for o in emp_obs
            if o.get("visit_type") == row.visit_type
            and o.get("status") == "realisee"
            and o.get("completed_date") == row.visit_date.isoformat()
        ]
        periodic_active = [
            o for o in active if o.get("visit_type") == row.visit_type
        ]
        phantoms = [
            o
            for o in active
            if o.get("visit_type") in phantom_types
        ]
        ok = (
            bool(realised)
            and len(periodic_active) <= 1
            and len(phantoms) == 0
            and (
                not row.renew_before
                or any(
                    o.get("due_date") == row.renew_before.isoformat()
                    for o in periodic_active
                )
            )
        )
        registry_checks.append(
            {
                "employee": label,
                "ok": ok,
                "realised": bool(realised),
                "periodic_active": len(periodic_active),
                "phantom_active": len(phantoms),
            }
        )
    report["medical_registry_checks"] = registry_checks
    report["medical_registry_ok"] = all(c.get("ok") for c in registry_checks)

    report["participation_bulletins"] = (
        supabase.table("participation_bulletins")
        .select("id", count="exact")
        .eq("company_id", CID)
        .execute()
        .count
    )
    report["participation_campaigns"] = rows(
        "participation_campaigns", "id, year, exercise_label, status"
    )

    budgets = rows("training_budget", "year, global_envelope")
    report["training_budget_2026"] = next(
        (b for b in budgets if b.get("year") == 2026), None
    )

    prev = mut = ret = 0
    for e in emps:
        sp = e.get("specificites_paie") or {}
        if not isinstance(sp, dict):
            continue
        if (sp.get("prevoyance") or {}).get("lignes_specifiques"):
            prev += 1
        mutuelle = sp.get("mutuelle") or {}
        if mutuelle.get("mutuelle_type_ids") or mutuelle.get("adhesion"):
            mut += 1
        if (sp.get("retraite_sup") or {}).get("lignes_specifiques"):
            ret += 1
    report["benefits"] = {
        "mutuelle": mut,
        "prevoyance": prev,
        "retraite_sup": ret,
        "total_employees": len(emps),
    }

    report["rcr_absences"] = (
        supabase.table("absence_requests")
        .select("id", count="exact")
        .eq("company_id", CID)
        .eq("type", "repos_compensateur")
        .eq("status", "validated")
        .execute()
        .count
    )

    report["medical_registry_missing"] = [
        f"{r.last_name} {r.first_hint or ''}".strip()
        for r in COMITECH_MEDICAL_REGISTRY
        if not resolve_employee(emps, r.last_name, r.first_hint, r.last_name_aliases)
    ]
    report["participation_missing"] = [
        f"{r.last_name} {r.first_hint or ''}".strip()
        for r in COMITECH_PARTICIPATION_2025
        if not resolve_employee(
            emps, r.last_name, r.first_hint, getattr(r, "last_name_aliases", ())
        )
    ]

    overview = get_contingent_overview(CID, 2025, date(2025, 12, 31))
    report["contingent_kpis"] = overview.get("kpis")
    report["contingent_exceeded"] = [
        f"{r['last_name']} {r['first_name']}"
        for r in overview.get("employees", [])
        if r.get("status") in ("management_exceeded", "cor_exceeded")
    ]

    for name in _noms_audites():
        row = next(
            (
                r
                for r in overview.get("employees", [])
                if name in (r.get("last_name") or "").upper()
            ),
            None,
        )
        if row:
            report[f"sample_{name}"] = {
                k: row.get(k)
                for k in (
                    "paid_hours",
                    "structural_hours",
                    "pause_deduction",
                    "rcr_hours",
                    "total_for_ceiling",
                    "management_contingent",
                    "status",
                )
            }

    report["goyat_in_db"] = [
        e for e in emps if _nom_temoin() in (e.get("last_name") or "").upper()
    ]

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
