"""Quel ajustement de congés s'applique à une année donnée.

Une reprise de soldes est datée (`cp_opening_reference_date`) et calibre les
deux périodes de congés qu'elle touche — pas une année civile. Lue par la seule
ligne de l'année, elle disparaissait au 1er janvier au milieu de la période :
Bugny (Colorplast) passait de 28 à 3 jours de N-1 entre le 31/12/2026 et le
31/01/2027. Les écarts CP d'une reprise datée suivent donc les années
suivantes ; les compteurs annuels (RTT, JTC) restent ceux de l'année.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.infrastructure.leave_settings_repository import (
    _row_to_adjustment,
    resoudre_ajustement_applicable,
)

pytestmark = pytest.mark.unit


def _ligne(year: int, **champs) -> dict:
    base = {
        "year": year,
        "cp_n1_opening_balance": 0,
        "cp_n_opening_balance": 0,
        "rtt_opening_balance": 0,
        "rtt_forfeited_at": None,
        "rtt_forfeited_days": 0,
        "jtc_opening_balance": 0,
        "note": None,
        "cp_opening_reference_date": None,
    }
    base.update(champs)
    return base


REPRISE_2026 = _ligne(
    2026,
    cp_n1_opening_balance="15.00",
    cp_opening_reference_date="2026-06-30",
    note="Reprise Quadra au 30/06/2026",
)


def test_la_ligne_lue_porte_sa_date_de_reference():
    assert _row_to_adjustment(REPRISE_2026).cp_opening_reference_date == date(2026, 6, 30)
    assert _row_to_adjustment(_ligne(2026)).cp_opening_reference_date is None


def test_la_ligne_de_l_annee_s_applique_telle_quelle():
    ajustement = resoudre_ajustement_applicable([REPRISE_2026], 2026)

    assert ajustement.cp_n1_opening_balance == 15.0
    assert ajustement.cp_opening_reference_date == date(2026, 6, 30)
    assert ajustement.note == "Reprise Quadra au 30/06/2026"


def test_sans_ligne_de_l_annee_la_reprise_datee_precedente_suit():
    ajustement = resoudre_ajustement_applicable([REPRISE_2026], 2027)

    assert ajustement.cp_n1_opening_balance == 15.0
    assert ajustement.cp_opening_reference_date == date(2026, 6, 30)


def test_les_compteurs_annuels_ne_suivent_pas():
    """RTT et JTC se comptent par année civile : l'écart de 2026 n'a rien à
    faire en 2027, ni la note qui déclenche le mode « fidèle au bulletin »."""
    ligne = _ligne(
        2026,
        cp_n1_opening_balance="15.00",
        rtt_opening_balance="3.50",
        rtt_forfeited_days="2.00",
        rtt_forfeited_at="2026-12-31T00:00:00+00:00",
        jtc_opening_balance="1.00",
        cp_opening_reference_date="2026-06-30",
        note="Import CP bulletin Juin 2026",
    )

    ajustement = resoudre_ajustement_applicable([ligne], 2027)

    assert ajustement.cp_n1_opening_balance == 15.0
    assert ajustement.rtt_opening_balance == 0.0
    assert ajustement.rtt_forfeited_days == 0.0
    assert ajustement.rtt_forfeited_at is None
    assert ajustement.jtc_opening_balance == 0.0
    assert ajustement.note is None


def test_un_ajustement_non_date_ne_suit_pas():
    ajustement = resoudre_ajustement_applicable([_ligne(2026, cp_n1_opening_balance="15.00")], 2027)

    assert ajustement.cp_n1_opening_balance == 0.0
    assert ajustement.cp_opening_reference_date is None


def test_une_ligne_annuelle_non_datee_n_efface_pas_la_reprise():
    """Poser un RTT en 2027 depuis l'écran ne doit pas faire perdre la
    reprise de 2026 : les CP viennent de la reprise, le reste de l'année."""
    annuelle_2027 = _ligne(2027, rtt_opening_balance="3.50", note="RTT 2027")

    ajustement = resoudre_ajustement_applicable([REPRISE_2026, annuelle_2027], 2027)

    assert ajustement.cp_n1_opening_balance == 15.0
    assert ajustement.cp_opening_reference_date == date(2026, 6, 30)
    assert ajustement.rtt_opening_balance == 3.5
    assert ajustement.note == "RTT 2027"


def test_une_reprise_datee_de_l_annee_prime_sur_la_precedente():
    reprise_2027 = _ligne(
        2027, cp_n1_opening_balance="-4.00", cp_opening_reference_date="2027-01-31"
    )

    ajustement = resoudre_ajustement_applicable([REPRISE_2026, reprise_2027], 2027)

    assert ajustement.cp_n1_opening_balance == -4.0
    assert ajustement.cp_opening_reference_date == date(2027, 1, 31)


def test_la_reprise_datee_la_plus_recente_gagne():
    reprise_2025 = _ligne(
        2025, cp_n1_opening_balance="9.00", cp_opening_reference_date="2025-12-31"
    )

    ajustement = resoudre_ajustement_applicable([reprise_2025, REPRISE_2026], 2028)

    assert ajustement.cp_n1_opening_balance == 15.0


def test_les_lignes_posterieures_a_l_annee_sont_ignorees():
    assert resoudre_ajustement_applicable([REPRISE_2026], 2025).cp_n1_opening_balance == 0.0
