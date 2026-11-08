"""Le minimum hiérarchique de la métallurgie se compare sur l'année (art. 138 à 140)."""

from __future__ import annotations

import pytest

from app.modules.payroll.domain.smh_metallurgie import (
    classe_controlable,
    ecart_smh,
    message_smh,
    mois_pleins,
)

pytestmark = pytest.mark.unit

MENSUEL_CLASSE_3 = 22710 / 12


def _mois(brut, *lignes, sortie=False):
    return {
        "salaire_brut": brut,
        "is_bulletin_sortie": sortie,
        "calcul_du_brut": [
            {"libelle": l, "gain": g if g > 0 else None, "perte": -g if g < 0 else None}
            for l, g in lignes
        ],
    }


def _plein(brut, *lignes):
    return _mois(brut, ("Salaire de base", brut), *lignes)


class TestEcart:
    def test_au_minimum_rien(self):
        assert ecart_smh([_plein(MENSUEL_CLASSE_3)] * 12, classe=3, annee=2026) is None

    def test_sous_le_minimum_montant_manquant(self):
        ecart = ecart_smh([_plein(1800.0)] * 10, classe=3, annee=2026)
        assert ecart.mois_compares == 10
        assert ecart.assiette == pytest.approx(18000.0)
        assert ecart.minimum == pytest.approx(18925.0)
        assert ecart.manque == pytest.approx(925.0)

    def test_la_prime_d_anciennete_ne_compte_pas(self):
        ecart = ecart_smh(
            [_plein(1900.0, ("Prime ancienneté", 100.0))], classe=3, annee=2026
        )
        assert ecart.assiette == pytest.approx(1800.0)

    @pytest.mark.parametrize(
        "libelle",
        [
            "PRIME ASTREINTE",
            "Prime exceptionnelle",
            "Paniers jours équipe soumis",
            "B_P majo. heures de nuit 50%",
            "Heures suppl. majorées à 25%",
            "Heures suppl. structurelles majorées à 25%",
        ],
    )
    def test_elements_exclus(self, libelle):
        ecart = ecart_smh([_plein(1900.0, (libelle, 100.0))], classe=3, annee=2026)
        assert ecart.assiette == pytest.approx(1800.0)

    def test_une_prime_de_presence_compte(self):
        assert (
            ecart_smh([_plein(MENSUEL_CLASSE_3, ("Prime de présence", 25.0))], classe=3, annee=2026)
            is None
        )

    @pytest.mark.parametrize(
        "libelle",
        ["Act. partiel. 250926", "Absence maladie 01-05", "Abs. congés s.solde", "Abs. maternité -"],
    )
    def test_un_mois_suspendu_n_est_pas_compare(self, libelle):
        mois = [_plein(MENSUEL_CLASSE_3), _mois(900.0, ("Salaire de base", 1800.0), (libelle, -900.0))]
        assert ecart_smh(mois, classe=3, annee=2026) is None

    def test_les_conges_payes_ne_suspendent_pas(self):
        mois = _mois(
            MENSUEL_CLASSE_3,
            ("Salaire de base", MENSUEL_CLASSE_3),
            ("H.Absence congés payés", -469.0),
            ("Congés payés", 469.0),
        )
        assert ecart_smh([mois], classe=3, annee=2026) is None
        assert ecart_smh([_plein(1800.0)], classe=3, annee=2026).mois_compares == 1

    def test_le_bulletin_de_sortie_n_est_pas_compare(self):
        assert ecart_smh([_mois(100.0, ("Salaire de base", 100.0), sortie=True)], classe=3, annee=2026) is None

    def test_le_treizieme_mois_compte_meme_un_mois_suspendu(self):
        mois = [
            _plein(1700.0),
            _mois(1200.0, ("Salaire de base", 1800.0), ("Act. partiel. 1", -700.0), ("Prorata 13ième mois", 100.0)),
        ]
        ecart = ecart_smh(mois, classe=3, annee=2026)
        assert ecart.assiette == pytest.approx(1800.0)
        assert ecart.mois_compares == 1

    def test_rien_a_comparer(self):
        assert ecart_smh([], classe=3, annee=2026) is None

    def test_annee_sans_bareme(self):
        assert ecart_smh([_plein(1000.0)], classe=3, annee=2020) is None

    def test_tolerance_d_un_euro(self):
        assert ecart_smh([_plein(MENSUEL_CLASSE_3 - 0.9)], classe=3, annee=2026) is None


class TestAdaptation:
    def test_temps_partiel_au_prorata(self):
        assert ecart_smh([_plein(946.25)], classe=3, annee=2026, duree_hebdo=17.5) is None
        assert ecart_smh([_plein(900.0)], classe=3, annee=2026, duree_hebdo=17.5).minimum == pytest.approx(946.25)

    def test_forfait_jours_majore_de_30_pour_cent(self):
        ecart = ecart_smh([_plein(2000.0)], classe=3, annee=2026, forfait_jours=True)
        assert ecart.minimum == pytest.approx(MENSUEL_CLASSE_3 * 1.30)

    def test_forfait_reduit_au_prorata_des_jours(self):
        ecart = ecart_smh(
            [_plein(1000.0)], classe=3, annee=2026, forfait_jours=True, jours_forfait=109
        )
        assert ecart.minimum == pytest.approx(MENSUEL_CLASSE_3 * 1.30 * 109 / 218, abs=0.01)


class TestClasse:
    def test_lue_au_niveau_dsn(self):
        assert classe_controlable({"idcc": "3248", "niveau_dsn": "4 B"}, "CDI") == 4

    def test_autre_convention(self):
        assert classe_controlable({"idcc": "0292", "niveau_dsn": "700"}, "CDI") is None

    def test_sans_niveau(self):
        assert classe_controlable({"idcc": "3248"}, "CDI") is None

    @pytest.mark.parametrize("contrat", ["Apprentissage", "Contrat de professionnalisation"])
    def test_alternant_ecarte(self, contrat):
        assert classe_controlable({"idcc": "3248", "niveau_dsn": "4 B"}, contrat) is None

    @pytest.mark.parametrize("niveau", ["11 F", "12 F"])
    def test_groupe_f_ecarte_bareme_debutant(self, niveau):
        assert classe_controlable({"idcc": "3248", "niveau_dsn": niveau}, "CDI") is None


class TestMoisPleins:
    def _mois(self, *numeros):
        return [{"month": m, "salaire_brut": 1.0} for m in numeros]

    def test_le_mois_d_entree_et_avant_sont_ecartes(self):
        gardes = mois_pleins(self._mois(1, 2, 3, 4), 2026, "2026-02-16", None)
        assert [b["month"] for b in gardes] == [3, 4]

    def test_embauche_d_une_autre_annee(self):
        gardes = mois_pleins(self._mois(1, 2), 2026, "2025-12-10", None)
        assert [b["month"] for b in gardes] == [1, 2]

    def test_le_mois_de_fin_de_contrat_est_ecarte(self):
        gardes = mois_pleins(self._mois(9, 10, 11), 2026, "2025-01-01", "2026-11-18")
        assert [b["month"] for b in gardes] == [9, 10]


def test_message():
    ecart = ecart_smh([_plein(1800.0)] * 10, classe=3, annee=2026)
    texte = message_smh(ecart, 2026)
    assert "925,00 €" in texte
    assert "classe 3" in texte
    assert "10 mois" in texte
    assert "décembre" in texte
