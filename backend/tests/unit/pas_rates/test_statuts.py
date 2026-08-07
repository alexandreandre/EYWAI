"""Règles de statut d'un taux de prélèvement à la source."""

from app.modules.pas_rates.domain.model import (
    STATUT_A_JOUR,
    STATUT_A_RAFRAICHIR,
    STATUT_BAREME,
    STATUT_MANQUANT,
    TYPE_BAREME,
    TYPE_PERSONNALISE,
    calculer_statut,
    ecart_mois,
    periode_valide,
    type_label,
)


def test_absence_de_taux_prime_sur_tout():
    """0 % appliqué sans que personne l'ait décidé : le cas le plus grave."""
    assert (
        calculer_statut(None, TYPE_PERSONNALISE, "2026-08", "2026-08")
        == STATUT_MANQUANT
    )
    assert calculer_statut(None, TYPE_BAREME, "2026-08", "2026-08") == STATUT_MANQUANT


def test_taux_bareme_signale_une_attente_dgfip():
    assert calculer_statut(5.3, TYPE_BAREME, "2026-08", "2026-08") == STATUT_BAREME


def test_taux_personnalise_recent_est_a_jour():
    assert calculer_statut(4.2, TYPE_PERSONNALISE, "2026-08", "2026-08") == STATUT_A_JOUR
    assert calculer_statut(4.2, TYPE_PERSONNALISE, "2026-06", "2026-08") == STATUT_A_JOUR


def test_frontiere_de_deux_mois():
    """Deux mois passent, trois mois ne passent plus."""
    assert calculer_statut(4.2, TYPE_PERSONNALISE, "2026-06", "2026-08") == STATUT_A_JOUR
    assert (
        calculer_statut(4.2, TYPE_PERSONNALISE, "2026-05", "2026-08")
        == STATUT_A_RAFRAICHIR
    )


def test_taux_sans_periode_est_a_rafraichir():
    """Un taux hérité des anciens imports : on ignore de quel mois il vient."""
    assert calculer_statut(4.2, TYPE_PERSONNALISE, None, "2026-08") == STATUT_A_RAFRAICHIR


def test_taux_zero_reste_un_taux():
    """La DGFiP peut transmettre 0 % : ce n'est pas une absence de taux."""
    assert calculer_statut(0.0, TYPE_PERSONNALISE, "2026-08", "2026-08") == STATUT_A_JOUR


def test_ecart_mois_franchit_les_annees():
    assert ecart_mois("2025-11", "2026-02") == 3
    assert ecart_mois("2026-02", "2026-02") == 0
    assert ecart_mois("2026-03", "2026-02") == -1
    assert ecart_mois("bidon", "2026-02") is None


def test_periode_valide_refuse_les_mois_impossibles():
    assert periode_valide("2026-01")
    assert periode_valide("2026-12")
    assert not periode_valide("2026-13")
    assert not periode_valide("2026-00")
    assert not periode_valide("202601")
    assert not periode_valide(None)


def test_libelle_de_type_reste_lisible_pour_un_code_inconnu():
    assert type_label(TYPE_PERSONNALISE) == "Taux personnalisé DGFiP"
    assert type_label(TYPE_BAREME) == "Barème par défaut (métropole)"
    assert type_label("07") == "Type 07"
    assert type_label(None) == "Origine inconnue"


def test_les_baremes_territoriaux_ont_le_meme_statut_que_la_metropole():
    """23, 33 et les variantes proratisées sont des barèmes comme le 13."""
    for code in ("13", "23", "33", "17", "27", "37"):
        assert calculer_statut(5.3, code, "2026-08", "2026-08") == STATUT_BAREME
