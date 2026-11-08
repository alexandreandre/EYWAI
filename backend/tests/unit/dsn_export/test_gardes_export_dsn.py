"""Les deux gardes de l'export DSN mensuel (R-442, R-443).

R-442 : un mois repris de l'ancien logiciel ne se déclare pas depuis Martine.
R-443 : une cotisation qui porte un montant et n'a pas de code DSN arrête le
fichier, au lieu d'être oubliée avec un simple avertissement. Une ligne sans
montant (gratification exonérée d'un stagiaire, ligne à zéro) ne l'arrête pas.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import (
    CotisationMappingError,
    build_bases_and_cotisations,
    cotisations_sans_code_dsn,
)
from app.modules.exports.infrastructure import export_dsn
from app.shared.reprise_paie import Bascule, raison_de_refus_dsn_mois_repris

pytestmark = pytest.mark.unit

BASCULE = Bascule(annee=2026, mois=9, logiciel_precedent="Quadra")
SOCIETE = {
    "siret": "73282932000074",
    "name": "Société Test",
    "code_naf": "2229A",
    "address": {"rue": "1 rue Test", "ville": "Lyon", "code_postal": "69000"},
}
MALADIE = {
    "coti_id": "securite_sociale_maladie",
    "libelle": "Maladie",
    "base": 2500,
    "montant_patronal": 175,
    "taux_patronal": 7,
}
MYSTERE = {"libelle": "Cotisation mystère", "base": 2500, "montant_patronal": 10}


def _construire(lignes):
    return build_bases_and_cotisations(
        lignes, brut=2500, period_start="01112026", period_end="30112026", require_codes=True
    )


def _bulletin(lignes):
    return {
        "salaire_brut": 2500,
        "synthese_net": {
            "net_imposable": 2000,
            "net_a_payer": 1900,
            "impot_prelevement_a_la_source": {"montant": 100, "taux": 5, "base": 2000},
        },
        "structure_cotisations": {"cotisations": lignes},
    }


def _salarie(identifiant, lignes):
    return {
        "employee": {
            "id": identifiant,
            "first_name": "Alice",
            "last_name": "Test",
            "nir": "1850175123456",
            "sexe": "F",
            "date_naissance": "1985-01-15",
            "contract_type": "CDI",
            "hire_date": "2020-01-01",
            "statut": "Non-Cadre",
            "adresse": {"rue": "10 rue Test", "code_postal": "75010", "ville": "Paris"},
        },
        "payslip": {"id": f"p-{identifiant}"},
        "payslip_data": _bulletin(lignes),
        "brut": 2500,
        "net_imposable": 2000,
        "pas": 100,
        "cotisations_detail": lignes,
    }


# --- R-443 : le mapping ------------------------------------------------------


def test_une_cotisation_avec_montant_sans_code_arrete_le_fichier():
    with pytest.raises(CotisationMappingError) as refus:
        _construire([MYSTERE])
    message = str(refus.value)
    assert "Cotisation mystère" in message
    assert "support" in message  # dit quoi faire


def test_une_exoneration_de_stage_sans_montant_ne_bloque_pas():
    # La ligne que le moteur pose sur chaque gratification de stage exonérée.
    _construire([{"coti_id": "exoneration_stage", "libelle": "Gratification de stage exonérée",
                  "base": 600, "montant_salarial": 0.0, "montant_patronal": 0.0}])


@pytest.mark.parametrize("coti_id", ["apec", "retraite_comp_t1", "ceg_t2", "at_mp", "forfait_social"])
def test_une_rubrique_connue_a_zero_ne_bloque_pas(coti_id):
    _construire([{"coti_id": coti_id, "libelle": coti_id, "base": 0, "montant_salarial": 0, "montant_patronal": 0}])


def test_toutes_les_rubriques_du_moteur_passent():
    # Une ligne de chaque rubrique que le moteur ou son catalogue pose.
    identifiants = [
        "ags", "allocations_familiales", "apec", "assurance_chomage", "at_mp", "ceg_t1", "ceg_t2", "cet",
        "CFP", "cpf_cdd", "csa", "csg_deductible", "csg_non_deductible", "crds", "deduction_hs_patronale",
        "dialogue_social", "fnal", "forfait_social", "mutuelle", "prevoyance_cadre", "prevoyance_non_cadre",
        "reduction_generale", "reduction_hs_salariale", "retraite_comp_t1", "retraite_comp_t2",
        "retraite_secu_deplafond", "retraite_secu_plafond", "retraite_sup", "securite_sociale_maladie",
        "taxe_apprentissage", "taxe_apprentissage_solde", "versement_mobilite",
        "contribution_indemnite_rupture",
    ]
    lignes = [
        {"coti_id": i, "libelle": "Sans mot-clé", "base": 2500, "montant_salarial": 1.5, "montant_patronal": 2.5}
        for i in identifiants
    ]
    assert cotisations_sans_code_dsn(lignes) == []
    _construire(lignes)


def test_l_exoneration_jei_avec_montant_bloque_tant_qu_elle_n_a_pas_de_code():
    # Vrai positif : son montant ne partirait pas en DSN (code 014 non branché).
    ligne = {"coti_id": "exoneration_jei", "libelle": "Exonération JEI (cotisations patronales)",
             "base": 2500, "montant_salarial": 0, "montant_patronal": -300}
    assert [c["libelle"] for c in cotisations_sans_code_dsn([ligne])] == [ligne["libelle"]]
    with pytest.raises(CotisationMappingError):
        _construire([ligne])


def test_seules_les_lignes_a_montant_sans_code_sont_listees():
    zero = {"libelle": "Ligne informative", "base": 100, "montant_salarial": 0, "montant_patronal": 0}
    assert cotisations_sans_code_dsn([MALADIE, zero, MYSTERE]) == [{"libelle": "Cotisation mystère", "montant": 10.0}]


# --- R-443 : l'aperçu et le fichier -------------------------------------------


def _bloquantes(anomalies):
    return [a for a in anomalies if a.get("severity") == "blocking"]


def test_l_apercu_nomme_le_salarie_et_la_cotisation_sans_code():
    donnees = [_salarie("e1", [MALADIE, MYSTERE])]
    anomalies, _ = export_dsn.check_dsn_data("c", "2026-11", donnees, SOCIETE, essai=True)
    (anomalie,) = [a for a in _bloquantes(anomalies) if "mystère" in a["message"]]
    assert anomalie["employee_id"] == "e1" and "Alice Test" in anomalie["message"]


def test_l_apercu_regarde_aussi_le_contrat_precedent():
    donnees = [{**_salarie("e1", [MALADIE]), "contrat_precedent": _salarie("e1", [MYSTERE])}]
    anomalies, _ = export_dsn.check_dsn_data("c", "2026-11", donnees, SOCIETE, essai=True)
    assert [a for a in _bloquantes(anomalies) if "mystère" in a["message"]]


def test_l_apercu_ne_bloque_pas_les_bulletins_sans_cotisation_inconnue():
    anomalies, _ = export_dsn.check_dsn_data("c", "2026-11", [_salarie("e1", [MALADIE])], SOCIETE, essai=True)
    assert not [a for a in _bloquantes(anomalies) if "code DSN" in a["message"]]


@pytest.fixture
def export():
    with patch.object(export_dsn, "get_company_data", return_value=SOCIETE), patch.object(
        export_dsn, "oeth_queries", MagicMock()
    ), patch.object(export_dsn, "periodes_deposees", return_value=set()), patch.object(
        export_dsn, "avis_changements_pcs", return_value=None
    ), patch.object(export_dsn, "lire_bascule", return_value=None) as bascule, patch(
        "app.shared.reprise_paie.lire_bascule", return_value=BASCULE
    ) as lecture:
        yield {"bascule": bascule, "lecture": lecture}


def test_erreur_injectee_le_fichier_n_est_pas_produit(export):
    # Deux salariés : le second porte l'erreur. Le fichier entier s'arrête, le
    # salarié n'est pas retiré en silence.
    donnees = [_salarie("e1", [MALADIE]), _salarie("e2", [MALADIE, MYSTERE])]
    with patch.object(export_dsn, "get_dsn_employees_data", return_value=(donnees, {})):
        with pytest.raises(ValueError, match="mystère"):
            export_dsn.generate_dsn_file("soc", "2026-11", "dsn_mensuelle_normale", essai=True)


# --- R-442 : le mois repris ---------------------------------------------------


@pytest.mark.parametrize(
    ("annee", "mois", "refuse"),
    [(2026, 9, True), (2026, 3, True), (2025, 12, True), (2026, 10, False), (2027, 1, False)],
)
def test_le_refus_suit_la_bascule(annee, mois, refuse):
    raison = raison_de_refus_dsn_mois_repris("soc", annee, mois, BASCULE)
    assert bool(raison) is refuse


def test_le_refus_dit_quoi_faire():
    raison = raison_de_refus_dsn_mois_repris("soc", 2026, 9, BASCULE)
    assert "09/2026" in raison and "Quadra" in raison and "10/2026" in raison


def test_sans_bascule_aucun_refus():
    with patch("app.shared.reprise_paie.lire_bascule", return_value=None):
        assert raison_de_refus_dsn_mois_repris("soc", 2026, 9) is None


def test_la_lecture_de_la_bascule_est_stricte():
    # Base injoignable : le contrôle s'arrête, il ne laisse pas passer le mois.
    with patch("app.shared.reprise_paie.lire_bascule", return_value=None) as lecture:
        raison_de_refus_dsn_mois_repris("soc", 2026, 9)
    assert lecture.call_args.kwargs == {"stricte": True}


@pytest.mark.parametrize("essai", [False, True])
def test_le_fichier_d_un_mois_repris_est_refuse(export, essai):
    with patch.object(export_dsn, "get_dsn_employees_data") as donnees, pytest.raises(ValueError, match="Quadra"):
        export_dsn.generate_dsn_file("soc", "2026-09", "dsn_mensuelle_normale", essai=essai)
    donnees.assert_not_called()


def test_l_alias_historique_est_garde_aussi(export):
    with pytest.raises(ValueError, match="Quadra"):
        export_dsn.generate_dsn_xml("soc", "2026-09", "dsn_mensuelle_normale")


def test_le_premier_mois_calcule_se_genere(export):
    donnees = [_salarie("e1", [MALADIE])]
    with patch.object(export_dsn, "get_dsn_employees_data", return_value=(donnees, {})):
        assert export_dsn.generate_dsn_file("soc", "2026-10", "dsn_mensuelle_normale", essai=True)


def test_l_apercu_d_un_mois_repris_interdit_la_generation(export):
    totaux = {"nombre_salaries": 1, "nombre_contrats": 1, "masse_salariale_brute": 2500.0, "total_charges": 0.0,
              "total_net_imposable": 2000.0, "total_pas": 100.0}
    with patch.object(export_dsn, "get_dsn_employees_data", return_value=([_salarie("e1", [MALADIE])], totaux)):
        apercu = export_dsn.preview_dsn("soc", "2026-09", "dsn_mensuelle_normale", essai=True)
    assert apercu["can_generate"] is False
    assert any("Quadra" in a["message"] for a in _bloquantes(apercu["anomalies"]))
    # L'aperçu reste lisible : il répond, il ne plante pas.
    assert apercu["nombre_salaries"] == 1


def test_le_signalement_de_fin_de_contrat_reste_hors_de_la_garde(export):
    # Le FCTU part de la DSN du mois de sortie : il n'est pas une DSN mensuelle.
    donnees = [_salarie("e1", [MALADIE])]
    with patch.object(export_dsn, "get_dsn_employees_data", return_value=(donnees, {})):
        assert export_dsn.generate_dsn_file(
            "soc", "2026-09", "dsn_mensuelle_normale", essai=True, pour_signalement=True
        )
