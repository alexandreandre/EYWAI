"""Juin 2026 de Colorplast rejoué depuis les feuilles de pointage, sur le TEST.

Le rejeu (`colorplast_rejeu_test.py`) juge le moteur sur les entrées de Quadra :
de février à juillet, la quantité d'heures sup est une saisie mensuelle lue sur
le bulletin du cabinet. Ce script pose l'autre question — celle de janvier,
étendue à la fenêtre de juin (25/05 → 21/06, semaines 22 à 25) : à partir des
feuilles brutes, le moteur retrouve-t-il seul les heures au-delà de 39 h et
leur répartition 25 % / 50 % ?

Déroulé, en bac à sable comme le rejeu : fiches relevées, juin posé par le
setup, feuilles écrites au calendrier réel (25 au 29/05 dans mai, 1ᵉʳ au 19/06
dans juin), saisies d'heures sup effacées, bulletins de juin générés. Puis
feuilles effacées, juin reposé et regénéré sur les saisies du cabinet, fiches
remises : la base est rendue telle que le rejeu l'a laissée.

Chaque bulletin est comparé à deux choses : ce que la règle hebdomadaire donne
sur les feuilles (le contrôle qui fait échouer le script — c'est le moteur
qu'on juge), et ce que le cabinet a payé (imprimé, pas jugé : ses écarts sont
expliqués dans `docs/colorplast-juin-2026-ligne-a-ligne.md`).

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payslips.application.dto import PayslipBadRequestError  # noqa: E402
from scripts.backtest.colorplast_feuilles_juin import (  # noqa: E402
    FEUILLES,
    MOIS,
    YEAR,
    effacer_les_feuilles,
    heures_par_semaine,
    heures_sup_attendues,
    poser_les_feuilles,
)
from scripts.backtest.colorplast_setup import MONTH_DATA, apply_month  # noqa: E402
from scripts.colorplast_rejeu_test import (  # noqa: E402
    COMPANY_ID,
    REFERENCES,
    SALARIES,
    _bulletin,
    _generer,
    _nettoyer_les_doublons_du_cabinet,
    _restaurer,
    _salaries_du_mois,
    _snapshot,
)

TOLERANCE_HEURES = 0.01


def _payees_par_le_cabinet(nom: str) -> tuple[float, float]:
    cfg = MONTH_DATA[MOIS].get(nom, {})
    return float(cfg.get("hs25") or 0.0), float(cfg.get("hs50") or 0.0)


def _heures_sup_du_bulletin(data: dict) -> tuple[float, float]:
    """Quantités des lignes d'heures sup conjoncturelles du brut (à 25 %, à 50 %)."""
    hs25 = hs50 = 0.0
    for ligne in data.get("calcul_du_brut") or []:
        lib = str(ligne.get("libelle", "")).lower()
        if "suppl" not in lib or "structur" in lib:
            continue
        quantite = float(ligne.get("quantite") or 0.0)
        if "50" in lib:
            hs50 += quantite
        else:
            hs25 += quantite
    return round(hs25, 2), round(hs50, 2)


def _imprimer_les_feuilles() -> None:
    print("=== Feuilles S22 à S25, total pointé par semaine, et ce qu'en fait la règle hebdomadaire ===")
    for nom in sorted(FEUILLES):
        semaines = " ".join(f"S{s}={t:g}" for s, t in heures_par_semaine(nom).items())
        a25, a50 = heures_sup_attendues(nom)
        c25, c50 = _payees_par_le_cabinet(nom)
        print(f"  {nom:10s} {semaines:44s} → {a25:5.2f} à 25 %, {a50:5.2f} à 50 % "
              f"(cabinet : {c25:g} et {c50:g})")


def _controler(nom: str, data: dict, res) -> int:
    q25, q50 = _heures_sup_du_bulletin(data)
    a25, a50 = heures_sup_attendues(nom) if nom in FEUILLES else (0.0, 0.0)
    c25, c50 = _payees_par_le_cabinet(nom)
    en_tete = data.get("en_tete") or {}
    brut = float(data.get("salaire_brut") or 0)
    ok = abs(q25 - a25) <= TOLERANCE_HEURES and abs(q50 - a50) <= TOLERANCE_HEURES
    print(f"\n{'OK' if ok else 'ECART':5s} {nom:10s} moteur {q25:5.2f} à 25 %, {q50:5.2f} à 50 % ; "
          f"feuilles {a25:5.2f} et {a50:5.2f} ; cabinet {c25:g} et {c50:g} ; "
          f"brut {brut:.2f} (Quadra {REFERENCES[MOIS]['brut'][nom]:.2f}, "
          f"écart {brut - REFERENCES[MOIS]['brut'][nom]:+.2f}) ; "
          f"fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; {res.status}")
    for ligne in data.get("calcul_du_brut") or []:
        lib = str(ligne.get("libelle", ""))
        if "suppl" in lib.lower() and "structur" not in lib.lower():
            print(f"      HS      {lib[:50]:50s} q={ligne.get('quantite')} +{ligne.get('gain')}")
    for cle in ("details_absences", "details_conges"):
        for ligne in data.get(cle) or []:
            print(f"      {cle[8:15]:7s} {str(ligne.get('libelle'))[:50]:50s} "
                  f"q={ligne.get('quantite')} -{ligne.get('perte')} +{ligne.get('gain')}")
    for w in res.warnings or []:
        print(f"      avertissement : {w}")
    if not ok:
        print(f"::error::{nom} {MOIS:02d}/{YEAR} : le moteur ne retrouve pas les heures sup des feuilles "
              f"({q25:.2f}/{q50:.2f} pour {a25:.2f}/{a50:.2f})")
    return 0 if ok else 1


def _generer_le_mois(emps: dict) -> dict[str, tuple[dict, object]]:
    bulletins = {}
    for nom in _salaries_du_mois(MOIS):
        try:
            res = _generer(emps[nom]["id"], MOIS)
        except PayslipBadRequestError as exc:
            print(f"::error::{nom} {MOIS:02d}/{YEAR} : {exc}")
            continue
        bulletins[nom] = (_bulletin(emps[nom]["id"], MOIS), res)
    return bulletins


def main() -> int:
    apply = "--apply" in sys.argv
    _imprimer_les_feuilles()
    if not apply:
        print("\nSIMULATION : rien n'est écrit. Avec --apply, juin est généré depuis ces feuilles puis remis en état.")
        return 0

    emps = {
        e["last_name"]: e
        for e in (supabase.table("employees").select("id, last_name")
                  .eq("company_id", COMPANY_ID).in_("last_name", list(SALARIES)).execute()).data or []
    }
    manquants = sorted(set(_salaries_du_mois(MOIS)) - set(emps))
    if manquants:
        print(f"::error::Salariés introuvables : {manquants}")
        return 1

    emp_avant, hist_avant = _snapshot([e["id"] for e in emps.values()])
    rc = 0
    try:
        print(f"\n{'=' * 62}\n=== {MOIS:02d}/{YEAR} : juin posé par le setup, puis les feuilles par-dessus\n{'=' * 62}")
        _nettoyer_les_doublons_du_cabinet(emps, [MOIS])
        apply_month("Colorplast", YEAR, MOIS)
        poser_les_feuilles(emps)
        print("\n=== Bulletins de juin générés depuis les feuilles ===")
        bulletins = _generer_le_mois(emps)
        if len(bulletins) != len(_salaries_du_mois(MOIS)):
            rc = 1
        for nom, (data, res) in bulletins.items():
            rc |= _controler(nom, data, res)
    finally:
        print(f"\n{'=' * 62}\n=== Remise en état : feuilles effacées, juin reposé sur les saisies du cabinet\n{'=' * 62}")
        effacer_les_feuilles(emps)
        apply_month("Colorplast", YEAR, MOIS)
        regeneres = _generer_le_mois(emps)
        for nom, (data, _res) in regeneres.items():
            q25, q50 = _heures_sup_du_bulletin(data)
            print(f"  {nom:10s} brut {float(data.get('salaire_brut') or 0):.2f} "
                  f"(Quadra {REFERENCES[MOIS]['brut'][nom]:.2f}) ; HS {q25:g} / {q50:g}")
        print("\n=== Fiches remises comme avant ===")
        _restaurer(emp_avant, hist_avant)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
