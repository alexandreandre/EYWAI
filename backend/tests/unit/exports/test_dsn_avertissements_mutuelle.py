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
            "2026-09": {
                "mutuelle": {"adhesion": True},
                "prevoyance": {"adhesion": True},
            }
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


DISPENSE_CONJOINT = {
    "motif": "couverture_collective",
    "demande_recue_le": "2026-08-01",
    "justificatif_recu_le": "2026-08-01",
    "fin_le": None,
}


def test_dispense_valable_plus_d_alerte_mutuelle():
    warnings = _avertissements(
        {
            "mutuelle": {"adhesion": False, "dispense": DISPENSE_CONJOINT},
            "prevoyance": {"adhesion": True},
        }
    )
    assert _sur(warnings, "mutuelle") == []


def test_la_dispense_de_mutuelle_ne_tait_pas_la_prevoyance():
    warnings = _avertissements(
        {
            "mutuelle": {"adhesion": False, "dispense": DISPENSE_CONJOINT},
            "prevoyance": {"adhesion": False},
        }
    )
    assert _sur(warnings, "mutuelle") == []
    assert len(_sur(warnings, "prévoyance absente")) == 1


def test_sans_dispense_l_alerte_dit_quoi_faire():
    warnings = _avertissements(
        {"mutuelle": {"adhesion": False}, "prevoyance": {"adhesion": True}}
    )
    (alerte,) = _sur(warnings, "mutuelle absente")
    assert alerte.startswith("Salarié Camille Exemple : mutuelle absente")
    assert "posez sa dispense" in alerte


def test_justificatif_perime_dans_l_apercu():
    perime = {
        **DISPENSE_CONJOINT,
        "demande_recue_le": "2025-08-01",
        "justificatif_recu_le": "2025-08-01",
    }
    warnings = _avertissements(
        {
            "mutuelle": {"adhesion": False, "dispense": perime},
            "prevoyance": {"adhesion": True},
        }
    )
    assert len(_sur(warnings, "justificatif de sa mutuelle collective")) == 1
