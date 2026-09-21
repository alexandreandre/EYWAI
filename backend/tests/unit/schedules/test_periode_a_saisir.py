"""La période à saisir pour la paie d'un mois : l'union du mois civil et de la
fenêtre des variables, jugée jour par jour, dans les bornes du contrat."""

from __future__ import annotations

import calendar
from datetime import date

import pytest

from app.modules.schedules.domain.periode_a_saisir import (
    libelle_plages,
    periode_a_saisir,
    plages,
)

pytestmark = pytest.mark.unit

FENETRE_JUILLET = (date(2026, 6, 22), date(2026, 7, 26))  # Colorplast : S26–S30


def _mois(annee: int, mois: int, *, reel_jusqu_au: int | None, heures: float = 8.0):
    """Prévu complet (travail en semaine, repos le week-end) ; réel jusqu'au jour donné."""
    prevu, reel = [], []
    for jour in range(1, calendar.monthrange(annee, mois)[1] + 1):
        d = date(annee, mois, jour)
        if d.weekday() >= 5:
            prevu.append({"jour": jour, "type": "repos", "heures_prevues": 0.0})
            continue
        prevu.append({"jour": jour, "type": "travail", "heures_prevues": heures})
        if reel_jusqu_au is not None and jour <= reel_jusqu_au:
            reel.append({"jour": jour, "type": "travail", "heures_faites": heures})
    return prevu, reel


def test_michel_juillet_2026_bloque_sur_juin_et_informe_sur_la_fin_de_juillet():
    """État du test au 20/09 : juin sans réel, juillet saisi du 1er au 24."""
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=None),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=24),
        },
        date_entree=date(2020, 1, 15),
    )

    assert (periode.debut, periode.fin) == (date(2026, 6, 22), date(2026, 7, 31))
    assert periode.statut == "a_saisir"
    assert [j.jour.isoformat() for j in periode.bloquants] == [
        "2026-06-22",
        "2026-06-23",
        "2026-06-24",
        "2026-06-25",
        "2026-06-26",
        "2026-06-29",
        "2026-06-30",
    ]
    assert [j.jour.day for j in periode.informatifs] == [27, 28, 29, 30, 31]
    assert {j.motif for j in periode.manquants} == {"prevu_sans_reel"}


def test_une_fois_juin_saisi_juillet_est_saisi_avec_cinq_informatifs():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=30),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=24),
        },
    )

    assert periode.statut == "saisi"
    assert len(periode.informatifs) == 5


def test_rien_a_saisir_avant_l_embauche_ni_apres_la_sortie():
    calendriers = {
        (2026, 6): _mois(2026, 6, reel_jusqu_au=None),
        (2026, 7): _mois(2026, 7, reel_jusqu_au=None),
    }

    entrant = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers=calendriers, date_entree=date(2026, 7, 6)
    )
    sortant = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers=calendriers, date_sortie=date(2026, 7, 15)
    )

    assert min(j.jour for j in entrant.manquants) == date(2026, 7, 6)
    assert max(j.jour for j in sortant.manquants) == date(2026, 7, 15)


def test_un_mois_sans_planning_attend_ses_jours_ouvres_pas_le_week_end():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=FENETRE_JUILLET,
        calendriers={(2026, 7): _mois(2026, 7, reel_jusqu_au=31)},  # pas de ligne pour juin
    )

    juin = [j for j in periode.manquants if j.jour.month == 6]
    assert [j.jour.day for j in juin] == [22, 23, 24, 25, 26, 29, 30]
    assert {j.motif for j in juin} == {"planning_absent"}
    assert all(j.bloquant for j in juin)


def test_un_forfait_jour_est_juge_sur_le_mois_civil_seul():
    prevu = [{"jour": j, "type": "travail", "heures_prevues": 1} for j in range(1, 32)]
    reel = [{"jour": j, "heures_faites": 1} for j in range(1, 32)]

    periode = periode_a_saisir(
        annee=2026, mois=7, fenetre=FENETRE_JUILLET, calendriers={(2026, 7): (prevu, reel)}, forfait=True
    )

    assert periode.fenetre == (date(2026, 7, 1), date(2026, 7, 31))
    assert periode.statut == "saisi" and not periode.manquants


def test_en_mode_mois_calendaire_il_n_y_a_pas_d_informatif():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 7, 1), date(2026, 7, 31)),
        calendriers={(2026, 7): _mois(2026, 7, reel_jusqu_au=24)},
    )

    assert not periode.informatifs
    assert [j.jour.day for j in periode.bloquants] == [27, 28, 29, 30, 31]


def test_une_fin_avancee_rend_la_derniere_semaine_informative():
    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 6, 22), date(2026, 7, 19)),
        calendriers={
            (2026, 6): _mois(2026, 6, reel_jusqu_au=30),
            (2026, 7): _mois(2026, 7, reel_jusqu_au=17),
        },
    )

    assert periode.statut == "saisi"
    assert [j.jour.day for j in periode.informatifs] == [20, 21, 22, 23, 24, 27, 28, 29, 30, 31]


def test_les_motifs_distinguent_prevu_sans_heures_et_reel_a_zero():
    prevu = [
        {"jour": 1, "type": "travail", "heures_prevues": None},
        {"jour": 2, "type": "travail", "heures_prevues": 8.0},
    ]
    reel = [{"jour": 2, "type": "travail", "heures_faites": 0.0}]

    periode = periode_a_saisir(
        annee=2026,
        mois=7,
        fenetre=(date(2026, 7, 1), date(2026, 7, 2)),
        calendriers={(2026, 7): (prevu, reel)},
        date_sortie=date(2026, 7, 2),
    )

    assert [(j.jour.day, j.motif) for j in periode.manquants] == [
        (1, "prevu_sans_heures"),
        (2, "reel_a_zero"),
    ]


def test_les_plages_regroupent_les_jours_consecutifs():
    jours = [date(2026, 6, 22), date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 26), date(2026, 7, 1)]

    assert plages(jours) == [
        (date(2026, 6, 22), date(2026, 6, 24)),
        (date(2026, 6, 26), date(2026, 6, 26)),
        (date(2026, 7, 1), date(2026, 7, 1)),
    ]
    assert libelle_plages(jours) == "22/06–24/06, 26/06, 01/07"
