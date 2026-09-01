"""Fonctions pures du script de réparation des arrêts calendaires."""

from datetime import date

from scripts.reparer_arrets_calendaires import (
    arret_a_cheval,
    arret_cible,
    jours_apres_expansion,
)


def test_expansion_comble_les_week_ends():
    complets, ajoutes, trous = jours_apres_expansion(["2026-08-14", "2026-08-17"])
    assert complets == ["2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17"]
    assert ajoutes == ["2026-08-15", "2026-08-16"]
    assert trous == []


def test_expansion_deja_complete_est_idempotente():
    complets, ajoutes, trous = jours_apres_expansion(["2026-08-14", "2026-08-15"])
    assert complets == ["2026-08-14", "2026-08-15"]
    assert ajoutes == []
    assert trous == []


def test_expansion_refuse_un_trou_en_semaine():
    # Lundi 03/08 → vendredi 07/08 puis lundi 24/08 → vendredi 28/08 : le trou
    # contient des jours ouvrés (reprise réelle ?) — rien n'est comblé.
    jours = [
        "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07",
        "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
    ]
    complets, ajoutes, trous = jours_apres_expansion(jours)
    assert complets == sorted(jours)
    assert ajoutes == []
    assert "2026-08-10" in trous and "2026-08-21" in trous
    assert all(date.fromisoformat(t).weekday() < 5 for t in trous)


def test_cible_exige_un_arret_entierement_apres_la_borne():
    row = {
        "status": "validated",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
        "selected_days": ["2026-08-03", "2026-08-10"],
    }
    assert arret_cible(row, date(2026, 8, 1)) is True
    a_cheval = {**row, "selected_days": ["2026-07-28", "2026-08-03"]}
    assert arret_cible(a_cheval, date(2026, 8, 1)) is False
    assert arret_a_cheval(a_cheval, date(2026, 8, 1)) is True
    avant = {**row, "selected_days": ["2026-07-01", "2026-07-10"]}
    assert arret_cible(avant, date(2026, 8, 1)) is False
    assert arret_a_cheval(avant, date(2026, 8, 1)) is False


def test_cible_exclut_mi_temps_therapeutique_non_valides_et_non_arrets():
    base = {
        "status": "validated",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
        "selected_days": ["2026-08-10"],
    }
    assert arret_cible(base, date(2026, 8, 1)) is True
    assert (
        arret_cible({**base, "arret_type": "mi_temps_therapeutique"}, date(2026, 8, 1))
        is False
    )
    assert arret_cible({**base, "status": "pending"}, date(2026, 8, 1)) is False
    assert arret_cible({**base, "type": "conge_paye"}, date(2026, 8, 1)) is False
