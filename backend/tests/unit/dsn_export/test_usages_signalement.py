import pytest

from app.modules.dsn_export.domain.usages_signalement import (
    NATURE_ARRET,
    NATURE_REPRISE,
    filtrer,
)


def test_le_contrat_ne_garde_que_debut_numero_et_lieu():
    contrat = {
        "S21.G00.40.001": "01092026", "S21.G00.40.002": "04", "S21.G00.40.004": "674a",
        "S21.G00.40.007": "02", "S21.G00.40.009": "00001", "S21.G00.40.019": "80248516900011",
    }
    assert filtrer(contrat, NATURE_ARRET) == {
        "S21.G00.40.001": "01092026", "S21.G00.40.009": "00001",
        "S21.G00.40.019": "80248516900011",
    }


def test_la_subrogation_est_interdite_dans_une_reprise():
    arret = {"S21.G00.60.001": "01", "S21.G00.60.004": "01", "S21.G00.60.007": "FR76",
             "S21.G00.60.010": "13102026"}
    assert filtrer(arret, NATURE_REPRISE) == {"S21.G00.60.001": "01", "S21.G00.60.010": "13102026"}
    assert filtrer(arret, NATURE_ARRET)["S21.G00.60.004"] == "01"


def test_le_mois_principal_et_l_ape_sont_interdits():
    assert filtrer({"S20.G00.05.005": "01102026", "S21.G00.06.003": "2229A"}, NATURE_ARRET) == {}


def test_une_nature_inconnue_est_refusee():
    with pytest.raises(ValueError):
        filtrer({}, "08")


def test_la_fin_de_contrat_garde_le_salarie_et_ecarte_l_etablissement():
    from app.modules.dsn_export.domain.usages_signalement import NATURE_FCTU

    rubriques = {
        "S20.G00.05.005": "01102026", "S21.G00.20.001": "URSSAF", "S21.G00.23.001": "100",
        "S21.G00.40.007": "02", "S21.G00.50.020": "01", "S21.G00.62.020": "01102026",
        "S21.G00.78.001": "03", "S21.G00.81.001": "018", "S21.G00.86.001": "07",
    }
    assert filtrer(rubriques, NATURE_FCTU) == {
        "S21.G00.40.007": "02", "S21.G00.50.020": "01", "S21.G00.62.020": "01102026",
        "S21.G00.78.001": "03", "S21.G00.81.001": "018", "S21.G00.86.001": "07",
    }
