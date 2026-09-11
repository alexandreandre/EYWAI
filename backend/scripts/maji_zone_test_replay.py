#!/usr/bin/env python3
"""Rejeu complet du backtest MAJI / ZONE 404 (janvier → juin 2026) sur la base
de TEST : configuration permanente, préalables, données de chaque mois, puis
génération des bulletins, dans l'ordre des mois (les réglages partagés — PAS,
titres-restaurant, transport, contrat — portent la valeur du mois en cours).

Prévu pour le workflow « Script sur l'env de test » (`script-env-test.yml`),
qui fournit SUPABASE_URL / SUPABASE_KEY / SUPABASE_SERVICE_KEY du projet de
test et ajoute `--apply` pour écrire. Sans `--apply` : plan et cible, rien
d'écrit.

Garde-fou : refuse de tourner contre le projet de production.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROD_REF = "slleauhyjnmiawosvlcg"
TEST_REF = "tlvkjwleahkmuzcegrde"
COMPANIES = ("Maji", "Zone")
YEAR = 2026
MONTHS = range(1, 7)


def _cible() -> str:
    url = os.environ.get("SUPABASE_URL", "")
    if PROD_REF in url:
        raise SystemExit("Refus : SUPABASE_URL pointe sur la PRODUCTION, ce rejeu est réservé au test.")
    if TEST_REF not in url:
        raise SystemExit(f"Refus : SUPABASE_URL inattendue ({url or 'vide'}), projet de test attendu.")
    return url


def _present(emp: dict, year: int, month: int) -> bool:
    import calendar as _cal

    debut = date(year, month, 1)
    fin = date(year, month, _cal.monthrange(year, month)[1])
    hire = str(emp.get("hire_date") or "")[:10]
    end = str(emp.get("contract_end_date") or "")[:10]
    if hire and hire > fin.isoformat():
        return False
    if end and end < debut.isoformat():
        return False
    return bool(emp.get("matricule"))


def main() -> None:
    apply = "--apply" in sys.argv
    url = _cible()
    print(f"Cible : {url} ({'ÉCRITURE' if apply else 'simulation'})")
    print(f"Sociétés : {', '.join(COMPANIES)} — mois {MONTHS.start}→{MONTHS.stop - 1}/{YEAR}")
    if not apply:
        from scripts.backtest.maji_zone_setup import MONTH_DATA, PERMANENT

        for company in COMPANIES:
            print(f"[{company}] {len(PERMANENT[company])} fiches à configurer ; "
                  f"mois renseignés : {sorted(MONTH_DATA.get(company, {}))}")
        print("Relancer avec --apply pour écrire et générer.")
        return

    from app.core.database import supabase
    from scripts.backtest.backtest_company_payroll import _generate_payslip, _load_payslip_data
    from scripts.backtest.employee_matching import EmployeeMatch, resolve_company_id
    from scripts.backtest.maji_zone_setup import apply_config, apply_month, prepare_maji

    for company in COMPANIES:
        print(f"\n===== {company} : configuration permanente =====")
        apply_config(company)
        print(f"===== {company} : préalables =====")
        prepare_maji(company)
        cid = resolve_company_id(company)
        for month in MONTHS:
            print(f"\n===== {company} {month:02d}/{YEAR} : données du mois =====")
            apply_month(company, YEAR, month)
            emps = (supabase.table("employees")
                    .select("id, company_id, first_name, last_name, employee_folder_name, "
                            "is_forfait_jour, matricule, hire_date, contract_end_date")
                    .eq("company_id", cid).execute().data)
            emps = sorted((e for e in emps if _present(e, YEAR, month)), key=lambda e: e["matricule"])
            print(f"===== {company} {month:02d}/{YEAR} : génération de {len(emps)} bulletins =====")
            for e in emps:
                m = EmployeeMatch(
                    employee_id=e["id"], company_id=cid, matricule=e["matricule"],
                    first_name=e.get("first_name") or "", last_name=e.get("last_name") or "",
                    employee_folder_name=e.get("employee_folder_name") or "",
                    is_forfait_jour=bool(e.get("is_forfait_jour")), reference=None,
                )
                try:
                    _generate_payslip(m, YEAR, month)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {m.matricule:12s} ERREUR {exc}")
                    continue
                data = _load_payslip_data(m.employee_id, YEAR, month) or {}
                syn = data.get("synthese_net") or {}
                pas = (syn.get("impot_prelevement_a_la_source") or {}).get("montant")
                print(f"  {m.matricule:12s} brut={data.get('salaire_brut')} NI={syn.get('net_imposable')} "
                      f"MNS={syn.get('montant_net_social')} NAP={data.get('net_a_payer')} PAS={pas}")
    print("\nRejeu terminé.")


if __name__ == "__main__":
    main()
