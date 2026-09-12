"""Passe les usines de Gaëlle en congés décomptés en jours ouvrés (2,083 j/mois).

Retour Gaëlle du 12/09/2026 (Girerd, juillet) : « chez MAJI on a 2,08 jours
de congés par mois et non 2,5 ; quand on pose une semaine c'est 5 jours,
soit 25 jours par an ». Toutes les sociétés étaient paramétrées en jours
ouvrables (2,5). Elsa a confirmé « jours ouvrés » pour toutes les boîtes ;
MAJI et ZONE 404 (Vanessa) ne sont pas touchées ici, à confirmer avec elle.

Passe par `update_leave_settings`, comme l'écran Entreprise → Congés : le
taux légal de l'unité est posé (2,083) et les compteurs repris d'un bulletin
sont réexprimés pour ne pas bouger (cf. `rebaser_reprises_cp`).

Exécuté en CI contre la base de l'environnement de TEST via
`script-env-test.yml` (les identifiants de test ne vivent que dans les
secrets GitHub). Usage : python scripts/usines_jours_ouvres.py [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.absences.application.leave_settings_commands import (  # noqa: E402
    update_leave_settings,
)
from app.modules.absences.infrastructure.leave_settings_repository import (  # noqa: E402
    get_leave_policy,
    list_company_adjustments_avec_reference,
)
from app.modules.absences.schemas.leave_settings import LeaveSettingsUpdate  # noqa: E402

USINES = ("Cartol Industrie", "Colorplast", "Comitech Composite", "LEWIS", "Mont Blanc Composite")


def main() -> int:
    apply = "--apply" in sys.argv
    rows = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("company_name", list(USINES))
        .execute()
    ).data or []
    if len(rows) != len(USINES):
        trouvees = sorted(r["company_name"] for r in rows)
        print(f"::error::Sociétés trouvées {trouvees}, attendues {sorted(USINES)}")
        return 1

    for row in sorted(rows, key=lambda r: r["company_name"]):
        company_id, nom = row["id"], row["company_name"]
        avant = get_leave_policy(company_id)
        reprises = len(list_company_adjustments_avec_reference(company_id))
        print(
            f"{nom:22s} avant : {avant.cp_counting_unit} "
            f"{avant.cp_acquisition_days_per_month} j/mois — {reprises} compteurs repris datés"
        )
        if avant.cp_counting_unit == "ouvre":
            print(f"{'':22s} déjà en jours ouvrés, rien à faire")
            continue
        if not apply:
            print(f"{'':22s} SIMULATION : passerait en ouvrés 2,083 (recalage des reprises)")
            continue
        update_leave_settings(company_id, LeaveSettingsUpdate(cp_counting_unit="ouvre"))
        apres = get_leave_policy(company_id)
        print(
            f"{'':22s} après : {apres.cp_counting_unit} "
            f"{apres.cp_acquisition_days_per_month} j/mois, "
            f"{apres.cp_annual_days_display} j/an"
        )
    print("Terminé (" + ("APPLIQUÉ" if apply else "simulation") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
