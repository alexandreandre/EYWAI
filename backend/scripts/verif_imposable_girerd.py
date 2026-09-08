"""Régénère le bulletin de juillet 2026 de GIRERD et relève son net imposable.

But : constater le chiffre réel après le correctif « part salariale de mutuelle
non déductible », au lieu de le prédire depuis les tests unitaires.

Bulletin de référence du service paie (Quadra, juillet 2026) :
  net imposable 2 668,88 € · PAS 114,76 € · net à payer 3 080,74 €
Avant correctif, EYWAI produisait 2 570,73 € / 110,54 € / 3 084,92 €.

Le bulletin visé est un BROUILLON sans édition manuelle (vérifié le 08/09/2026 :
manually_edited=false, edit_count=0) ; le régénérer n'écrase donc aucune
saisie. À lancer sur l'environnement de TEST via `script-env-test.yml`.

Usage : python scripts/verif_imposable_girerd.py [--apply]
        (sans --apply : n'affiche que l'état actuel, ne régénère rien)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402

ANNEE, MOIS = 2026, 7
CIBLE_CABINET = {"net_imposable": 2668.88, "pas": 114.76, "net_a_payer": 3080.74}
AVANT_CORRECTIF = {"net_imposable": 2570.73, "pas": 110.54, "net_a_payer": 3084.92}


def _lire_bulletin(employee_id: str) -> dict | None:
    res = (
        supabase.table("payslips")
        .select("payslip_data, status, manually_edited, edit_count, updated_at")
        .eq("employee_id", employee_id)
        .eq("year", ANNEE)
        .eq("month", MOIS)
        .maybe_single()
        .execute()
    )
    return res.data if res else None


def _chiffres(bulletin: dict) -> dict:
    data = bulletin.get("payslip_data") or {}
    synthese = data.get("synthese_net") or {}
    pas = (synthese.get("impot_prelevement_a_la_source") or {}).get("montant")
    return {
        "net_imposable": synthese.get("net_imposable"),
        "pas": pas,
        "net_a_payer": data.get("net_a_payer"),
    }


def _lignes_mutuelle(bulletin: dict) -> list[str]:
    data = bulletin.get("payslip_data") or {}
    bloc = (data.get("structure_cotisations") or {}).get("bloc_principales") or []
    return [
        f"{l.get('libelle')} → salarial {l.get('montant_salarial')} "
        f"/ patronal {l.get('montant_patronal')}"
        for l in bloc
        if "mutuelle" in str(l.get("libelle", "")).lower()
        or "famille" in str(l.get("libelle", "")).lower()
    ]


def main() -> int:
    apply = "--apply" in sys.argv

    emp = (
        supabase.table("employees")
        .select("id, first_name, last_name, company_id")
        .ilike("last_name", "GIRERD")
        .maybe_single()
        .execute()
    ).data
    if not emp:
        print("REFUS : GIRERD introuvable.")
        return 1
    employee_id = str(emp["id"])

    avant = _lire_bulletin(employee_id)
    if not avant:
        print(f"REFUS : aucun bulletin {MOIS:02d}/{ANNEE} pour GIRERD.")
        return 1
    if avant.get("manually_edited"):
        print("REFUS : bulletin édité à la main, régénérer l'écraserait.")
        return 1

    print(f"AVANT  ({avant.get('status')}, maj {avant.get('updated_at')}) : {_chiffres(avant)}")
    for ligne in _lignes_mutuelle(avant):
        print(f"  {ligne}")

    if not apply:
        print("\nSimulation — aucune régénération. Relancer avec --apply.")
        return 0

    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation,
    )

    print(f"\nRégénération de {MOIS:02d}/{ANNEE}…")
    process_payslip_generation(employee_id, ANNEE, MOIS)

    apres = _lire_bulletin(employee_id)
    if not apres:
        print("ÉCHEC : bulletin introuvable après régénération.")
        return 1
    chiffres = _chiffres(apres)
    print(f"APRÈS  : {chiffres}")
    for ligne in _lignes_mutuelle(apres):
        print(f"  {ligne}")

    print("\nComparaison au bulletin du service paie :")
    ecarts = []
    for cle, attendu in CIBLE_CABINET.items():
        obtenu = float(chiffres.get(cle) or 0)
        ecart = round(obtenu - attendu, 2)
        print(f"  {cle:<15} {obtenu:>10.2f}  vs {attendu:>10.2f}  écart {ecart:+.2f}")
        if abs(ecart) > 0.05:
            ecarts.append(f"{cle} : {ecart:+.2f} €")

    if ecarts:
        print("\nÉCARTS au-delà de 5 centimes : " + " · ".join(ecarts))
        return 1
    print("\nConvergence au centime près (tolérance 0,05 €).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
