"""`GET /api/simulation/<id>` d'une simulation absente répond 404, jamais 500.

Relevé au tournage G.6-G.9 (20/10/2026) : la lecture d'une simulation absente
répondait 500. `maybe_single().execute()` rend None sans ligne (postgrest 2.31)
et le dépôt lisait `.data` dessus ; un identifiant qui n'est pas un UUID
faisait aussi échouer la requête en base (22P02).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.payroll.api import router
from app.modules.payroll.infrastructure import simulation_repository as depot
from tests.unit.sans_ligne import sans_ligne  # noqa: F401 — fixture

pytestmark = pytest.mark.unit

RH = SimpleNamespace(
    is_platform_admin=False,
    active_company_id="soc-1",
    has_rh_access_in_company=lambda _cid: True,
)
ABSENTE = "5e0ef791-e6e8-42fe-843e-8eb7c86c4caa"


def test_les_lectures_des_simulations_rendent_none_sans_ligne(sans_ligne):
    sans_ligne(depot)
    assert depot.fetch_company_row("c") is None
    assert depot.fetch_employee_row("e") is None
    assert depot.fetch_simulation_row(ABSENTE, "c") is None
    assert depot.fetch_payslip_row("p", "c") is None


def test_une_simulation_absente_repond_404(sans_ligne):
    sans_ligne(depot)
    with pytest.raises(HTTPException) as e:
        router.get_simulation(ABSENTE, current_user=RH)
    assert e.value.status_code == 404
    assert e.value.detail == "Simulation introuvable."


def test_un_identifiant_qui_n_est_pas_un_uuid_repond_404_sans_requete(sans_ligne):
    client = sans_ligne(depot)
    with pytest.raises(HTTPException) as e:
        router.get_simulation("pas-un-uuid", current_user=RH)
    assert e.value.status_code == 404
    assert client.lues == []
