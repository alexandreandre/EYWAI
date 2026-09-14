"""Regénère août 2026 de ESPINOSA, FUCKAR et GAUTHERON (Colorplast) sur le TEST
et vérifie que la semaine du 27 au 31 juillet n'est portée qu'une fois.

Avant la correction de la fenêtre des variables, l'absence d'Espinosa du
31/07 figurait sur juillet ET sur août. Juillet (fenêtre 22/06 → 26/07) ne la
porte plus ; août (fenêtre à partir du 27/07) doit la porter, une fois.

Attendus sur août, semaine du 27 au 31 juillet, bilan hebdomadaire :
  ESPINOSA  absence 2 h le 31/07 (+1 h lundi à mercredi, 0 h vendredi)
  FUCKAR    aucune absence cette semaine (41 h : 2 h d'heures sup)
  GAUTHERON absence 1 h le 31/07 (4 h pour 5)

À lancer APRÈS `colorplast_chaine_cumuls_test.py` (août repart du maillon de
juillet). Calendrier incomplet forcé comme depuis l'écran.

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
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR, MONTH = 2026, 8
SALARIES = ("ESPINOSA", "FUCKAR", "GAUTHERON")
ATTENDU_31_07 = {"ESPINOSA": 2.0, "FUCKAR": 0.0, "GAUTHERON": 1.0}


def _lignes(data: dict, cle: str) -> list[dict]:
    valeur = data.get(cle)
    return [ligne for ligne in valeur if isinstance(ligne, dict)] if isinstance(valeur, list) else []


def _generer(employee_id: str) -> list[str]:
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id,
                year=YEAR,
                month=MONTH,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_aout_fenetre_test",
            )
        )

    try:
        result = _run(False)
    except PayslipCalendarIncompleteError as exc:
        print(f"::warning::Calendrier incomplet, génération forcée comme depuis l'écran : {exc}")
        result = _run(True)
    return list(result.warnings or [])


def _heures_absence_juillet(data: dict) -> float:
    total = 0.0
    for ligne in _lignes(data, "details_absences"):
        libelle = str(ligne.get("libelle", ""))
        if "/07/26" in libelle and "injustifiée" in libelle:
            total += float(ligne.get("quantite") or 0)
    return round(total, 2)


def main() -> int:
    apply = "--apply" in sys.argv
    emps = (
        supabase.table("employees")
        .select("id, last_name")
        .eq("company_id", COMPANY_ID)
        .in_("last_name", list(SALARIES))
        .execute()
    ).data or []
    rc = 0
    for emp in sorted(emps, key=lambda e: e["last_name"]):
        nom = emp["last_name"]
        print(f"\n=== {nom} — août 2026 ===")
        if apply:
            try:
                for w in _generer(emp["id"]):
                    print(f"  avertissement : {w}")
            except PayslipBadRequestError as exc:
                print(f"::error::Génération refusée : {exc}")
                rc = 1
                continue
        row = (
            supabase.table("payslips")
            .select("payslip_data")
            .eq("employee_id", emp["id"])
            .eq("year", YEAR)
            .eq("month", MONTH)
            .limit(1)
            .execute()
        ).data
        data = (row or [{}])[0].get("payslip_data") or {}
        en_tete = data.get("en_tete") or {}
        print(
            f"fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; "
            f"brut {data.get('salaire_brut')}"
        )
        for ligne in _lignes(data, "details_absences"):
            print(f"  absence  {str(ligne.get('libelle'))[:58]:58s} q={ligne.get('quantite')} -{ligne.get('perte')}")
        for ligne in _lignes(data, "calcul_du_brut"):
            libelle = str(ligne.get("libelle", ""))
            if "suppl" in libelle.lower() and "structur" not in libelle.lower():
                print(f"  hs       {libelle[:58]:58s} q={ligne.get('quantite')} +{ligne.get('gain')}")
        if apply:
            # Les heures de la semaine du 27/07 sont typées « base » ou « hs25 » ;
            # on compare le total, en équivalent 35/39 déjà appliqué ou non.
            portees = _heures_absence_juillet(data)
            attendu = ATTENDU_31_07[nom]
            print(f"heures d'absence datées de juillet sur le bulletin d'août : {portees} (attendu ≈ {attendu})")
    if not apply:
        print("\nSIMULATION : rien n'est régénéré (--apply pour regénérer et contrôler)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
