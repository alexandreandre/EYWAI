"""Remet le paramétrage du maintien de salaire de Colorplast tel qu'il était.

Le 15/09/2026, le réglage a été poussé à « 3 jours à 100 %, sans carence » pour
essayer de reproduire le bulletin de mars de Gautheron. Le moteur a refusé :
3 jours à 100 % valent moins que le plancher légal (90 % pendant 30 jours pour
plus d'un an d'ancienneté), il signale `conflit_convention` et retient le
légal — ce qui est le comportement voulu.

Tant que la question n'est pas tranchée avec Gaëlle (qui verse le complément
au-delà du 3ᵉ jour : la prévoyance GAN ?), la fiche revient à son état
antérieur plutôt que de porter une convention qu'on ne sait pas justifier.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
ETAT_ANTERIEUR = {
    "remove_employer_waiting": False,
    "maintain_100_percent": False,
    "custom_duration_days": None,
}
LIGNES_LUES = (
    "company_id, apply_legal_maintenance, remove_employer_waiting, "
    "maintain_100_percent, custom_duration_days, employer_waiting_days, "
    "min_seniority_months, subrogation_mode, provident_relay_days"
)


def main() -> int:
    admin = get_supabase_admin_client()
    avant = (
        admin.table("company_maintenance_settings").select(LIGNES_LUES)
        .eq("company_id", COMPANY_ID).maybe_single().execute()
    )
    if not avant or not avant.data:
        print("::error::Aucun paramétrage de maintien pour Colorplast.")
        return 1
    print("Avant :")
    for cle, valeur in sorted(avant.data.items()):
        print(f"  {cle:28s} {valeur}")
    if "--apply" not in sys.argv:
        print(f"\nSIMULATION : rien n'est écrit. À poser : {ETAT_ANTERIEUR}")
        return 0

    admin.table("company_maintenance_settings").update(ETAT_ANTERIEUR).eq(
        "company_id", COMPANY_ID
    ).execute()
    apres = (
        admin.table("company_maintenance_settings").select(LIGNES_LUES)
        .eq("company_id", COMPANY_ID).maybe_single().execute()
    ).data
    print("\nAprès :")
    for cle, valeur in sorted(apres.items()):
        print(f"  {cle:28s} {valeur}")
    rc = 0
    for cle, attendu in ETAT_ANTERIEUR.items():
        if apres.get(cle) != attendu:
            print(f"::error::{cle} vaut {apres.get(cle)}, attendu {attendu}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
