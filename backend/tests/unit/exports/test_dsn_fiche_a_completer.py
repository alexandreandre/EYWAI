"""La fiche qui ferait refuser la DSN par DSN-VAL est signalée avant la génération."""

import pytest

from app.modules.dsn_export.domain.fiche_a_completer import fiche_a_completer
from app.modules.exports.infrastructure.export_dsn import check_dsn_data

pytestmark = pytest.mark.unit


def _cdi(**extra):
    base = {
        "contract_type": "CDI",
        "classification_conventionnelle": {"pcs": "674a"},
    }
    base.update(extra)
    return base


def test_fiche_complete_rien_a_signaler():
    assert fiche_a_completer(_cdi()) == []


def test_pcs_absent_est_signale():
    manques = fiche_a_completer(_cdi(classification_conventionnelle={}))
    assert any("S21.G00.40.004" in m and "manquant" in m for m in manques)


def test_pcs_hors_format_est_signale_sans_etre_corrige():
    manques = fiche_a_completer(_cdi(classification_conventionnelle={"pcs": "9999"}))
    assert any("S21.G00.40.004" in m and "9999" in m for m in manques)


def test_cdd_sans_date_de_fin_ni_motif():
    manques = fiche_a_completer(_cdi(contract_type="CDD"))
    assert any("S21.G00.40.010" in m for m in manques)
    assert any("S21.G00.40.021" in m for m in manques)


def test_cdd_complet_par_la_fiche_et_la_reprise():
    emp = _cdi(
        contract_type="CDD",
        contract_end_date="2026-12-18",
        specificites_paie={"dsn_reprise": {"motif_recours": "02"}},
    )
    assert fiche_a_completer(emp) == []


def test_apprenti_sans_diplome_ni_fin():
    manques = fiche_a_completer(_cdi(contract_type="Apprentissage"))
    assert any("S21.G00.30.025" in m for m in manques)
    assert any("S21.G00.40.010" in m for m in manques)
    assert not any("S21.G00.40.021" in m for m in manques)


def test_apprenti_complet():
    emp = _cdi(
        contract_type="Apprentissage",
        contract_end_date="2028-08-31",
        specificites_paie={"dsn_reprise": {"niveau_diplome_prepare": "05"}},
    )
    assert fiche_a_completer(emp) == []


def test_l_apercu_reprend_ces_manques_dans_ses_avertissements():
    emp = {
        "id": "e1", "first_name": "A", "last_name": "B", "nir": "1850575123456",
        "contract_type": "CDD",
        "adresse": {"rue": "1", "ville": "L", "code_postal": "69000"},
        "classification_conventionnelle": {},
    }
    _, warnings = check_dsn_data(
        "c", "2026-09", [{"employee": emp, "brut": 2000.0, "net_imposable": 1500.0}],
        {"siret": "73282932000074", "code_naf": "2229A"},
    )
    assert any("S21.G00.40.004" in w for w in warnings)
