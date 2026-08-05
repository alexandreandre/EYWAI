"""Constantes du module trial_periods, alignées sur les contraintes SQL."""

from app.modules.trial_periods.domain.constants import (
    STATUS_CONFIRMEE,
    STATUS_EN_COURS,
    STATUS_ROMPUE,
    VALID_STATUSES,
)
from app.modules.trial_periods.infrastructure.queries import TABLE_TRIAL_PERIODS


def test_statuts_conformes_a_la_contrainte_sql():
    assert VALID_STATUSES == frozenset({"en_cours", "confirmee", "rompue"})
    assert STATUS_EN_COURS == "en_cours"
    assert STATUS_CONFIRMEE == "confirmee"
    assert STATUS_ROMPUE == "rompue"


def test_nom_de_table():
    assert TABLE_TRIAL_PERIODS == "trial_periods"
