#!/usr/bin/env python3
"""
Test E2E : recrutement → embauche → PDF identifiants de connexion.

Usage (depuis backend/) :
  python scripts/test_recruitment_credentials_e2e.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.core.database import supabase
from app.modules.employees.application.credentials_pdf import (
    find_credentials_pdf_path,
    get_credentials_pdf_url,
)
from app.modules.employees.infrastructure.providers import get_storage_provider
from app.modules.recruitment.application.service import (
    service_create_candidate,
    service_create_job,
    service_hire_candidate,
)
from app.modules.recruitment.infrastructure.repository import _pipeline_stage_repo


def _pick_company_id() -> str:
    res = supabase.table("companies").select("id, company_name").limit(1).execute()
    if not res.data:
        raise RuntimeError("Aucune entreprise en base")
    row = res.data[0]
    print(f"Entreprise : {row.get('company_name')} ({row['id']})")
    return str(row["id"])


def _pick_actor_id(company_id: str) -> str:
    res = (
        supabase.table("user_company_accesses")
        .select("user_id, role")
        .eq("company_id", company_id)
        .in_("role", ["admin", "rh", "collaborateur_rh"])
        .limit(1)
        .execute()
    )
    if res.data:
        return str(res.data[0]["user_id"])
    prof = supabase.table("profiles").select("id").limit(1).execute()
    if prof.data:
        return str(prof.data[0]["id"])
    raise RuntimeError("Aucun utilisateur RH trouvé")


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"e2e.onboard.{suffix}@eywai-test.local"
    company_id = _pick_company_id()
    actor_id = _pick_actor_id(company_id)

    print("\n=== 1. Création poste ===")
    job = service_create_job(
        company_id,
        actor_id,
        {
            "title": f"Test E2E Onboarding {suffix}",
            "contract_type": "CDI",
            "location": "Paris",
            "description": "Poste test credentials PDF",
        },
    )
    job_id = str(job["id"])
    print(f"Job créé : {job_id}")

    print("\n=== 2. Création candidat ===")
    stages = _pipeline_stage_repo.list_by_job(company_id, job_id)
    first_stage = sorted(stages, key=lambda s: int(s.get("position") or 0))[0]
    candidate = service_create_candidate(
        company_id,
        actor_id,
        {
            "job_id": job_id,
            "first_name": "E2E",
            "last_name": f"Onboard{suffix[:4].upper()}",
            "email": email,
            "current_stage_id": first_stage["id"],
        },
    )
    candidate_id = str(candidate["id"])
    print(f"Candidat créé : {candidate_id} ({email})")

    print("\n=== 3. Embauche (recrutement → salarié + onboarding + compte) ===")
    employee = service_hire_candidate(
        candidate_id,
        company_id,
        date.today().isoformat(),
        job_title="Testeur E2E",
        contract_type="CDI",
        actor_id=actor_id,
    )
    if employee.get("requires_confirmation"):
        print("ERREUR : doublon salarié détecté")
        return 1

    employee_id = str(employee["id"])
    print(f"Salarié créé : {employee_id}")
    print(f"  user_id     : {employee.get('user_id')}")
    print(f"  username    : {employee.get('username')}")
    print(f"  statut      : {employee.get('employment_status')}")

    emp_row = (
        supabase.table("employees")
        .select("id, user_id, username, email")
        .eq("id", employee_id)
        .single()
        .execute()
    ).data
    print(f"  user_id DB  : {emp_row.get('user_id')}")

    print("\n=== 4. Vérification PDF identifiants ===")
    storage = get_storage_provider()
    pdf_path = find_credentials_pdf_path(
        storage,
        company_id,
        employee_id,
        str(emp_row.get("user_id") or "") or None,
        employee.get("employee_folder_name"),
    )
    if not pdf_path:
        print("ÉCHEC : PDF introuvable en storage")
        return 1
    print(f"PDF storage : {pdf_path}")

    signed_url = get_credentials_pdf_url(employee_id)
    if not signed_url:
        print("ÉCHEC : URL signée non générée")
        return 1
    print(f"URL signée  : {signed_url[:90]}...")

    cl = (
        supabase.table("onboarding_checklists")
        .select("id")
        .eq("employee_id", employee_id)
        .limit(1)
        .execute()
    )
    print(f"Checklist onboarding : {'oui' if cl.data else 'non'}")

    print("\n=== SUCCÈS ===")
    print(f"Fiche RH      : /employees/{employee_id} → Documents → Autres")
    print(f"Email compte  : {email}")
    print(f"Identifiant   : {emp_row.get('username')}")
    print("Mot de passe  : voir PDF « Identifiants de connexion »")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
