"""Rubriques du contrat que l'établissement porte quand la fiche ne les a pas,
et taux de prélèvement à la source lu dans les taux reçus.

Trois fiches Colorplast de 2026 n'ont aucune classification DSN (créées dans
EYWAI, pas importées) : la DSN de juin sortait leurs contrats sans IDCC, sans
régimes de base, sans taux AT — tous refusés au dépôt. Ce que l'établissement
fixe pour tous se reprend ; ce qui est propre au salarié (PCS) reste signalé.
"""

from __future__ import annotations

from typing import Dict, List

from app.modules.dsn_export.application.builder import (
    build_parsed_dsn_from_payroll,
    taux_pas_du_mois,
)
from app.modules.dsn_export.domain.settings import DsnSettings

SOCIETE = {
    "siret": "12345678900011",
    "name": "Société d'essai",
    "address": {"rue": "1 rue de l'Essai", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "code_naf": "2229A",
    "taux_at_mp": 3.15,
}

COMPLET = {
    "id": "e1",
    "first_name": "Paul",
    "last_name": "ESSAI",
    "nir": "177017512345678",
    "sexe": "M",
    "date_naissance": "1977-01-01",
    "lieu_naissance": "PARIS (75)",
    "adresse": {"rue": "1 rue du Test", "code_postal": "01000", "ville": "BOURG EN BRESSE"},
    "hire_date": "2014-09-01",
    "contract_type": "CDI",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 39.0,
    "classification_conventionnelle": {
        "pcs": "674a",
        "idcc": "0292",
        "position": "200",
        "niveau_dsn": "720",
        "classification_dsn": "252HK",
        "taux_at_individuel_dsn": "3.15",
        "code_statut_dsn": "06",
        "numero_contrat_dsn": "00000",
        "dispositif_politique_publique": "99",
    },
}

SANS_CLASSIFICATION = {
    **COMPLET,
    "id": "e2",
    "first_name": "Marie",
    "last_name": "TESTEUR",
    "nir": "285017512345678",
    "sexe": "F",
    "hire_date": "2026-03-23",
    "contract_type": "CDD",
    "contract_end_date": "2026-07-24",
    "classification_conventionnelle": {"classe_emploi": "710", "coefficient": 710, "groupe_emploi": None},
}

BULLETIN = {"salaire_brut": 2000.0, "synthese_net": {"net_imposable": 1600.0}}


def _contrats(salaries: List[Dict], settings: DsnSettings = None):
    fichier, avertissements = build_parsed_dsn_from_payroll(
        SOCIETE,
        [{"employee": s, "payslip_data": BULLETIN} for s in salaries],
        "2026-06",
        settings=settings or DsnSettings(idcc="0292"),
    )
    contrats = {
        ind.nir: ind.contrats[0].rubriques for ind in fichier.etablissement.individus
    }
    return contrats, avertissements


def test_la_fiche_sans_classification_reprend_ce_que_l_etablissement_fixe():
    contrats, _ = _contrats([COMPLET, SANS_CLASSIFICATION])
    contrat = contrats["2850175123456"]
    assert contrat["S21.G00.40.017"] == "0292"  # IDCC de l'établissement
    assert contrat["S21.G00.40.018"] == "200"  # régime général, maladie
    assert contrat["S21.G00.40.020"] == "200"  # vieillesse
    assert contrat["S21.G00.40.039"] == "200"  # accident du travail
    assert contrat["S21.G00.40.043"] == "3.15"  # taux AT de la société
    assert contrat["S21.G00.40.040"] == "252HK"  # code risque commun à l'établissement
    assert contrat["S21.G00.40.041"] == "710"  # coefficient de la fiche


def test_le_pcs_propre_au_salarie_reste_signale():
    _, avertissements = _contrats([COMPLET, SANS_CLASSIFICATION])
    assert any("PCS" in a and "2850175123456" in a for a in avertissements)


def test_un_code_risque_qui_varie_dans_l_etablissement_n_est_pas_devine():
    autre = {
        **COMPLET,
        "id": "e3",
        "nir": "178017512345678",
        "classification_conventionnelle": {
            **COMPLET["classification_conventionnelle"],
            "classification_dsn": "251AA",
        },
    }
    contrats, avertissements = _contrats([COMPLET, autre, SANS_CLASSIFICATION])
    assert "S21.G00.40.040" not in contrats["2850175123456"]
    assert any("risque" in a.lower() for a in avertissements)


def test_l_apprenti_porte_le_dispositif_d_apprentissage():
    """CDD devenu apprentissage, fiche sans dispositif : 65 au-delà de 10
    salariés (64 en deçà), jamais 99 ; le niveau de diplôme manquant est dit."""
    apprenti = {
        **SANS_CLASSIFICATION,
        "contract_type": "Apprentissage",
        "contract_end_date": "2028-08-31",
    }
    societe = {**SOCIETE, "effectif": 25}
    fichier, avertissements = build_parsed_dsn_from_payroll(
        societe,
        [{"employee": apprenti, "payslip_data": BULLETIN}],
        "2026-09",
        settings=DsnSettings(idcc="0292"),
    )
    contrat = fichier.etablissement.individus[0].contrats[0].rubriques
    assert contrat["S21.G00.40.007"] == "02"
    assert contrat["S21.G00.40.008"] == "65"
    assert any("diplôme" in a for a in avertissements)


# --------------------------------------------------------------------------
# Taux de prélèvement à la source reçus (employee_pas_rates)
# --------------------------------------------------------------------------


def test_le_taux_pas_est_le_dernier_recu_avant_ou_pendant_le_mois():
    lignes = [
        {"periode": "2026-04", "taux": 2.0, "type_taux": "01", "identifiant_taux": "111"},
        {"periode": "2026-06", "taux": 2.2, "type_taux": "01", "identifiant_taux": "222"},
        {"periode": "2026-07", "taux": 9.9, "type_taux": "01", "identifiant_taux": "333"},
    ]
    assert taux_pas_du_mois(lignes, "2026-06") == {
        "pas_type_taux": "01",
        "pas_identifiant_taux": "222",
    }


def test_un_bareme_n_a_pas_d_identifiant():
    lignes = [{"periode": "2026-05", "taux": 0.0, "type_taux": "13", "identifiant_taux": None}]
    assert taux_pas_du_mois(lignes, "2026-06") == {"pas_type_taux": "13"}


def test_sans_taux_recu_rien_n_est_impose():
    assert taux_pas_du_mois([], "2026-06") == {}


def test_le_taux_recu_alimente_le_versement():
    salarie = {**COMPLET, "pas_type_taux": "01", "pas_identifiant_taux": "434000000"}
    fichier, _ = build_parsed_dsn_from_payroll(
        SOCIETE, [{"employee": salarie, "payslip_data": BULLETIN}], "2026-06"
    )
    versement = fichier.etablissement.individus[0].contrats[0].versements[0]
    assert versement.rubriques["S21.G00.50.007"] == "01"
    assert versement.rubriques["S21.G00.50.008"] == "434000000"
