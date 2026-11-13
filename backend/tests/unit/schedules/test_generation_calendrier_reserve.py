"""Génération depuis un modèle pendant l'enregistrement d'un calendrier (13/11).

Le trigger refuse (PT409) l'écriture d'un mois qu'une RH enregistre. La génération est
alors rejouée entière, relecture comprise, jamais renvoyée telle quelle ; au-delà du
délai, la RH reçoit un 409 explicite.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.core import calendar_write_context as ctx
from app.core.calendar_write_context import CalendrierReserve
from app.modules.schedules.application import calendar_generation, plan_commands
from app.modules.schedules.application.calendar_generation import (
    GenerationSpec,
    generate,
)
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.presets_2026 import get_registry
from app.modules.schedules.infrastructure import repository as schedule_repo_module


class _Pt409(Exception):
    code = "PT409"


def _days():
    for t in get_registry()["mbc"].templates:
        if t.name == "MBC — Standard (37,5h)":
            return t.days
    raise AssertionError("modèle MBC introuvable")


def _spec():
    return GenerationSpec(
        company_id="c", template_cycle=["t"], start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31), cycle_anchor=date(2026, 3, 2),
    )


@pytest.fixture
def base(monkeypatch):
    etat = SimpleNamespace(lectures=0, refus=1, ecrits=[])
    days = _days()
    monkeypatch.setattr(ctx.time, "sleep", lambda _s: None)
    monkeypatch.setattr(calendar_generation.plans_repo, "get_templates_by_ids",
                        lambda c, ids: {ids[0]: {"id": ids[0], "day_configs": days}})
    monkeypatch.setattr(calendar_generation.plans_repo, "resolve_scope_employees",
                        lambda c, st, sr: [{"id": "e1", "statut": None, "first_name": "A", "last_name": "B"}])
    monkeypatch.setattr(calendar_generation, "day_numbers_observed_holidays", lambda y, m, c: set())

    def lire(_e, _ym):
        etat.lectures += 1
        return []

    def ecrire(payloads):
        if etat.refus:
            etat.refus -= 1
            raise _Pt409("Un enregistrement de ce calendrier est en cours.")
        etat.ecrits.append(payloads)

    monkeypatch.setattr(calendar_generation.schedule_repository, "get_schedules_for_months", lire)
    monkeypatch.setattr(calendar_generation.schedule_repository, "bulk_upsert_schedules", ecrire)
    return etat


def test_rejoue_la_generation_entiere_relecture_comprise(base):
    resultat = generate(_spec(), dry_run=False)
    assert resultat["status"] == "applied"
    assert base.lectures == 2
    assert len(base.ecrits) == 1


def test_mois_reste_reserve_409_explicite(base, monkeypatch):
    base.refus = 10_000
    horloge = iter(range(0, 100_000, 5))
    monkeypatch.setattr(ctx.time, "monotonic", lambda: float(next(horloge)))
    monkeypatch.setattr(calendar_generation.plans_repo, "get_plan", lambda c, p: {"id": p})
    monkeypatch.setattr(calendar_generation, "spec_from_plan", lambda plan, **_k: _spec())
    payload = SimpleNamespace(plan_id="p1", year=2026, overwrite_mode=None, dry_run=False, recalculate_payroll=False)
    with pytest.raises(ScheduleAppError) as exc:
        plan_commands.generate(payload, SimpleNamespace(active_company_id="c", has_rh_access_in_company=lambda _c: True))
    assert exc.value.status_code == 409
    assert isinstance(exc.value.__cause__, CalendrierReserve)
    assert base.ecrits == []


def test_l_apercu_n_attend_pas(base):
    resultat = generate(_spec(), dry_run=True)
    assert resultat["status"] == "preview"
    assert base.lectures == 1


def test_upsert_d_un_mois_reserve_n_est_pas_renvoye(monkeypatch):
    envois = []

    class _Req:
        def upsert(self, payload, on_conflict=None):
            return self

        def execute(self):
            envois.append(1)
            raise _Pt409("Un enregistrement de ce calendrier est en cours.")

    monkeypatch.setattr(schedule_repo_module, "supabase", SimpleNamespace(table=lambda _n: _Req()))
    with pytest.raises(_Pt409):
        schedule_repo_module.schedule_repository.upsert_schedule(
            employee_id="e1", company_id="c", year=2026, month=3, actual_hours={"x": 1}
        )
    assert len(envois) == 1
