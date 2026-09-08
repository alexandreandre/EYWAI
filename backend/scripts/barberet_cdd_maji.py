"""BARBERET Théo — réactivation de sa fiche MAJI en CDD 29→30/06/2026 + sortie
fin de CDD. Exécutable contre la prod (local) ou la base de test (workflow
script-env-test.yml) : l'état se recalcule par environnement.

Historique (déclarante, 07/09/2026, parole faisant foi) : CDI MAJI
23/01→28/02 (transfert Zone 404 sans STC — dossier déjà corrigé), CDI
Zone 404 01/03→21/06 (STC payé 06/2026, solde CP repart à 0), CDD MAJI
29→30/06. Salaire du CDD : 3 000 €/35 h — continuité documentée des DEUX
contrats précédents (fiches MAJI et Zone 404 identiques). Le NIR étant
unique par société, on RÉUTILISE sa fiche MAJI (jamais de seconde ligne).

Chemin de création : create_reconciliation_exit (bypass « contrat généré »,
comme Demory) + calculate_exit_indemnities. NOTE ordre des opérations : les
indemnités calculées ici valent 0 tant que le bulletin de juillet n'existe
pas (le brut du contrat se lit dans les bulletins) — RECALCULER les
indemnités après validation du bulletin de juillet, puis archiver.

Usage : python scripts/barberet_cdd_maji.py [--apply]
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402

MAJI_ID = "113b2f33-82ec-4cec-8d3a-f16cda8f74f2"
BARBERET_ID = "498460a6-19ef-47da-9470-f7dabf9ef7e4"
#: Alexandre (super admin) — id identique prod/test (base copiée).
ACTOR_ID = "00da85da-9490-459a-a576-d44e4d70a1d4"


def main() -> int:
    apply = "--apply" in sys.argv

    emp = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, company_id, contract_type, hire_date, "
            "contract_end_date, employment_status, salaire_de_base, "
            "duree_hebdomadaire, statut, current_exit_id"
        )
        .eq("id", BARBERET_ID)
        .maybe_single()
        .execute()
    ).data
    if not emp or str(emp["company_id"]) != MAJI_ID:
        print("REFUS : fiche MAJI de Barberet introuvable.")
        return 1
    print(
        f"État actuel : {emp['contract_type']} {emp['hire_date']}→"
        f"{emp['contract_end_date']} | {emp['employment_status']} | "
        f"{emp['salaire_de_base']} | {emp['duree_hebdomadaire']} h | {emp['statut']}"
    )

    exits = (
        supabase.table("employee_exits")
        .select("id, exit_type, status, last_working_day")
        .eq("employee_id", BARBERET_ID)
        .execute()
    ).data or []
    for x in exits:
        print(f"Sortie existante : {x['exit_type']} {x['status']} lwd={x['last_working_day']}")
    deja = [x for x in exits if x["exit_type"] == "fin_cdd"]
    if deja:
        print("Déjà fait : sortie fin_cdd présente — rien à écrire.")
        return 0

    if not apply:
        print(
            "\nSIMULATION — prévu : fiche → CDD 29/06→30/06 (salaire/35 h "
            "inchangés), statut actif, puis sortie fin_cdd au 30/06 "
            "(réconciliation, sans archivage) + calcul des indemnités. "
            "Relancer avec --apply."
        )
        return 0

    # 1) Fiche : CDD 29→30/06, réactivée le temps de créer la sortie.
    supabase.table("employees").update(
        {
            "employment_status": "actif",
            "contract_type": "CDD",
            "hire_date": "2026-06-29",
            "contract_end_date": "2026-06-30",
            "current_exit_id": None,
        }
    ).eq("id", BARBERET_ID).execute()
    print("Fiche mise à jour : CDD 29/06→30/06, statut actif.")

    # 2) Sortie fin de CDD (chemin réconciliation : pas d'exigence de contrat
    #    généré ; fast_archive=False — archiver APRÈS validation du bulletin
    #    de juillet et recalcul des indemnités).
    from app.modules.employee_exits.application.commands import (
        create_reconciliation_exit,
    )

    created = create_reconciliation_exit(
        BARBERET_ID,
        MAJI_ID,
        ACTOR_ID,
        exit_type="fin_cdd",
        last_working_day=date(2026, 6, 30),
        exit_reason=(
            "Fin de CDD à son terme (29-30/06/2026) — historique transmis par "
            "la déclarante le 07/09/2026."
        ),
        fast_archive=False,
        source="dsn_reconciliation",
    )
    exit_id = str(created.get("id"))
    print(f"Sortie créée : {exit_id} ({created.get('status')})")

    # 3) Indemnités (précarité informative + ICCP) — seront à RECALCULER
    #    après le bulletin de juillet (le brut du contrat se lit dans les
    #    bulletins, inexistants à ce stade).
    from app.modules.employee_exits.application.queries import (
        calculate_exit_indemnities,
    )

    indemnities = calculate_exit_indemnities(exit_id, MAJI_ID)
    resume = {
        k: indemnities.get(k)
        for k in ("total_gross_indemnities", "indemnite_precarite")
        if k in indemnities
    }
    print("Indemnités initiales :", json.dumps(resume, ensure_ascii=False)[:300])

    # 4) Contrôle final.
    emp2 = (
        supabase.table("employees")
        .select("contract_type, hire_date, contract_end_date, employment_status")
        .eq("id", BARBERET_ID)
        .maybe_single()
        .execute()
    ).data
    print("Contrôle fiche :", emp2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
