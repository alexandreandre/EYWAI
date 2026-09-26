"""
Prêts employeur : périmètre société des mutations (audit du 25/09/2026, E1).

Sept routes de mutation (modifier, supprimer, annuler, activer, mettre en
défaut, rembourser par anticipation, déclarer 2062) et la lecture de l'encours
d'un salarié ne contrôlaient que le rôle RH, puis accédaient au prêt par son
seul identifiant : une RH de la société A agissait sur le prêt d'un salarié
de la société B. Les routes de lecture voisines passaient déjà par
`require_loan_access` ; les mutations le suivent désormais.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.employee_loans.schemas.responses import (
    EmployeeLoan,
    EmployeeLoanOutstanding,
)
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "aaaaaaaa-1111-1111-1111-111111111111"
SOCIETE_B = "bbbbbbbb-2222-2222-2222-222222222222"
PRET = "eeeeeeee-5555-5555-5555-555555555555"
SALARIE = "cccccccc-3333-3333-3333-333333333333"


def _user(role: str = "rh", *, platform_admin: bool = False) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="rh@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=platform_admin,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE_A,
                company_name="Société A",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE_A,
    )


def _pret(company_id: str) -> EmployeeLoan:
    return EmployeeLoan.model_validate(
        {
            "id": PRET,
            "company_id": company_id,
            "employee_id": SALARIE,
            "principal_amount": 5000,
            "annual_interest_rate": 0,
            "start_date": "2026-06-01",
            "duration_months": 12,
            "monthly_payment": 416.67,
            "repayment_day": 1,
            "status": "draft",
            "remaining_capital": 0,
            "requires_2062_declaration": True,
            "declared_2062": False,
        }
    )


# (méthode HTTP, suffixe d'URL, corps JSON, commande appelée)
MUTATIONS = [
    ("patch", "", {"notes": "relu"}, "update_loan"),
    ("delete", "", None, "delete_loan"),
    ("post", "/cancel", None, "cancel_loan"),
    ("post", "/activate", None, "activate_loan"),
    ("post", "/default", None, "mark_loan_defaulted"),
    (
        "post",
        "/early-repayment",
        {"amount": 100, "repayment_date": "2026-09-01"},
        "record_early_repayment",
    ),
    ("patch", "/declared-2062", None, "mark_declared_2062"),
]


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _appeler(client: TestClient, methode: str, suffixe: str, corps):
    url = f"/api/employee-loans/{PRET}{suffixe}"
    if corps is None:
        return getattr(client, methode)(url)
    return getattr(client, methode)(url, json=corps)


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_pret_d_une_autre_societe_refuse(client, methode, suffixe, corps, commande):
    with (
        patch(
            "app.modules.employee_loans.api.access.queries.get_loan",
            return_value=_pret(SOCIETE_B),
        ),
        patch(
            "app.modules.employee_loans.api.access.resolve_my_employee_id",
            return_value="ffffffff-6666-6666-6666-666666666666",
        ),
        patch("app.modules.employee_loans.api.router.commands") as commands,
    ):
        reponse = _appeler(client, methode, suffixe, corps)

    # Même refus que la lecture voisine (require_loan_access) : 403.
    assert reponse.status_code == 403
    # Le plus important : aucune écriture n'a démarré.
    getattr(commands, commande).assert_not_called()


@pytest.mark.parametrize("methode,suffixe,corps,commande", MUTATIONS)
def test_pret_de_ma_societe_autorise_comme_avant(
    client, methode, suffixe, corps, commande
):
    with (
        patch(
            "app.modules.employee_loans.api.access.queries.get_loan",
            return_value=_pret(SOCIETE_A),
        ),
        patch("app.modules.employee_loans.api.router.commands") as commands,
    ):
        getattr(commands, commande).return_value = _pret(SOCIETE_A)
        reponse = _appeler(client, methode, suffixe, corps)

    assert reponse.status_code in (200, 204)
    getattr(commands, commande).assert_called_once()
    assert getattr(commands, commande).call_args.args[0] == PRET


def test_pret_introuvable_repond_404_sans_ecrire(client):
    with (
        patch(
            "app.modules.employee_loans.api.access.queries.get_loan",
            side_effect=ValueError("Prêt non trouvé."),
        ),
        patch("app.modules.employee_loans.api.router.commands") as commands,
    ):
        reponse = client.post(f"/api/employee-loans/{PRET}/cancel")
    assert reponse.status_code == 404
    commands.cancel_loan.assert_not_called()


# ----- encours d'un salarié -----


def _encours() -> EmployeeLoanOutstanding:
    return EmployeeLoanOutstanding(
        employee_id=SALARIE,
        total_remaining_capital=0,
        active_loans_count=0,
    )


def test_encours_d_un_salarie_d_une_autre_societe_refuse(client):
    with (
        patch(
            "app.modules.access_control.application.service.providers"
        ) as providers,
        patch("app.modules.employee_loans.api.router.queries") as queries,
    ):
        providers.get_employee_company_id.return_value = SOCIETE_B
        reponse = client.get(f"/api/employee-loans/employees/{SALARIE}/outstanding")
    # 404 : patron de require_employee_access, l'existence n'est pas révélée.
    assert reponse.status_code == 404
    queries.get_outstanding_for_employee.assert_not_called()


def test_encours_d_un_salarie_de_ma_societe_autorise(client):
    with (
        patch(
            "app.modules.access_control.application.service.providers"
        ) as providers,
        patch("app.modules.employee_loans.api.router.queries") as queries,
    ):
        providers.get_employee_company_id.return_value = SOCIETE_A
        queries.get_outstanding_for_employee.return_value = _encours()
        reponse = client.get(f"/api/employee-loans/employees/{SALARIE}/outstanding")
    assert reponse.status_code == 200
    assert reponse.json()["employee_id"] == SALARIE
    queries.get_outstanding_for_employee.assert_called_once_with(SALARIE)


def test_encours_reste_reserve_aux_rh():
    app.dependency_overrides[get_current_user] = lambda: _user("collaborateur")
    try:
        with patch("app.modules.employee_loans.api.router.queries") as queries:
            reponse = TestClient(app).get(
                f"/api/employee-loans/employees/{SALARIE}/outstanding"
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert reponse.status_code == 403
    queries.get_outstanding_for_employee.assert_not_called()


def test_platform_admin_garde_son_acces_transverse():
    app.dependency_overrides[get_current_user] = lambda: _user(platform_admin=True)
    try:
        with (
            patch(
                "app.modules.employee_loans.api.access.queries.get_loan",
                return_value=_pret(SOCIETE_B),
            ),
            patch("app.modules.employee_loans.api.router.commands") as commands,
        ):
            commands.cancel_loan.return_value = _pret(SOCIETE_B)
            reponse = TestClient(app).post(f"/api/employee-loans/{PRET}/cancel")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert reponse.status_code == 200
    commands.cancel_loan.assert_called_once_with(PRET)

