"""Blocs individu (S21.G00.30) et contrat (S21.G00.40) construits depuis la fiche.

Les valeurs attendues viennent des DSN du cabinet acceptées par net-entreprises.
"""

from __future__ import annotations

from typing import Dict

import pytest

from app.modules.dsn_export.application.builder import build_individu_from_payroll

SALARIE = {
    "id": "1",
    "first_name": "Michel",
    "last_name": "BUGNY",
    "nir": "177037305401687",
    "sexe": "M",
    "date_naissance": "1977-03-08",
    "lieu_naissance": "BOURG SAINT MAURICE (73)",
    "adresse": {
        "rue": "1 route de Contrevoz",
        "ville": "CHAZEY BONS",
        "code_postal": "01300",
        "complement": None,
    },
    "hire_date": "2022-12-01",
    "contract_type": "CDI",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 39.0,
    "is_temps_partiel": False,
    "classification_conventionnelle": {
        "pcs": "674a",
        "idcc": "0292",
        "position": "200",
        "niveau_dsn": "720",
        "libelle_emploi": "Logisticien Polyvalent",
        "code_statut_dsn": "06",
        "numero_contrat_dsn": "00000",
        "classification_dsn": "252HK",
        "taux_at_individuel_dsn": "3.15",
        "dispositif_politique_publique": "99",
    },
}

BULLETIN = {"salaire_brut": 2500.0, "synthese_net": {"net_imposable": 2000.0}}


def construire(salarie: Dict = None, bulletin: Dict = None):
    individu, avertissements = build_individu_from_payroll(
        salarie or SALARIE,
        bulletin or BULLETIN,
        period="2026-05",
        company_siret="80248516900022",
    )
    return individu.rubriques, individu.contrats[0].rubriques, avertissements


def test_le_prenom_garde_sa_casse():
    individu, _contrat, _ = construire()
    assert individu["S21.G00.30.004"] == "Michel"


def test_le_lieu_de_naissance_perd_le_departement_qui_part_dans_sa_rubrique():
    individu, _contrat, _ = construire()
    assert individu["S21.G00.30.007"] == "BOURG SAINT MAURICE"
    assert individu["S21.G00.30.014"] == "73"
    assert individu["S21.G00.30.015"] == "FR"


def test_le_departement_de_naissance_se_deduit_du_nir_a_defaut():
    salarie = {**SALARIE, "lieu_naissance": "BOURG SAINT MAURICE"}
    individu, _contrat, _ = construire(salarie)
    assert individu["S21.G00.30.014"] == "73"


def test_naissance_a_l_etranger_ne_declare_pas_la_france():
    salarie = {
        **SALARIE,
        "nir": "163089913913944",
        "lieu_naissance": "PORTO",
    }
    individu, _contrat, avertissements = construire(salarie)
    assert individu.get("S21.G00.30.015") != "FR"
    assert any("pays de naissance" in a for a in avertissements)


def test_le_nom_d_usage_est_declare_quand_il_existe():
    salarie = {**SALARIE, "nom_usage": "DEPLANNE"}
    individu, _contrat, _ = construire(salarie)
    assert individu["S21.G00.30.003"] == "DEPLANNE"


def test_le_sexe_suit_le_nir_quand_la_fiche_le_contredit():
    """Huit salariés sont déclarés avec un sexe que leur NIR contredit."""
    salarie = {**SALARIE, "sexe": "M", "nir": "277037305401642"}
    individu, _contrat, avertissements = construire(salarie)
    assert individu["S21.G00.30.005"] == "02"
    assert any("sexe" in a.lower() for a in avertissements)


def test_le_numero_de_contrat_n_est_pas_le_nom_du_salarie():
    _individu, contrat, _ = construire()
    assert contrat["S21.G00.40.009"] == "00000"
    assert contrat["S21.G00.40.009"] != SALARIE["last_name"]


def test_la_quotite_suit_la_duree_hebdomadaire_reelle():
    """39 h par semaine font 169 h par mois, pas 151,67."""
    _individu, contrat, _ = construire()
    assert contrat["S21.G00.40.013"] == "169.00"
    assert contrat["S21.G00.40.012"] == "151.67"


def test_la_classification_conventionnelle_alimente_le_contrat():
    _individu, contrat, _ = construire()
    assert contrat["S21.G00.40.017"] == "0292"
    assert contrat["S21.G00.40.018"] == "200"
    assert contrat["S21.G00.40.020"] == "200"
    assert contrat["S21.G00.40.039"] == "200"
    assert contrat["S21.G00.40.040"] == "252HK"
    assert contrat["S21.G00.40.041"] == "720"
    assert contrat["S21.G00.40.043"] == "3.15"
    assert contrat["S21.G00.40.016"] == "99"


def test_l_idcc_manquant_est_signale_sans_bloquer():
    salarie = {
        **SALARIE,
        "classification_conventionnelle": {
            **SALARIE["classification_conventionnelle"],
            "idcc": "",
        },
    }
    _individu, contrat, avertissements = construire(salarie)
    assert "S21.G00.40.017" not in contrat
    assert any("convention collective" in a.lower() for a in avertissements)


def test_le_forfait_jours_se_compte_en_jours():
    """Un cadre au forfait annuel en jours ne se déclare pas en heures."""
    salarie = {**SALARIE, "is_forfait_jour": True, "duree_hebdomadaire": 35.0}
    _individu, contrat, _ = construire(salarie)
    assert contrat["S21.G00.40.011"] == "20"
    assert contrat["S21.G00.40.012"] == "21.27"
    assert contrat["S21.G00.40.013"] == "21.27"
