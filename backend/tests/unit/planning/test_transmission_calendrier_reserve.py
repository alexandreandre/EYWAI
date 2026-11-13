"""Transmission du planning verrouillé pendant l'enregistrement d'un calendrier (13/11).

L'enregistrement d'une RH recalcule `payroll_events` : la transmission doit relire
et refusionner après son achèvement, jamais renvoyer une fusion faite sur une
lecture périmée. Avant, un PT409 arrêtait toute la semaine sans la marquer transmise.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import calendar_write_context as ctx
from app.modules.planning.application import commands


class _Pt409(Exception):
    code = "PT409"


class _Requete:
    def __init__(self, base: "_Base") -> None:
        self.base = base
        self.mode = "select"
        self.valeurs = None

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def maybe_single(self):
        return self

    def update(self, valeurs):
        self.mode, self.valeurs = "update", valeurs
        return self

    def execute(self):
        if self.mode == "select":
            self.base.lectures += 1
            return SimpleNamespace(data={"id": "ligne", "payroll_events": dict(self.base.evenements)})
        if self.base.refus:
            self.base.refus -= 1
            # Pendant ce temps, l'enregistrement de la RH a recalculé les événements.
            self.base.evenements = {"calendrier_analyse": ["recalculé par la RH"]}
            raise _Pt409("Un enregistrement de ce calendrier est en cours.")
        self.base.evenements = self.valeurs["payroll_events"]
        self.base.ecritures += 1
        return SimpleNamespace(data=[])


class _Base:
    def __init__(self, refus: int) -> None:
        self.refus = refus
        self.lectures = 0
        self.ecritures = 0
        self.evenements: dict = {"calendrier_analyse": ["ancien"]}

    def table(self, nom):
        assert nom == "employee_schedules"
        return _Requete(self)


@pytest.fixture
def base(monkeypatch):
    b = _Base(refus=1)
    monkeypatch.setattr(commands, "supabase", b)
    monkeypatch.setattr(ctx.time, "sleep", lambda _s: None)
    transmis: list = []
    monkeypatch.setattr(
        commands.planning_repository, "get_company_planning_settings",
        lambda _c: {"payroll_shift_metrics_enabled": False},
    )
    monkeypatch.setattr(
        commands.planning_repository, "set_payroll_transmitted",
        lambda c, w: transmis.append((c, w)),
    )
    b.transmis = transmis
    return b


def test_relit_et_refusionne_apres_l_enregistrement_de_la_rh(base):
    shifts = [{"id": "s1", "employee_id": "e1", "shift_date": "2026-11-09",
               "start_time": "08:00", "end_time": "12:00", "shift_types": {"code": "M"}}]
    commands._transmit_to_payroll("c1", "2026-11-09", shifts)
    assert base.lectures == 2
    assert base.ecritures == 1
    # Les événements recalculés par la RH sont gardés, le planning s'y ajoute.
    assert base.evenements["calendrier_analyse"] == ["recalculé par la RH"]
    assert base.evenements["planning_week_start"] == "2026-11-09"
    assert base.transmis == [("c1", "2026-11-09")]
