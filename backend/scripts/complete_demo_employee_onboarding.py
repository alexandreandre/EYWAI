#!/usr/bin/env python3
"""Finalise l'onboarding d'un collaborateur (fiche paie + tâches → statut actif)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.core.database import supabase
from app.modules.onboarding.domain.profile import is_payroll_eligible, is_profile_complete
from app.modules.onboarding.infrastructure.repository import onboarding_repository

from rh_recruitment_onboarding_flow import complete_onboarding, _pick_actor_id

EMPLOYEE_ID = "f9dcfff2-c623-4d0a-b732-69acced5388e"


def main() -> int:
    emp = (
        supabase.table("employees")
        .select("id, company_id, first_name, last_name, employment_status")
        .eq("id", EMPLOYEE_ID)
        .maybe_single()
        .execute()
    ).data
    if not emp:
        print(f"Employé {EMPLOYEE_ID} introuvable")
        return 1

    company_id = str(emp["company_id"])
    actor_id = _pick_actor_id(company_id)
    print(f"Finalisation : {emp['first_name']} {emp['last_name']} ({EMPLOYEE_ID})")

    refreshed = complete_onboarding(EMPLOYEE_ID, company_id, actor_id)

    cl = onboarding_repository.get_checklist_by_employee(EMPLOYEE_ID, company_id)
    done = sum(1 for t in (cl or {}).get("tasks", []) if t.get("is_completed"))
    total = len((cl or {}).get("tasks", []))

    print(f"  Statut           : {refreshed.get('employment_status')}")
    print(f"  Fiche complète   : {is_profile_complete(refreshed)}")
    print(f"  Éligible paie    : {is_payroll_eligible(refreshed)}")
    print(f"  Onboarding       : {done}/{total} tâches")
    print(f"\nFiche : /employees/{EMPLOYEE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
