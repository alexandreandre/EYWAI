"""Aligne, sur le TEST, le maillon de juin 2026 de chaque salarié Colorplast sur
le cumul net imposable de Quadra à fin juin, puis regénère juillet.

Constat du 14/09 au soir, bulletins Quadra de janvier à juillet relus : Quadra
n'a réintégré la part patronale de mutuelle dans le net imposable qu'à partir
d'avril (Girerd : 2 600,18 de janvier à mars, 2 629,13 en avril). Nos bulletins
de janvier à mars, refaits le 27/08, la réintègrent. Le cumul que Gaëlle lisait
sur juillet (18 435,65) était à deux centimes de Quadra (18 435,67) : la chaîne
d'avant ce soir était la bonne, et c'est la regénération de janvier à juin,
puis le retour aux bulletins du 27/08, qui l'ont décalée de + 87 €.

Le cumul à reprendre, c'est celui du cabinet : ce qui a été déclaré. Juin
repart donc du cumul Quadra à fin juin (somme des nets imposables mensuels des
bulletins Quadra, ou cumul annuel imprimé), les autres champs du maillon sont
laissés tels quels. Puis juillet est regénéré pour tous : son cumul doit
retomber sur le cumul annuel Quadra de juillet là où on le connaît.

Gautheron : cumul Quadra illisible dans le PDF ; on reprend la valeur d'avant
ce soir (juillet 12 474,75 moins juillet 1 471,04), celle que Gaëlle a vue.

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

#: Cumul net imposable Quadra à fin juin 2026 (source, bulletins du cabinet).
LIEN_JUIN_QUADRA = {
    "BUGNY": 15025.37,  # somme janv.→juin : 1865,90 + 1867,82 + 1865,40 + 1895,49 + 5600,16 + 1930,60
    "COTTE": 13387.68,  # cumul annuel imprimé sur juin
    "DEMORY": 4443.26,  # cumul annuel imprimé sur juin
    "ESPINOSA": 15243.02,  # cumul juillet 17 225,93 − net imposable juillet 1 982,91
    "FUCKAR": 4083.42,  # cumul annuel imprimé sur juin
    "GAUTHERON": 11003.71,  # valeur d'avant ce soir, Quadra illisible
    "GIRERD": 15766.79,  # 3 × 2600,18 + 2629,13 + 2 × 2668,56
}

#: Cumul annuel Quadra sur le bulletin de juillet, quand il est lisible.
CUMUL_JUILLET_QUADRA = {
    "BUGNY": 16955.59,
    "COTTE": 15144.81,
    "ESPINOSA": 17225.93,
    "FUCKAR": 5442.06,
    "GIRERD": 18435.67,
}


def main() -> int:
    apply = "--apply" in sys.argv
    emps = {
        e["last_name"]: e
        for e in (
            supabase.table("employees")
            .select("id, last_name")
            .eq("company_id", COMPANY_ID)
            .execute()
        ).data
        or []
    }
    rc = 0
    print("=== Maillon de juin : net imposable cumulé ===")
    for nom, cible in LIEN_JUIN_QUADRA.items():
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
        actuel = ((cumuls.get("cumuls") or {}).get("net_imposable"))
        print(f"  {nom:10s} {actuel} → {cible}")
        if not apply or not data.get("id"):
            continue
        cumuls.setdefault("cumuls", {})["net_imposable"] = cible
        supabase.table("employee_schedules").update({"cumuls": cumuls}).eq("id", data["id"]).execute()

    if not apply:
        print("\nSIMULATION : rien n'écrit, juillet non regénéré")
        return rc

    print("\n=== Juillet regénéré sur ces maillons ===")
    chaine.MOIS = range(7, 8)
    chaine.main()

    print("\n=== Contrôle : cumul de juillet contre Quadra ===")
    for nom, attendu in CUMUL_JUILLET_QUADRA.items():
        emp = emps.get(nom)
        figures = chaine._figures(emp["id"], 7) if emp else None
        obtenu = (figures or {}).get("cumul_ni")
        ecart = None if obtenu is None else round(obtenu - attendu, 2)
        etat = "OK" if ecart is not None and abs(ecart) <= 0.05 else "ECART"
        print(f"  {etat:5s} {nom:10s} EYWAI {obtenu} — Quadra {attendu} — écart {ecart}")
        if etat != "OK":
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
