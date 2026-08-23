"""
Contexte d'authentification des tests d'intégration monthly_inputs.

Depuis l'audit du 22/08/2026, ces routes exigent un compte authentifié et
travaillent dans la société active de l'appelant. Les tests injectent donc
une RH de la société de test ; le refus de l'anonyme est prouvé ailleurs
(tests/unit/security/test_monthly_inputs_cloisonnement.py), pour ne pas
diluer ici le sujet de chaque test.
"""

from __future__ import annotations

import pytest

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

COMPANY_ID_TEST = "11111111-1111-1111-1111-111111111111"


def _rh_de_test() -> User:
    return User(
        id="33333333-3333-3333-3333-333333333333",
        email="rh@entreprise-test.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=COMPANY_ID_TEST,
                company_name="Entreprise Test",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=COMPANY_ID_TEST,
    )


@pytest.fixture(autouse=True)
def rh_authentifiee():
    app.dependency_overrides[get_current_user] = _rh_de_test
    yield
    app.dependency_overrides.pop(get_current_user, None)
