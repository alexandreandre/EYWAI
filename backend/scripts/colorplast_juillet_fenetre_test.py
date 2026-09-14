"""Régénère juillet 2026 de ESPINOSA, FUCKAR et GAUTHERON (Colorplast) sur le TEST
et compare le brut aux bulletins Quadra.

Retour Gaëlle du 14/09/2026 : deux règles corrigées, la fenêtre des variables
(22/06 au 26/07) qui borne désormais les absences, et le bilan par semaine
des absences. Attendus, cf. docs/superpowers/specs/2026-09-14-fenetre-
variables-et-bilan-hebdo-design.md :

  FUCKAR    1 906,45  (Quadra 1 906,45)
  ESPINOSA  3 191,76  (Quadra 3 191,76)
  GAUTHERON 2 085,64  (Quadra 2 089,06 ; les 3,42 restants sont la donnée du
                       17/07, 4 h 45 pointées pour 5 h, absente chez Quadra)

Les trois bulletins sont regénérés même s'ils portent une édition manuelle :
les heures sup corrigées par Gaëlle sont des saisies du mois (« corrigées au
bulletin ») que le moteur relit, et Gaëlle regénère elle-même juillet le
15/09 au matin. Calendrier incomplet forcé comme depuis l'écran.

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
ATTENDUS = {
    "FUCKAR": (1906.45, 1906.45),
    "ESPINOSA": (3191.76, 3191.76),
    "GAUTHERON": (2085.64, 2089.06),
}
TOLERANCE = 0.01


def _lignes(data: dict, cle: str) -> list[dict]:
    valeur = data.get(cle)
    return [ligne for ligne in valeur if isinstance(ligne, dict)] if isinstance(valeur, list) else []


def _generer(employee_id: str) -> tuple[str, list[str]]:
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id,
                year=YEAR,
                month=MONTH,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_juillet_fenetre_test",
            )
        )

    try:
        result = _run(False)
    except PayslipCalendarIncompleteError as exc:
        print(f"::warning::Calendrier incomplet, génération forcée comme depuis l'écran : {exc}")
        result = _run(True)
    return f"{result.status} — {result.message}", list(result.warnings or [])


def main() -> int:
    apply = "--apply" in sys.argv
    emps = (
        supabase.table("employees")
        .select("id, last_name, first_name")
        .eq("company_id", COMPANY_ID)
        .in_("last_name", list(ATTENDUS))
        .execute()
    ).data or []
    if len(emps) != len(ATTENDUS):
        print(f"::error::{len(emps)} fiche(s) trouvée(s) pour {sorted(ATTENDUS)}")
        return 1

    rc = 0
    for emp in sorted(emps, key=lambda e: e["last_name"]):
        nom = emp["last_name"]
        attendu, quadra = ATTENDUS[nom]
        print(f"\n=== {nom} {emp['first_name']} — juillet 2026 ===")
        if apply:
            try:
                statut, warnings = _generer(emp["id"])
            except PayslipBadRequestError as exc:
                print(f"::error::Génération refusée : {exc}")
                rc = 1
                continue
            print(f"génération : {statut}")
            for w in warnings:
                print(f"  avertissement : {w}")
        row = (
            supabase.table("payslips")
            .select("payslip_data, manually_edited, edit_count")
            .eq("employee_id", emp["id"])
            .eq("year", YEAR)
            .eq("month", MONTH)
            .limit(1)
            .execute()
        ).data
        data = (row or [{}])[0].get("payslip_data") or {}
        brut = float(data.get("salaire_brut") or 0)
        en_tete = data.get("en_tete") or {}
        print(
            f"fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; "
            f"brut EYWAI {brut:.2f} — attendu {attendu:.2f} — Quadra {quadra:.2f}"
        )
        for cle in ("details_absences", "details_conges"):
            for ligne in _lignes(data, cle):
                print(
                    f"  {cle:16s} {str(ligne.get('libelle'))[:58]:58s} "
                    f"q={ligne.get('quantite')} -{ligne.get('perte')} +{ligne.get('gain')}"
                )
        for ligne in _lignes(data, "calcul_du_brut"):
            libelle = str(ligne.get("libelle", ""))
            if "suppl" in libelle.lower():
                print(f"  {'calcul_du_brut':16s} {libelle[:58]:58s} q={ligne.get('quantite')} +{ligne.get('gain')}")
        if apply:
            if abs(brut - attendu) <= TOLERANCE:
                print(f"OK : {nom} au centime")
            else:
                print(f"::error::{nom} : brut {brut:.2f} ≠ attendu {attendu:.2f} (écart {brut - attendu:+.2f})")
                rc = 1
    if not apply:
        print("\nSIMULATION : rien n'est régénéré (--apply pour regénérer et contrôler)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
