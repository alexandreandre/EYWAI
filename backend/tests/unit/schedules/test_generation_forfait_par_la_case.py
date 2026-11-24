"""Génération du planning depuis un plan : le forfait jours se lit sur la case (24/11).

En base, `employees.statut` ne vaut que « Cadre » ou « Non-Cadre ». La génération
lisait le libellé seul : un cadre au forfait (case cochée) recevait un prévu en
heures (7 h par jour) au lieu de jours (1 par jour travaillé). Comme le
générateur du bulletin forfait, elle lit la case `is_forfait_jour`, le libellé
seulement si la case est vide.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.schedules.application import calendar_generation
from app.modules.schedules.application.calendar_generation import GenerationSpec, generate
from app.modules.schedules.infrastructure import schedule_plans_repository

pytestmark = pytest.mark.unit

_SEMAINE_7H = [
    {"day": iso, "type": "travail", "hours": 7.0} for iso in range(1, 6)
] + [{"day": 6, "type": "repos", "hours": 0}, {"day": 7, "type": "repos", "hours": 0}]


def _generer(monkeypatch, fiche: dict) -> list[dict]:
    monkeypatch.setattr(
        calendar_generation.plans_repo,
        "get_templates_by_ids",
        lambda c, ids: {ids[0]: {"id": ids[0], "day_configs": _SEMAINE_7H}},
    )
    monkeypatch.setattr(
        calendar_generation.plans_repo,
        "resolve_scope_employees",
        lambda c, st, sr: [{"id": "e1", "first_name": "A", "last_name": "B", **fiche}],
    )
    monkeypatch.setattr(calendar_generation, "day_numbers_observed_holidays", lambda y, m, c: set())
    monkeypatch.setattr(
        calendar_generation.schedule_repository, "get_schedules_for_months", lambda e, ym: []
    )
    ecrits: list = []
    monkeypatch.setattr(
        calendar_generation.schedule_repository, "bulk_upsert_schedules", ecrits.extend
    )
    spec = GenerationSpec(
        company_id="c",
        template_cycle=["t"],
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
        cycle_anchor=date(2026, 11, 2),
    )
    generate(spec)
    assert len(ecrits) == 1
    return ecrits[0]["planned_calendar"]["calendrier_prevu"]


def _heures_des_jours_travailles(entries: list[dict]) -> set[float]:
    return {e["heures_prevues"] for e in entries if e["type"] == "travail"}


@pytest.mark.parametrize(
    "fiche",
    [
        {"statut": "Cadre", "is_forfait_jour": True},
        {"statut": "Non-Cadre", "is_forfait_jour": True},
        {"statut": None, "is_forfait_jour": True},
        # Case vide : le libellé historique sert encore de repli.
        {"statut": "Cadre au forfait jour", "is_forfait_jour": None},
    ],
)
def test_salarie_au_forfait_prevu_en_jours(monkeypatch, fiche):
    assert _heures_des_jours_travailles(_generer(monkeypatch, fiche)) == {1}


@pytest.mark.parametrize(
    "fiche",
    [
        {"statut": "Cadre", "is_forfait_jour": False},
        {"statut": "Cadre", "is_forfait_jour": None},
        # La case décochée l'emporte sur un libellé trompeur.
        {"statut": "Cadre au forfait jour", "is_forfait_jour": False},
    ],
)
def test_salarie_en_heures_prevu_en_heures(monkeypatch, fiche):
    assert _heures_des_jours_travailles(_generer(monkeypatch, fiche)) == {7.0}


class _Requete:
    def __init__(self, selects: list[str]):
        self._selects = selects

    def select(self, colonnes):
        self._selects.append(colonnes)
        return self

    def __getattr__(self, _nom):
        return lambda *a, **k: self

    def execute(self):
        return SimpleNamespace(data=[])


@pytest.mark.parametrize(
    ("scope_type", "scope_ref"),
    [("employees", {"employee_ids": ["e1"]}), ("company", {}), ("team", {"team_id": "t"})],
)
def test_la_portee_lit_la_case_du_forfait(monkeypatch, scope_type, scope_ref):
    selects: list[str] = []
    monkeypatch.setattr(
        schedule_plans_repository,
        "supabase",
        SimpleNamespace(table=lambda _n: _Requete(selects)),
    )
    schedule_plans_repository.resolve_scope_employees("c", scope_type, scope_ref)
    assert selects and all("is_forfait_jour" in s for s in selects)
