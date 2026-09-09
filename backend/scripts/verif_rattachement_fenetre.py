"""
Avant/après du changement de rattachement, sur la BASE DE TEST.

Le bulletin porte désormais le mois civil et seules les heures sup et les
paniers suivent la fenêtre des variables. La question à laquelle ce script
répond : qu'est-ce que ça déplace réellement, sur de vrais bulletins ?

Deux sociétés sont examinées :
- une à arrêté glissant (Colorplast, `paie_jour_de_fin` 4 / occurrence -2) :
  les deux fenêtres diffèrent, des écarts sont ATTENDUS et doivent porter sur
  les heures supplémentaires ;
- une au mois civil (Comitech) : les deux fenêtres coïncident, il ne doit y
  avoir AUCUN écart. C'est le témoin — sans lui, un « rien n'a bougé » ne
  prouverait rien.

Sans `--apply` : lecture seule (fenêtres résolues + totaux actuels).
Avec `--apply` : régénère les bulletins et affiche l'avant/après.

Usage (via .github/workflows/script-env-test.yml) :
    python scripts/verif_rattachement_fenetre.py [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payroll.application.periode_variables_service import (  # noqa: E402
    resoudre_fenetre_variables,
)

ANNEE = 2026
MOIS = 5

#: (nom de société, ce qu'on attend du témoin)
SOCIETES = [
    ("Colorplast", "arrêté glissant — des écarts sur les heures sup sont attendus"),
    ("Comitech Composite", "mois civil — AUCUN écart ne doit apparaître"),
]

#: Grandeurs comparées, cherchées où qu'elles soient dans payslip_data.
CHAMPS = (
    "salaire_brut_total",
    "net_imposable",
    "net_a_payer",
    "total_heures_supp",
    "remuneration_brute_heures_supp",
)


def _chercher(donnees: Any, champ: str) -> float | None:
    """Première valeur numérique trouvée pour `champ`, à n'importe quelle profondeur."""
    if isinstance(donnees, dict):
        valeur = donnees.get(champ)
        if isinstance(valeur, (int, float)):
            return round(float(valeur), 2)
        for sous in donnees.values():
            trouve = _chercher(sous, champ)
            if trouve is not None:
                return trouve
    elif isinstance(donnees, list):
        for sous in donnees:
            trouve = _chercher(sous, champ)
            if trouve is not None:
                return trouve
    return None


def _totaux(employee_id: str) -> dict[str, float | None]:
    res = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": employee_id, "year": ANNEE, "month": MOIS})
        .maybe_single()
        .execute()
    )
    donnees = (res.data or {}).get("payslip_data") if res and res.data else None
    return {champ: _chercher(donnees, champ) for champ in CHAMPS}


def _salaries(company_id: str) -> list[dict[str, Any]]:
    res = (
        supabase.table("employees")
        .select("id, last_name, first_name, statut")
        .eq("company_id", company_id)
        .execute()
    )
    return sorted(res.data or [], key=lambda e: str(e.get("last_name") or ""))


def _societe(nom: str) -> dict[str, Any] | None:
    res = (
        supabase.table("companies")
        .select("id, company_name, paie_jour_de_fin, paie_occurrence")
        .eq("company_name", nom)
        .maybe_single()
        .execute()
    )
    return res.data if res and res.data else None


def _regenerer(employee_id: str, statut: str | None) -> str:
    est_forfait = str(statut or "").lower().startswith("cadre")
    try:
        if est_forfait:
            from app.modules.payroll.documents.payslip_generator_forfait import (
                process_payslip_generation_forfait,
            )

            process_payslip_generation_forfait(employee_id, ANNEE, MOIS)
        else:
            from app.modules.payroll.documents.payslip_generator import (
                process_payslip_generation,
            )

            process_payslip_generation(employee_id, ANNEE, MOIS)
        return "ok"
    except Exception as exc:  # noqa: BLE001 — on veut le rapport complet
        return f"échec : {exc}"


def main() -> None:
    appliquer = "--apply" in sys.argv
    print(f"=== Rattachement fenêtre / mois civil — {MOIS:02d}/{ANNEE} ===")
    print("Mode :", "RÉGÉNÉRATION (écrit sur la base de test)" if appliquer else "lecture seule")

    ecarts_totaux = 0
    for nom, attendu in SOCIETES:
        societe = _societe(nom)
        if not societe:
            print(f"\n--- {nom} : société introuvable, ignorée")
            continue

        fenetre = resoudre_fenetre_variables(
            str(societe["id"]), ANNEE, MOIS, societe=societe
        )
        print(f"\n--- {nom} ({attendu})")
        print(
            f"    réglage : jour_de_fin={societe.get('paie_jour_de_fin')} "
            f"occurrence={societe.get('paie_occurrence')}"
        )
        print(f"    bulletin  : 01/{MOIS:02d}/{ANNEE} → fin du mois")
        print(f"    variables : {fenetre.debut:%d/%m/%Y} → {fenetre.fin:%d/%m/%Y} ({fenetre.origine})")

        salaries = _salaries(str(societe["id"]))
        avant = {str(s["id"]): _totaux(str(s["id"])) for s in salaries}

        if not appliquer:
            for s in salaries:
                t = avant[str(s["id"])]
                if all(v is None for v in t.values()):
                    continue
                print(f"    {s['last_name']:<14} " + "  ".join(
                    f"{c}={t[c]}" for c in CHAMPS if t[c] is not None
                ))
            continue

        for s in salaries:
            etat = _regenerer(str(s["id"]), s.get("statut"))
            if etat != "ok":
                print(f"    {s['last_name']:<14} {etat}")

        for s in salaries:
            eid = str(s["id"])
            apres = _totaux(eid)
            lignes = []
            for champ in CHAMPS:
                a, b = avant[eid][champ], apres[champ]
                if a is None and b is None:
                    continue
                if a != b:
                    lignes.append(f"{champ} : {a} → {b}")
            if lignes:
                ecarts_totaux += 1
                print(f"    ⚠ {s['last_name']:<14} " + " | ".join(lignes))
            else:
                print(f"      {s['last_name']:<14} inchangé")

    if appliquer:
        print(f"\n=== {ecarts_totaux} bulletin(s) modifié(s) ===")
        print("Attendu : des écarts sur Colorplast (heures sup), AUCUN sur Comitech.")


if __name__ == "__main__":
    main()
