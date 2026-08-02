"""Sémantique des quantités de saisie et forme du barème frais professionnels."""

from app.modules.payroll.engine.calcul_frais import valeur_unitaire


def test_quantite_en_nombre_divise_le_montant():
    """« Paniers jours non soumis » : 207,20 € pour 28 paniers -> 7,40 €."""
    assert valeur_unitaire(207.20, 28.0, "count") == 7.4


def test_quantite_en_valeur_unitaire_est_retournee_telle_quelle():
    """« Paniers Jours non soumis » (MBC) : quantity porte déjà 7,50 €."""
    assert valeur_unitaire(165.0, 7.5, "unit_value") == 7.5


def test_sans_kind_on_divise_comme_avant():
    """Rétrocompatibilité : le comportement historique est conservé."""
    assert valeur_unitaire(195.0, 13.0, None) == 15.0


def test_quantite_absente_renvoie_le_montant():
    assert valeur_unitaire(100.0, None, None) == 100.0


def test_quantite_nulle_renvoie_le_montant():
    assert valeur_unitaire(100.0, 0.0, "count") == 100.0


def test_quantite_invalide_renvoie_le_montant():
    assert valeur_unitaire(100.0, "pas un nombre", "count") == 100.0


# --- Forme du barème et plafonds -------------------------------------------

from app.modules.payroll.engine.calcul_frais import (  # noqa: E402
    appliquer_exoneration_note_frais,
    exoneration_repas,
    sections_frais_pro,
)

BAREME_REPAS = {
    "sur_lieu_travail": 7.5,
    "hors_locaux_avec_restaurant": 21.4,
    "hors_locaux_sans_restaurant": 10.4,
}

# Forme réellement stockée dans payroll_config (versions 2 à 4, active).
FORME_STOCKEE = {
    "FRAIS_PRO": [{"id": 1, "libelle": "Frais pro", "sections": {"repas": BAREME_REPAS}}]
}
# Forme de la version 1 : sections à la racine.
FORME_V1 = {"repas": BAREME_REPAS}
# Forme attendue par le code d'origine, jamais rencontrée en base.
FORME_HISTORIQUE = {"sections": {"repas": BAREME_REPAS}}


def test_sections_lues_depuis_la_forme_reellement_stockee():
    assert sections_frais_pro(FORME_STOCKEE) == {"repas": BAREME_REPAS}


def test_sections_lues_depuis_la_forme_v1():
    assert sections_frais_pro(FORME_V1) == FORME_V1


def test_sections_lues_depuis_la_forme_historique():
    assert sections_frais_pro(FORME_HISTORIQUE) == {"repas": BAREME_REPAS}


def test_sections_absentes_donnent_un_dict_vide():
    assert sections_frais_pro(None) == {}
    assert sections_frais_pro({"autre": 1}) == {}


def test_plafond_repas_par_defaut_reste_le_plus_eleve():
    """Repli délibéré : durcir sans connaître la situation réintégrerait à tort
    les paniers chauffeur à 15 €, qui sont des repas hors locaux légitimes."""
    assert exoneration_repas(FORME_STOCKEE) == 21.4


def test_plafond_repas_selon_la_situation_declaree():
    assert exoneration_repas(FORME_STOCKEE, situation="sur_lieu_travail") == 7.5
    assert exoneration_repas(FORME_STOCKEE, situation="hors_locaux_sans_restaurant") == 10.4
    assert exoneration_repas(FORME_STOCKEE, situation="hors_locaux_avec_restaurant") == 21.4


def test_situation_inconnue_retombe_sur_le_repli():
    assert exoneration_repas(FORME_STOCKEE, situation="inexistante") == 21.4


def test_panier_sans_situation_declaree_reste_exonere():
    """15 € le repas passe sous le plafond le plus élevé (21,40 €)."""
    exo, reint, plafond = appliquer_exoneration_note_frais(
        {"montant": 15.0, "prime_id": "panier", "type": "panier"},
        FORME_STOCKEE,
    )
    assert plafond == 21.4
    assert exo == 15.0
    assert reint == 0.0


def test_panier_declare_sur_lieu_de_travail_est_plafonne():
    exo, reint, plafond = appliquer_exoneration_note_frais(
        {
            "montant": 15.0,
            "prime_id": "panier",
            "type": "panier",
            "situation_repas": "sur_lieu_travail",
        },
        FORME_STOCKEE,
    )
    assert plafond == 7.5
    assert exo == 7.5
    assert reint == 7.5


def test_valeurs_unitaires_reelles_de_la_base_restent_exonerees():
    """5,00 / 7,40 / 7,50 / 15,00 € sont les seules valeurs unitaires en base :
    toutes sous le repli, donc la réparation ne déplace aucun euro."""
    for unite in (5.0, 7.4, 7.5, 15.0):
        exo, reint, _ = appliquer_exoneration_note_frais(
            {"montant": unite, "prime_id": "panier", "type": "panier"},
            FORME_STOCKEE,
        )
        assert exo == unite
        assert reint == 0.0
