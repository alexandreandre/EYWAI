#!/usr/bin/env python3
"""
Flux RH complet : recrutement → embauche → onboarding → collaborateur actif.

Utilise la génération aléatoire de mot de passe (provision_collaborator_account),
sans mot de passe fixe.

Usage (depuis backend/) :
  python scripts/rh_recruitment_onboarding_flow.py
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
from app.modules.auth.application.service import login
from app.modules.employees.application.commands import update_employee
from app.modules.employees.application.credentials_pdf import (
    find_credentials_pdf_path,
    get_credentials_pdf_url,
)
from app.modules.employees.infrastructure.providers import get_storage_provider
from app.modules.onboarding.domain.profile import is_payroll_eligible, is_profile_complete
from app.modules.onboarding.infrastructure.repository import onboarding_repository
from app.modules.recruitment.application.service import (
    service_create_candidate,
    service_create_job,
    service_hire_candidate,
)
from app.modules.recruitment.infrastructure.repository import _pipeline_stage_repo

PAYROLL_PROFILE = {
    "nir": "185057401234567",
    "date_naissance": "1995-03-15",
    "lieu_naissance": "Lyon",
    "nationalite": "Française",
    "adresse": {
        "rue": "12 rue de la République",
        "code_postal": "69002",
        "ville": "Lyon",
    },
    "coordonnees_bancaires": {
        "iban": "FR7612345678901234567890123",
        "bic": "BNPAFRPP",
    },
    "statut": "Non-Cadre",
    "is_temps_partiel": False,
    "duree_hebdomadaire": 35.0,
    "salaire_de_base": {"montant": 2400, "valeur": 2400},
    "classification_conventionnelle": {
        "groupe_emploi": "C",
        "classe_emploi": 6,
        "coefficient": 240,
    },
    "avantages_en_nature": {
        "repas": {"nombre_par_mois": 0},
        "logement": {"beneficie": False},
        "vehicule": {"beneficie": False},
    },
    "specificites_paie": {
        "is_alsace_moselle": False,
        "prelevement_a_la_source": {"is_personnalise": False, "taux": 0},
        "transport": {"abonnement_mensuel_total": 0},
        "titres_restaurant": {"beneficie": False, "nombre_par_mois": 0},
        "mutuelle": {"adhesion": True, "lignes_specifiques": []},
        "prevoyance": {"adhesion": True, "lignes_specifiques": []},
    },
    "periode_essai": {
        "duree_initiale": 2,
        "unite": "mois",
        "renouvellement_possible": True,
    },
}


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


def _unique_nir() -> str:
    """NIR fictif unique (15 chiffres) pour les tests."""
    base = uuid.uuid4().int % 10**13
    return f"1{base:013d}"[:15]


def complete_onboarding(
    employee_id: str,
    company_id: str,
    actor_id: str,
) -> dict:
    """Complète toutes les tâches onboarding + fiche paie → statut actif."""
    checklist = onboarding_repository.get_checklist_by_employee(employee_id, company_id)
    if not checklist:
        checklist = onboarding_repository.create_checklist(employee_id, company_id)

    checklist_id = str(checklist["id"])
    for task in checklist.get("tasks") or []:
        if not task.get("is_completed"):
            onboarding_repository.complete_task(
                str(task["id"]), checklist_id, company_id, actor_id
            )

    payroll = dict(PAYROLL_PROFILE)
    payroll["nir"] = _unique_nir()
    update_employee(employee_id, payroll)

    refreshed = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .single()
        .execute()
    ).data
    return refreshed


def main() -> int:
    suffix = uuid.uuid4().hex[:6]
    first_name = "Camille"
    last_name = "RecruteRH"
    email = f"camille.recruterh.{suffix}@eywai-demo.com"
    company_id = _pick_company_id()
    actor_id = _pick_actor_id(company_id)

    print("\n=== 1. Création du poste (Recrutement) ===")
    job = service_create_job(
        company_id,
        actor_id,
        {
            "title": f"Opérateur production ({suffix})",
            "contract_type": "CDI",
            "location": "Site principal",
            "description": "Poste créé via flux RH complet",
        },
    )
    job_id = str(job["id"])

    print("\n=== 2. Candidat ===")
    stages = _pipeline_stage_repo.list_by_job(company_id, job_id)
    first_stage = sorted(stages, key=lambda s: int(s.get("position") or 0))[0]
    candidate = service_create_candidate(
        company_id,
        actor_id,
        {
            "job_id": job_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "current_stage_id": first_stage["id"],
        },
    )
    candidate_id = str(candidate["id"])

    print("\n=== 3. Embauche (salarié + compte + PDF identifiants aléatoires) ===")
    employee = service_hire_candidate(
        candidate_id,
        company_id,
        date.today().isoformat(),
        job_title="Opérateur de production",
        contract_type="CDI",
        actor_id=actor_id,
    )
    if employee.get("requires_confirmation"):
        print("ERREUR : un salarié avec cet email existe déjà")
        return 1

    employee_id = str(employee["id"])
    username = str(employee.get("username") or "")
    generated_password = employee.get("generated_password")

    if not generated_password:
        print("ERREUR : aucun mot de passe aléatoire généré à l'embauche")
        return 1

    emp_row = (
        supabase.table("employees")
        .select("id, user_id, username, email, employee_folder_name, employment_status")
        .eq("id", employee_id)
        .single()
        .execute()
    ).data

    storage = get_storage_provider()
    pdf_found = find_credentials_pdf_path(
        storage,
        company_id,
        employee_id,
        str(emp_row.get("user_id") or "") or None,
        emp_row.get("employee_folder_name"),
    )
    signed_url = get_credentials_pdf_url(employee_id)

    if not pdf_found or not signed_url:
        print("ERREUR : PDF identifiants introuvable après embauche")
        return 1

    print(f"  Statut initial     : {emp_row.get('employment_status')}")
    print("  PDF identifiants   : OK")

    print("\n=== 4. Onboarding (tâches + fiche paie) ===")
    refreshed = complete_onboarding(employee_id, company_id, actor_id)

    cl = onboarding_repository.get_checklist_by_employee(employee_id, company_id)
    done = sum(1 for t in (cl or {}).get("tasks", []) if t.get("is_completed"))
    total = len((cl or {}).get("tasks", []))

    print(f"  Tâches             : {done}/{total}")
    print(f"  Fiche complète     : {is_profile_complete(refreshed)}")
    print(f"  Éligible paie      : {is_payroll_eligible(refreshed)}")
    print(f"  Statut final       : {refreshed.get('employment_status')}")

    if str(refreshed.get("employment_status") or "").lower() != "actif":
        print("ERREUR : le collaborateur n'est pas passé en statut actif")
        return 1

    active_in_list = (
        supabase.table("employees")
        .select("id")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    ).data
    if not active_in_list:
        print("ERREUR : collaborateur absent de la liste « Actifs »")
        return 1

    print("\n=== 5. Vérification connexion (mot de passe aléatoire) ===")
    try:
        login(username, generated_password)
        print("  Connexion testée   : OK")
    except Exception as login_err:
        print(f"  Connexion testée   : ÉCHEC ({login_err})")
        return 1

    print("\n" + "=" * 60)
    print("FLUX RH TERMINÉ — COLLABORATEUR PRÊT")
    print("=" * 60)
    print(f"\nFiche RH           : /employees/{employee_id}")
    print("Liste collaborateurs (filtre Actif) : /employees")
    print(f"Onboarding         : /onboarding/{employee_id}")
    print(f"Candidat embauché  : {candidate_id}")
    print("\n--- Identifiants (mot de passe aléatoire, affiché une seule fois) ---")
    print(f"  Email              : {email}")
    print(f"  Nom d'utilisateur  : {username}")
    print(f"  Mot de passe       : {generated_password}")
    print("\n--- Documents ---")
    print("  RH → fiche → Documents → Autres → « Identifiants de connexion »")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
