"""Régénère le bulletin de mai 2026 de SMITH (MAJI) sur l'environnement de TEST.

Le rejeu du 14/09 a régénéré les 81 bulletins de MAJI et Zone 404 sans
l'alerte de versement mobilité, sauf celui-ci : la génération est tombée sur
un 400 non JSON pendant le déploiement du backend de test, et le bulletin a
gardé sa version du 11/09 avec l'alerte. Reprise par la commande réelle, en
ligne de commande, sans passer par l'API.

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

SOCIETE = "MAJI"
NOM = "SMITH"
YEAR, MONTH = 2026, 5


def main() -> int:
    apply = "--apply" in sys.argv
    societe = (
        supabase.table("companies").select("id").eq("company_name", SOCIETE).execute()
    ).data or []
    if len(societe) != 1:
        print(f"::error::{len(societe)} société(s) {SOCIETE}")
        return 1
    emps = (
        supabase.table("employees")
        .select("id, last_name, first_name")
        .eq("company_id", societe[0]["id"])
        .ilike("last_name", f"{NOM}%")
        .execute()
    ).data or []
    if len(emps) != 1:
        print(f"::error::{len(emps)} fiche(s) {NOM} chez {SOCIETE}, attendu 1")
        return 1
    emp = emps[0]
    existant = (
        supabase.table("payslips")
        .select("id, status, manually_edited, payslip_data->alertes_baremes")
        .eq("employee_id", emp["id"])
        .eq("year", YEAR)
        .eq("month", MONTH)
        .execute()
    ).data or []
    print(f"{emp['last_name']} {emp['first_name']} — bulletin {MONTH:02d}/{YEAR} : {existant or 'aucun'}")
    if existant and existant[0].get("manually_edited"):
        print("::error::Bulletin modifié à la main, on ne le régénère pas d'autorité")
        return 1
    if not apply:
        print("SIMULATION : rien n'est régénéré")
        return 0

    def _generer(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=emp["id"],
                year=YEAR,
                month=MONTH,
                force_calendrier_incomplet=force,
                regenerer_bulletin_valide=True,
                requested_by_name="script smith_mai_test",
            )
        )

    try:
        try:
            result = _generer(False)
        except PayslipCalendarIncompleteError as exc:
            print(f"::warning::Calendrier incomplet, génération forcée : {exc}")
            result = _generer(True)
    except PayslipBadRequestError as exc:
        print(f"::error::Génération refusée : {exc}")
        return 1
    print(f"génération : {result.status} — {result.message}")

    row = (
        supabase.table("payslips")
        .select("payslip_data->salaire_brut, payslip_data->alertes_baremes")
        .eq("employee_id", emp["id"])
        .eq("year", YEAR)
        .eq("month", MONTH)
        .limit(1)
        .execute()
    ).data or [{}]
    print(f"brut {row[0].get('salaire_brut')} — alertes {row[0].get('alertes_baremes') or 'aucune'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
