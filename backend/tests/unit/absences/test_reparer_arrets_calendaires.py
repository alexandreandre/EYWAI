"""Fonctions pures du script de réparation des arrêts calendaires."""

from datetime import date

from scripts.reparer_arrets_calendaires import arret_cible, jours_apres_expansion


def test_expansion_comble_les_week_ends():
    complets, ajoutes = jours_apres_expansion(["2026-08-14", "2026-08-17"])
    assert complets == ["2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17"]
    assert ajoutes == ["2026-08-15", "2026-08-16"]


def test_expansion_deja_complete_est_idempotente():
    complets, ajoutes = jours_apres_expansion(["2026-08-14", "2026-08-15"])
    assert complets == ["2026-08-14", "2026-08-15"]
    assert ajoutes == []


def test_cible_respecte_la_borne_depuis():
    row = {
        "status": "validated",
        "type": "arret_maladie",
        "arret_type": "maladie_simple",
        "selected_days": ["2026-07-01", "2026-07-10"],
    }
    assert arret_cible(row, date(2026, 8, 1)) is False
    a_cheval = {**row, "selected_days": ["2026-07-28", "2026-08-03"]}
    assert arret_cible(a_cheval, date(2026, 8, 1)) is True


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
