"""Vue de présentation du bulletin — gabarit Cegid."""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import (
    _civilite,
    _date_fr,
    _formater_nir,
    construire_vue_bulletin,
)


def bulletin_minimal() -> dict:
    """Bulletin réduit aux clés que la vue consomme, calqué sur CARTOL juin 2026."""
    return {
        "en_tete": {
            "periode": "Juin 2026",
            "annee": 2026,
            "mois": 6,
            "date_paiement": "30/06/2026",
            "entreprise": {
                "raison_sociale": "Société CARTOL",
                "siret": "95147478200020",
                "naf_ape": "2562B",
                "adresse": {
                    "rue": "10 BOULEVARD GEORGES POMPIDOU",
                    "code_postal": "79140",
                    "ville": "CERIZAY",
                },
            },
            "salarie": {
                "nom": "ALVES",
                "prenom": "Lucas",
                "nom_complet": "Lucas ALVES",
                "sexe": "M",
                "matricule": "ALVES",
                "nir": "102098519123974",
                "adresse": {
                    "rue": "32 rue de la Fabrique",
                    "code_postal": "79250",
                    "ville": "NUEIL LES AUBIERS",
                },
                "mode_paiement": "virement",
                "emploi": "Opérateur polyvalent",
                "date_entree": "2026-04-08",
                "date_anciennete": "2026-04-08",
                "classification_brute": {"coefficient": "A"},
                "convention_collective": "Convention collective nationale de la métallurgie",
            },
        },
        "calcul_du_brut": [],
        "details_conges": [],
        "details_absences": [],
        "salaire_brut": 1436.21,
        "cotisations_officielles": [],
        "structure_cotisations": {"total_salarial": 0.0, "total_patronal": 0.0},
        "synthese_net": {},
        "primes_non_soumises": [],
        "net_a_payer": 910.64,
        "pied_de_page": {},
        "parametres": {"smic_horaire": 12.31, "pss_mensuel": 3337.50},
    }


class TestHelpers:
    def test_nir_groupe_comme_cegid(self):
        assert _formater_nir("102098519123974") == "1 02 09 85 191 239 74"

    def test_nir_non_standard_rendu_tel_quel(self):
        assert _formater_nir("12345") == "12345"

    def test_nir_absent_donne_chaine_vide(self):
        assert _formater_nir(None) == ""

    @pytest.mark.parametrize("valeur", ["M", "m", "H", "1"])
    def test_civilite_masculine(self, valeur):
        assert _civilite(valeur) == "MR"

    @pytest.mark.parametrize("valeur", ["F", "f", "2"])
    def test_civilite_feminine(self, valeur):
        assert _civilite(valeur) == "MME"

    def test_civilite_inconnue_absente(self):
        assert _civilite(None) is None
        assert _civilite("X") is None

    def test_date_iso_vers_francais(self):
        assert _date_fr("2026-04-08") == "08/04/2026"

    def test_date_absente_donne_chaine_vide(self):
        assert _date_fr(None) == ""


class TestBandeau:
    def test_bandeau_reprend_identification_entreprise(self):
        bandeau = construire_vue_bulletin(bulletin_minimal())["bandeau"]
        assert bandeau["raison_sociale"] == "Société CARTOL"
        assert bandeau["siret"] == "95147478200020"
        assert bandeau["naf_ape"] == "2562B"
        assert bandeau["adresse"] == [
            "10 BOULEVARD GEORGES POMPIDOU",
            "79140 CERIZAY",
        ]

    def test_bandeau_calcule_les_bornes_de_periode(self):
        bandeau = construire_vue_bulletin(bulletin_minimal())["bandeau"]
        assert bandeau["periode"] == "Juin 2026"
        assert bandeau["du"] == "01/06/2026"
        assert bandeau["au"] == "30/06/2026"

    def test_bandeau_sans_mois_n_invente_pas_de_bornes(self):
        bulletin = bulletin_minimal()
        del bulletin["en_tete"]["mois"]
        bandeau = construire_vue_bulletin(bulletin)["bandeau"]
        assert bandeau["du"] == ""
        assert bandeau["au"] == ""


class TestSalarieEtIdentite:
    def test_nom_precede_de_la_civilite_nom_en_premier(self):
        salarie = construire_vue_bulletin(bulletin_minimal())["salarie"]
        assert salarie["civilite"] == "MR"
        assert salarie["nom_ligne"] == "ALVES Lucas"

    def test_adresse_postale_sur_deux_lignes(self):
        salarie = construire_vue_bulletin(bulletin_minimal())["salarie"]
        assert salarie["adresse"] == ["32 rue de la Fabrique", "79250 NUEIL LES AUBIERS"]

    def test_identite_reprend_matricule_nir_et_emploi(self):
        identite = construire_vue_bulletin(bulletin_minimal())["identite"]
        assert identite["matricule"] == "ALVES"
        assert identite["nir"] == "1 02 09 85 191 239 74"
        assert identite["emploi"] == "Opérateur polyvalent"
        assert identite["date_entree"] == "08/04/2026"
        assert identite["coefficient"] == "A"

    def test_anciennete_se_replie_sur_la_date_d_entree(self):
        bulletin = bulletin_minimal()
        bulletin["en_tete"]["salarie"]["date_anciennete"] = None
        identite = construire_vue_bulletin(bulletin)["identite"]
        assert identite["anciennete"] == "08/04/2026"
