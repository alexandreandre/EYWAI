"""« Primes du mois » lit les jours travaillés sans heure d'arrivée (L19, 27/11).

Une lecture : la génération des variables en simulation, rien d'écrit ni de stocké.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.modules.payroll_variables.api import router as module_router

pytestmark = pytest.mark.unit


def _client(monkeypatch, lecture):
    app = FastAPI()
    app.include_router(module_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        is_platform_admin=True, active_company_id="c1"
    )
    monkeypatch.setattr(module_router, "jours_sans_heure_d_arrivee", lecture)
    return TestClient(app)


def test_la_route_rend_les_jours_par_salarie(monkeypatch):
    appels = []

    def lecture(company_id, year, month, employee_id=None):
        appels.append((company_id, year, month, employee_id))
        return [{"employee_id": "e1", "first_name": "A", "last_name": "B", "rule_label": "Panier",
                 "dates": ["2026-10-05"]}]

    r = _client(monkeypatch, lecture).get(
        "/api/payroll-variables/jours-sans-heure-d-arrivee", params={"year": 2026, "month": 10}
    )
    assert r.status_code == 200
    assert r.json() == [{"employee_id": "e1", "first_name": "A", "last_name": "B", "rule_label": "Panier",
                         "dates": ["2026-10-05"]}]
    assert appels == [("c1", 2026, 10, None)]
