"""Saisie d'un contrat passé : la fin ne peut pas précéder le début."""

import pytest
from pydantic import ValidationError

from app.modules.employees.application.contract_periods import ContractPeriodIn


def test_periode_acceptee():
    periode = ContractPeriodIn(
        contract_type=" CDD ",
        date_debut="2026-03-01",
        date_fin="2026-05-31",
    )
    assert periode.contract_type == "CDD"
    assert periode.date_fin.isoformat() == "2026-05-31"


def test_fin_avant_debut_refusee():
    with pytest.raises(ValidationError):
        ContractPeriodIn(
            contract_type="CDD",
            date_debut="2026-09-01",
            date_fin="2026-05-31",
        )


# ---------------------------------------------------------------------------
# Routes : chaque ajout ou suppression laisse une trace d'audit.
# ---------------------------------------------------------------------------

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.users.schemas.responses import CompanyAccess, User  # noqa: E402

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_FICHE = "cccccccc-3333-3333-3333-333333333333"
_PERIODE = "eeeeeeee-5555-5555-5555-555555555555"
_ROUTER = "app.modules.employees.api.router"


def _rh() -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société A", role="rh", is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _rh
    try:
        with patch(f"{_ROUTER}._rh_employee", return_value=_SOCIETE):
            yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_ajout_d_un_contrat_passe_journalise(client):
    ligne = {"id": _PERIODE, "contract_type": "CDD", "date_debut": "2026-03-01", "date_fin": "2026-05-31"}
    with patch(f"{_ROUTER}.contract_periods.add_contract_period", return_value=ligne), patch(
        f"{_ROUTER}.log_audit_event"
    ) as audit:
        reponse = client.post(
            f"/api/employees/{_FICHE}/contract-periods",
            json={"contract_type": "CDD", "date_debut": "2026-03-01", "date_fin": "2026-05-31"},
        )
    assert reponse.status_code == 201
    audit.assert_called_once()
    kwargs = audit.call_args.kwargs
    assert kwargs["action"] == "employee.contract_period.create"
    assert kwargs["resource_id"] == _FICHE
    assert kwargs["details"] == {
        "period_id": _PERIODE,
        "contract_type": "CDD",
        "date_debut": "2026-03-01",
        "date_fin": "2026-05-31",
    }


def test_suppression_d_un_contrat_passe_journalise(client):
    with patch(f"{_ROUTER}.contract_periods.delete_contract_period"), patch(
        f"{_ROUTER}.log_audit_event"
    ) as audit:
        reponse = client.delete(f"/api/employees/{_FICHE}/contract-periods/{_PERIODE}")
    assert reponse.status_code == 204
    audit.assert_called_once()
    assert audit.call_args.kwargs["action"] == "employee.contract_period.delete"
    assert audit.call_args.kwargs["details"] == {"period_id": _PERIODE}
