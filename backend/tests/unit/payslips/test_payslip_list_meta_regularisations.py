"""La liste des bulletins dit quelles cotisations ont été régularisées."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation
from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta

pytestmark = pytest.mark.unit


def test_la_liste_dit_les_cotisations_regularisees():
    ligne = RegularisationCotisation(
        coti_id="mutuelle",
        libelle="Mutuelle",
        motif="Tarif",
        montant_patronal=8.3,
        saisie_id="s1",
    ).ligne_de_cotisation()
    meta = payslip_list_meta({"cotisations_officielles": [{"code": "sante", "lignes": [ligne]}]})
    assert meta["regularisations"] == ["Mutuelle"]


def test_un_bulletin_sans_regularisation_n_en_dit_aucune():
    assert payslip_list_meta({})["regularisations"] == []
    assert payslip_list_meta(None)["regularisations"] == []
