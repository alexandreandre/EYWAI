"""Grille des salaires minima de la plasturgie 2026 : celle de l'accord, pas celle de l'extraction.

Source : accord du 19 février 2026 relatif aux salaires (IDCC 292), article 3.1 « Barèmes des
salaires minima mensuels », en vigueur au 1er mars 2026, étendu par arrêté du 23 septembre 2026
(JORF du 3 octobre 2026) — Légifrance KALIARTI000054177244 (lu le 26/10/2026) ; même grille sur
code.travail.gouv.fr (contribution 292, mise à jour du 01/06/2026).

La règle en base (`convention_collective_rules`, IDCC 0292) porte le titre et la date d'effet de
cet accord, mais des montants plus bas (coefficient 900 : 3 221 € au lieu de 3 366 €) : le
contrôle du minimum conventionnel (`controles_convention`, alerte `cc_salaire_sous_minimum`) se
faisait sur une grille fausse. Le moteur ne lit cette grille que pour ce contrôle (la prime
d'ancienneté de la plasturgie part du salaire de base).

Sans --ecrire : affiche les écarts, n'écrit rien. Avec --ecrire : sauvegarde JSON de la règle,
puis remplace les montants dans `salaires_minima` et dans la grille de l'accord.

Usage (depuis backend/) :
    PYTHONPATH=. python -m scripts.grille_plasturgie_2026 [--ecrire]
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

IDCC = "0292"
ACCORD = "Accord du 19 février 2026 relatif aux salaires"
DATE_EFFET = "2026-03-01"
SOURCE = "https://www.legifrance.gouv.fr/conv_coll/id/KALIARTI000054177244/?idConteneur=KALICONT000005635856"
#: Article 3.1 : coefficient → valeur mensuelle (euros), 151,67 h ou forfait jours.
GRILLE_2026: dict[int, float] = {
    700: 1835.0, 710: 1848.0, 720: 1868.0, 730: 1921.0, 740: 2004.0, 750: 2126.0,
    800: 2266.0, 810: 2424.0, 820: 2652.0, 830: 2841.0,
    900: 3366.0, 910: 3525.0, 920: 4047.0, 930: 5253.0, 940: 6543.0,
}


def _corriger_minima(minima: list[dict]) -> tuple[list[dict], list[str]]:
    sortie, ecarts = [], []
    for m in minima or []:
        m = dict(m)
        coeff = int(float(m.get("coefficient") or 0))
        attendu = GRILLE_2026.get(coeff)
        if attendu is not None and abs(float(m.get("valeur") or 0) - attendu) >= 0.005:
            ecarts.append(f"coefficient {coeff} : {float(m.get('valeur') or 0):.2f} → {attendu:.2f}")
            m["valeur"] = attendu
        sortie.append(m)
    return sortie, ecarts


def grille_corrigee(rules: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """(règles corrigées, écarts) : `salaires_minima` et la grille de l'accord du 19/02/2026
    (date d'effet 01/03/2026) prennent les montants de l'article 3.1. Les autres grilles
    (autres accords, autres dates) ne sont pas touchées."""
    nouvelles = copy.deepcopy(rules or {})
    nouvelles["salaires_minima"], ecarts = _corriger_minima(nouvelles.get("salaires_minima") or [])
    for g in nouvelles.get("grilles_salaires") or []:
        if str(g.get("date_effet") or "")[:10] == DATE_EFFET and ACCORD in str(g.get("source_titre") or ""):
            g["minima"], ecarts_g = _corriger_minima(g.get("minima") or [])
            ecarts += [f"grille du {DATE_EFFET} — {e}" for e in ecarts_g]
            g["source_url"] = SOURCE
    return nouvelles, ecarts


def main(ecrire: bool) -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if not ecrire:
        from scripts.verification_rgdu import piege

        piege.poser_le_piege()
    from app.core.database import supabase

    lignes = supabase.table("convention_collective_rules").select("idcc, rules").eq("idcc", IDCC).execute().data
    if len(lignes) != 1:
        print(f"!! {len(lignes)} règle(s) pour l'IDCC {IDCC}, une attendue")
        return 1
    rules = lignes[0]["rules"] or {}
    nouvelles, ecarts = grille_corrigee(rules)
    print(f"=== Plasturgie {IDCC}, {ACCORD} (effet {DATE_EFFET})")
    for e in ecarts:
        print("  " + e)
    print(f"{len(ecarts)} montant(s) de la grille à corriger.")
    if ecrire and ecarts:
        dossier = Path("/Users/alex/dev/EYWAI/data/_sauvegardes")
        dossier.mkdir(parents=True, exist_ok=True)
        sauvegarde = dossier / f"grille-plasturgie-avant-{datetime.now():%Y%m%d-%H%M%S}.json"
        sauvegarde.write_text(json.dumps(lignes[0], ensure_ascii=False, indent=1, default=str))
        supabase.table("convention_collective_rules").update({"rules": nouvelles}).eq("idcc", IDCC).execute()
        print(f"grille écrite ; sauvegarde : {sauvegarde}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--ecrire" in sys.argv))
