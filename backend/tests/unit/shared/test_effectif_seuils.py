"""Effectif retenu pour les seuils de paie (11, 20, 50 salariés).

Le moteur lisait `companies.effectif`, que tient un déclencheur de la base :
le nombre de comptes de la société (admins, RH et salariés partis compris).
Colorplast y était à 19 pour environ 5 salariés, Comitech à 25 pour 15 à 17,
MAJI à 14 pour 5 à 9 : formation à 1 % au lieu de 0,55 %, déduction heures
sup à 0,50 €/h au lieu de 1,50 €/h. Créer un compte suffisait à changer un
bulletin (enquête du 10/10/2026).

La loi retient pour une année la moyenne des effectifs de chaque mois de
l'année précédente (CSS L130-1, R130-1) ; l'Urssaf la communique. Elle se
saisit donc par année ; le nombre de comptes n'est plus qu'un dernier recours,
signalé sur le bulletin.
"""

from __future__ import annotations

import pytest

from app.shared.domain.effectif_seuils import (
    CLE_EFFECTIF_SEUILS,
    CODE_ALERTE_EFFECTIF,
    alerte_effectif,
    effectif_retenu,
    effectifs_avec,
    palier_effectif,
)

pytestmark = pytest.mark.unit


def _societe(saisis=None, comptes=19):
    settings = {"autre": 1}
    if saisis is not None:
        settings[CLE_EFFECTIF_SEUILS] = saisis
    return {"effectif": comptes, "settings": settings}


class TestEffectifRetenu:
    def test_l_effectif_saisi_pour_l_annee_l_emporte_sur_le_nombre_de_comptes(self):
        retenu = effectif_retenu(_societe({"2026": 5}), 2026)
        assert (retenu.valeur, retenu.annee_source) == (5, 2026)
        assert retenu.saisi_pour_l_annee

    def test_sans_saisie_pour_l_annee_la_derniere_annee_saisie_est_reprise(self):
        retenu = effectif_retenu(_societe({"2025": 7, "2026": 5}), 2027)
        assert (retenu.valeur, retenu.annee_source) == (5, 2026)
        assert not retenu.saisi_pour_l_annee

    def test_une_annee_anterieure_a_toute_saisie_reprend_la_plus_proche(self):
        retenu = effectif_retenu(_societe({"2026": 5, "2027": 8}), 2025)
        assert (retenu.valeur, retenu.annee_source) == (5, 2026)

    def test_sans_aucune_saisie_le_nombre_de_comptes_sert_en_dernier_recours(self):
        retenu = effectif_retenu(_societe(None, comptes=19), 2026)
        assert (retenu.valeur, retenu.annee_source) == (19, None)

    def test_creer_un_compte_ne_change_plus_l_effectif_retenu(self):
        avant = effectif_retenu(_societe({"2026": 5}, comptes=19), 2026)
        apres = effectif_retenu(_societe({"2026": 5}, comptes=20), 2026)
        assert avant.valeur == apres.valeur == 5

    @pytest.mark.parametrize("illisible", ["cinq", None, -3, True, 4.5])
    def test_une_valeur_illisible_est_ignoree(self, illisible):
        retenu = effectif_retenu(_societe({"2026": illisible, "2025": 6}), 2026)
        assert (retenu.valeur, retenu.annee_source) == (6, 2025)

    def test_settings_absent_ou_mal_forme(self):
        assert effectif_retenu({"effectif": 3, "settings": None}, 2026).valeur == 3
        assert effectif_retenu({"settings": {CLE_EFFECTIF_SEUILS: [1]}}, 2026).valeur == 0


class TestPalier:
    @pytest.mark.parametrize(
        "valeur, palier",
        [
            (0, "moins de 11"),
            (10, "moins de 11"),
            (11, "de 11 à 19"),
            (19, "de 11 à 19"),
            (20, "de 20 à 49"),
            (49, "de 20 à 49"),
            (50, "50 et plus"),
            (250, "50 et plus"),
        ],
    )
    def test_les_paliers_suivent_les_seuils_du_moteur(self, valeur, palier):
        assert palier_effectif(valeur) == palier


class TestAlerte:
    def test_rien_a_signaler_quand_l_annee_est_saisie(self):
        assert alerte_effectif(effectif_retenu(_societe({"2026": 5}), 2026)) is None

    def test_une_annee_reprise_est_signalee_avec_ce_qui_est_repris(self):
        alerte = alerte_effectif(effectif_retenu(_societe({"2026": 5}), 2027))
        assert alerte["code"] == CODE_ALERTE_EFFECTIF
        assert "2027" in alerte["message"]
        assert "2026 (5)" in alerte["message"]
        assert "paramètres de paie" in alerte["message"]

    def test_le_nombre_de_comptes_est_signale_comme_n_etant_pas_l_effectif(self):
        alerte = alerte_effectif(effectif_retenu(_societe(None, comptes=19), 2026))
        assert "comptes" in alerte["message"]
        assert "19" in alerte["message"]
        assert "À vérifier avant de valider ce bulletin." in alerte["message"]


class TestSaisie:
    def test_la_saisie_d_une_annee_garde_les_autres(self):
        assert effectifs_avec({CLE_EFFECTIF_SEUILS: {"2025": 7}}, 2026, 5) == {
            "2025": 7,
            "2026": 5,
        }

    def test_sans_settings(self):
        assert effectifs_avec(None, 2026, 5) == {"2026": 5}
