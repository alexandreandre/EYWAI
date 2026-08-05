"""Les relances de période d'essai lisent la table, plus le jsonb."""

from datetime import date

from app.modules.employees.domain.deadline_reminders import (
    REMINDER_TYPE_TRIAL,
    list_hr_deadline_candidates,
)

REF = date(2026, 8, 5)


def _employee(trial):
    return {
        "id": "e1",
        "first_name": "Alex",
        "last_name": "Martin",
        "employment_status": "actif",
        "hire_date": "2026-06-01",
        "trial_period": trial,
    }


def test_periode_active_dans_la_fenetre_declenche_une_relance():
    emp = _employee({"end_date": "2026-08-15", "status": "en_cours"})
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    trials = [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL]
    assert len(trials) == 1
    assert trials[0].deadline == date(2026, 8, 15)


def test_periode_confirmee_ne_declenche_rien():
    emp = _employee({"end_date": "2026-08-15", "status": "confirmee"})
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    assert [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL] == []


def test_periode_rompue_ne_declenche_rien():
    emp = _employee({"end_date": "2026-08-15", "status": "rompue"})
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    assert [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL] == []


def test_absence_de_periode_ne_declenche_rien():
    emp = _employee(None)
    candidates = list_hr_deadline_candidates([emp], reference_date=REF)
    assert [c for c in candidates if c.reminder_type == REMINDER_TYPE_TRIAL] == []
