"""Répartition des périodes d'essai en sections de suivi."""

from datetime import date

from app.modules.trial_periods.application.queries import (
    select_to_qualify,
    split_sections,
)

REF = date(2026, 8, 5)


def _trial(end: str, status: str = "en_cours"):
    return {"id": f"tp-{end}", "end_date": end, "status": status}


def test_en_cours_et_a_confirmer_separes_par_le_delai_d_alerte():
    trials = [
        _trial("2026-12-31"),  # loin
        _trial("2026-08-15"),  # dans 10 jours, sous l'alerte de 15
        _trial("2026-07-01"),  # dépassée
    ]
    sections = split_sections(trials, alert_days=15, reference=REF)
    assert [t["end_date"] for t in sections["en_cours"]] == ["2026-12-31"]
    assert [t["end_date"] for t in sections["a_confirmer"]] == [
        "2026-07-01",
        "2026-08-15",
    ]


def test_le_delai_d_alerte_est_inclusif():
    sections = split_sections([_trial("2026-08-20")], alert_days=15, reference=REF)
    assert len(sections["a_confirmer"]) == 1


def test_les_periodes_closes_sont_ecartees():
    trials = [
        _trial("2026-07-01", status="confirmee"),
        _trial("2026-07-02", status="rompue"),
    ]
    sections = split_sections(trials, alert_days=15, reference=REF)
    assert sections["en_cours"] == []
    assert sections["a_confirmer"] == []


def test_a_qualifier_ne_retient_que_les_embauches_recentes_sans_periode():
    employees = [
        {"id": "e1", "hire_date": "2026-07-01", "employment_status": "actif"},
        {"id": "e2", "hire_date": "2020-01-01", "employment_status": "actif"},
        {"id": "e3", "hire_date": "2026-06-01", "employment_status": "actif"},
        {"id": "e4", "hire_date": "2026-07-15", "employment_status": "en_sortie"},
        {"id": "e5", "hire_date": None, "employment_status": "actif"},
    ]
    result = select_to_qualify(employees, covered_ids={"e3"}, reference=REF)
    assert [e["id"] for e in result] == ["e1"]


def test_a_qualifier_prend_en_onboarding():
    employees = [
        {"id": "e1", "hire_date": "2026-07-01", "employment_status": "en_onboarding"}
    ]
    assert [e["id"] for e in select_to_qualify(employees, set(), REF)] == ["e1"]


def test_a_qualifier_borne_a_huit_mois():
    # 240 jours avant le 5 août 2026 : le 8 décembre 2025.
    employees = [
        {"id": "dedans", "hire_date": "2025-12-10", "employment_status": "actif"},
        {"id": "dehors", "hire_date": "2025-12-01", "employment_status": "actif"},
    ]
    assert [e["id"] for e in select_to_qualify(employees, set(), REF)] == ["dedans"]
