"""Vérifie, contre les données réelles d'un environnement, qu'un congé validé
atteint bien le moteur de paie.

LECTURE SEULE : aucune écriture, aucun bulletin produit. On rejoue le maillon
qui avait cassé — étiquetage `source_absence` depuis les demandes validées,
puis agrégation de l'analyzer — et on vérifie que le jour de congé survit.

Le bug du 07-08/09/2026 : l'étiquetage échouait silencieusement, donc tout
congé projeté à 0 h disparaissait du bulletin. Les tests unitaires ne
pouvaient pas le voir (ils travaillent en mémoire) ; seul un passage contre
une vraie base le montre. D'où ce script, à relancer après toute évolution
touchant les congés, le calendrier ou la validation d'absence.

Usage : python scripts/verif_conges_au_bulletin.py [--societe NOM] [--mois AAAA-MM]
        (par défaut : Colorplast, juillet et août 2026)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payroll.application.analyzer import (  # noqa: E402
    analyser_horaires_du_mois,
)
from app.modules.payroll.documents.payslip_generator import (  # noqa: E402
    _stamp_source_absence_conges,
)

SOCIETE_DEFAUT = "Colorplast"
MOIS_DEFAUT = [(2026, 7), (2026, 8)]


def _arg(nom: str) -> str | None:
    if nom in sys.argv:
        i = sys.argv.index(nom)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def _entrees(planned_calendar: Any) -> list[dict]:
    if not isinstance(planned_calendar, dict):
        return []
    entries = planned_calendar.get("calendrier_prevu")
    return entries if isinstance(entries, list) else []


def main() -> int:
    societe = _arg("--societe") or SOCIETE_DEFAUT
    if _arg("--mois"):
        annee_s, mois_s = str(_arg("--mois")).split("-")
        mois_a_verifier = [(int(annee_s), int(mois_s))]
    else:
        mois_a_verifier = MOIS_DEFAUT

    comp = (
        supabase.table("companies")
        .select("id, company_name")
        .eq("company_name", societe)
        .maybe_single()
        .execute()
    ).data
    if not comp:
        print(f"REFUS : société « {societe} » introuvable.")
        return 1
    company_id = str(comp["id"])

    employes = (
        supabase.table("employees")
        .select("id, first_name, last_name, duree_hebdomadaire, statut")
        .eq("company_id", company_id)
        .execute()
    ).data or []

    total_jours = 0
    total_survivants = 0
    anomalies: list[str] = []

    for annee, mois in mois_a_verifier:
        print(f"\n=== {societe} — {mois:02d}/{annee} ===")
        for emp in sorted(employes, key=lambda e: e["last_name"]):
            emp_id = str(emp["id"])
            rows = (
                supabase.table("employee_schedules")
                .select("year, month, planned_calendar, actual_hours")
                .eq("employee_id", emp_id)
                .eq("year", annee)
                .eq("month", mois)
                .execute()
            ).data or []
            if not rows:
                continue

            planned: list[dict] = []
            actual: list[dict] = []
            for row in rows:
                for e in _entrees(row.get("planned_calendar")):
                    planned.append({**e, "annee": annee, "mois": mois})
                reel = (row.get("actual_hours") or {}).get("calendrier_reel") or []
                for e in reel:
                    actual.append({**e, "annee": annee, "mois": mois})

            jours_cp = [e for e in planned if e.get("type") == "conges_payes"]
            if not jours_cp:
                continue

            # Le maillon qui avait cassé — il doit lever s'il ne peut pas lire.
            _stamp_source_absence_conges(planned, emp_id)
            etiquetes = [e for e in jours_cp if e.get("source_absence")]

            evenements = analyser_horaires_du_mois(
                planned,
                actual,
                float(emp.get("duree_hebdomadaire") or 35),
                annee,
                mois,
                f"{emp['first_name']} {emp['last_name']}",
            )
            survivants = [e for e in evenements if e.get("type") == "conges_payes"]

            total_jours += len(jours_cp)
            total_survivants += len(survivants)

            etat = "OK " if len(survivants) == len(jours_cp) else "ÉCART"
            print(
                f"  {etat} {emp['last_name']:<12} {len(jours_cp):>2} jour(s) de congé "
                f"au planning · {len(etiquetes):>2} étiqueté(s) · "
                f"{len(survivants):>2} atteignant le bulletin"
            )
            if len(survivants) != len(jours_cp):
                perdus = sorted(
                    {int(e["jour"]) for e in jours_cp}
                    - {int(e["jour"]) for e in survivants}
                )
                anomalies.append(
                    f"{emp['last_name']} {mois:02d}/{annee} : jours perdus {perdus}"
                )

    print(
        f"\nTotal : {total_survivants}/{total_jours} jours de congé atteignent le bulletin."
    )
    if anomalies:
        print("\nÉCARTS :")
        for a in anomalies:
            print(f"  - {a}")
        return 1
    if total_jours == 0:
        print("Aucun jour de congé sur la période — vérification sans objet.")
        return 1
    print("Aucun congé perdu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
