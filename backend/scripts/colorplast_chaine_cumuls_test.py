"""Remet d'aplomb la chaîne des cumuls de Colorplast sur le TEST en regénérant
janvier → juillet 2026 dans l'ordre, salarié par salarié.

Retour Gaëlle du 14/09/2026 (Girerd) : le cumul net imposable du bulletin de
juillet (18 435,65) ne vaut pas la somme de nos bulletins de janvier à juillet
(18 522,80). Le cumul est porté de mois en mois par `employee_schedules.cumuls`
: chaque mois repart du maillon du mois précédent. Les maillons de janvier à
avril datent du 2 août (avant la réintégration de la part patronale de
mutuelle dans le net imposable) et n'ont pas été réécrits par le rejeu du
27/08. Regénérer dans l'ordre réécrit chaque maillon à partir du précédent.

Pour chaque bulletin, le script relève brut, net imposable, net à payer et
réduction générale avant et après, et signale tout mouvement : la chaîne doit
changer, pas les bulletins (hors effets attendus des règles corrigées ce
jour : fenêtre des variables et bilan hebdomadaire des absences).

Les bulletins édités à la main sont regénérés aussi : sans cela leur maillon
resterait faux. Les heures sup corrigées par Gaëlle sont des saisies du mois
que le moteur relit. Calendrier incomplet forcé comme depuis l'écran.

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
YEAR = 2026
MOIS = range(1, 8)
SEUIL = 0.01


def _nombre(valeur) -> float:
    try:
        return round(float(valeur or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _figures(employee_id: str, month: int) -> dict | None:
    row = (
        supabase.table("payslips")
        .select("payslip_data, manually_edited, edit_count")
        .eq("employee_id", employee_id)
        .eq("year", YEAR)
        .eq("month", month)
        .limit(1)
        .execute()
    ).data
    if not row:
        return None
    data = row[0].get("payslip_data") or {}
    synthese = data.get("synthese_net") or {}
    reduction = 0.0
    for cot in (data.get("structure_cotisations") or {}).get("bloc_allegements") or []:
        if "générale" in str(cot.get("libelle", "")).lower():
            reduction = _nombre(cot.get("montant_patronal"))
    cumuls = ((data.get("cumuls") or {}).get("cumuls")) or {}
    return {
        "brut": _nombre(data.get("salaire_brut")),
        "net_imposable": _nombre(synthese.get("net_imposable")),
        "net_a_payer": _nombre(data.get("net_a_payer")),
        "reduction_generale": reduction,
        "cumul_ni": _nombre(cumuls.get("net_imposable")),
        "cumul_heures": _nombre(cumuls.get("heures_remunerees")),
        "edite": bool(row[0].get("manually_edited")),
        "editions": int(row[0].get("edit_count") or 0),
    }


def _maillon(employee_id: str, month: int) -> float:
    row = (
        supabase.table("employee_schedules")
        .select("cumuls")
        .eq("employee_id", employee_id)
        .eq("year", YEAR)
        .eq("month", month)
        .maybe_single()
        .execute()
    )
    cumuls = ((row.data or {}).get("cumuls") or {}).get("cumuls") if row else None
    return _nombre((cumuls or {}).get("net_imposable"))


def _generer(employee_id: str, month: int) -> list[str]:
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id,
                year=YEAR,
                month=month,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_chaine_cumuls_test",
            )
        )

    try:
        result = _run(False)
    except PayslipCalendarIncompleteError:
        result = _run(True)
    return list(result.warnings or [])


def main() -> int:
    apply = "--apply" in sys.argv
    emps = sorted(
        (
            supabase.table("employees")
            .select("id, last_name")
            .eq("company_id", COMPANY_ID)
            .execute()
        ).data
        or [],
        key=lambda e: e["last_name"],
    )
    rc = 0
    mouvements = 0
    for month in MOIS:
        print(f"\n=== {month:02d}/{YEAR} ===")
        for emp in emps:
            avant = _figures(emp["id"], month)
            if avant is None:
                continue
            nom = emp["last_name"]
            note = f" (édité à la main, {avant['editions']} éditions, regénéré quand même)" if avant["edite"] else ""
            if not apply:
                print(f"  {nom:10s} brut {avant['brut']:>9.2f}  NI {avant['net_imposable']:>8.2f}  cumul NI {avant['cumul_ni']:>9.2f}{note}")
                continue
            try:
                warnings = _generer(emp["id"], month)
            except PayslipBadRequestError as exc:
                print(f"::error::{nom} {month:02d} : génération refusée : {exc}")
                rc = 1
                continue
            apres = _figures(emp["id"], month) or {}
            ecarts = []
            for cle in ("brut", "net_imposable", "net_a_payer", "reduction_generale"):
                if abs(apres.get(cle, 0) - avant[cle]) > SEUIL:
                    ecarts.append(f"{cle} {avant[cle]:.2f}→{apres[cle]:.2f}")
            if ecarts:
                mouvements += 1
            marque = "MOUVEMENT " if ecarts else ""
            print(
                f"  {marque}{nom:10s} brut {apres.get('brut', 0):>9.2f}  NI {apres.get('net_imposable', 0):>8.2f}  "
                f"cumul NI {avant['cumul_ni']:>9.2f}→{apres.get('cumul_ni', 0):>9.2f}  "
                f"maillon {_maillon(emp['id'], month):>9.2f}{note}"
                + (f"  | {' ; '.join(ecarts)}" if ecarts else "")
            )
            for w in warnings:
                print(f"      avertissement : {w}")

    if apply:
        print("\n=== Contrôle Girerd : cumul de juillet = somme des bulletins ? ===")
        girerd = next((e for e in emps if e["last_name"] == "GIRERD"), None)
        if girerd:
            somme = 0.0
            for month in MOIS:
                f = _figures(girerd["id"], month)
                if f:
                    somme += f["net_imposable"]
                    print(f"  {month:02d} : NI {f['net_imposable']:>8.2f}  cumul {f['cumul_ni']:>9.2f}  somme {somme:>9.2f}")
            juillet = _figures(girerd["id"], 7) or {}
            if abs(juillet.get("cumul_ni", 0) - somme) > 0.05:
                print(f"::error::Girerd : cumul de juillet {juillet.get('cumul_ni')} ≠ somme {somme:.2f}")
                rc = 1
            else:
                print(f"OK : cumul de juillet {juillet.get('cumul_ni'):.2f} = somme des bulletins")
        print(f"\n{mouvements} bulletin(s) dont brut, net imposable, net à payer ou réduction générale ont bougé.")
    else:
        print("\nSIMULATION : rien n'est régénéré (--apply pour regénérer dans l'ordre)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
