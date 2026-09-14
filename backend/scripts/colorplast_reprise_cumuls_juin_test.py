"""Reprise des cumuls Colorplast à fin juin 2026 depuis les bulletins Quadra,
sur le TEST, puis regénération de juillet et comparaison aux cumuls Quadra de
juillet, salarié par salarié.

Principe (retour Gaëlle du 14/09) : sur une reprise en cours d'année, la
chaîne de cumuls suit le cabinet, c'est-à-dire ce qui a été déclaré. Le
maillon de juin de chaque salarié (`employee_schedules.cumuls`) reçoit les
cumuls imprimés sur le bulletin Quadra de juin : net imposable, impôt prélevé
à la source, cumul heures, cumul heures sup, bruts. Juillet regénéré repart
de là ; ce qui reste d'écart est alors le mois de juillet lui-même.

Valeurs lues sur `data/colorplast/bulletins/2026-06/06-2026-colorplast.pdf`
et `2026-07/07-2026-colorplast.pdf` (colonne HEURES / CUMULS et ligne
« Montant net imposable … cumul annuel »).

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from scripts import colorplast_chaine_cumuls_test as chaine  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR = 2026

CHAMPS = ("net_imposable", "impot_preleve_a_la_source", "heures_remunerees",
          "heures_supplementaires_remunerees", "brut_total")

#: Cumuls Quadra à fin juin 2026 : (net imposable, PAS, heures, heures sup, bruts).
JUIN_QUADRA = {
    "BUGNY": (15025.37, 510.87, 1114.5, 204.48, 17769.87),
    "COTTE": (13387.68, 281.13, 989.1, 103.22, 14468.06),
    "DEMORY": (4443.26, 0.0, 494.4, 48.52, 6197.76),
    "ESPINOSA": (15243.02, 0.0, 1123.75, 213.73, 18693.24),
    "FUCKAR": (4083.42, 0.0, 452.0, 62.49, 5934.26),
    "GAUTHERON": (10299.87, 164.80, 748.1, 80.12, 11097.89),
    "GIRERD": (15796.02, 679.23, 1014.0, 103.98, 22908.20),
}

#: Cumuls Quadra sur le bulletin de juillet 2026, même ordre.
JUILLET_QUADRA = {
    "BUGNY": (16955.59, 576.50, 1309.0, 247.31, 20932.84),
    "COTTE": (15144.81, 318.03, 1166.1, 128.55, 17044.47),
    "DEMORY": (7122.56, 0.0, 634.8, 62.92, 9707.67),
    "ESPINOSA": (17225.93, 0.0, 1313.0, 251.31, 21885.00),
    "FUCKAR": (5442.06, 0.0, 603.0, 77.97, 7840.71),
    "GAUTHERON": (11801.04, 188.82, 891.6, 94.84, 13186.95),
    "GIRERD": (18464.90, 793.99, 1183.0, 121.31, 26764.18),
}


def _cumuls_juillet(employee_id: str) -> dict:
    row = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": employee_id, "year": YEAR, "month": 7})
        .maybe_single()
        .execute()
    )
    data = (row.data or {}).get("payslip_data") if row else None
    return ((data or {}).get("cumuls") or {}).get("cumuls") or {}


def main() -> int:
    apply = "--apply" in sys.argv
    emps = {
        e["last_name"]: e
        for e in (
            supabase.table("employees").select("id, last_name").eq("company_id", COMPANY_ID).execute()
        ).data
        or []
    }
    rc = 0
    print("=== Maillon de juin : cumuls Quadra ===")
    for nom, valeurs in JUIN_QUADRA.items():
        emp = emps.get(nom)
        if not emp:
            print(f"::error::{nom} introuvable")
            rc = 1
            continue
        row = (
            supabase.table("employee_schedules")
            .select("id, cumuls")
            .match({"employee_id": emp["id"], "year": YEAR, "month": 6})
            .maybe_single()
            .execute()
        )
        data = (row.data or {}) if row else {}
        cumuls = data.get("cumuls") or {}
        bloc = cumuls.setdefault("cumuls", {})
        avant = " ".join(f"{c.split('_')[0][:5]}={bloc.get(c)}" for c in CHAMPS)
        print(f"  {nom:10s} avant : {avant}")
        for champ, valeur in zip(CHAMPS, valeurs):
            bloc[champ] = valeur
        if apply and data.get("id"):
            supabase.table("employee_schedules").update({"cumuls": cumuls}).eq("id", data["id"]).execute()

    if not apply:
        print("\nSIMULATION : rien n'écrit, juillet non regénéré")
        return rc

    print("\n=== Juillet regénéré sur ces maillons ===")
    chaine.MOIS = range(7, 8)
    chaine.main()

    print("\n=== Juillet : EYWAI contre Quadra (écart = EYWAI − Quadra) ===")
    print(f"  {'':10s} {'net imposable':>16s} {'PAS':>10s} {'heures':>10s} {'h. sup':>10s} {'bruts':>12s}")
    for nom, attendus in JUILLET_QUADRA.items():
        emp = emps.get(nom)
        obtenu = _cumuls_juillet(emp["id"]) if emp else {}
        cellules = []
        for champ, attendu in zip(CHAMPS, attendus):
            valeur = obtenu.get(champ)
            ecart = None if valeur is None else round(float(valeur) - attendu, 2)
            cellules.append(f"{ecart:+.2f}" if ecart is not None else "?")
            if ecart is not None and abs(ecart) > 0.05 and champ in ("net_imposable", "brut_total"):
                rc = 1
        print(f"  {nom:10s} {cellules[0]:>16s} {cellules[1]:>10s} {cellules[2]:>10s} {cellules[3]:>10s} {cellules[4]:>12s}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
