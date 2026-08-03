"""Congés payés d'ancienneté : paramétrage des sociétés (point #19).

Contexte
--------
Seule Comitech avait un paramétrage de congés d'ancienneté. Les six autres
sociétés n'avaient aucune ligne, donc aucun jour accordé — alors que Cegid en
crédite bien à la clôture du 31 mai.

La règle vient d'Elsa (WhatsApp du 19/06/2026) : c'est l'article 89 de la
convention métallurgie, en jours ouvrables, cumulatif :

    + 1 jour   à partir de 2 ans d'ancienneté
    + 1 jour   à partir de 2 ans d'ancienneté et 45 ans
    + 1 jour   à partir de 20 ans d'ancienneté et 55 ans
    + 1 jour   pour les forfaits annuels ayant 1 an d'ancienneté

Elle ne vaut que pour la métallurgie (Cartol, LEWIS). Les sociétés de la
plasturgie reprennent le barème de leur convention, déjà appliqué chez
Comitech.

Vérification
------------
Le barème a été confronté aux bulletins Cegid de Cartol : sur les 19 salariés
dont le compteur est lisible sans historique N-1, 18 tombent juste, et le seul
écart est un homonyme mal apparié. L'ancienneté retenue est celle acquise dans
la société : y ajouter `prior_service_months` faisait échouer trois cas, ce
champ contenant déjà l'ancienneté reprise.

Usage
-----
    python scripts/setup_cp_anciennete.py            # simulation
    python scripts/setup_cp_anciennete.py --apply    # écriture + sauvegarde
    python scripts/setup_cp_anciennete.py --revert FICHIER
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.absences.domain.cp_seniority_resolver import (  # noqa: E402
    METALLURGIE_3248_RULES,
    PLASTURGIE_0292_RULES,
)
from app.modules.absences.infrastructure.cp_seniority_repository import (  # noqa: E402
    get_cp_seniority_settings_row,
    upsert_cp_seniority_settings,
)

PRESET_PAR_IDCC = {
    "3248": ("metallurgie_idcc_3248", METALLURGIE_3248_RULES),
    "0292": ("plasturgie_idcc_0292", PLASTURGIE_0292_RULES),
}

FORFAIT_PAR_SOCIETE = {"Cartol Industrie": 214.0}
FORFAIT_DEFAUT = 216.0


def _cible(company: dict) -> dict | None:
    idcc = (company.get("idcc") or "").strip()
    preset = PRESET_PAR_IDCC.get(idcc)
    if not preset:
        return None
    nom = company["company_name"]
    return {
        "enabled": True,
        "preset": preset[0],
        "rules": preset[1],
        "seniority_reference": "cp_period_end",
        # `prior_service_months` contient déjà l'ancienneté reprise : l'ajouter
        # doublerait le compte et fait échouer la confrontation aux bulletins.
        "seniority_basis": "company_only",
        "counting_unit": "ouvrable",
        "forfait_annual_days_default": FORFAIT_PAR_SOCIETE.get(nom, FORFAIT_DEFAUT),
        "forfait_reduction_enabled": True,
        "company_agreement_overrides": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="écrit en base")
    parser.add_argument("--revert", metavar="FICHIER", help="restaure une sauvegarde")
    args = parser.parse_args()

    if args.revert:
        sauvegarde = json.loads(Path(args.revert).read_text())
        for entree in sauvegarde:
            if entree["avant"] is None:
                supabase.table("company_cp_seniority_settings").delete().eq(
                    "company_id", entree["company_id"]
                ).execute()
                print(f"  {entree['company_name']} : paramétrage supprimé")
            else:
                upsert_cp_seniority_settings(entree["company_id"], entree["avant"])
                print(f"  {entree['company_name']} : paramétrage restauré")
        return

    companies = supabase.table("companies").select("id, company_name, idcc").execute().data or []
    sauvegarde: list[dict] = []
    for company in sorted(companies, key=lambda c: c["company_name"]):
        cid = str(company["id"])
        nom = company["company_name"]
        cible = _cible(company)
        if not cible:
            print(f"  {nom:<24} IDCC absent ou inconnu → laissé tel quel")
            continue
        avant = get_cp_seniority_settings_row(cid)
        if avant and avant.get("enabled") and avant.get("preset") == cible["preset"]:
            print(f"  {nom:<24} déjà paramétré ({cible['preset']})")
            continue
        print(
            f"  {nom:<24} → {cible['preset']}"
            f" (forfait {cible['forfait_annual_days_default']:.0f} j)"
            + ("" if args.apply else "   [simulation]")
        )
        sauvegarde.append({"company_id": cid, "company_name": nom, "avant": avant})
        if args.apply:
            upsert_cp_seniority_settings(cid, cible)

    if args.apply and sauvegarde:
        horodatage = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        chemin = Path(f"cp_anciennete_avant_{horodatage}.json")
        chemin.write_text(json.dumps(sauvegarde, indent=2, default=str))
        print(f"\nSauvegarde : {chemin}")
    elif not args.apply:
        print("\nSimulation — relancer avec --apply pour écrire.")


if __name__ == "__main__":
    main()
