"""Sous le barème, un jour maintenu vaut ce que son absence a retiré du salaire.

Mois entier en arrêt : le salaire du mois, réparti au prorata des jours.
Mois partiel : la journée, comptée par bloc comme le cabinet (conception du
24/10/2026, §3.3). Salaires de la fiche de Comitech, initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.maintien_salaire_service import _base_des_jours

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

JUIN = (date(2026, 6, 1), date(2026, 6, 30))
JUILLET = (date(2026, 7, 1), date(2026, 7, 31))
MAI = (date(2026, 5, 1), date(2026, 5, 31))
AVRIL = (date(2026, 4, 1), date(2026, 4, 30))


def _sg():
    return build_test_contexte(
        salaire_base=1952.60, duree_hebdo=39.0, date_entree="2003-07-15",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _ds():
    return build_test_contexte(
        statut="Cadre", salaire_base=3368.60, duree_hebdo=39.0, date_entree="2003-09-01",
        specificites_extra={"salaire_hors_hs_structurelles": True},
    )


def _base(contexte, debut, fin, periode, **extra):
    arret = {"date_debut": debut, "date_fin": fin, "maintien_base_ouvree": True, **extra}
    return _base_des_jours(arret, contexte, *periode)


def test_mois_entier_le_salaire_du_mois():
    base = _base(_sg(), "2026-05-04", "2026-09-30", JUIN)
    assert base.mois_entier and base.jours_du_mois == 22
    assert base.salaire_du_mois == 2231.48  # 1 952,60 + 17,33 h à 16,0925
    assert base.valeur(22) == 2231.48
    assert _base(_ds(), "2026-04-27", "2026-07-17", MAI).valeur(21) == 3849.73


def test_mois_entier_partage_entre_deux_paliers_au_prorata_des_jours_ouvres():
    base = _base(_sg(), "2026-05-04", "2026-09-30", JUILLET)
    assert base.jours_du_mois == 23
    assert (base.valeur(2), base.valeur(21)) == (194.04, 2037.44)


def test_mois_partiel_les_journees_comptees_par_bloc():
    assert _base(_sg(), "2026-05-04", "2026-05-31", MAI).valeur(20) == 2059.84
    ds = _base(_ds(), "2026-04-27", "2026-07-17", AVRIL)
    assert not ds.mois_entier
    assert ds.valeur(4) == 710.72
    assert _base(_ds(), "2026-07-18", "2026-07-26", JUILLET).valeur(5) == 888.40


def test_les_week_ends_ne_comptent_qu_en_jours_calendaires():
    ouvres = _base(_sg(), "2026-05-04", "2026-09-30", JUIN)
    assert not ouvres.compte(date(2026, 6, 6)) and ouvres.compte(date(2026, 6, 8))
    calendaires = _base_des_jours(
        {"date_debut": "2026-05-04", "date_fin": "2026-09-30"}, _sg(), *JUIN
    )
    assert calendaires.compte(date(2026, 6, 6))


def test_mode_calendaire_mois_entier_et_mois_partiel():
    contexte = build_test_contexte(salaire_base=2500.0)
    entier = _base_des_jours({"date_debut": "2026-05-04", "date_fin": "2026-09-30"}, contexte, *JUIN)
    assert entier.jours_du_mois == 30 and entier.valeur(30) == 2500.0
    partiel = _base_des_jours({"date_debut": "2026-06-08", "date_fin": "2026-06-17"}, contexte, *JUIN)
    assert partiel.valeur(10) == 821.83  # 2 500 / 30,42 × 10


def test_temps_partiel_la_quotite_ne_touche_que_la_journee():
    contexte = build_test_contexte(salaire_base=1500.0, duree_hebdo=21.0, is_temps_partiel=True)
    extra = {"is_temps_partiel": True, "quotite_temps_partiel": 0.6}
    assert _base(contexte, "2026-06-08", "2026-06-12", JUIN).valeur(5) == 576.92  # 35 h à 16,4835
    assert _base(contexte, "2026-06-08", "2026-06-12", JUIN, **extra).valeur(5) == 346.15
    entier = _base(contexte, "2026-05-04", "2026-09-30", JUIN, **extra)
    assert entier.valeur(22) == 1500.0


def test_plusieurs_arrets_qui_couvrent_le_mois_le_disent():
    base = _base(_sg(), "2026-06-16", "2026-06-30", JUIN, mois_entier_en_arret=True)
    assert base.mois_entier and base.valeur(11) == 1115.74
