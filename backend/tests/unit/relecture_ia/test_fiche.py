"""La fiche envoyée à l'IA : le filtre et le contenu, sur des bulletins inventés."""

from __future__ import annotations

import json

import pytest

from app.modules.relecture_ia.domain.fiche import (
    code_salarie,
    construire_fiche,
    filtrer_donnees_personnelles,
)

pytestmark = pytest.mark.unit

NIR = "1 84 12 75 108 234 56"
IBAN = "FR76 3000 6000 0112 3456 7890 189"
EMAIL = "camille.testeur@exemple.fr"


def _bulletin(**surcharges) -> dict:
    donnees = {
        "en_tete": {
            "periode": "Octobre 2026",
            "annee": 2026,
            "mois": 10,
            "entreprise": {"raison_sociale": "Société Test", "adresse": "1 rue du Test"},
            "salarie": {
                "nom_complet": "Camille Testeur",
                "nom": "Testeur",
                "prenom": "Camille",
                "matricule": "000123",
                "adresse": "12 rue des Lilas, 69000 Lyon",
                "nir": NIR,
                "emploi": "Technicien",
                "statut": "Non-Cadre",
                "type_contrat": "CDI",
                "classification": "Niveau 3 Échelon 2",
                "date_entree": "2020-03-02",
            },
        },
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "quantite": 151.67, "taux": 16.5, "gain": 2502.56},
            {"libelle": "Prime pour Camille Testeur", "gain": 150.0},
        ],
        "salaire_brut": 2652.56,
        "structure_cotisations": {"total_salarial": 580.42, "bloc_principales": []},
        "synthese_net": {
            "net_imposable": 2130.12,
            "alertes_maintien": ["Maintien à revoir"],
        },
        "net_a_payer": 2072.14,
        "primes_non_soumises": [],
        "details_absences": [{"libelle": "Absence", "quantite": 7.0}],
        "details_conges": [],
        "alertes_baremes": [
            {"message": "Écart de minimum pour Mme TESTEUR, voir " + EMAIL},
        ],
        "pied_de_page": {
            "solde_conges": {"acquis": 25.0},
            "mentions_legales": {"information": "www.service-public.fr"},
        },
        "coordonnees_bancaires": {"iban": IBAN},
    }
    donnees.update(surcharges)
    return donnees


CONTRAT = {
    "duree_hebdomadaire": 35.0,
    "is_forfait_jour": False,
    "statut": "Non-Cadre",
    "first_name": "Camille",
    "email": EMAIL,
}


class TestFiltre:
    @pytest.mark.parametrize(
        "cle",
        [
            "nom",
            "prenom",
            "nom_complet",
            "first_name",
            "lastName",
            "nir",
            "numero_securite_sociale",
            "iban",
            "bic",
            "adresse",
            "address",
            "email",
            "courriel",
            "date_naissance",
            "date_de_naissance",
            "birthDate",
            "numero_titre_sejour",
            "residence_permit_number",
            "matricule",
        ],
    )
    def test_chaque_cle_personnelle_est_retiree_a_toute_profondeur(self, cle):
        entree = {"a": [{"b": {cle: "valeur", "montant": 12.5}}]}
        assert filtrer_donnees_personnelles(entree) == {"a": [{"b": {"montant": 12.5}}]}

    @pytest.mark.parametrize("cle", ["nombre_jours", "denomination", "libelle", "montant"])
    def test_une_cle_de_paie_est_gardee(self, cle):
        assert filtrer_donnees_personnelles({cle: 1}) == {cle: 1}

    def test_nir_iban_courriel_masques_dans_le_texte(self):
        sortie = filtrer_donnees_personnelles(
            {"libelle": f"NIR {NIR} compte {IBAN} écrit à {EMAIL}"}
        )
        texte = sortie["libelle"]
        assert "75 108" not in texte and "3000 6000" not in texte
        assert "@" not in texte

    def test_grand_nombre_entier_retire(self):
        assert filtrer_donnees_personnelles({"x": 184127510823456}) == {"x": None}

    def test_le_nom_est_remplace_par_le_code_sans_tenir_compte_des_accents(self):
        sortie = filtrer_donnees_personnelles(
            {"libelle": "Prime pour Éloïse LE FICTIF", "autre": "ELOISE"},
            noms=["Éloïse", "Le Fictif"],
            code="SAL-ABC",
        )
        assert sortie["libelle"] == "Prime pour SAL-ABC SAL-ABC"
        assert sortie["autre"] == "SAL-ABC"

    def test_les_particules_courtes_ne_sont_pas_remplacees(self):
        sortie = filtrer_donnees_personnelles(
            {"libelle": "Indemnité de transport"}, noms=["De", "Fictif"], code="SAL-ABC"
        )
        assert sortie["libelle"] == "Indemnité de transport"


class TestCode:
    def test_stable_et_sans_chiffre(self):
        code = code_salarie("7b0e4a8e-1111-2222-3333-444455556666")
        assert code == code_salarie("7b0e4a8e-1111-2222-3333-444455556666")
        assert not any(c.isdigit() for c in code)

    def test_deux_salaries_deux_codes(self):
        assert code_salarie("a") != code_salarie("b")


class TestFiche:
    def _fiche(self):
        return construire_fiche(
            _bulletin(),
            precedent=_bulletin(salaire_brut=2502.56, net_a_payer=1950.0),
            contrat=CONTRAT,
            code="SAL-ABC",
        )

    def test_aucune_donnee_personnelle_ne_sort(self):
        texte = json.dumps(self._fiche(), ensure_ascii=False)
        for interdit in ("Camille", "Testeur", "TESTEUR", "Lilas", "000123", "camille.", "FR76", "108 234"):
            assert interdit not in texte, interdit

    def test_contenu_utile_present(self):
        fiche = self._fiche()
        assert fiche["salarie"] == "SAL-ABC"
        assert fiche["mois"]["salaire_brut"] == 2652.56
        assert fiche["mois"]["calcul_du_brut"][0]["libelle"] == "Salaire de base"
        assert fiche["mois"]["en_tete"]["salarie"]["classification"] == "Niveau 3 Échelon 2"
        assert fiche["mois"]["details_absences"][0]["quantite"] == 7.0
        assert fiche["mois_precedent"]["net_a_payer"] == 1950.0
        assert fiche["contrat"] == {
            "duree_hebdomadaire": 35.0,
            "is_forfait_jour": False,
            "statut": "Non-Cadre",
        }
        assert fiche["mois"]["pied_de_page"]["solde_conges"] == {"acquis": 25.0}
        assert "mentions_legales" not in fiche["mois"]["pied_de_page"]

    def test_alertes_deja_levees_presentes_sans_nom(self):
        fiche = self._fiche()
        assert "SAL-ABC" in fiche["mois"]["alertes_baremes"][0]["message"]
        assert fiche["mois"]["synthese_net"]["alertes_maintien"] == ["Maintien à revoir"]

    def test_ecarts_avec_le_mois_precedent_calcules_par_le_serveur(self):
        assert self._fiche()["ecarts_avec_mois_precedent"] == {
            "salaire_brut": 150.0,
            "net_a_payer": 122.14,
        }

    def test_sans_mois_precedent(self):
        fiche = construire_fiche(_bulletin(), precedent=None, contrat={}, code="SAL-ABC")
        assert fiche["mois_precedent"] is None
        assert fiche["ecarts_avec_mois_precedent"] == {}


class TestNomsConnus:
    def test_le_nom_d_usage_est_retire_d_un_libelle(self):
        bulletin = {
            "en_tete": {"salarie": {"nom": "Durand", "prenom": "Alice"}},
            "primes_non_soumises": [{"libelle": "Contrat de prêt BERNARD", "montant": 50}],
        }
        fiche = construire_fiche(
            bulletin, precedent=None, contrat={}, code="SAL-X", noms_connus=["Bernard"]
        )
        assert "BERNARD" not in json.dumps(fiche, ensure_ascii=False)
        assert "Contrat de prêt SAL-X" in json.dumps(fiche, ensure_ascii=False)

    def test_une_duree_en_jours_n_est_pas_un_titre_de_sejour(self):
        assert filtrer_donnees_personnelles({"franchise_jours": 3}) == {"franchise_jours": 3}
        assert filtrer_donnees_personnelles({"titre_de_sejour": "x"}) == {}
