"""Régénère le bulletin d'un salarié et relève ses lignes de congés payés.

Contrôle de bout en bout du correctif « les congés posés depuis le module
Absences atteignent le bulletin » : on compte les jours de congé au planning,
on régénère, puis on lit les lignes réellement produites.

Refuse de tourner sur un bulletin édité à la main (la régénération écraserait
les saisies).

Usage : python scripts/verif_conges_regeneration.py --salarie BUGNY --mois 2026-08 [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402

DEFAUT_SALARIE = "BUGNY"
DEFAUT_MOIS = "2026-08"


def _arg(nom: str, defaut: str) -> str:
    if nom in sys.argv:
        i = sys.argv.index(nom)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return defaut


def _lignes_conges(bulletin: dict | None) -> list[str]:
    if not bulletin:
        return []
    details = (bulletin.get("payslip_data") or {}).get("details_conges") or []
    return [
        f"{l.get('libelle')} · qté {l.get('quantite')} · "
        f"gain {l.get('gain')} · perte {l.get('perte')}"
        for l in details
    ]


def _bulletin(employee_id: str, annee: int, mois: int) -> dict | None:
    res = (
        supabase.table("payslips")
        .select("payslip_data, status, manually_edited, updated_at")
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .maybe_single()
        .execute()
    )
    return res.data if res else None


def main() -> int:
    apply = "--apply" in sys.argv
    nom = _arg("--salarie", DEFAUT_SALARIE)
    annee, mois = (int(x) for x in _arg("--mois", DEFAUT_MOIS).split("-"))

    emp = (
        supabase.table("employees")
        .select("id, first_name, last_name")
        .ilike("last_name", nom)
        .maybe_single()
        .execute()
    ).data
    if not emp:
        print(f"REFUS : salarié « {nom} » introuvable.")
        return 1
    employee_id = str(emp["id"])

    planning = (
        supabase.table("employee_schedules")
        .select("planned_calendar")
        .eq("employee_id", employee_id)
        .eq("year", annee)
        .eq("month", mois)
        .maybe_single()
        .execute()
    ).data
    jours = [
        int(e["jour"])
        for e in ((planning or {}).get("planned_calendar") or {}).get(
            "calendrier_prevu", []
        )
        if e.get("type") == "conges_payes"
    ]
    print(
        f"{emp['first_name']} {emp['last_name']} — {mois:02d}/{annee} : "
        f"{len(jours)} jour(s) de congé au planning "
        + (f"({', '.join(f'{j:02d}' for j in sorted(jours))})" if jours else "")
    )

    avant = _bulletin(employee_id, annee, mois)
    if not avant:
        print("REFUS : aucun bulletin sur ce mois.")
        return 1
    if avant.get("manually_edited"):
        print("REFUS : bulletin édité à la main, régénérer l'écraserait.")
        return 1

    lignes_avant = _lignes_conges(avant)
    print(f"\nAVANT ({avant.get('status')}, maj {avant.get('updated_at')}) : "
          f"{len(lignes_avant)} ligne(s) de congés")
    for l in lignes_avant:
        print(f"  {l}")

    if not apply:
        print("\nSimulation — aucune régénération. Relancer avec --apply.")
        return 0

    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation,
    )

    print("\nRégénération…")
    process_payslip_generation(employee_id, annee, mois)

    apres = _bulletin(employee_id, annee, mois)
    lignes_apres = _lignes_conges(apres)
    print(f"APRÈS : {len(lignes_apres)} ligne(s) de congés")
    for l in lignes_apres:
        print(f"  {l}")

    if jours and not lignes_apres:
        print("\nÉCHEC : des congés au planning, aucune ligne au bulletin.")
        return 1
    print("\nLes congés atteignent le bulletin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
