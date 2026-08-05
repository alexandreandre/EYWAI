"""Paramètre les comptes comptables d'une société depuis son plan de comptes.

Le fichier source vit dans `data/<societe>/comptabilite/plan_comptable.json` et
n'est jamais versionné : il contient le paramétrage comptable du client, relevé
sur l'OD de paie que produit son cabinet.

Usage :
    python -m scripts.import_plan_comptable --company-id <uuid> \\
        --file ../data/colorplast/comptabilite/plan_comptable.json [--apply]

Sans --apply, le script affiche ce qu'il ferait sans rien écrire. Vérifiez vers
quel projet Supabase pointe votre configuration avant d'appliquer : backend/.env
pointe sur la production.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from app.core.database import supabase

ORGANISME_RUBRIQUES = {
    "URSSAF": "organisme_urssaf",
    "RETRAITE": "organisme_retraite",
    "RETRAITE_SUP": "organisme_retraite_sup",
    "MUTUELLE": "organisme_mutuelle",
    "PREVOYANCE": "organisme_prevoyance",
}

# type_rubrique est contraint en base : salaire, charge_patronale, dette_salarie,
# dette_organisme, pas, autre.
TYPE_PAR_ELEMENT = {
    "salaire_brut": "salaire",
    "prime_soumise": "salaire",
    "net_a_payer": "dette_salarie",
    "pas": "pas",
    "saisie_opposition": "dette_salarie",
    "note_de_frais": "dette_salarie",
    "indemnite_transport": "autre",
}


def _rows_from_plan(company_id: str, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    journal = str(plan.get("journal") or "OD")
    rows: List[Dict[str, Any]] = []

    for organisme, comptes in (plan.get("organismes") or {}).items():
        rubrique = ORGANISME_RUBRIQUES.get(organisme)
        if not rubrique:
            print(f"  ! organisme inconnu, ignoré : {organisme}", file=sys.stderr)
            continue
        charge = str(comptes.get("compte_charge") or "")
        tiers = str(comptes.get("compte_tiers") or "")
        rows.append(
            {
                "company_id": company_id,
                "rubrique_code": rubrique,
                "rubrique_libelle": comptes.get("libelle") or organisme,
                "compte_comptable": charge or tiers,
                "compte_charge": charge or None,
                "compte_tiers": tiers or None,
                "organisme": organisme,
                "sens": "debit",
                "type_rubrique": "charge_patronale",
                "journal": journal,
                "is_active": True,
            }
        )

    for element, comptes in (plan.get("elements") or {}).items():
        charge = str(comptes.get("compte_charge") or "")
        tiers = str(comptes.get("compte_tiers") or "")
        rows.append(
            {
                "company_id": company_id,
                "rubrique_code": element,
                "rubrique_libelle": element.replace("_", " ").capitalize(),
                "compte_comptable": charge or tiers,
                "compte_charge": charge or None,
                "compte_tiers": tiers or None,
                "organisme": None,
                "sens": "debit" if charge else "credit",
                "type_rubrique": TYPE_PAR_ELEMENT.get(element, "autre"),
                "journal": journal,
                "is_active": True,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    plan = json.loads(args.file.read_text(encoding="utf-8"))
    rows = _rows_from_plan(args.company_id, plan)

    print(f"{plan.get('company_name', '?')} — {len(rows)} rubriques")
    for row in rows:
        print(
            f"  {row['rubrique_code']:<24} charge {row['compte_charge'] or '—':<10} "
            f"tiers {row['compte_tiers'] or '—':<10} journal {row['journal']}"
        )

    a_confirmer = plan.get("a_confirmer") or {}
    if a_confirmer:
        print("\nÀ confirmer auprès du cabinet :")
        for cle, texte in a_confirmer.items():
            print(f"  — {cle} : {texte}")

    if not args.apply:
        print("\nSimulation — relancer avec --apply pour écrire.")
        return 0

    for row in rows:
        existing = (
            supabase.table("accounting_mappings")
            .select("id")
            .eq("company_id", args.company_id)
            .eq("rubrique_code", row["rubrique_code"])
            .execute()
        )
        if existing and existing.data:
            supabase.table("accounting_mappings").update(row).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            supabase.table("accounting_mappings").insert(row).execute()
    print(f"\n{len(rows)} rubriques écrites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
