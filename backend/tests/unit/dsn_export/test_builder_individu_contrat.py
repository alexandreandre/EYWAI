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


def construire_individu(salarie: Dict = None, bulletin: Dict = None):
    individu, avertissements = build_individu_from_payroll(
        salarie or SALARIE,
        bulletin or BULLETIN,
        period="2026-05",
        company_siret="80248516900022",
    )
    return individu, avertissements


def test_les_remunerations_portent_le_numero_de_leur_contrat():
    """Un 51.010 qui ne pointe aucun 40.009 fabrique un contrat sans
    rémunération (CCH-13) et une rémunération orpheline (CCH-11)."""
    salarie = {
        **SALARIE,
        "classification_conventionnelle": {
            **SALARIE["classification_conventionnelle"],
            "numero_contrat_dsn": "00001",
        },
    }
    individu, _ = construire_individu(salarie)
    contrat = individu.contrats[0]
    assert contrat.rubriques["S21.G00.40.009"] == "00001"
    for rem in contrat.versements[0].remunerations:
        assert rem.rubriques["S21.G00.51.010"] == "00001"


def test_un_embauche_du_mois_compte_son_anciennete_en_jours():
    """86.003 à zéro est refusé (CCH-12) : le cabinet passe en jours, du
    premier jour inclus — entré le 04/05, déclaré fin mai : 28 jours."""
    salarie = {**SALARIE, "hire_date": "2026-05-04"}
    individu, _ = construire_individu(salarie)
    anciennete = individu.contrats[0].rubriques["_anciennete_entreprise"]
    assert anciennete["unite"] == "01"
    assert anciennete["valeur"] == "28"


def test_les_periodes_demarrent_au_premier_jour_du_contrat():
    """Embauché en cours de mois : 51.001 et 78.002 au début du contrat,
    pas au premier du mois (CCH-11 sur 51.001, SIG-17 sur 78.003)."""
    salarie = {**SALARIE, "hire_date": "2026-05-04"}
    individu, _ = construire_individu(salarie)
    versement = individu.contrats[0].versements[0]
    for rem in versement.remunerations:
        assert rem.rubriques["S21.G00.51.001"] == "04052026"
    for base in versement.bases_assujetties:
        assert base.rubriques["S21.G00.78.002"] == "04052026"


def test_naissance_a_l_etranger_reprend_le_departement_et_le_pays_du_cabinet():
    """Le cabinet déclare 30.014='99' et 30.015='FR' pour un né à l'étranger :
    repris tels quels, le pays ne se déduit pas du NIR."""
    salarie = {
        **SALARIE,
        "nir": "163089913913944",
        "lieu_naissance": "PORTO",
        "dsn_reprise": {"departement_naissance": "99", "pays_naissance": "FR"},
    }
    individu, avertissements = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.014"] == "99"
    assert individu.rubriques["S21.G00.30.015"] == "FR"
    assert not any("pays de naissance" in a for a in avertissements)


def test_naissance_dans_les_dom_reprend_le_97_du_cabinet():
    """Mayotte comprise, le cabinet déclare 30.014='97' + 30.015='FR'."""
    salarie = {
        **SALARIE,
        "nir": "193079850500404",
        "lieu_naissance": "CHICONI",
        "dsn_reprise": {"departement_naissance": "97", "pays_naissance": "FR"},
    }
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.014"] == "97"
    assert individu.rubriques["S21.G00.30.015"] == "FR"


def test_la_ville_perd_apostrophe_et_trait_d_union():
    """La regex de la localité (CSL-00) n'admet ni l'un ni l'autre : le
    cabinet déclare « L ABSIE » et « LE BOURGET DU LAC »."""
    salarie = {**SALARIE, "adresse": {**SALARIE["adresse"], "ville": "L'ABSIE"}}
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.010"] == "L ABSIE"
    salarie = {**SALARIE, "adresse": {**SALARIE["adresse"], "ville": "LE BOURGET-DU-LAC"}}
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.010"] == "LE BOURGET DU LAC"


def test_le_complement_d_adresse_perd_les_separateurs_interdits():
    """Virgule et barre oblique sont interdites, le tiret entre espaces
    aussi (CSL-11) : « BAT A1 - Appart 3 » passe, resserré."""
    salarie = {
        **SALARIE,
        "adresse": {**SALARIE["adresse"], "complement": "Appt 6 / Bat A1 - étage 2, B"},
    }
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.016"] == "Appt 6 Bat A1 étage 2 B"


def test_le_lieu_de_naissance_resserre_le_tiret_entre_espaces():
    salarie = {**SALARIE, "lieu_naissance": "SAINT ANDRE - REUNION", "nir": "169069740909304"}
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.007"] == "SAINT ANDRE REUNION"


def test_l_apprenti_reprend_niveau_de_diplome_et_date_de_fin():
    """Dispositif alternance : 30.025 exigé (CCH-11) et 40.010 exigée pour un
    CDD (CCH-12) — repris du cabinet quand la fiche ne les porte pas."""
    salarie = {
        **SALARIE,
        "contract_type": "CDD",
        "dsn_reprise": {"niveau_diplome_prepare": "06", "date_fin_contrat": "31082026"},
    }
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.025"] == "06"
    assert individu.contrats[0].rubriques["S21.G00.40.010"] == "31082026"


def test_la_reprise_se_lit_aussi_dans_specificites_paie():
    """En base réelle, la reprise DSN vit sous specificites_paie (portée par
    dsn_reprise_loader.py) — le builder doit la lire là aussi."""
    salarie = {
        **SALARIE,
        "nir": "163089913913944",
        "lieu_naissance": "PORTO",
        "specificites_paie": {
            "dsn_reprise": {
                "departement_naissance": "99",
                "pays_naissance": "FR",
                "pas_type": "01",
                "pas_identifiant": "434178834",
            },
            "affiliations_psc": [
                {"option": "E", "population": "ENSP", "id_affiliation": "1", "id_contrat": "2"}
            ],
        },
    }
    individu, _ = construire_individu(salarie)
    assert individu.rubriques["S21.G00.30.014"] == "99"
    assert individu.rubriques["S21.G00.30.015"] == "FR"
    contrat = individu.contrats[0]
    assert contrat.affiliations[0].rubriques["S21.G00.70.012"] == "1"
    versement = contrat.versements[0]
    assert versement.rubriques["S21.G00.50.007"] == "01"
    assert versement.rubriques["S21.G00.50.008"] == "434178834"
