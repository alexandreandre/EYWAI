"""
Le référentiel de taux est commun à toutes les sociétés : seul un admin
plateforme peut lancer une mise à jour, l'annuler, ou couper le lot du mois.

Avant, tout RH d'une société pouvait couper la mise à jour automatique pour
toute la plateforme, ou lancer un scraping global depuis la page. La lecture
(taux, état du mois, suivi d'un lot) reste ouverte aux RH.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_ROUTER = "app.modules.rates.api.router"


def _compte(*, admin_plateforme: bool) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="compte@societe-a.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=admin_plateforme,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société A", role="rh", is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )


@pytest.fixture
def client_rh():
    app.dependency_overrides[get_current_user] = lambda: _compte(admin_plateforme=False)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client_admin():
    app.dependency_overrides[get_current_user] = lambda: _compte(admin_plateforme=True)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize(
    ("methode", "chemin", "corps"),
    [
        ("patch", "/api/rates/monthly", {"enabled": False}),
        ("post", "/api/rates/monthly/run", {"force": False}),
        ("post", "/api/rates/sync", {"scope": "all"}),
        ("post", "/api/rates/sync/11111111-2222-3333-4444-555555555555/cancel", None),
    ],
)
def test_un_rh_ne_lance_ni_ne_coupe_la_mise_a_jour(client_rh, methode, chemin, corps):
    with patch(f"{_ROUTER}.set_monthly_auto_enabled") as interrupteur, patch(
        f"{_ROUTER}.launch_monthly_sync"
    ) as lot, patch(f"{_ROUTER}.start_rates_sync") as sync, patch(
        f"{_ROUTER}.cancel_rates_sync"
    ) as annulation:
        reponse = getattr(client_rh, methode)(chemin, json=corps)
    assert reponse.status_code == 403
    assert "administrateurs plateforme" in reponse.json()["detail"]
    for appel in (interrupteur, lot, sync, annulation):
        appel.assert_not_called()


def test_un_admin_plateforme_coupe_le_lot_du_mois(client_admin):
    with patch(f"{_ROUTER}.set_monthly_auto_enabled", return_value={"enabled": False}) as interrupteur:
        reponse = client_admin.patch("/api/rates/monthly", json={"enabled": False})
    assert reponse.status_code == 200
    interrupteur.assert_called_once_with(False)


def test_un_rh_lit_toujours_l_etat_du_mois(client_rh):
    with patch(f"{_ROUTER}.get_monthly_rates_state", return_value={"enabled": True}):
        reponse = client_rh.get("/api/rates/monthly")
    assert reponse.status_code == 200
