"""Règle « Par jour travaillé » : les jours se comptent dans le calendrier du salarié."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll_variables.domain.jours_travailles import (
    compter_jours_travailles,
    index_calendrier,
)
from app.modules.payroll_variables.domain.rules import compute_rule_amount

pytestmark = pytest.mark.unit


def _semaine():
    """Lundi 5 au dimanche 11/10/2026 : 5 jours de 7 h prévus, week-end en repos."""
    prevu = index_calendrier(
        2026,
        10,
        [{"jour": j, "type": "travail", "heures_prevues": 7} for j in range(5, 10)]
        + [
            {"jour": 10, "type": "weekend", "heures_prevues": 0},
            {"jour": 11, "type": "weekend"},
        ],
    )
    return prevu


def test_sans_heures_reelles_les_jours_prevus_comptent():
    assert (
        compter_jours_travailles(
            _semaine(), {}, set(), date(2026, 10, 5), date(2026, 10, 11)
        )
        == 5
    )


def test_une_absence_validee_retire_le_jour_prevu():
    absences = {date(2026, 10, 7)}
    assert (
        compter_jours_travailles(
            _semaine(), {}, absences, date(2026, 10, 5), date(2026, 10, 11)
        )
        == 4
    )


def test_les_heures_reelles_priment_sur_le_prevu():
    reel = index_calendrier(
        2026,
        10,
        [
            {"jour": 5, "type": "travail", "heures_faites": 0},  # pas venu
            {"jour": 6, "type": "travail", "heures_faites": 3.5},
            {"jour": 10, "type": "travail", "heures_faites": 6},  # samedi travaillé
        ],
    )
    assert (
        compter_jours_travailles(
            _semaine(), reel, set(), date(2026, 10, 5), date(2026, 10, 11)
        )
        == 5
    )


def test_seuil_d_heures():
    reel = index_calendrier(2026, 10, [{"jour": 6, "heures_faites": 3.5}])
    assert (
        compter_jours_travailles(
            _semaine(), reel, set(), date(2026, 10, 5), date(2026, 10, 11), min_heures=6
        )
        == 4
    )


def test_bornes_de_la_fenetre():
    assert (
        compter_jours_travailles(
            _semaine(), {}, set(), date(2026, 10, 7), date(2026, 10, 8)
        )
        == 2
    )


def test_montant_par_jour():
    assert compute_rule_amount("per_worked_day", 7.5, None, 18) == 135.0


def test_un_panier_genere_sans_type_de_prime_est_non_soumis():
    from app.modules.payroll_variables.application.generate_monthly import (
        _bonus_type_meta,
    )

    label, social, taxable, catalog_id, _, _ = _bonus_type_meta(
        {"label": "Panier repas", "rule_type": "per_worked_day", "conditions": {}}
    )
    assert (label, social, taxable, catalog_id) == (
        "Panier repas",
        False,
        False,
        "indemnite_panier_repas",
    )
    _, social, taxable, catalog_id, _, _ = _bonus_type_meta(
        {"label": "Prime d'équipe", "rule_type": "per_worked_day", "conditions": {}}
    )
    assert (social, taxable, catalog_id) == (True, True, None)
