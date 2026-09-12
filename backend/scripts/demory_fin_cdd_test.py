"""Requalifie le départ de DEMORY (Colorplast) en fin de CDD et refait son bulletin de juillet.

Constat du 12/09/2026 sur l'environnement de TEST : son dossier de départ
est typé « licenciement », validé et archivé la même seconde le 28/08, sans
indemnités calculées. Or c'est un CDD arrivé à son terme (fin de contrat et
dernier jour travaillé au 24/07). Conséquence sur le bulletin de juillet :
un départ sans indemnités calculées bloque l'indemnité compensatrice de
congés payés automatique (cf. `resolve_exit_state_for_payslip`), et Quadra
en porte une de 940,23.

Ce script :
1. retype le départ en `fin_cdd` ;
2. calcule ses indemnités par la commande réelle du module Départs ;
3. régénère juillet par la commande réelle de génération et imprime les
   lignes face au bulletin Quadra (brut 3 509,91, précarité 797,04,
   indemnité de CP 940,23).

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.employee_exits.application.queries import (  # noqa: E402
    calculate_exit_indemnities,
)
from app.modules.employee_exits.infrastructure.repository import (  # noqa: E402
    EmployeeExitRepository,
)
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR, MONTH = 2026, 7
QUADRA = {"salaire_brut": 3509.91, "prime_precarite": 797.04, "indemnite_cp": 940.23}


def _lignes(data: dict, cle: str) -> list[dict]:
    valeur = data.get(cle)
    return valeur if isinstance(valeur, list) else []


def main() -> int:
    apply = "--apply" in sys.argv
    emps = (
        supabase.table("employees")
        .select("id, last_name, first_name, employment_status, contract_type, contract_end_date")
        .eq("company_id", COMPANY_ID)
        .ilike("last_name", "DEMORY%")
        .execute()
    ).data or []
    if len(emps) != 1:
        print(f"::error::{len(emps)} fiche(s) DEMORY chez Colorplast, attendu 1")
        return 1
    emp = emps[0]
    sorties = (
        supabase.table("employee_exits")
        .select("id, exit_type, status, last_working_day, calculated_indemnities")
        .eq("employee_id", emp["id"])
        .not_.in_("status", ["annulee", "annule", "cancelled", "canceled"])
        .execute()
    ).data or []
    if len(sorties) != 1:
        print(f"::error::{len(sorties)} départ(s) actif(s) pour DEMORY, attendu 1")
        return 1
    sortie = sorties[0]
    print(
        f"{emp['last_name']} {emp['first_name']} — {emp['contract_type']} fin {emp['contract_end_date']} ; "
        f"départ {sortie['exit_type']} / {sortie['status']} / dernier jour {sortie['last_working_day']} / "
        f"indemnités {'calculées' if sortie.get('calculated_indemnities') else 'ABSENTES'}"
    )
    if not apply:
        print("SIMULATION : rien n'est modifié")
        return 0

    repo = EmployeeExitRepository(supabase)
    if sortie["exit_type"] != "fin_cdd":
        repo.update(sortie["id"], COMPANY_ID, {"exit_type": "fin_cdd"})
        print("départ retypé en fin_cdd")
    indemnites = calculate_exit_indemnities(sortie["id"], COMPANY_ID)
    for cle, valeur in indemnites.items():
        print(f"  indemnité {cle}: {str(valeur)[:160]}")

    try:
        result = generate_payslip(
            GeneratePayslipInput(
                employee_id=emp["id"],
                year=YEAR,
                month=MONTH,
                requested_by_name="script demory_fin_cdd_test",
            )
        )
    except (PayslipCalendarIncompleteError, PayslipBadRequestError) as exc:
        print(f"::error::Génération refusée : {exc}")
        return 1
    print(f"génération : {result.status} — {result.message}")
    for w in result.warnings or []:
        print(f"  avertissement : {w}")

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
    print(f"net à payer EYWAI {data.get('net_a_payer')}")
    for cle in ("calcul_du_brut", "details_conges", "details_absences", "indemnites_sortie"):
        for ligne in _lignes(data, cle):
            if not isinstance(ligne, dict) or ligne.get("is_sous_total"):
                continue
            print(
                f"  {cle:16s} {str(ligne.get('libelle'))[:60]:60s} "
                f"q={ligne.get('quantite')} t={ligne.get('taux')} "
                f"+{ligne.get('gain') or ligne.get('montant')} -{ligne.get('perte')}"
            )
    print(f"référence Quadra : {QUADRA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
