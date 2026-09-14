"""Régénère le bulletin de juillet 2026 de Marion GAUTHERON (Colorplast) sur le TEST.

Retour Gaëlle du 12/09/2026 : ses absences non rémunérées de juillet ne
donnaient pas les mêmes heures que Quadra (7,63 h pour une journée de
8,5 h, 6,73 h pour 7,5 h, et 2,61 h retirées sur les heures sup). Le moteur
applique désormais le prorata du contrat (35/39 en base, 4/39 en HS). Ce
script régénère juillet par la commande réelle et imprime les lignes
d'absence face au bulletin Quadra.

Référence Quadra (juillet 2026) : brut 2 089,06 ; absences 07/07 7,63 h
(100,28), 08/07 7,63 h (100,28), 09/07 6,73 h (88,45), 20/07 0,23 h (3,02),
23/07 0,67 h (8,81) ; heures sup retirées 2,61 h (42,88).

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
YEAR, MONTH = 2026, 7
QUADRA = {
    "salaire_brut": 2089.06,
    "absences": {"07/07": (7.63, 100.28), "08/07": (7.63, 100.28), "09/07": (6.73, 88.45),
                 "20/07": (0.23, 3.02), "23/07": (0.67, 8.81)},
    "reduction_hs": (2.61, 42.88),
}


def _lignes(data: dict, cle: str) -> list[dict]:
    valeur = data.get(cle)
    return valeur if isinstance(valeur, list) else []


def main() -> int:
    apply = "--apply" in sys.argv
    emps = (
        supabase.table("employees")
        .select("id, last_name, first_name, duree_hebdomadaire")
        .eq("company_id", COMPANY_ID)
        .ilike("last_name", "GAUTHERON%")
        .execute()
    ).data or []
    if len(emps) != 1:
        print(f"::error::{len(emps)} fiche(s) GAUTHERON chez Colorplast, attendu 1")
        return 1
    emp = emps[0]
    existant = (
        supabase.table("payslips")
        .select("id, status, manually_edited, edit_count")
        .eq("employee_id", emp["id"])
        .eq("year", YEAR)
        .eq("month", MONTH)
        .execute()
    ).data or []
    print(f"{emp['last_name']} {emp['first_name']} — {emp['duree_hebdomadaire']} h ; bulletin 07/2026 : {existant or 'aucun'}")
    if existant and existant[0].get("manually_edited"):
        print("::error::Bulletin modifié à la main, on ne le régénère pas d'autorité")
        return 1
    if not apply:
        print("SIMULATION : rien n'est régénéré")
        return 0

    try:
        result = generate_payslip(
            GeneratePayslipInput(
                employee_id=emp["id"],
                year=YEAR,
                month=MONTH,
                requested_by_name="script gautheron_juillet_test",
            )
        )
    except (PayslipCalendarIncompleteError, PayslipBadRequestError) as exc:
        print(f"::error::Génération refusée : {exc}")
        return 1
    print(f"génération : {result.status} — {result.message}")

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
    print(f"brut EYWAI {data.get('salaire_brut')} — Quadra {QUADRA['salaire_brut']}")
    for cle in ("details_absences", "details_conges"):
        for ligne in _lignes(data, cle):
            if not isinstance(ligne, dict):
                continue
            print(
                f"  {cle:16s} {str(ligne.get('libelle'))[:58]:58s} "
                f"q={ligne.get('quantite')} t={ligne.get('taux')} -{ligne.get('perte')} +{ligne.get('gain')}"
            )
    print(f"référence Quadra : {QUADRA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
