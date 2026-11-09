"""Une fiche qui n'appartient pas à la société active répond 404, pas 500.

PostgREST refuse `.single()` sur zéro ligne (PGRST116) : l'exception remontait en 500.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from app.modules.employees.infrastructure.repository import EmployeeRepository

pytestmark = pytest.mark.unit

ERREUR_ZERO_LIGNE = APIError(
    {"message": "Cannot coerce the result to a single JSON object", "code": "PGRST116"}
)


def _client_sans_ligne() -> MagicMock:
    """Comme PostgREST : `.single()` lève, `.maybe_single()` rend None sans ligne."""
    client = MagicMock()
    filtre = client.table.return_value.select.return_value.eq.return_value.eq.return_value
    filtre.single.return_value.execute.side_effect = ERREUR_ZERO_LIGNE
    filtre.maybe_single.return_value.execute.return_value = None
    return client


def test_fiche_d_une_autre_societe_rend_none_sans_erreur():
    with patch("app.modules.employees.infrastructure.repository.supabase", _client_sans_ligne()):
        assert EmployeeRepository().get_by_id("salarie", "autre-societe") is None


def test_la_route_detail_repond_404():
    from fastapi import HTTPException

    from app.modules.employees.api import router as routes
    from app.modules.employees.application import queries

    with (
        patch("app.modules.employees.infrastructure.repository.supabase", _client_sans_ligne()),
        patch.object(routes, "assert_can_read_employee_profile"),
        patch.object(queries, "_employee_repository", EmployeeRepository()),
    ):
        utilisateur = MagicMock(active_company_id="autre-societe")
        with pytest.raises(HTTPException) as refus:
            routes.get_employee_details("salarie", utilisateur)
    assert refus.value.status_code == 404
