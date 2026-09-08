"""Recalage des compteurs CP Colorplast à fin août 2026 — exécuté en CI
contre la base de l'ENVIRONNEMENT DE TEST (workflow recalage-cp-test.yml).

Pourquoi un workflow : les écarts de reprise se calculent PAR ENVIRONNEMENT
(le moteur recalcule le théorique avec les absences validées de la base
visée — les saisies d'été du service paie n'existent que sur test), et les
identifiants de la base de test ne vivent que dans les secrets GitHub. La
CI est donc le seul endroit où le moteur peut tourner contre le test.

Source des cibles : feuille Drive « compteur COLORPLAST FIN AOUT.xlsx »
(service paie, 07/09/2026), recoupée avec les bulletins Quadra de Bugny.
Même mécanisme que la prod (appliquée et vérifiée au centime le 08/09) :
apply_cp_solde_import, note « Import CP bulletin Août 2026 » (ancre le mode
« fidèle au bulletin »), soldes RTT affichés repassés tels quels.

Usage : python scripts/recalage_cp_test_env.py [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.absences.application.leave_settings_commands import (  # noqa: E402
    apply_cp_solde_import,
)
from app.modules.absences.application.queries import get_my_absence_balances  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast (id identique prod/test)
YEAR = 2026
MONTH = 8  # référence 31/08/2026

#: (cp_n1, cp_n) à fin août — feuille du service paie.
CIBLES = {
    "BUGNY": (28.0, 6.24),
    "COTTE": (10.0, 6.24),
    "ESPINOSA": (13.0, 6.24),
    "FUCKAR": (0.0, -0.43),
    "GAUTHERON": (3.0, 6.24),
    "GIRERD": (12.0, 6.24),
}

NOTE = (
    "Import CP bulletin Août 2026 (compteurs fin août — feuille service paie "
    "du 07/09/2026, saisie via workflow recalage-cp-test)"
)


def rtt_affiche(employee_id: str) -> float:
    for b in get_my_absence_balances(employee_id):
        if str(b.get("type", "")).upper() == "RTT":
            rem = b.get("remaining")
            return float(rem) if rem is not None else 0.0
    return 0.0


def main() -> int:
    apply = "--apply" in sys.argv
    emps = (
        supabase.table("employees")
        .select("id, last_name, first_name, employment_status")
        .eq("company_id", COMPANY_ID)
        .execute()
    ).data
    by_name: dict[str, list] = {}
    for e in emps:
        by_name.setdefault(str(e["last_name"]).upper(), []).append(e)

    plan = []
    for nom, (n1, n) in CIBLES.items():
        cands = [
            e
            for e in by_name.get(nom, [])
            if e["employment_status"] in ("actif", "en_sortie")
        ]
        if len(cands) != 1:
            print(f"REFUS {nom}: {len(cands)} correspondance(s) active(s)")
            return 1
        emp = cands[0]
        rtt = rtt_affiche(emp["id"])
        plan.append((emp, n1, n, rtt))
        print(
            f"{nom:12s} {emp['first_name']:10s} -> CP N-1 cible {n1:6.2f} | "
            f"CP N cible {n:6.2f} | RTT préservé {rtt:6.2f}"
        )

    if not apply:
        print("\nSIMULATION — rien écrit. Relancer avec --apply.")
        return 0

    for emp, n1, n, rtt in plan:
        apply_cp_solde_import(
            COMPANY_ID,
            emp["id"],
            YEAR,
            cp_n1_solde=n1,
            cp_n_solde=n,
            rtt_solde=rtt,
            month=MONTH,
            note=NOTE,
        )
        print(f"OK {emp['last_name']}")

    print("\nContrôle post-écriture (solde CP affiché) :")
    ecart_detecte = False
    for emp, n1, n, _ in plan:
        attendu = max(0.0, n1) + max(0.0, n)
        for b in get_my_absence_balances(emp["id"]):
            t = str(b.get("type", ""))
            if t == "Congés Payés":
                affiche = b.get("remaining")
                # Les prises postérieures au 31/08 réduisent légitimement
                # l'affiché : on signale seulement un affiché SUPÉRIEUR.
                statut = "OK" if affiche is not None and affiche <= attendu + 0.01 else "ECART"
                if statut == "ECART":
                    ecart_detecte = True
                print(
                    f"{emp['last_name']:12s} affiché={affiche} "
                    f"(cible 31/08 ~{attendu:.2f}) {statut}"
                )
    return 1 if ecart_detecte else 0


if __name__ == "__main__":
    raise SystemExit(main())
