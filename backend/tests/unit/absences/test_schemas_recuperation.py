"""La récupération se prend aussi en heures (spec 2026-11-05 § 3.5)."""

from datetime import date

import pytest

from app.modules.absences.schemas.requests import AbsenceRequestCreate

pytestmark = pytest.mark.unit


def test_recuperation_en_heures_acceptee():
    demande = AbsenceRequestCreate(
        employee_id="emp-1",
        type="recuperation_modulation",
        selected_days=[date(2026, 8, 14)],
        heures_par_jour={date(2026, 8, 14): 3.5},
    )
    assert demande.heures_par_jour == {date(2026, 8, 14): 3.5}


def test_conge_paye_en_heures_toujours_refuse():
    with pytest.raises(ValueError, match="en heures"):
        AbsenceRequestCreate(
            employee_id="emp-1",
            type="conge_paye",
            selected_days=[date(2026, 8, 14)],
            heures_par_jour={date(2026, 8, 14): 3.5},
        )
