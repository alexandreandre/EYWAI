from copy import deepcopy
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.security import get_current_user
from app.modules.schedules.api import router as routes
from app.modules.schedules.application import calendar_edit as service
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.infrastructure import calendar_edit_repository as repo
from app.modules.schedules.schemas.requests import CalendarSaveRequest

REVISION = "00000000-0000-0000-0000-000000000001"
NEW_REVISION = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def gateway(monkeypatch):
    state = {
        "begin": "acquired", "renew": True, "calls": [], "commands": [],
        "snapshot": {"revision": NEW_REVISION, "busy": False,
                     "planned_calendar": {"calendrier_prevu": [{"jour": 6, "type": "repos", "heures_prevues": 0}]},
                     "actual_hours": {"calendrier_reel": [{"jour": 6, "type": "repos", "heures_faites": 7}]}},
    }
    def rpc(name, params):
        state["calls"].append((name, deepcopy(params)))
        if name == "begin_calendar_edit":
            if isinstance(state["begin"], Exception):
                raise state["begin"]
            return state["begin"]
        if name == "renew_calendar_edit":
            return state["renew"]
        if name == "end_calendar_edit":
            return None
        if name == "read_calendar_snapshot":
            return deepcopy(state["snapshot"])
        raise AssertionError(name)
    monkeypatch.setattr(repo, "_rpc", rpc)
    monkeypatch.setattr(service.queries, "_jours_en_conflit_du_mois", lambda *a, **kw: [])
    for name in ["update_planned_calendar", "update_actual_hours", "calculate_payroll_events"]:
        def command(*args, _name=name):
            state["commands"].append(_name)
            return {"warnings": [{"code": "conge_cree", "jour": 6}]} if _name == "update_planned_calendar" else {}
        monkeypatch.setattr(service.commands, name, Mock(side_effect=command))
    return state


def payload(**changes):
    return CalendarSaveRequest(**{
        "year": 2026, "month": 11, "expected_revision": REVISION,
        "calendrier_prevu": [{"jour": 6, "type": "repos", "heures_prevues": 0}],
        "calendrier_reel": [{"jour": 6, "type": "repos", "heures_faites": 7}],
        "recalculate_payroll": True, **changes,
    })


def test_save_reserves_before_commands_and_keeps_order_and_server_snapshot(gateway):
    result = service.save_calendar("employee-a", "company-a", payload())
    assert gateway["commands"] == ["update_planned_calendar", "update_actual_hours", "calculate_payroll_events"]
    assert gateway["calls"][0][0] == "begin_calendar_edit"
    assert gateway["calls"][0][1]["p_expected_revision"] == REVISION
    assert gateway["calls"][-1][0] == "end_calendar_edit"
    assert result["revision"] == NEW_REVISION
    assert result["calendrier_prevu"][0]["heures_prevues"] == 0
    assert result["calendrier_reel"][0]["heures_faites"] == 7
    assert result["warnings"] == [{"code": "conge_cree", "jour": 6}]
    assert result["payroll_recalculated"] is True


@pytest.mark.parametrize("result,code,status", [("busy", "calendar_busy", 409), ("conflict", "calendar_conflict", 409), ("not_found", "not_found", 404), (None, "calendar_unavailable", 503), ({}, "calendar_unavailable", 503)])
def test_refusal_never_calls_calendar_or_absence_commands(gateway, result, code, status):
    gateway["begin"] = result
    with pytest.raises(ScheduleAppError) as caught:
        service.save_calendar("employee-a", "company-a", payload())
    assert (caught.value.code, caught.value.status_code) == (code, status)
    assert not gateway["commands"]


def test_uncertain_acquisition_attempt_releases_only_its_token(gateway):
    gateway["begin"] = TimeoutError("No response")
    with pytest.raises(ScheduleAppError) as caught:
        service.save_calendar("employee-a", "company-a", payload())
    assert caught.value.status_code == 503 and not gateway["commands"]
    begin, end = gateway["calls"]
    assert begin[0] == "begin_calendar_edit" and end[0] == "end_calendar_edit"
    assert begin[1]["p_token"] == end[1]["p_token"]


@pytest.mark.parametrize("name,stage,confirmed", [
    ("update_planned_calendar", "planned", []),
    ("update_actual_hours", "actual", ["planned"]),
    ("calculate_payroll_events", "payroll", ["planned", "actual"]),
])
def test_failure_does_not_report_full_success_and_releases_lease(gateway, name, stage, confirmed):
    getattr(service.commands, name).side_effect = ValueError("simulated")
    with pytest.raises(ScheduleAppError) as caught:
        service.save_calendar("employee-a", "company-a", payload())
    assert caught.value.detail["stage"] == stage
    assert caught.value.detail["confirmed"] == confirmed
    assert gateway["calls"][-1][0] == "end_calendar_edit"
    if name == "update_planned_calendar":
        service.commands.update_actual_hours.assert_not_called()
    if name != "calculate_payroll_events":
        service.commands.calculate_payroll_events.assert_not_called()


def test_expired_lease_stops_before_first_write(gateway):
    gateway["renew"] = False
    with pytest.raises(ScheduleAppError):
        service.save_calendar("employee-a", "company-a", payload())
    assert not gateway["commands"]
    assert gateway["calls"][-1][0] == "end_calendar_edit"


def test_partial_actual_save_does_not_touch_planned_or_calculate(gateway):
    service.save_calendar("employee-a", "company-a", payload(calendrier_prevu=None, recalculate_payroll=False))
    assert gateway["commands"] == ["update_actual_hours"]


def test_null_revision_for_new_month_is_transmitted_explicitly(gateway):
    service.save_calendar("employee-a", "company-a", payload(expected_revision=None))
    assert gateway["calls"][0][1]["p_expected_revision"] is None


@pytest.mark.parametrize("changes", [{"month": 13}, {"year": 1800}, {"expected_revision": "invalid"}, {"calendrier_prevu": None, "calendrier_reel": None}])
def test_schema_refuses_invalid_or_empty_save(changes):
    with pytest.raises(ValidationError):
        payload(**changes)


def test_schema_requires_expected_revision_even_for_new_month():
    raw = payload().model_dump()
    del raw["expected_revision"]
    with pytest.raises(ValidationError):
        CalendarSaveRequest(**raw)


@pytest.mark.parametrize("method,path,permission", [
    ("GET", "/calendar-snapshot?year=2026&month=11", "schedules.view_all"),
    ("POST", "/calendar-save", "schedules.update"),
])
def test_routes_keep_employee_and_company_permission_checks(monkeypatch, gateway, method, path, permission):
    app = FastAPI()
    app.include_router(routes.router)
    user = Mock(active_company_id="company-a")
    app.dependency_overrides[get_current_user] = lambda: user
    check = Mock(side_effect=HTTPException(403, "Refus simulé"))
    monkeypatch.setattr(routes.access_control_service, "require_employee_access", check)
    with TestClient(app) as client:
        response = client.request(method, "/api/employees/employee-a" + path, json=payload().model_dump(mode="json") if method == "POST" else None)
    assert response.status_code == 403
    check.assert_called_once_with(user, "company-a", permission, "employee-a")
    assert not gateway["calls"]


@pytest.mark.parametrize("path,entries", [("planned-calendar", "calendrier_prevu"), ("actual-hours", "calendrier_reel")])
def test_old_manual_endpoint_requires_revision_before_any_command(monkeypatch, gateway, path, entries):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: Mock(active_company_id="company-a")
    monkeypatch.setattr(routes.access_control_service, "require_employee_access", Mock())
    with TestClient(app) as client:
        result = client.post(f"/api/employees/employee-a/{path}", json={"year": 2026, "month": 11, entries: []})
    assert result.status_code == 428
    assert not gateway["calls"] and not gateway["commands"]


@pytest.mark.parametrize("changes", [{"revision": None}, {"busy": True}])
def test_final_snapshot_must_confirm_a_persisted_revision_and_ownership(gateway, changes):
    gateway["snapshot"].update(changes)
    with pytest.raises(ScheduleAppError) as caught:
        service.save_calendar("employee-a", "company-a", payload())
    assert caught.value.detail["stage"] == "confirmation"
    assert gateway["calls"][-1][0] == "end_calendar_edit"


def test_lease_does_not_renew_forever(gateway, monkeypatch):
    monkeypatch.setattr(repo, "MAX_SECONDS", 0)
    with pytest.raises(ScheduleAppError):
        service.save_calendar("employee-a", "company-a", payload())
    assert not gateway["commands"]


def test_a_running_payslip_refuses_calendar_before_reserving_or_writing(gateway, verrous_de_generation):
    verrous_de_generation.tenus[("employee-a", 2026, 11)] = "another-request"
    with pytest.raises(ScheduleAppError) as caught:
        service.save_calendar("employee-a", "company-a", payload())
    assert caught.value.status_code == 409 and caught.value.code == "calendar_busy"
    assert not gateway["calls"] and not gateway["commands"]


def test_calendar_requires_confirmed_payslip_lock_before_any_write(gateway, monkeypatch):
    from app.modules.payroll.documents import verrou_generation
    monkeypatch.setattr(verrou_generation, "_rpc", lambda *a: (_ for _ in ()).throw(ConnectionError()))
    with pytest.raises(ScheduleAppError) as caught:
        service.save_calendar("employee-a", "company-a", payload())
    assert caught.value.status_code == 503 and not gateway["calls"] and not gateway["commands"]


def test_old_apply_model_route_is_refused_before_any_write(monkeypatch):
    """Un onglet ouvert avant paie-2026-11-13.1 appelle encore POST /api/schedules/apply-model,
    sans révision : il est invité à recharger, rien n'est écrit."""
    app = FastAPI()
    app.include_router(routes.router_rh)
    app.dependency_overrides[get_current_user] = lambda: Mock(active_company_id="company-a")
    app.dependency_overrides[routes._exiger_profil_rh] = lambda: Mock(active_company_id="company-a")
    ecriture = Mock()
    monkeypatch.setattr(routes.commands, "apply_schedule_model", ecriture)
    body = {"employee_ids": ["employee-a"], "year": 2026, "month": 11, "week_configs": {}}
    with TestClient(app) as client:
        result = client.post("/api/schedules/apply-model", json=body)
    assert result.status_code == 428
    assert "Rechargez la page" in result.json()["detail"]
    ecriture.assert_not_called()
