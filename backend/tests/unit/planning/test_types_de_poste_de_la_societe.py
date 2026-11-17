"""Types de poste : seulement ceux de la convention planning de la société.

Constat du guide 1 (17/11) : sans convention planning, l'écran listait les types
actifs de toutes les conventions (postes en double) et laissait les modifier.
"""

from __future__ import annotations

import pytest

from app.modules.planning.application import queries, shift_type_commands
from app.modules.planning.infrastructure.repository import planning_repository

pytestmark = pytest.mark.unit


@pytest.fixture
def repo(monkeypatch):
    etat = {"cc": None, "maj": []}
    monkeypatch.setattr(
        planning_repository,
        "get_company_planning_settings",
        lambda cid: {"collective_agreement_id": etat["cc"]},
    )
    monkeypatch.setattr(
        planning_repository,
        "get_shift_types_by_cc",
        lambda cc: [{"id": "t1", "code": "MATIN", "collective_agreement_id": cc}],
    )
    monkeypatch.setattr(
        planning_repository,
        "get_all_active_shift_types",
        lambda: pytest.fail("types de toutes les conventions lus"),
    )
    monkeypatch.setattr(
        planning_repository,
        "get_shift_type_by_id",
        lambda sid: {"id": sid, "collective_agreement_id": "cc-autre"},
    )
    monkeypatch.setattr(
        planning_repository, "update_shift_type", lambda sid, d: etat["maj"].append(sid) or {}
    )
    monkeypatch.setattr(
        planning_repository, "deactivate_shift_type", lambda sid: etat["maj"].append(sid)
    )
    return etat


def test_sans_convention_aucun_type(repo):
    assert queries.get_shift_types_for_company("co-1") == []


def test_avec_convention_ses_types(repo):
    repo["cc"] = "cc-1"
    assert [t["code"] for t in queries.get_shift_types_for_company("co-1")] == ["MATIN"]


@pytest.mark.parametrize("cc", [None, "cc-1"])
def test_un_type_d_une_autre_convention_ne_se_modifie_pas(repo, cc):
    repo["cc"] = cc
    with pytest.raises(PermissionError):
        shift_type_commands.update_shift_type("co-1", "t9", {"paid_break_minutes": 10})
    with pytest.raises(PermissionError):
        shift_type_commands.delete_shift_type("co-1", "t9")
    assert repo["maj"] == []
