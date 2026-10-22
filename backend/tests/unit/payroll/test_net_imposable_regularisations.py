"""Le net imposable classe une régularisation comme la ligne qu'elle régularise."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine import calcul_net
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def _mutuelle(patronal):
    return {"coti_id": "mutuelle", "libelle": "Mutuelle", "montant_salarial": 20.0, "montant_patronal": patronal}


def test_sans_regularisation_la_part_reintegree_est_inchangee():
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [_mutuelle(30.0)]) == 30.0
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, []) == 0.0


def test_une_regularisation_de_la_part_patronale_est_reintegree():
    regul = RegularisationCotisation(
        coti_id="mutuelle",
        libelle="Mutuelle",
        motif="Tarif 2026",
        montant_patronal=5.0,
    ).ligne_de_cotisation()
    with patch.object(calcul_net, "_get_part_patronale_mutuelle", return_value=30.0):
        assert calcul_net._part_patronale_mutuelle_du_bulletin(None, [_mutuelle(30.0), regul]) == 35.0


def test_une_regularisation_de_csg_non_deductible_est_lue_comme_elle():
    regul = RegularisationCotisation(
        coti_id="csg_non_deductible",
        libelle="CSG/CRDS non déductible",
        motif="Base oubliée",
        base=100.0,
        taux_salarial=0.029,
    ).ligne_de_cotisation()
    libelle = regul["libelle"].lower()
    assert "csg/crds" in libelle and "non déductible" in libelle and "sur hs" not in libelle
