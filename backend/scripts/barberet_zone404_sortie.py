"""BARBERET Théo — clôture de sa fiche ZONE 404 (fantôme « actif »).

Historique (déclarante, 07/09/2026) : CDI Zone 404 01/03→21/06/2026, parti
avec solde de tout compte payé sur 06/2026 (chez Quadra), puis CDD MAJI
29-30/06. Sa fiche Zone 404 était restée « actif » sans sortie — elle fausse
les effectifs (et le périmètre JEI fraîchement activé).

HYPOTHÈSE appliquée (décision Alexandre 08/09 : ne rien demander) :
départ volontaire pour re-signer dans le groupe → DÉMISSION au 21/06.
Enregistrement purement administratif via le chemin réconciliation
(aucune indemnité calculée, aucun document généré — le STC réel a été payé
chez Quadra sur 06/2026), archivage immédiat → statut « parti ».

Usage : python scripts/barberet_zone404_sortie.py [--apply]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402

ZONE404_ID = "03fb17a5-134b-4c6e-9927-2083370c44d4"
#: Alexandre (super admin) — id identique prod/test.
ACTOR_ID = "00da85da-9490-459a-a576-d44e4d70a1d4"


def main() -> int:
    apply = "--apply" in sys.argv

    emp = (
        supabase.table("employees")
        .select("id, first_name, last_name, employment_status, hire_date, contract_type")
        .eq("company_id", ZONE404_ID)
        .ilike("last_name", "%BARBERET%")
        .maybe_single()
        .execute()
    ).data
    if not emp:
        print("REFUS : fiche Zone 404 de Barberet introuvable.")
        return 1
    print(
        f"État actuel : {emp['contract_type']} depuis {emp['hire_date']} | "
        f"{emp['employment_status']}"
    )

    exits = (
        supabase.table("employee_exits")
        .select("id, exit_type, status, last_working_day")
        .eq("employee_id", emp["id"])
        .execute()
    ).data or []
    for x in exits:
        print(f"Sortie existante : {x['exit_type']} {x['status']} lwd={x['last_working_day']}")
    if exits or emp["employment_status"] in ("parti", "en_sortie"):
        print("Déjà traité — rien à écrire.")
        return 0

    if not apply:
        print(
            "\nSIMULATION — prévu : contract_end_date=2026-06-21, sortie "
            "démission au 21/06 (réconciliation, archivage immédiat → parti). "
            "Relancer avec --apply."
        )
        return 0

    supabase.table("employees").update(
        {"contract_end_date": "2026-06-21"}
    ).eq("id", emp["id"]).execute()

    from app.modules.employee_exits.application.commands import (
        create_reconciliation_exit,
    )

    created = create_reconciliation_exit(
        str(emp["id"]),
        ZONE404_ID,
        ACTOR_ID,
        exit_type="demission",
        last_working_day=date(2026, 6, 21),
        exit_reason=(
            "Fin du CDI Zone 404 au 21/06/2026, STC payé sur 06/2026 (paie "
            "actuelle) — HYPOTHÈSE démission (départ volontaire pour re-signer "
            "en CDD chez MAJI le 29/06), historique déclarante du 07/09/2026."
        ),
        fast_archive=True,
        source="dsn_reconciliation",
    )
    print(f"Sortie créée : {created.get('id')} ({created.get('status')})")

    emp2 = (
        supabase.table("employees")
        .select("employment_status, contract_end_date")
        .eq("id", emp["id"])
        .maybe_single()
        .execute()
    ).data
    print("Contrôle fiche :", emp2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
