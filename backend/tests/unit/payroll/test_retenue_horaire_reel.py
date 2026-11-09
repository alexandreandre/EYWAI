"""R-381 : la retenue d'absence se calcule à l'horaire réel du mois.

Cass. soc. 11/02/1982, n° 80-40.359 : salaire du mois divisé par les heures de
travail du mois considéré (lu via Human Avocats, Payfit et Fiche-paie : Légifrance
ne s'ouvre pas). Un réglage de société garde le taux moyen pour une convention
qui l'imposerait.
"""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import (
    calculer_salaire_brut,
    coefficient_horaire_reel,
)
from app.modules.payroll.engine.maintien_salaire_service import _base_des_jours

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUILLET = (date(2026, 7, 1), date(2026, 7, 31))  # 23 jours ouvrés
FEVRIER = (date(2026, 2, 1), date(2026, 2, 28))  # 20 jours ouvrés
JOURS_MOYENS = 151.67 / 7
SALAIRE = 2000.0


def _contexte(**kwargs):
    return build_test_contexte(salaire_base=SALAIRE, duree_hebdo=35.0, **kwargs)


def _absence(iso, type_ev="absence_non_remuneree", heures=7.0):
    return {"date_complete": iso, "type": type_ev, "heures": heures}


def _ligne(res, motif):
    return next(l for l in res["lignes_composants_brut"] if motif in str(l.get("libelle")))


def test_le_coefficient_suit_les_jours_ouvres_du_mois():
    ctx = _contexte()
    assert coefficient_horaire_reel(ctx, date(2026, 7, 7)) == pytest.approx(JOURS_MOYENS / 23)
    assert coefficient_horaire_reel(ctx, date(2026, 2, 3)) == pytest.approx(JOURS_MOYENS / 20)


def test_le_mois_long_retient_moins_que_le_taux_moyen():
    res = calculer_salaire_brut(_contexte(), [_absence("2026-07-07")], *JUILLET, [])
    taux_reel = SALAIRE / 151.67 * JOURS_MOYENS / 23
    assert _ligne(res, "Absence non rémunérée")["perte"] == pytest.approx(round(7 * taux_reel, 2), abs=0.01)


def test_le_mois_court_retient_plus_que_le_taux_moyen():
    res = calculer_salaire_brut(_contexte(), [_absence("2026-02-03")], *FEVRIER, [])
    taux_reel = SALAIRE / 151.67 * JOURS_MOYENS / 20
    assert _ligne(res, "Absence non rémunérée")["perte"] == pytest.approx(round(7 * taux_reel, 2), abs=0.01)


def test_tous_les_jours_du_mois_retiennent_le_salaire():
    jours = [date(2026, 7, j) for j in range(1, 32)]
    cal = [
        {**_absence(j.isoformat(), "arret_maladie"), "arret_type": "maladie_simple"}
        for j in jours
        if j.weekday() < 5
    ]
    res = calculer_salaire_brut(_contexte(), cal, *JUILLET, [])
    retenue = sum(float(l.get("perte") or 0) for l in res["lignes_composants_brut"] if l.get("is_arret_maladie"))
    assert retenue == pytest.approx(SALAIRE, abs=0.5)


def test_le_reglage_de_societe_garde_le_taux_moyen():
    ctx = _contexte()
    ctx.entreprise.setdefault("parametres_paie", {})["methode_retenue_absence"] = "taux_moyen"
    assert coefficient_horaire_reel(ctx, date(2026, 7, 7)) == 1.0
    res = calculer_salaire_brut(ctx, [_absence("2026-07-07")], *JUILLET, [])
    assert _ligne(res, "Absence non rémunérée")["perte"] == pytest.approx(round(7 * SALAIRE / 151.67, 2), abs=0.01)


def test_le_mois_d_entree_garde_son_prorata():
    ctx = _contexte(date_entree="2026-07-10")
    res = calculer_salaire_brut(ctx, [_absence("2026-07-20")], *JUILLET, [])
    assert ctx.coefficient_horaire_reel == 1.0
    assert _ligne(res, "Absence non rémunérée")["taux"] == pytest.approx(SALAIRE / 151.67, abs=0.01)


def test_le_maintien_restitue_au_meme_taux():
    ctx = _contexte()
    calculer_salaire_brut(ctx, [_absence("2026-07-07", "arret_maladie")], *JUILLET, [])
    arret = {"date_debut": "2026-07-07", "date_fin": "2026-07-09", "maintien_base_ouvree": True}
    base = _base_des_jours(arret, ctx, *JUILLET)
    assert base.taux_horaire_base == pytest.approx(SALAIRE / 151.67 * JOURS_MOYENS / 23, abs=0.001)
