"""Une régularisation de cotisation part en DSN avec les dates du mois (R-175).

CT 2026.1 § 2.2.2.2 et 2.2.2.5 : la période de rattachement est la période
d'origine. Martine n'a pas ce mois : l'aperçu le dit, ligne par ligne.
"""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_dsn

pytestmark = pytest.mark.unit

TOTAUX = {
    "nombre_salaries": 1, "nombre_contrats": 1, "masse_salariale_brute": 0,
    "total_charges": 0, "total_net_imposable": 0, "total_pas": 0,
}


def _bulletin(lignes):
    return {"cotisations_officielles": [{"lignes": lignes}]}


def _ligne_regularisee():
    return {
        "libelle": "Régularisation mutuelle",
        "regularisation": {
            "saisie_id": "s1", "coti_id": "mutuelle", "libelle": "Régularisation mutuelle",
            "motif": "erreur de taux", "montant_salarial": 12.5,
        },
    }


def _apercu(payslip_data):
    employe = {
        "employee": {"id": "e1", "first_name": "Paul", "last_name": "ESSAI"},
        "payslip_data": payslip_data, "brut": 0, "net_imposable": 0, "pas": 0,
        "cotisations_salariales": 0, "cotisations_patronales": 0, "cotisations_detail": [],
    }
    with patch.object(export_dsn, "get_company_data", return_value={"siret": "1"}), patch.object(
        export_dsn, "get_dsn_employees_data", return_value=([employe], TOTAUX)
    ), patch.object(export_dsn, "check_dsn_data", return_value=([], [])), patch.object(
        export_dsn, "raison_de_refus_dsn_mois_repris", return_value=None
    ), patch.object(export_dsn, "periodes_deposees", return_value=frozenset()):
        return export_dsn.preview_dsn("co", "2026-10", "dsn_mensuelle_normale")


def test_l_apercu_nomme_la_regularisation_et_le_manque():
    avis = _apercu(_bulletin([_ligne_regularisee()]))["warnings"]
    assert len(avis) == 1
    assert "Paul ESSAI" in avis[0]
    assert "Régularisation mutuelle" in avis[0]
    assert "mois d'origine" in avis[0]
    assert "octobre 2026" in avis[0]


def test_sans_regularisation_aucun_avis():
    assert _apercu(_bulletin([{"libelle": "Maladie"}]))["warnings"] == []


# Un rappel saisi en prime est fondu dans le mois (CT 2026.1 § 2.1.3.6 demande le rattachement).


def _bulletin_avec_primes(*libelles, saisie_id="s1"):
    return {
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "gain": 2000.0},
            *({"libelle": libelle, "gain": 100.0, "saisie_id": saisie_id} for libelle in libelles),
        ]
    }


@pytest.mark.parametrize(
    "libelle",
    ["Rappel de maintien de salaire", "Rappel maintien juillet 2026", "Régul prime mai", "Rappel IJSS"],
)
def test_l_apercu_signale_un_rappel_en_prime(libelle):
    avis = _apercu(_bulletin_avec_primes(libelle))["warnings"]
    assert len(avis) == 1
    assert "Paul ESSAI" in avis[0]
    assert f"« {libelle} »" in avis[0]
    assert "octobre 2026" in avis[0]
    assert "mois d'origine" in avis[0]


@pytest.mark.parametrize("libelle", ["Prime exceptionnelle", "Prime régulière d'équipe", "Panier"])
def test_les_autres_primes_ne_declenchent_rien(libelle):
    assert _apercu(_bulletin_avec_primes(libelle))["warnings"] == []


def test_une_ligne_de_rappel_calculee_par_le_moteur_n_est_pas_une_saisie():
    bulletin = {"calcul_du_brut": [{"libelle": "Rappel de salaire", "gain": 50.0}]}
    assert _apercu(bulletin)["warnings"] == []


def test_deux_saisies_au_meme_libelle_un_seul_avis():
    bulletin = _bulletin_avec_primes("Rappel IJSS")
    bulletin["calcul_du_brut"].append({"libelle": "Rappel IJSS", "gain": 12.0, "saisie_id": "s2"})
    assert len(_apercu(bulletin)["warnings"]) == 1
