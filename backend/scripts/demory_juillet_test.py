"""Génère le bulletin de juillet 2026 de DEMORY (Colorplast), sorti le 24/07.

Retour Gaëlle du 12/09/2026 : « je ne retrouve pas le salarié dans bulletin
de paie de juillet ni de juin ; il sort des effectifs le 24 juillet, j'aurais
aimé contrôler le STC ». Il était au statut « parti » : la liste paie
l'excluait et la génération le refusait. Les deux sont corrigés sur la
branche ; ce script passe par la commande réelle `generate_payslip`, avec
ses gardes, pour poser le bulletin manquant sur l'environnement de TEST.

Référence pour le contrôle : bulletin Quadra de juillet (du 01/07 au 24/07)
— base 126 h, HS 25 % 14,40 h, un jour de CP, prime de précarité 797,04,
indemnité de CP 940,23, brut 3 509,91.

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
    "salaire_brut": 3509.91,
    "heures_base": 126.0,
    "hs_25": 14.40,
    "prime_precarite": 797.04,
    "indemnite_cp": 940.23,
}


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
    print(
        f"{emp['last_name']} {emp['first_name']} — {emp['employment_status']}, "
        f"{emp['contract_type']}, fin de contrat {emp['contract_end_date']}"
    )
    existants = (
        supabase.table("payslips")
        .select("id, status, generated_at")
        .eq("employee_id", emp["id"])
        .eq("year", YEAR)
        .eq("month", MONTH)
        .execute()
    ).data or []
    print(f"bulletins {MONTH:02d}/{YEAR} existants : {existants or 'aucun'}")
    if not apply:
        print("SIMULATION : rien n'est généré")
        return 0

    try:
        result = generate_payslip(
            GeneratePayslipInput(
                employee_id=emp["id"],
                year=YEAR,
                month=MONTH,
                requested_by_name="script demory_juillet_test",
            )
        )
    except PayslipCalendarIncompleteError as exc:
        print(f"::error::Calendrier de juillet incomplet, rien généré : {exc}")
        return 1
    except PayslipBadRequestError as exc:
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
    if not row:
        print("::error::Bulletin introuvable après génération")
        return 1
    data = row[0]["payslip_data"] or {}
    print(f"brut EYWAI {data.get('salaire_brut')} — Quadra {QUADRA['salaire_brut']}")
    print(f"net à payer EYWAI {data.get('net_a_payer')}")
    for cle in ("calcul_du_brut", "details_conges", "details_absences"):
        for ligne in _lignes(data, cle):
            if not isinstance(ligne, dict) or ligne.get("is_sous_total"):
                continue
            print(
                f"  {cle:16s} {str(ligne.get('libelle'))[:60]:60s} "
                f"q={ligne.get('quantite')} t={ligne.get('taux')} "
                f"+{ligne.get('gain')} -{ligne.get('perte')}"
            )
    print(f"référence Quadra : {QUADRA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
