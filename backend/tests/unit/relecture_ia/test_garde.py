"""Le filtre « pas trop sensible » : garde des nombres, vus, plafond."""

from __future__ import annotations

import pytest

from app.modules.relecture_ia.domain.garde import (
    appliquer_plafond,
    garder_signalements,
    nombres_de_la_fiche,
    normaliser_ligne,
    plafond_pour,
)

pytestmark = pytest.mark.unit

FICHE = {
    "salarie": "SAL-ABC",
    "mois": {
        "salaire_brut": 2652.56,
        "net_a_payer": 2072.14,
        "calcul_du_brut": [
            {"libelle": "Heures sup. 125 %", "quantite": 8.0, "taux": 20.625, "gain": 165.0}
        ],
    },
    "ecarts_avec_mois_precedent": {"net_a_payer": -122.1},
}


def _signalement(**surcharges):
    base = {
        "gravite": "important",
        "ligne": "Salaire de base",
        "raison": "Le brut de 2652,56 € paraît trop haut.",
        "chiffres_cites": ["2652,56"],
    }
    base.update(surcharges)
    return base


class TestNombres:
    def test_nombres_et_texte(self):
        nombres = nombres_de_la_fiche({"a": 1.5, "b": "Heures sup. 125 %", "c": True})
        assert {n for n in map(str, nombres)} >= {"1.5", "125"}

    def test_format_francais_et_signe(self):
        assert nombres_de_la_fiche({"a": "1 234,56"}) == nombres_de_la_fiche({"a": -1234.56})


class TestGarde:
    def test_un_chiffre_de_la_fiche_passe(self):
        resultat = garder_signalements([_signalement()], FICHE, code="SAL-ABC")
        assert len(resultat.retenus) == 1
        assert resultat.ecartes == {}

    @pytest.mark.parametrize("cite", ["2652.56", "2 652,56", "2652,560", "-2652,56"])
    def test_formats_equivalents(self, cite):
        s = _signalement(chiffres_cites=[cite], raison="Brut à vérifier.")
        assert garder_signalements([s], FICHE, code="SAL-ABC").retenus

    def test_valeur_arrondie_au_centime_acceptee(self):
        fiche = {"taux": 20.6254}
        s = _signalement(chiffres_cites=["20,63"], raison="Taux à vérifier.")
        assert garder_signalements([s], fiche, code="X").retenus

    def test_ecart_serveur_utilisable(self):
        s = _signalement(chiffres_cites=["122,1"], raison="Le net baisse de 122,1 €.")
        assert garder_signalements([s], FICHE, code="SAL-ABC").retenus

    def test_ecarte_si_chiffre_cite_inconnu(self):
        s = _signalement(chiffres_cites=["2652,56", "9999"])
        resultat = garder_signalements([s], FICHE, code="SAL-ABC")
        assert resultat.retenus == []
        assert resultat.ecartes == {"chiffre_absent_de_la_fiche": 1}

    def test_ecarte_si_la_raison_contient_un_autre_chiffre(self):
        s = _signalement(raison="Le brut devrait être de 2700 €.")
        assert garder_signalements([s], FICHE, code="SAL-ABC").retenus == []

    def test_ecarte_si_aucun_chiffre_cite(self):
        resultat = garder_signalements(
            [_signalement(chiffres_cites=[])], FICHE, code="SAL-ABC"
        )
        assert resultat.retenus == []
        assert resultat.ecartes == {"sans_chiffre": 1}

    def test_ecarte_si_gravite_inconnue(self):
        resultat = garder_signalements(
            [_signalement(gravite="critique")], FICHE, code="SAL-ABC"
        )
        assert resultat.ecartes == {"incomplet": 1}

    def test_ecarte_si_ligne_vide(self):
        resultat = garder_signalements([_signalement(ligne=" ")], FICHE, code="SAL-ABC")
        assert resultat.ecartes == {"incomplet": 1}

    def test_ecarte_si_deja_vu_quelle_que_soit_la_casse(self):
        s = _signalement(ligne="  SALAIRE  de base ")
        resultat = garder_signalements(
            [s], FICHE, code="SAL-ABC", vus={normaliser_ligne("Salaire de base")}
        )
        assert resultat.retenus == []
        assert resultat.ecartes == {"deja_vu": 1}

    def test_doublon_de_ligne_garde_le_plus_grave(self):
        resultat = garder_signalements(
            [
                _signalement(gravite="a_verifier"),
                _signalement(gravite="important"),
            ],
            FICHE,
            code="SAL-ABC",
        )
        assert [r["gravite"] for r in resultat.retenus] == ["important"]
        assert resultat.ecartes == {"doublon": 1}

    def test_le_code_salarie_ne_sort_pas_dans_la_raison(self):
        s = _signalement(raison="SAL-ABC a un brut de 2652,56 €.")
        retenu = garder_signalements([s], FICHE, code="SAL-ABC").retenus[0]
        assert "SAL-ABC" not in retenu["raison"]
        assert "ce salarié" in retenu["raison"]


class TestPlafond:
    @pytest.mark.parametrize(
        ("bulletins", "attendu"),
        [(0, 3), (5, 3), (30, 3), (31, 4), (45, 5), (100, 10), (101, 11)],
    )
    def test_dix_pour_cent_au_moins_trois(self, bulletins, attendu):
        assert plafond_pour(bulletins) == attendu

    def test_les_plus_graves_d_abord_et_le_reste_compte(self):
        points = [
            {"gravite": "a_verifier", "ligne": "a"},
            {"gravite": "important", "ligne": "b"},
            {"gravite": "a_verifier", "ligne": "c"},
            {"gravite": "important", "ligne": "d"},
        ]
        gardes, autres = appliquer_plafond(points, 10)
        assert [p["ligne"] for p in gardes] == ["b", "d", "a"]
        assert autres == 1

    def test_sous_le_plafond_rien_de_cache(self):
        gardes, autres = appliquer_plafond([{"gravite": "important", "ligne": "a"}], 10)
        assert len(gardes) == 1 and autres == 0
