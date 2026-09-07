"""Repos compensateur pris en heures — compteur en heures de bout en bout."""

from datetime import date

import pytest

from app.modules.absences.domain.rules import heures_repos_prises
from app.modules.absences.schemas.requests import AbsenceRequestCreate
from app.modules.repos_compensateur.domain.contingent_rules import compute_rcr_hours

pytestmark = pytest.mark.unit


class TestSchemaHeuresParJour:
    def test_rc_en_heures_valide(self):
        req = AbsenceRequestCreate(
            employee_id="emp-1",
            type="repos_compensateur",
            selected_days=[date(2026, 9, 14)],
            heures_par_jour={date(2026, 9, 14): 2.0},
        )
        assert req.heures_par_jour == {date(2026, 9, 14): 2.0}

    def test_refuse_hors_repos_compensateur(self):
        with pytest.raises(ValueError, match="repos compensateur"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="conge_paye",
                selected_days=[date(2026, 9, 14)],
                heures_par_jour={date(2026, 9, 14): 2.0},
            )

    def test_refuse_heures_hors_bornes(self):
        with pytest.raises(ValueError, match="entre 0 et 12"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="repos_compensateur",
                selected_days=[date(2026, 9, 14)],
                heures_par_jour={date(2026, 9, 14): 13.0},
            )

    def test_refuse_jour_hors_selection(self):
        with pytest.raises(ValueError, match="jour sélectionné"):
            AbsenceRequestCreate(
                employee_id="emp-1",
                type="repos_compensateur",
                selected_days=[date(2026, 9, 14)],
                heures_par_jour={date(2026, 9, 20): 2.0},
            )


class TestHeuresReposPrises:
    def test_mix_heures_et_journees(self):
        """2 h le 14 + journée entière le 15 (7,5 h société) = 9,5 h."""
        requests = [
            {
                "type": "repos_compensateur",
                "status": "validated",
                "selected_days": ["2026-09-14", "2026-09-15"],
                "heures_par_jour": {"2026-09-14": 2.0},
            }
        ]
        assert (
            heures_repos_prises(
                requests, date(2026, 12, 31), hours_per_rest_day=7.5
            )
            == 9.5
        )

    def test_autres_types_ignores(self):
        requests = [
            {
                "type": "conge_paye",
                "status": "validated",
                "selected_days": ["2026-09-14"],
            }
        ]
        assert (
            heures_repos_prises(requests, date(2026, 12, 31), hours_per_rest_day=7.0)
            == 0.0
        )


class TestComputeRcrHeuresReelles:
    def test_prise_partielle_ne_compte_plus_une_journee(self):
        requests = [
            {
                "type": "repos_compensateur",
                "status": "validated",
                "selected_days": ["2026-03-10", "2026-03-11"],
                "heures_par_jour": {"2026-03-10": 2.0},
            }
        ]
        # 2 h réelles + 1 journée × 7 h = 9 h (avant : 2 jours × 7 = 14 h).
        assert (
            compute_rcr_hours(requests, date(2026, 12, 31), 2026, 7.0) == 9.0
        )
