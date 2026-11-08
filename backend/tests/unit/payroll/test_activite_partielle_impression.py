"""Activité partielle : le bulletin imprime les heures et le taux, pas le seul montant."""

import pytest

from app.modules.payroll.documents.bulletin_view import _ligne_brut, _lignes_hors_brut
from app.modules.payroll.engine.activite_partielle import heures_et_taux

pytestmark = pytest.mark.unit


def test_heures_et_taux_depuis_la_saisie():
    assert heures_et_taux(-290.0, 20.0) == {"quantite": 20.0, "taux": 14.5}


def test_sans_heures_saisies_rien_n_est_invente():
    assert heures_et_taux(-290.0, 0.0) == {}


def test_la_ligne_de_chomage_imprime_heures_et_taux():
    ligne = _ligne_brut({"libelle": "Heures chômées (act. part.)", "gain": -290.0, "quantite": 20.0, "taux": 14.5})
    assert (ligne["base"], ligne["taux"]) == (20.0, 14.5)


def test_l_indemnite_imprime_heures_et_taux():
    lignes = _lignes_hors_brut(
        {"revenus_hors_brut_imposables": [{"libelle": "Indemnité activité partielle", "montant": 190.4, "quantite": 20.0, "taux": 9.52}]}
    )
    assert (lignes[0]["base"], lignes[0]["taux"], lignes[0]["montant_salarial"]) == (20.0, 9.52, 190.4)
