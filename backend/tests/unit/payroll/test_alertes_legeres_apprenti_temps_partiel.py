"""Deux alertes légères, sans blocage (12/10) : salaire d'apprenti sous le minimum légal,
heures complémentaires au-delà de la limite d'un temps partiel.

Barème des apprentis : service-public.fr, fiche F2918 (pourcentage du SMIC selon
l'âge et l'année d'apprentissage ; les majorations d'âge jouent le 1er du mois
suivant l'anniversaire). Limite des heures complémentaires : 1/10 de la durée
du contrat (service-public.fr, fiche F32428), sauf accord qui prévoit autrement.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.controles_convention import (
    controle_heures_complementaires,
    controle_salaire_apprenti,
)

pytestmark = pytest.mark.unit

SMIC_MENSUEL = 1823.03  # 35 h


def _apprenti(*, naissance, debut, periode, salaire, duree=35.0, apprenti=True):
    return SimpleNamespace(
        is_apprenti=apprenti,
        date_naissance=naissance,
        date_debut_execution=debut,
        date_fin_periode=periode,
        duree_hebdo_contrat=duree,
        smic_mensuel_proratise=lambda proratiser=True: SMIC_MENSUEL * duree / 35.0,
        contrat={"remuneration": {"salaire_de_base": {"valeur": salaire}}},
    )


def _codes(alertes):
    return [a["code"] for a in alertes]


def test_apprenti_de_19_ans_en_premiere_annee_sous_43_pour_cent_du_smic():
    ctx = _apprenti(naissance="2007-03-02", debut="2026-09-01", periode=date(2026, 10, 31), salaire=700.0)
    alertes = controle_salaire_apprenti(ctx, 700.0)
    assert _codes(alertes) == ["apprenti_salaire_sous_minimum_legal"]
    assert alertes[0]["critique"] is False
    assert "43 %" in alertes[0]["message"]
    assert "783,90 €" in alertes[0]["message"]  # 43 % de 1 823,03 €


def test_apprenti_au_minimum_ou_au_dessus_pas_d_alerte():
    ctx = _apprenti(naissance="2007-03-02", debut="2026-09-01", periode=date(2026, 10, 31), salaire=783.90)
    assert controle_salaire_apprenti(ctx, 783.90) == []


def test_la_tranche_d_age_change_le_premier_du_mois_suivant_l_anniversaire():
    # 21 ans le 15 octobre : encore 43 % en octobre, 53 % en novembre.
    octobre = _apprenti(naissance="2005-10-15", debut="2026-09-01", periode=date(2026, 10, 31), salaire=800.0)
    novembre = _apprenti(naissance="2005-10-15", debut="2026-09-01", periode=date(2026, 11, 30), salaire=800.0)
    assert controle_salaire_apprenti(octobre, 800.0) == []
    assert _codes(controle_salaire_apprenti(novembre, 800.0)) == ["apprenti_salaire_sous_minimum_legal"]


def test_deuxieme_annee_a_partir_du_premier_anniversaire_du_contrat():
    # 17 ans, 2e année : 39 % de 1 823,03 € = 710,98 €.
    ctx = _apprenti(naissance="2009-05-01", debut="2025-09-01", periode=date(2026, 10, 31), salaire=700.0)
    alertes = controle_salaire_apprenti(ctx, 700.0)
    assert "39 %" in alertes[0]["message"]


def test_temps_partiel_le_minimum_suit_la_duree_du_contrat():
    # 17 h 30 : la moitié du minimum, soit 43 % de 911,52 € = 391,95 €.
    ctx = _apprenti(naissance="2007-03-02", debut="2026-09-01", periode=date(2026, 10, 31), salaire=400.0, duree=17.5)
    assert controle_salaire_apprenti(ctx, 400.0) == []


@pytest.mark.parametrize(
    "champs",
    [
        {"naissance": ""},
        {"debut": ""},
        {"periode": None},
        {"salaire": 0.0},
        {"apprenti": False},
    ],
)
def test_il_manque_une_donnee_pas_d_alerte(champs):
    base = dict(naissance="2007-03-02", debut="2026-09-01", periode=date(2026, 10, 31), salaire=700.0)
    base.update(champs)
    assert controle_salaire_apprenti(_apprenti(**base), 700.0) == []


def _temps_partiel(duree, heures_compl):
    return SimpleNamespace(duree_hebdo_contrat=duree, heures_complementaires_mois=heures_compl)


def test_heures_complementaires_au_dela_du_dixieme_du_contrat():
    # 24 h par semaine = 104 h par mois ; le dixième = 10,40 h.
    alertes = controle_heures_complementaires(_temps_partiel(24.0, 12.0))
    assert _codes(alertes) == ["temps_partiel_heures_complementaires_limite"]
    assert alertes[0]["critique"] is False
    assert "12,00 h" in alertes[0]["message"]
    assert "10,40 h" in alertes[0]["message"]


@pytest.mark.parametrize(
    "duree,heures",
    [(24.0, 10.4), (24.0, 0.0), (35.0, 30.0), (39.0, 30.0), (24.0, None)],
)
def test_dans_la_limite_ou_pas_temps_partiel_pas_d_alerte(duree, heures):
    assert controle_heures_complementaires(_temps_partiel(duree, heures)) == []
