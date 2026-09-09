"""
Avant/après du changement de rattachement, sur la BASE DE TEST.

Le bulletin porte désormais le mois civil et seules les heures sup et les
paniers suivent la fenêtre des variables. La question : qu'est-ce que ça
déplace réellement, sur de vrais bulletins ?

Deux cas, dont un témoin :
- Colorplast 05/2026 (arrêté glissant, 7 bulletins) : les deux fenêtres
  diffèrent, des écarts sont ATTENDUS et doivent porter sur les heures sup ;
- MAJI 01/2026 (mois civil, 1 bulletin) : les deux fenêtres coïncident, il ne
  doit y avoir AUCUN écart. Sans ce témoin, un « rien n'a bougé » côté
  Colorplast ne prouverait rien.

La comparaison porte sur l'INTÉGRALITÉ de `payslip_data`, feuille par feuille,
et non sur une liste de champs choisis d'avance : un écart ne peut pas passer
entre les mailles.

Sans `--apply` : lecture seule (fenêtres résolues, inventaire des bulletins).
Avec `--apply` : régénère puis affiche chaque valeur qui a changé.

Usage (via .github/workflows/script-env-test.yml) :
    python scripts/verif_rattachement_fenetre.py [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payroll.application.periode_variables_service import (  # noqa: E402
    resoudre_fenetre_variables,
)

#: (société, année, mois, ce qu'on attend)
CAS = [
    ("Colorplast", 2026, 5, "arrêté glissant — des écarts sur les heures sup sont attendus"),
    ("MAJI", 2026, 1, "mois civil — AUCUN écart ne doit apparaître"),
]

#: Clés dont la valeur bouge à chaque génération sans rien dire de la paie.
VOLATILES = {
    "generated_at",
    "date_generation",
    "created_at",
    "updated_at",
    "id",
    "uuid",
    "timestamp",
}


def _feuilles(donnees: Any, chemin: str = "") -> Iterator[tuple[str, Any]]:
    """Aplatit une structure imbriquée en (chemin, valeur terminale)."""
    if isinstance(donnees, dict):
        for cle, valeur in donnees.items():
            if str(cle).lower() in VOLATILES:
                continue
            yield from _feuilles(valeur, f"{chemin}.{cle}" if chemin else str(cle))
    elif isinstance(donnees, list):
        for i, valeur in enumerate(donnees):
            yield from _feuilles(valeur, f"{chemin}[{i}]")
    else:
        yield chemin, donnees


def _bulletin(employee_id: str, annee: int, mois: int) -> dict[str, Any] | None:
    res = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": employee_id, "year": annee, "month": mois})
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        return None
    donnees = res.data.get("payslip_data")
    return donnees if isinstance(donnees, dict) else None


def _ecarts(avant: dict | None, apres: dict | None) -> list[str]:
    if avant is None or apres is None:
        return ["bulletin absent avant ou après"]
    a = dict(_feuilles(avant))
    b = dict(_feuilles(apres))
    lignes = []
    for chemin in sorted(set(a) | set(b)):
        va, vb = a.get(chemin, "∅"), b.get(chemin, "∅")
        if va != vb:
            lignes.append(f"{chemin} : {va} → {vb}")
    return lignes


def _salaries(company_id: str) -> list[dict[str, Any]]:
    res = (
        supabase.table("employees")
        .select("id, last_name, is_forfait_jour")
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


def _regenerer(employee_id: str, forfait_jour: Any, annee: int, mois: int) -> str:
    est_forfait = bool(forfait_jour)
    try:
        if est_forfait:
            from app.modules.payroll.documents.payslip_generator_forfait import (
                process_payslip_generation_forfait,
            )

            process_payslip_generation_forfait(employee_id, annee, mois)
        else:
            from app.modules.payroll.documents.payslip_generator import (
                process_payslip_generation,
            )

            process_payslip_generation(employee_id, annee, mois)
        return "ok"
    except Exception as exc:  # noqa: BLE001 — on veut le rapport complet
        return f"ÉCHEC : {exc}"


def main() -> None:
    appliquer = "--apply" in sys.argv
    print("=== Rattachement fenêtre / mois civil — base de TEST ===")
    print("Mode :", "RÉGÉNÉRATION" if appliquer else "lecture seule")

    total_modifies = 0
    for nom, annee, mois, attendu in CAS:
        societe = _societe(nom)
        if not societe:
            print(f"\n--- {nom} : société introuvable")
            continue

        fenetre = resoudre_fenetre_variables(
            str(societe["id"]), annee, mois, societe=societe
        )
        print(f"\n--- {nom} {mois:02d}/{annee} ({attendu})")
        print(
            f"    réglage   : jour_de_fin={societe.get('paie_jour_de_fin')} "
            f"occurrence={societe.get('paie_occurrence')}"
        )
        print(f"    variables : {fenetre.debut:%d/%m/%Y} → {fenetre.fin:%d/%m/%Y} ({fenetre.origine})")

        salaries = _salaries(str(societe["id"]))
        avant = {}
        for s in salaries:
            b = _bulletin(str(s["id"]), annee, mois)
            if b is not None:
                avant[str(s["id"])] = b
        print(f"    bulletins : {len(avant)}")

        if not appliquer:
            for s in salaries:
                if str(s["id"]) in avant:
                    print(f"      {s['last_name']}")
            continue

        for s in salaries:
            if str(s["id"]) not in avant:
                continue
            etat = _regenerer(str(s["id"]), s.get("is_forfait_jour"), annee, mois)
            if etat != "ok":
                print(f"    {s['last_name']:<14} {etat}")

        for s in salaries:
            eid = str(s["id"])
            if eid not in avant:
                continue
            lignes = _ecarts(avant[eid], _bulletin(eid, annee, mois))
            if lignes:
                total_modifies += 1
                print(f"    ⚠ {s['last_name']} — {len(lignes)} valeur(s) changée(s) :")
                for ligne in lignes[:25]:
                    print(f"        {ligne}")
                if len(lignes) > 25:
                    print(f"        … et {len(lignes) - 25} autres")
            else:
                print(f"      {s['last_name']} : bulletin identique au bit près")

    if appliquer:
        print(f"\n=== {total_modifies} bulletin(s) modifié(s) ===")
        print("Attendu : des écarts sur Colorplast, AUCUN sur MAJI.")


if __name__ == "__main__":
    main()
