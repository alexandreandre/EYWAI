"""Le droit à congés d'ancienneté se calcule en mémoire dans un calcul en lecture seule. [lot 31]

Le pied du bulletin calcule les soldes de congés, et ce calcul enregistrait au
passage le droit d'ancienneté de l'année (`employee_cp_seniority_grants`) : une
écriture à chaque essai du brut d'une prime, relevée au lot 30. En lecture
seule, le droit est calculé de la même façon et rendu, sans être enregistré.
Hors lecture seule, il est enregistré comme avant.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.lecture_seule import lecture_seule
from app.modules.absences.application import cp_seniority_queries as q
from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
)

pytestmark = pytest.mark.unit

REFERENCE = date(2026, 5, 31)
REGLAGES = CpSenioritySettings(enabled=True, preset="plasturgie_idcc_0292")
SALARIE = EmployeeCpSeniorityContext(hire_date=date(2010, 3, 1), statut="Non-Cadre")


@pytest.fixture
def enregistres(monkeypatch) -> list[tuple]:
    ecrits: list[tuple] = []
    monkeypatch.setattr(
        q.repo, "upsert_cp_seniority_grant", lambda *a, **_k: ecrits.append(a) or {}
    )
    return ecrits


def test_hors_lecture_seule_le_droit_est_enregistre(enregistres):
    resultat = q.compute_and_persist_grant("soc", "emp", REGLAGES, SALARIE, REFERENCE)

    assert len(enregistres) == 1
    assert enregistres[0][3] == resultat["grant"].days_granted


def test_en_lecture_seule_le_droit_est_calcule_sans_etre_enregistre(enregistres):
    hors = q.compute_and_persist_grant("soc", "emp", REGLAGES, SALARIE, REFERENCE)
    enregistres.clear()

    with lecture_seule():
        dedans = q.compute_and_persist_grant("soc", "emp", REGLAGES, SALARIE, REFERENCE)

    assert enregistres == []
    assert dedans["grant"] == hors["grant"]
    assert dedans["grant"].days_granted > 0
    assert dedans["forfait_annual_days_adjusted"] == hors["forfait_annual_days_adjusted"]
