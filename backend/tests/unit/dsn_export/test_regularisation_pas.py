"""Bloc S21.G00.56, régularisation de prélèvement à la source (R-173).

Contrôles repris de la fiche du bloc, CT 2026.1 : CCH-11 à 18, 26 et 27 de
56.002, CCH-11 de 56.001 et 56.008, formats CSL. Montants d'essai.
"""

from __future__ import annotations

import copy

import pytest

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.regularisation_pas import blocs_regularisation_pas
from app.modules.dsn_export.domain.writer import encode_dsn_bytes
from app.modules.dsn_import.domain.parser import parse_dsn_content
from tests.unit.dsn_export.test_builder_versement import BULLETIN, SALARIE, SOCIETE

pytestmark = pytest.mark.unit

TAUX = {
    "mois_erreur": "2026-09",
    "type_erreur": "02",
    "regul_taux": -8,
    "montant_soumis_declare": 2500,
    "montant_regul_pas": -200,
}
NET_FISCAL = {
    "mois_erreur": "2026-09",
    "type_erreur": "01",
    "regul_net_fiscal": 100,
    "taux_declare": 4.3,
    "regul_montant_soumis": 100,
    "montant_regul_pas": 4.3,
}


def test_rectification_de_taux_ecrit_les_rubriques_attendues():
    blocs, erreurs = blocs_regularisation_pas([TAUX], "2026-10")
    assert erreurs == []
    assert blocs == [
        {
            "S21.G00.56.001": "092026",
            "S21.G00.56.002": "02",
            "S21.G00.56.005": "-8.00",
            "S21.G00.56.007": "-200.00",
            "S21.G00.56.015": "2500.00",
        }
    ]


def test_rectification_sur_net_fiscal():
    blocs, erreurs = blocs_regularisation_pas([NET_FISCAL], "2026-10")
    assert erreurs == []
    assert blocs[0]["S21.G00.56.003"] == "100.00"
    assert blocs[0]["S21.G00.56.006"] == "4.30"
    assert blocs[0]["S21.G00.56.010"] == "100.00"


def test_un_bloc_par_mois_d_erreur():
    autre = {**TAUX, "mois_erreur": "2026-08"}
    blocs, _ = blocs_regularisation_pas([TAUX, autre], "2026-10")
    assert [b["S21.G00.56.001"] for b in blocs] == ["092026", "082026"]


def test_rien_a_regulariser_rien_a_ecrire():
    assert blocs_regularisation_pas(None, "2026-10") == ([], [])
    assert blocs_regularisation_pas([], "2026-10") == ([], [])


@pytest.mark.parametrize(
    "regul,attendu",
    [
        ({**TAUX, "mois_erreur": "2026-11"}, "postérieur"),  # CCH-11 de 56.001
        ({**TAUX, "mois_erreur": "2025-09"}, "année"),  # CCH-16
        ({**TAUX, "regul_taux": None}, "S21.G00.56.005"),  # CCH-12
        ({**TAUX, "regul_net_fiscal": 10}, "S21.G00.56.003"),  # CCH-18
        ({**TAUX, "regul_taux": 0}, "S21.G00.56.005"),  # CSL : écart nul impossible
        ({**NET_FISCAL, "taux_declare": None}, "S21.G00.56.006"),  # CCH-11 de 56.002
        ({**NET_FISCAL, "regul_taux": 1}, "S21.G00.56.005"),  # CCH-15
        ({**NET_FISCAL, "montant_regul_pas": None}, "S21.G00.56.007"),
        ({**NET_FISCAL, "type_erreur": "03"}, "négati"),  # CCH-14
        ({**NET_FISCAL, "type_erreur": "04"}, "S21.G00.56.007"),  # CCH-27
        ({**NET_FISCAL, "type_erreur": "09"}, "type d'erreur"),
        ({**NET_FISCAL, "mois_erreur": "septembre"}, "mois"),
        ({**NET_FISCAL, "regul_net_fiscal": "beaucoup"}, "S21.G00.56.003"),
    ],
)
def test_contraintes_du_cahier(regul, attendu):
    blocs, erreurs = blocs_regularisation_pas([regul], "2026-10")
    assert blocs == []
    assert len(erreurs) == 1
    assert erreurs[0].startswith("Régularisation de PAS")
    assert attendu in erreurs[0]


def test_janvier_regularise_seulement_l_annee_precedente():  # CCH-17
    blocs, _ = blocs_regularisation_pas([{**TAUX, "mois_erreur": "2026-11"}], "2027-01")
    assert len(blocs) == 1
    blocs, erreurs = blocs_regularisation_pas([{**TAUX, "mois_erreur": "2027-01"}], "2027-01")
    assert blocs == [] and "année" in erreurs[0]


def test_type_04_sans_prelevement():
    regul = {
        "mois_erreur": "2026-09", "type_erreur": "04", "regul_net_fiscal": 100,
        "regul_montant_soumis": 100, "montant_regul_pas": 0,
    }
    blocs, erreurs = blocs_regularisation_pas([regul], "2026-10")
    assert erreurs == [] and blocs[0]["S21.G00.56.007"] == "0.00"


def _lignes(bulletin):
    fichier, avertissements = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": SALARIE, "payslip_data": bulletin}], "2026-10"
    )
    return encode_dsn_bytes(fichier), avertissements


def test_le_bloc_56_vient_entre_le_54_et_le_58_et_se_relit():
    bulletin = {**copy.deepcopy(BULLETIN), "regularisations_pas": [TAUX]}
    contenu, _ = _lignes(bulletin)
    codes = [l.split(",")[0] for l in contenu.decode("iso-8859-15").splitlines()]
    assert "S21.G00.56.001" in codes
    blocs = [c[:10] for c in codes if c[:10] in ("S21.G00.54", "S21.G00.56", "S21.G00.58")]
    assert blocs.index("S21.G00.56") > max(i for i, b in enumerate(blocs) if b == "S21.G00.54")
    assert blocs.index("S21.G00.58") > max(i for i, b in enumerate(blocs) if b == "S21.G00.56")
    parse_dsn_content(contenu, file_name="essai.dsn")


def test_regularisation_invalide_garde_le_salarie_et_le_dit():
    bulletin = {**copy.deepcopy(BULLETIN), "regularisations_pas": [{**TAUX, "regul_taux": None}]}
    contenu, avertissements = _lignes(bulletin)
    assert "S21.G00.30.001" in contenu.decode("iso-8859-15")
    assert "S21.G00.56" not in contenu.decode("iso-8859-15")
    assert any(a.startswith("Régularisation de PAS") for a in avertissements)


def test_une_regularisation_valide_dit_de_verifier_le_versement_dgfip():
    bulletin = {**copy.deepcopy(BULLETIN), "regularisations_pas": [TAUX]}
    _, avertissements = _lignes(bulletin)
    assert any("DGFiP" in a and "-200.00" in a for a in avertissements)


def test_sans_regularisation_le_fichier_ne_change_pas():
    sans, _ = _lignes(copy.deepcopy(BULLETIN))
    assert b"S21.G00.56" not in sans
