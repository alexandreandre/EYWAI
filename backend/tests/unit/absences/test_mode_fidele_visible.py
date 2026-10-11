"""Le mode « fidèle au bulletin » se voit sur la ligne des congés de la fiche.

Quand la note d'ajustement porte « Import CP bulletin », le solde ne reçoit plus
d'acquisition et le recalage RH est refusé : l'écran doit le dire avant que la
gestionnaire ne tente de corriger.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.absences.application import leave_settings_commands as cmd
from app.modules.absences.application import queries
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
SALARIE = "bbbbbbbb-2222-2222-2222-222222222222"

LIGNES = [
    {"type": "Congés Payés", "acquired": 31.24, "taken": 4.0, "remaining": 27.24},
    {"type": "Congés Payés (période en cours)", "acquired": 6.24, "taken": 0.0, "remaining": 6.24},
    {"type": "RTT", "acquired": 5.0, "taken": 1.0, "remaining": 4.0},
]


def _rh() -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=SOCIETE, company_name="Société A", role="rh", is_primary=True)
        ],
        active_company_id=SOCIETE,
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        queries, "get_employee_absence_balances_for_rh", lambda cid, eid: [dict(l) for l in LIGNES]
    )
    app.dependency_overrides[get_current_user] = _rh
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _soldes(client) -> dict[str, dict]:
    reponse = client.get(f"/api/absences/employees/{SALARIE}/balances")
    assert reponse.status_code == 200, reponse.text
    return {b["type"]: b for b in reponse.json()["balances"]}


def test_les_lignes_de_conges_disent_qu_elles_suivent_le_bulletin(client, monkeypatch):
    monkeypatch.setattr(
        cmd,
        "get_adjustments_by_employees_year",
        lambda ids, year: {SALARIE: replace(EmployeeLeaveAdjustment.empty(), note="Import CP bulletin Août 2026 (x.pdf)")},
    )
    soldes = _soldes(client)
    assert soldes["Congés Payés"]["suit_bulletin"] is True
    assert soldes["Congés Payés (période en cours)"]["suit_bulletin"] is True
    assert soldes["RTT"]["suit_bulletin"] is False


def test_sans_import_de_bulletin_le_mode_n_est_pas_signale(client, monkeypatch):
    monkeypatch.setattr(
        cmd,
        "get_adjustments_by_employees_year",
        lambda ids, year: {SALARIE: replace(EmployeeLeaveAdjustment.empty(), note="Recalage RH du 02/10/2026")},
    )
    assert _soldes(client)["Congés Payés"]["suit_bulletin"] is False
