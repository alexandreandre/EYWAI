"""Net imposable négatif : déclaré signé, sans prélèvement (audit du 03/11/2026, D 4a).

Cahier technique DSN 2026.1 : S21.G00.50.002 « Rémunération nette fiscale »,
format `-?[0]*(0|[1-9][0-9]*)\\.[0-9]{2}` (le signe est admis) ; S21.G00.50.009
« Montant de prélèvement à la source » et S21.G00.50.013 « Montant soumis au
PAS », format `[0]*(0|[1-9][0-9]*)\\.[0-9]{2}` (jamais négatifs). Fiche DSN-info
n° 1810 « Rémunération nette fiscale négative » : 50.002 déclaré tel quel
(exemple : -180.00), 50.013 à 0.00 et 50.009 à 0.00.

Arbitrage D, verdict 4a : l'ancien logiciel déclarait 0,00 en 50.002 (11 624,76 €
de revenu déclaré en trop sur 31 mois-salarié). Martine signait déjà 50.002 ;
elle déclarait en revanche une assiette et un prélèvement négatifs (formats
refusés), et le bulletin rendait l'impôt (-0,16 €).
"""

from __future__ import annotations

import copy

import pytest

from tests.unit.dsn_export.test_builder_versement import BULLETIN, _lignes, _valeur

pytestmark = pytest.mark.unit


def _bulletin_au_net_fiscal_negatif():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["synthese_net"]["net_imposable"] = -31.65
    bulletin["synthese_net"]["impot_prelevement_a_la_source"] = {"base": -31.65, "taux": 13.3, "montant": -4.21}
    return bulletin


def test_le_net_fiscal_negatif_se_declare_signe():
    assert _valeur(_lignes(bulletin=_bulletin_au_net_fiscal_negatif()), "S21.G00.50.002") == "-31.65"


def test_l_assiette_et_le_prelevement_ne_sont_jamais_negatifs():
    lignes = _lignes(bulletin=_bulletin_au_net_fiscal_negatif())
    assert _valeur(lignes, "S21.G00.50.013") == "0.00"
    assert _valeur(lignes, "S21.G00.50.009") == "0.00"


def test_sans_assiette_dans_le_bulletin_la_rnf_negative_ne_passe_pas_en_50_013():
    bulletin = _bulletin_au_net_fiscal_negatif()
    bulletin["synthese_net"]["impot_prelevement_a_la_source"] = {"taux": 0.0, "montant": 0.0}
    assert _valeur(_lignes(bulletin=bulletin), "S21.G00.50.013") == "0.00"


def test_un_zero_negatif_s_ecrit_sans_signe():
    bulletin = copy.deepcopy(BULLETIN)
    bulletin["synthese_net"]["net_imposable"] = -0.0
    bulletin["synthese_net"]["impot_prelevement_a_la_source"] = {"base": -0.0, "taux": 0.0, "montant": -0.0}
    lignes = _lignes(bulletin=bulletin)
    assert _valeur(lignes, "S21.G00.50.002") == "0.00"
    assert _valeur(lignes, "S21.G00.50.009") == "0.00"
    assert _valeur(lignes, "S21.G00.50.013") == "0.00"
