"""Forfait jour : retenues d'absence (journée, diviseur société, férié non payé,
mois entier, jours hors contrat) et entrée au premier jour ouvré.

Valeurs de référence : bulletins du cabinet (Cegid) MAJI / ZONE 404 2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _ev(jour: str, type_ev: str, heures: float = 7.8) -> dict:
    return {"date_complete": jour, "type": type_ev, "heures": heures}


def _brut(ctx, cal, debut, fin):
    return calculer_salaire_brut_forfait(ctx, cal, debut, fin, [])


def _ctx(**kw):
    ctx = build_test_contexte(statut="Cadre", salaire_base=kw.pop("salaire", 3608.0),
                              specificites_extra={"is_forfait_jour": True}, **kw)
    return ctx


def test_absence_non_remuneree_vaut_une_journee_par_jour():
    # ASSANHAJI Zone 404 03/2026 : 5 j non rémunérés posés à 7,8 h « prévues »
    # (gabarit horaire) valaient 7,8 journées chacun et vidaient le brut.
    ctx = _ctx()
    cal = [_ev(f"2026-03-{d:02d}", "absence_non_remuneree") for d in (16, 17, 18, 19, 20)]
    res = _brut(ctx, cal, date(2026, 3, 1), date(2026, 3, 31))
    attendu = 3608.0 - 5 * 3608.0 / 21.67
    assert res["salaire_brut_total"] == pytest.approx(round(attendu, 2), abs=0.02)


def test_diviseur_societe_pour_les_absences_mais_pas_les_conges():
    ctx = _ctx()
    ctx.entreprise.setdefault("parametres_paie", {})["forfait_jours_ouvres_mois"] = 22
    cal = [_ev("2026-03-16", "arret_maladie", 0.0)]
    res = _brut(ctx, cal, date(2026, 3, 1), date(2026, 3, 31))
    lignes = {l["libelle"]: l for l in res["lignes_composants_brut"]}
    ligne = next(v for k, v in lignes.items() if k.startswith("Absence maladie"))
    assert ligne["perte"] == pytest.approx(round(3608.0 / 22, 2), abs=0.01)


def test_ferie_non_paye_retenu_sous_trois_mois_d_anciennete():
    # BARAN Zone 404, entré le 05/03/2026 : lundi de Pâques 06/04 non payé → 5 000 / 22.
    ctx = _ctx(salaire=5000.0, date_entree="2026-03-05", prior_service_months=0)
    ctx.entreprise.setdefault("parametres_paie", {})["forfait_jours_ouvres_mois"] = 22
    cal = [_ev("2026-04-06", "ferie", 0.0)]
    res = _brut(ctx, cal, date(2026, 4, 1), date(2026, 4, 30))
    assert res["salaire_brut_total"] == pytest.approx(5000.0 - 227.27, abs=0.02)


def test_ferie_paye_avec_anciennete():
    ctx = _ctx(salaire=5000.0, date_entree="2020-01-01")
    cal = [_ev("2026-04-06", "ferie", 0.0)]
    res = _brut(ctx, cal, date(2026, 4, 1), date(2026, 4, 30))
    assert res["salaire_brut_total"] == pytest.approx(5000.0, abs=0.01)


def test_ferie_avant_l_entree_non_retenu_deux_fois():
    # FILLINGER Zone 404, entré le 27/04 : Pâques 06/04 est déjà dans le prorata d'entrée.
    ctx = _ctx(salaire=3166.66, date_entree="2026-04-27", prior_service_months=0)
    ctx.entreprise.setdefault("parametres_paie", {})["forfait_jours_ouvres_mois"] = 22
    cal = [_ev("2026-04-06", "ferie", 0.0)]
    res = _brut(ctx, cal, date(2026, 4, 1), date(2026, 4, 30))
    # 22 jours ouvrés en avril 2026, 18 avant l'entrée → 4/22.
    assert res["salaire_brut_total"] == pytest.approx(round(3166.66 * 4 / 22, 2), abs=0.02)


def test_mois_entier_absent_vaut_zero_meme_a_vingt_jours_ouvres():
    # ANDRE MAJI 02/2026 : 20 jours ouvrés d'arrêt sur 20 → brut 0 (pas 7,7 % de résidu).
    ctx = _ctx(salaire=6666.66)
    ctx.entreprise.setdefault("parametres_paie", {})["forfait_jours_ouvres_mois"] = 22
    cal = [
        _ev(date(2026, 2, d).isoformat(), "arret_maladie", 0.0)
        for d in range(1, 29)
        if date(2026, 2, d).weekday() < 5
    ]
    res = _brut(ctx, cal, date(2026, 2, 1), date(2026, 2, 28))
    assert res["salaire_brut_total"] == pytest.approx(0.0, abs=0.01)


def test_entree_au_premier_jour_ouvre_apres_un_ferie_vaut_un_mois_complet():
    # SMITH MAJI, entré le lundi 04/05/2026 (1er mai férié, puis week-end) : salaire plein.
    ctx = _ctx(salaire=1396.18, date_entree="2026-05-04", prior_service_months=0)
    cal = [_ev("2026-05-01", "ferie", 0.0)]
    res = _brut(ctx, cal, date(2026, 5, 1), date(2026, 5, 31))
    assert res["salaire_brut_total"] == pytest.approx(1396.18, abs=0.01)


def test_entree_en_cours_de_mois_proratisee_en_jours_ouvres():
    # BARBERET MAJI, entré le 23/01/2026 : 6 jours ouvrés payés sur 22.
    ctx = _ctx(salaire=3000.0, date_entree="2026-01-23", prior_service_months=0)
    cal = [_ev("2026-01-01", "ferie", 0.0)]
    res = _brut(ctx, cal, date(2026, 1, 1), date(2026, 1, 31))
    assert res["salaire_brut_total"] == pytest.approx(round(3000.0 * 6 / 22, 2), abs=0.02)
