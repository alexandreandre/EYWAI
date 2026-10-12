"""Avertissements DSN « mutuelle / prévoyance absente » : sur la fiche du mois.

Le contrôle lisait la fiche brute : une adhésion datée du mois (surcharge
mensuelle) donnait un faux avertissement, et une mutuelle à `null` faisait
tomber l'aperçu. Le reste de l'export lit la fiche du mois.
"""

import pytest

from app.modules.exports.infrastructure.export_dsn import check_dsn_data

pytestmark = pytest.mark.unit

SOCIETE = {"siret": "73282932000074", "company_name": "Exemple SAS"}


def _avertissements(specificites):
    employe = {
        "id": "emp-1",
        "first_name": "Camille",
        "last_name": "Exemple",
        "nir": "1850575123456",
        "contract_type": "CDI",
        "adresse": {"rue": "1 rue X", "ville": "Lyon", "code_postal": "69000"},
        "specificites_paie": specificites,
    }
    donnees = [{"employee": employe, "brut": 2000.0, "net_imposable": 1500.0}]
    _, warnings = check_dsn_data("co-1", "2026-09", donnees, SOCIETE)
    return warnings


def _sur(warnings, mot):
    return [w for w in warnings if mot in w]


def test_adhesion_datee_du_mois_pas_de_faux_avertissement():
    specificites = {
        "mutuelle": {"adhesion": False},
        "prevoyance": {"adhesion": False},
        "overrides_mensuels": {
            "2026-09": {"mutuelle": {"adhesion": True}, "prevoyance": {"adhesion": True}}
        },
    }
    warnings = _avertissements(specificites)
    assert _sur(warnings, "mutuelle absente") == []
    assert _sur(warnings, "prévoyance absente") == []


def test_la_surcharge_d_un_autre_mois_ne_compte_pas():
    specificites = {
        "mutuelle": {"adhesion": False},
        "prevoyance": {"adhesion": True},
        "overrides_mensuels": {"2026-08": {"mutuelle": {"adhesion": True}}},
    }
    warnings = _avertissements(specificites)
    assert len(_sur(warnings, "mutuelle absente")) == 1
    assert _sur(warnings, "prévoyance absente") == []


def test_mutuelle_ou_prevoyance_a_null_ne_fait_pas_tomber_l_apercu():
    warnings = _avertissements({"mutuelle": None, "prevoyance": None})
    assert len(_sur(warnings, "mutuelle absente")) == 1
    assert len(_sur(warnings, "prévoyance absente")) == 1


def test_sans_aucune_specificite_les_deux_sont_signalees():
    warnings = _avertissements({})
    assert len(_sur(warnings, "mutuelle absente")) == 1
    assert len(_sur(warnings, "prévoyance absente")) == 1
