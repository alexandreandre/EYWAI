"""Fenêtre des variables (heures sup, paniers) — fonctions pures."""

from __future__ import annotations

from datetime import date

import pytest

from app.shared.domain.periode_variables import (
    FenetreVariables,
    bornes_mois_civil,
    normaliser_fin_semaine,
    resoudre_fenetre,
    semaines_iso,
)

pytestmark = pytest.mark.unit


def test_normalisation_au_dimanche_de_la_semaine():
    """Gaëlle arrête au samedi 25/07 ; la semaine 30 va jusqu'au dimanche 26."""
    assert normaliser_fin_semaine(date(2026, 7, 25)) == date(2026, 7, 26)


def test_normalisation_dun_dimanche_ne_bouge_pas():
    assert normaliser_fin_semaine(date(2026, 7, 26)) == date(2026, 7, 26)


def test_normalisation_dun_lundi_va_au_dimanche_suivant():
    assert normaliser_fin_semaine(date(2026, 7, 20)) == date(2026, 7, 26)


def test_bornes_mois_civil():
    assert bornes_mois_civil(2026, 7) == (date(2026, 7, 1), date(2026, 7, 31))


def test_sans_surcharge_la_regle_sapplique_telle_quelle():
    """Repli : le comportement actuel, à la date près."""
    fenetre = resoudre_fenetre(
        bornes_regle=(date(2026, 6, 22), date(2026, 7, 26)),
        fin_mois_precedent=date(2026, 6, 21),
        surcharge=None,
    )
    assert fenetre == FenetreVariables(
        debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle"
    )


def test_la_surcharge_impose_sa_fin_normalisee():
    """Cartol juillet : Gaëlle a arrêté au 18/07, la semaine 29 finit le 19."""
    fenetre = resoudre_fenetre(
        bornes_regle=(date(2026, 6, 22), date(2026, 7, 26)),
        fin_mois_precedent=date(2026, 6, 21),
        surcharge=date(2026, 7, 18),
    )
    assert fenetre == FenetreVariables(
        debut=date(2026, 6, 22), fin=date(2026, 7, 19), origine="manuel"
    )


def test_le_debut_suit_toujours_la_fin_du_mois_precedent():
    """Cartol août : juillet s'est arrêté au 19, août commence le 20."""
    fenetre = resoudre_fenetre(
        bornes_regle=(date(2026, 7, 27), date(2026, 8, 23)),
        fin_mois_precedent=date(2026, 7, 19),
        surcharge=None,
    )
    assert fenetre.debut == date(2026, 7, 20)
    assert fenetre.fin == date(2026, 8, 23)


def test_pavage_sans_trou_ni_recouvrement():
    juillet = resoudre_fenetre(
        bornes_regle=(date(2026, 6, 22), date(2026, 7, 26)),
        fin_mois_precedent=date(2026, 6, 21),
        surcharge=date(2026, 7, 18),
    )
    aout = resoudre_fenetre(
        bornes_regle=(date(2026, 7, 27), date(2026, 8, 23)),
        fin_mois_precedent=juillet.fin,
        surcharge=None,
    )
    assert (aout.debut - juillet.fin).days == 1


def test_une_fin_anterieure_au_debut_est_refusee():
    with pytest.raises(ValueError, match="antérieure"):
        resoudre_fenetre(
            bornes_regle=(date(2026, 7, 27), date(2026, 8, 23)),
            fin_mois_precedent=date(2026, 8, 30),
            surcharge=None,
        )


def test_semaines_iso_de_la_fenetre():
    assert semaines_iso(date(2026, 6, 22), date(2026, 7, 26)) == [26, 27, 28, 29, 30]
