"""Marion GAUTHERON (Colorplast), TEST : passe le vendredi 17/07/2026 à 5 h
pointées (au lieu de 4 h 45), regénère juillet et contrôle le brut Quadra.

Retour Gaëlle du 14/09 : seul écart restant sur son brut de juillet, 15 minutes
retenues ce vendredi (3,42 €) que Quadra n'a pas. Sa feuille de pointage dit
5 h (l'OCR avait même lu 6 h). Attendu après regénération : 2 089,06.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipCalendarIncompleteError,
)

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
YEAR, MONTH, JOUR, HEURES = 2026, 7, 17, 5.0
QUADRA_BRUT = 2089.06


def main() -> int:
    apply = "--apply" in sys.argv
    emp = (
        supabase.table("employees")
        .select("id, last_name")
        .eq("company_id", COMPANY_ID)
        .eq("last_name", "GAUTHERON")
        .single()
        .execute()
    ).data
    sched = (
        supabase.table("employee_schedules")
        .select("id, actual_hours")
        .match({"employee_id": emp["id"], "year": YEAR, "month": MONTH})
        .single()
        .execute()
    ).data
    actual = sched["actual_hours"] or {}
    jours = actual.get("calendrier_reel") or []
    jour = next((j for j in jours if int(j.get("jour") or 0) == JOUR), None)
    print(f"17/07 avant : {jour}")
    if not apply:
        print("SIMULATION : rien n'est modifié")
        return 0
    if jour is None:
        jours.append({"jour": JOUR, "type": "travail", "heures_faites": HEURES})
    else:
        jour["heures_faites"] = HEURES
        jour["type"] = "travail"
    actual["calendrier_reel"] = jours
    supabase.table("employee_schedules").update({"actual_hours": actual}).eq("id", sched["id"]).execute()
    print(f"17/07 après : {HEURES} h")

    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=emp["id"],
                year=YEAR,
                month=MONTH,
                force_calendrier_incomplet=force,
                requested_by_name="script gautheron_17_07_test",
            )
        )

    try:
        result = _run(False)
    except PayslipCalendarIncompleteError:
        result = _run(True)
    print(f"génération : {result.status}")

    data = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": emp["id"], "year": YEAR, "month": MONTH})
        .single()
        .execute()
    ).data["payslip_data"]
    brut = float(data.get("salaire_brut") or 0)
    for ligne in data.get("details_absences") or []:
        print(f"  {str(ligne.get('libelle'))[:58]:58s} q={ligne.get('quantite')} -{ligne.get('perte')}")
    print(f"brut EYWAI {brut:.2f} — Quadra {QUADRA_BRUT:.2f} — écart {brut - QUADRA_BRUT:+.2f}")
    if abs(brut - QUADRA_BRUT) > 0.01:
        print("::error::Marion ne converge pas")
        return 1
    print("OK : Marion au centime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
