"""Annule, sur le TEST, la regénération de janvier à juin 2026 de Colorplast
faite par `colorplast_chaine_cumuls_test.py` le 14/09/2026 au soir.

Cette regénération a recalculé les six mois avec les salaires et réglages
d'aujourd'hui, pas ceux de l'époque (Girerd : 3 855,98 en janvier au lieu de
3 799,07 ; Gautheron avril : 335,06 au lieu de 1 782,85). L'historique de
chaque bulletin porte la version d'avant (`previous_payslip_data`, entrée
« script colorplast_chaine_cumuls_test ») : on la remet en place, on refait le
PDF, et on aligne le maillon de cumuls du mois (`employee_schedules.cumuls`)
sur les cumuls que ce bulletin portait. Juillet n'est pas touché : Gaëlle le
regénère le 15/09 au matin et il repartira du maillon de juin ainsi rétabli.

Aucun drapeau d'édition manuelle n'est posé : ce n'est pas une saisie, c'est
un retour à l'état d'avant. Une entrée d'historique « retour_chaine » garde la
version annulée, au cas où.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payroll.documents.payslip_editor import (  # noqa: E402
    regenerate_pdf_from_data,
)

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR = 2026
MOIS = range(1, 7)
AUTEUR_A_ANNULER = "script colorplast_chaine_cumuls_test"


def _brut(data: dict) -> float:
    try:
        return round(float((data or {}).get("salaire_brut") or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    apply = "--apply" in sys.argv
    emps = {
        e["id"]: e
        for e in (
            supabase.table("employees")
            .select("id, last_name, employee_folder_name")
            .eq("company_id", COMPANY_ID)
            .execute()
        ).data
        or []
    }
    rows = (
        supabase.table("payslips")
        .select("id, employee_id, month, payslip_data, edit_history, pdf_storage_path, pdf_notes, manually_edited, edited_at")
        .eq("company_id", COMPANY_ID)
        .eq("year", YEAR)
        .in_("month", list(MOIS))
        .execute()
    ).data or []
    rows.sort(key=lambda r: (r["month"], emps.get(r["employee_id"], {}).get("last_name", "")))

    rc = 0
    restaures = 0
    for row in rows:
        emp = emps.get(row["employee_id"]) or {}
        nom = emp.get("last_name", "?")
        historique = row.get("edit_history") or []
        entrees = [h for h in historique if h.get("edited_by_name") == AUTEUR_A_ANNULER]
        if not entrees:
            print(f"  {nom:10s} {row['month']:02d} : rien à annuler")
            continue
        entree = sorted(entrees, key=lambda h: h.get("edited_at") or "")[-1]
        avant = entree.get("previous_payslip_data")
        if not isinstance(avant, dict) or "salaire_brut" not in avant or "cumuls" not in avant:
            print(f"::error::{nom} {row['month']:02d} : sauvegarde incomplète, non restauré")
            rc = 1
            continue
        actuel = row.get("payslip_data") or {}
        print(
            f"  {nom:10s} {row['month']:02d} : brut {_brut(actuel):>8.2f} → {_brut(avant):>8.2f} ; "
            f"cumul NI {((avant.get('cumuls') or {}).get('cumuls') or {}).get('net_imposable')}"
        )
        if not apply:
            continue

        pdf_path = regenerate_pdf_from_data(
            payslip_data=avant,
            employee_id=row["employee_id"],
            employee_folder_name=emp["employee_folder_name"],
            company_id=COMPANY_ID,
            month=row["month"],
            year=YEAR,
            pdf_notes=row.get("pdf_notes"),
            manually_edited=bool(row.get("manually_edited")),
            edited_at=datetime.fromisoformat(row["edited_at"]) if row.get("edited_at") else None,
        )
        with open(pdf_path, "rb") as f:
            supabase.storage.from_("payslips").upload(
                path=row["pdf_storage_path"], file=f.read(), file_options={"x-upsert": "true"}
            )
        historique.append(
            {
                "action": "retour_chaine",
                "version": len(historique) + 1,
                "edited_at": datetime.now(timezone.utc).isoformat(),
                "edited_by": None,
                "edited_by_name": "script colorplast_retour_chaine_test",
                "changes_summary": "Retour à la version d'avant la regénération de la chaîne du 14/09",
                "previous_payslip_data": actuel,
            }
        )
        supabase.table("payslips").update(
            {"payslip_data": avant, "edit_history": historique}
        ).eq("id", row["id"]).execute()
        supabase.table("employee_schedules").update({"cumuls": avant["cumuls"]}).match(
            {"employee_id": row["employee_id"], "year": YEAR, "month": row["month"]}
        ).execute()
        restaures += 1

    if apply:
        print(f"\n{restaures} bulletin(s) remis à leur version d'avant, PDF refaits, maillons alignés.")
        girerd = next((e for e in emps.values() if e["last_name"] == "GIRERD"), None)
        if girerd:
            juin = (
                supabase.table("employee_schedules")
                .select("cumuls")
                .match({"employee_id": girerd["id"], "year": YEAR, "month": 6})
                .maybe_single()
                .execute()
            )
            lien = (((juin.data or {}).get("cumuls") or {}).get("cumuls") or {}).get("net_imposable") if juin else None
            print(f"Girerd, maillon de juin : net imposable cumulé {lien} (juillet repartira de là : + 2 668,86)")
    else:
        print("\nSIMULATION : rien n'est restauré (--apply pour restaurer)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
