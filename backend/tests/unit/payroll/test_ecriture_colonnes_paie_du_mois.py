"""Cumuls et événements du mois écrits pendant l'enregistrement d'un calendrier (13/11).

Le trigger `guard_calendar_edit` refuse (PT409) toute écriture sur la ligne d'un mois
qu'une RH est en train d'enregistrer, cumuls compris. Le bulletin est déjà en base
quand ses cumuls s'écrivent : on attend la fin de l'enregistrement et on rejoue.
"""
from __future__ import annotations

import pytest

from app.core import calendar_write_context as ctx
from app.core.calendar_write_context import CalendrierReserve, calendar_write_token
from app.modules.payroll.infrastructure.colonnes_paie_du_mois import (
    ecrire_colonnes_paie_du_mois,
)


class _Pt409(Exception):
    code = "PT409"


class _Table:
    def __init__(self, base: _Base) -> None:
        self.base = base
        self.valeurs: dict | None = None
        self.filtre: dict | None = None

    def update(self, valeurs: dict) -> _Table:
        self.valeurs = valeurs
        return self

    def match(self, filtre: dict) -> _Table:
        self.filtre = filtre
        return self

    def execute(self):
        self.base.essais += 1
        if self.base.refus > 0:
            self.base.refus -= 1
            raise _Pt409("Un enregistrement de ce calendrier est en cours.")
        self.base.ecrits.append((self.valeurs, self.filtre))
        return type("R", (), {"data": [self.valeurs]})()


class _Base:
    def __init__(self, refus: int) -> None:
        self.refus = refus
        self.essais = 0
        self.ecrits: list = []
        self.tables: list[str] = []

    def table(self, nom: str) -> _Table:
        self.tables.append(nom)
        return _Table(self)


@pytest.fixture(autouse=True)
def _sans_attente(monkeypatch):
    monkeypatch.setattr(ctx.time, "sleep", lambda _s: None)


def test_ecrit_une_fois_quand_le_mois_est_libre():
    base = _Base(refus=0)
    ecrire_colonnes_paie_du_mois(base, "e1", 2026, 10, {"cumuls": {"brut": 1}})
    assert base.tables == ["employee_schedules"]
    assert base.ecrits == [({"cumuls": {"brut": 1}}, {"employee_id": "e1", "year": 2026, "month": 10})]


def test_attend_la_fin_de_l_enregistrement_puis_ecrit():
    base = _Base(refus=2)
    ecrire_colonnes_paie_du_mois(base, "e1", 2026, 10, {"cumuls": {"brut": 1}})
    assert base.essais == 3
    assert len(base.ecrits) == 1


def test_mois_reste_reserve_erreur_explicite(monkeypatch):
    base = _Base(refus=10_000)
    horloge = iter(range(0, 100_000, 5))
    monkeypatch.setattr(ctx.time, "monotonic", lambda: float(next(horloge)))
    with pytest.raises(CalendrierReserve):
        ecrire_colonnes_paie_du_mois(base, "e1", 2026, 10, {"cumuls": None})
    assert base.ecrits == []


def test_n_ecrit_que_les_colonnes_demandees():
    base = _Base(refus=0)
    with pytest.raises(ValueError):
        ecrire_colonnes_paie_du_mois(base, "e1", 2026, 10, {"actual_hours": {}})
    assert base.essais == 0


def test_sous_un_jeton_d_enregistrement_ne_rejoue_pas():
    base = _Base(refus=1)
    with calendar_write_token("jeton"), pytest.raises(_Pt409):
        ecrire_colonnes_paie_du_mois(base, "e1", 2026, 10, {"cumuls": None})
    assert base.essais == 1
