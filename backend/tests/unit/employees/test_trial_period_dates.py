"""Calcul de la fin de période d'essai (décompte de quantième à quantième)."""

from datetime import date

import pytest

from app.modules.employees.domain.trial_period_dates import compute_trial_end


@pytest.mark.parametrize(
    "start, value, unit, expected",
    [
        # Deux mois à compter du 1er mars expirent le 30 avril, pas le 1er mai.
        (date(2026, 3, 1), 2, "mois", date(2026, 4, 30)),
        # Le quantième 31 février n'existe pas : la période court jusqu'au
        # dernier jour du mois d'arrivée.
        (date(2026, 1, 31), 1, "mois", date(2026, 2, 28)),
        (date(2028, 1, 31), 1, "mois", date(2028, 2, 29)),
        (date(2026, 3, 31), 1, "mois", date(2026, 4, 30)),
        (date(2026, 3, 16), 1, "mois", date(2026, 4, 15)),
        (date(2026, 3, 1), 4, "mois", date(2026, 6, 30)),
        # Le jour d'embauche compte comme premier jour.
        (date(2026, 3, 2), 8, "jours", date(2026, 3, 9)),
        (date(2026, 3, 2), 1, "jours", date(2026, 3, 2)),
        (date(2026, 3, 2), 2, "semaines", date(2026, 3, 15)),
    ],
)
def test_fin_sans_renouvellement(start, value, unit, expected):
    assert compute_trial_end(start, value, unit) == expected


def test_renouvellement_prolonge_depuis_la_fin_initiale():
    # 1er mars + 2 mois = 30 avril ; renouvelée 2 mois, elle repart le 1er mai
    # et expire le 30 juin.
    assert compute_trial_end(
        date(2026, 3, 1), 2, "mois", renewal_value=2, renewal_unit="mois"
    ) == date(2026, 6, 30)


def test_renouvellement_en_jours():
    assert compute_trial_end(
        date(2026, 3, 2), 8, "jours", renewal_value=8, renewal_unit="jours"
    ) == date(2026, 3, 17)


def test_renouvellement_bascule_sur_un_quantieme_inexistant():
    # 30 décembre + 1 mois = 29 janvier ; renouvelée 1 mois, elle repart le
    # 30 janvier et le quantième 30 février n'existe pas.
    assert compute_trial_end(
        date(2025, 12, 30), 1, "mois", renewal_value=1, renewal_unit="mois"
    ) == date(2026, 2, 28)


@pytest.mark.parametrize("value", [0, -1])
def test_duree_non_positive_refusee(value):
    assert compute_trial_end(date(2026, 3, 1), value, "mois") is None


def test_unite_inconnue_refusee():
    assert compute_trial_end(date(2026, 3, 1), 2, "trimestres") is None
