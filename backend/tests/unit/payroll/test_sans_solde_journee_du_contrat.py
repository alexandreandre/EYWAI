"""Congé sans solde à 0 h : la journée retenue est la durée journalière du contrat.

Une demande « sans solde » validée écrit le jour en `absence_non_remuneree` à
0 h prévue (depuis le 01/10/2026). Le moteur imputait alors la journée légale
(`min(contrat ; 35) ÷ 5` = 7 h), puis la répartissait 35/39 sur un contrat de
39 h : 6,28 h de base + 0,72 h d'heures sup structurelles, soit 7 h au lieu de
7,8 h. Quadra retient 7 h de base plus 0,8 h structurelle par jour de « Congés
sans solde » (Colorplast, août 2026 : 4 jours, 28 h et 3,2 h), comme le moteur
le fait déjà pour une journée d'arrêt. Écart mesuré : 10,83 € de retenue par
jour pour un salarié à 39 h.

Règle : un jour sans solde à 0 h retient la durée journalière du contrat
(durée hebdomadaire ÷ 5) ; une demi-journée (`quotite_absence` = 0,5), sa
moitié. Un jour qui porte ses heures prévues garde la règle du prorata 35/39
sur ces heures (test_absence_prorata_contrat.py), inchangée.
"""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUILLET = (date(2026, 7, 1), date(2026, 7, 31))
JOUR_SANS_SOLDE = "2026-07-07"


def _calendrier(duree_hebdo: float, quotite: float | None = None) -> list[dict]:
    """Un mois travaillé à la journée du contrat, sauf le 07/07 sans solde à 0 h."""
    cal = []
    jour = date(2026, 7, 1)
    while jour.month == 7:
        if jour.weekday() < 5:
            iso = jour.isoformat()
            if iso == JOUR_SANS_SOLDE:
                ev = {"date_complete": iso, "type": "absence_non_remuneree", "heures": 0.0}
                if quotite is not None:
                    ev["quotite_absence"] = quotite
                    ev["demi_journee"] = "matin"
                cal.append(ev)
            else:
                cal.append({"date_complete": iso, "type": "travail_base", "heures": duree_hebdo / 5})
        jour = date.fromordinal(jour.toordinal() + 1)
    return cal


def _lignes(res, motif: str):
    return [l for l in res["lignes_composants_brut"] if motif in str(l.get("libelle"))]


def test_journee_sans_solde_39h_retient_7h_plus_0h80():
    ctx = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    res = calculer_salaire_brut(ctx, _calendrier(39.0), *JUILLET, [])

    absences = _lignes(res, "Absence non rémunérée")
    assert [l["quantite"] for l in absences] == [7.0]
    reduction = _lignes(res, "Réduction HS structurelles")
    assert len(reduction) == 1
    assert reduction[0]["quantite"] == pytest.approx(0.8, abs=0.005)


def test_journee_sans_solde_39h_retient_comme_une_journee_d_arret():
    # Même salarié, même jour : la journée d'arrêt retient 7 h + 0,8 h
    # structurelle (Quadra, S13). Le sans solde retient la même somme.
    ctx = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    sans_solde = calculer_salaire_brut(ctx, _calendrier(39.0), *JUILLET, [])

    cal_arret = [
        {**e, "type": "arret_maladie"} if e["date_complete"] == JOUR_SANS_SOLDE else e
        for e in _calendrier(39.0)
    ]
    ctx2 = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    arret = calculer_salaire_brut(ctx2, cal_arret, *JUILLET, [])

    def retenue(res):
        return round(sum(float(l.get("perte") or 0) for l in res["lignes_composants_brut"]), 2)

    assert retenue(sans_solde) == retenue(arret)


def test_demi_journee_sans_solde_39h_retient_3h50_plus_0h40():
    ctx = build_test_contexte(salaire_base=2278.11, duree_hebdo=39.0)
    res = calculer_salaire_brut(ctx, _calendrier(39.0, quotite=0.5), *JUILLET, [])

    absences = _lignes(res, "Absence non rémunérée")
    assert [l["quantite"] for l in absences] == [3.5]
    reduction = _lignes(res, "Réduction HS structurelles")
    assert reduction[0]["quantite"] == pytest.approx(0.4, abs=0.005)


def test_demi_journee_sans_solde_35h_retient_3h50():
    ctx = build_test_contexte(salaire_base=2000.0, duree_hebdo=35.0)
    res = calculer_salaire_brut(ctx, _calendrier(35.0, quotite=0.5), *JUILLET, [])

    absences = _lignes(res, "Absence non rémunérée")
    assert [l["quantite"] for l in absences] == [3.5]
    assert _lignes(res, "Réduction HS structurelles") == []


def test_journee_sans_solde_35h_et_temps_partiel_inchangees():
    ctx35 = build_test_contexte(salaire_base=2000.0, duree_hebdo=35.0)
    res35 = calculer_salaire_brut(ctx35, _calendrier(35.0), *JUILLET, [])
    assert [l["quantite"] for l in _lignes(res35, "Absence non rémunérée")] == [7.0]

    ctx24 = build_test_contexte(salaire_base=1400.0, duree_hebdo=24.0, is_temps_partiel=True)
    res24 = calculer_salaire_brut(ctx24, _calendrier(24.0), *JUILLET, [])
    assert [l["quantite"] for l in _lignes(res24, "Absence non rémunérée")] == [4.8]
