"""Corrige la reprise du 14/09 tard le soir (`colorplast_reprise_cumuls_juin_test.py`)
sur le TEST : remet heures rémunérées, heures sup et brut cumulés du maillon de
juin à leurs valeurs d'avant, garde net imposable et PAS de Quadra, regénère
juillet.

Pourquoi : la réduction générale se régularise progressivement à partir des
cumuls de brut, d'heures (SMIC de référence) et de réduction déjà appliquée.
Changer les deux premiers sans le troisième a fait exploser la réduction de
juillet (Bugny −374 → −1 582, Gautheron devenue positive). Les trois doivent
rester cohérents entre eux : ils restent donc les nôtres. Le net imposable et
le PAS cumulés n'entrent pas dans ce calcul et suivent Quadra.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from scripts import colorplast_chaine_cumuls_test as chaine  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
YEAR = 2026

#: (heures rémunérées, heures sup, brut) cumulés à fin juin, valeurs d'avant la reprise.
AVANT = {
    "BUGNY": (1014.0, 288.48, 19309.66),
    "COTTE": (1014.0, 105.98, 14468.06),
    "DEMORY": (1014.0, 89.65, 6628.72),
    "ESPINOSA": (1014.0, 213.73, 18693.24),
    "FUCKAR": (507.0, 63.44, 5934.25),
    "GAUTHERON": (1014.0, 107.48, 13036.03),
    "GIRERD": (1014.0, 103.98, 22908.24),
}
#: Réduction générale de juillet attendue après retour (valeurs d'avant la reprise).
RG_AVANT = {"BUGNY": -374.05, "COTTE": -623.51, "ESPINOSA": -346.31, "FUCKAR": -758.96, "GIRERD": -244.54}


def main() -> int:
    apply = "--apply" in sys.argv
    emps = {e["last_name"]: e for e in (supabase.table("employees").select("id, last_name").eq("company_id", COMPANY_ID).execute()).data or []}
    for nom, (heures, hsup, brut) in AVANT.items():
        emp = emps[nom]
        row = supabase.table("employee_schedules").select("id, cumuls").match({"employee_id": emp["id"], "year": YEAR, "month": 6}).maybe_single().execute()
        cumuls = (row.data or {}).get("cumuls") or {}
        bloc = cumuls.setdefault("cumuls", {})
        print(f"  {nom:10s} heures {bloc.get('heures_remunerees')}→{heures} hsup {bloc.get('heures_supplementaires_remunerees')}→{hsup} brut {bloc.get('brut_total')}→{brut} (NI {bloc.get('net_imposable')} gardé)")
        bloc["heures_remunerees"], bloc["heures_supplementaires_remunerees"], bloc["brut_total"] = heures, hsup, brut
        if apply:
            supabase.table("employee_schedules").update({"cumuls": cumuls}).eq("id", row.data["id"]).execute()
    if not apply:
        print("SIMULATION")
        return 0
    chaine.MOIS = range(7, 8)
    chaine.main()
    rc = 0
    print("\n=== Réduction générale de juillet, retour à l'état d'avant ? ===")
    for nom, attendu in RG_AVANT.items():
        f = chaine._figures(emps[nom]["id"], 7) or {}
        rg = f.get("reduction_generale")
        etat = "OK" if rg is not None and abs(rg - attendu) <= 0.05 else "ECART"
        if etat != "OK":
            rc = 1
        print(f"  {etat:5s} {nom:10s} RG {rg} (avant {attendu})  cumul NI {f.get('cumul_ni')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
