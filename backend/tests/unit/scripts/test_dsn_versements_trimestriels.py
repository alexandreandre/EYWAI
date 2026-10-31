"""Le paramétrage reprend du cabinet le jour de paiement et les types de population."""

from __future__ import annotations

import pytest

from scripts.dsn_versements_trimestriels import completer
from tests.unit.dsn_export.test_versements_complementaires import DSN_DU_CABINET

pytestmark = pytest.mark.unit


def test_le_jour_de_paiement_et_le_type_de_population_viennent_du_cabinet():
    versements = [{"organisme": "AGGEEV", "mode": "05"}, {"organisme": "DGFIP"}]
    contrats = [
        {"reference": "20000802485169", "organisme": "AGGEEV", "ordre": "1"},
        {"reference": "30000802485169", "organisme": "AGGEEV", "ordre": "3"},
    ]
    nouveaux_versements, nouveaux_contrats, changements = completer(
        versements, contrats, DSN_DU_CABINET
    )
    assert nouveaux_versements[0]["jour_paiement"] == "25"
    assert "jour_paiement" not in nouveaux_versements[1]
    assert nouveaux_contrats[0]["type_population"] == "NON CADRE"
    assert "type_population" not in nouveaux_contrats[1]
    assert changements == [
        "AGGEEV : jour de paiement 25",
        "AGGEEV 20000802485169 : type de population « NON CADRE »",
    ]
    # Rien n'est modifié en place.
    assert "jour_paiement" not in versements[0]


def test_deja_a_jour_ne_change_rien():
    versements = [{"organisme": "AGGEEV", "jour_paiement": "25"}]
    contrats = [{"reference": "20000802485169", "organisme": "AGGEEV", "type_population": "NON CADRE"}]
    assert completer(versements, contrats, DSN_DU_CABINET)[2] == []
