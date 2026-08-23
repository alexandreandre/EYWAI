"""
Le routeur « RH » des plannings exige réellement un droit RH.

Audit axe C : `router_rh` (prefix /api/schedules) porte le mot RH dans son
nom et ses tags, mais ses routes ne vérifiaient que l'authentification. Un
salarié quelconque pouvait donc :
  - lister les heures supplémentaires NOMINATIVES de tous ses collègues ;
  - approuver ses PROPRES heures supplémentaires (le calendrier réel passait
    de 8 h à 10 h, donc payées) ;
  - désactiver l'exigence de validation manager pour toute la société, et
    mettre la pause à 0 minute pour tout le monde.

C'est un vecteur de fraude à la paie, ouvert à chacun des ~245 salariés dès
que la vague 1 leur donnera un compte.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE = "11111111-1111-1111-1111-111111111111"

# (méthode, chemin, corps) — l'échantillon couvre lecture, décision et réglages.
ROUTES_SENSIBLES = [
    ("get", "/api/schedules/punch-overtime-reviews", None),
    (
        "patch",
        "/api/schedules/punch-overtime-reviews/rev-1",
        {"status": "approved"},
    ),
    ("get", "/api/schedules/punch-accounting/settings", None),
    (
        "patch",
        "/api/schedules/punch-accounting/settings",
        {"require_manager_validation_for_overtime": False},
    ),
    ("get", "/api/schedules/punch-accounting/slots", None),
]


def _utilisateur(role: str) -> User:
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="salarie@entreprise.fr",
        first_name="Simon",
        last_name="Salarié",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=SOCIETE,
                company_name="Entreprise",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=SOCIETE,
    )


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)


class TestSalarieSansDroitRh:
    @pytest.mark.parametrize("methode,chemin,corps", ROUTES_SENSIBLES)
    def test_un_collaborateur_est_refuse(self, methode, chemin, corps):
        utilisateur = _utilisateur("collaborateur")
        assert not utilisateur.has_rh_access_in_company(SOCIETE)

        app.dependency_overrides[get_current_user] = lambda: utilisateur
        try:
            # Aucun mock : la garde doit refuser AVANT d'atteindre la couche
            # métier. Si elle laissait passer, l'appel toucherait la base et
            # le test échouerait autrement — ce qui reste un échec.
            reponse = getattr(TestClient(app), methode)(
                chemin, **({"json": corps} if corps is not None else {})
            )
            assert reponse.status_code == 403, (
                f"{methode.upper()} {chemin} accessible à un collaborateur "
                f"(reçu {reponse.status_code})"
            )
        finally:
            _teardown()


class TestProfilRhAutorise:
    @pytest.mark.parametrize("methode,chemin,corps", ROUTES_SENSIBLES)
    def test_une_rh_passe(self, methode, chemin, corps):
        app.dependency_overrides[get_current_user] = lambda: _utilisateur("rh")
        try:
            with patch(
                "app.modules.schedules.application.punch_accounting_commands."
                "get_punch_accounting_settings",
                return_value={},
            ), patch(
                "app.modules.schedules.application.punch_accounting_commands."
                "list_punch_shift_slots",
                return_value=[],
            ), patch(
                "app.modules.schedules.application.punch_accounting_commands."
                "list_punch_overtime_reviews",
                return_value=[],
            ):
                reponse = TestClient(app, raise_server_exceptions=False)
                reponse = getattr(reponse, methode)(
                    chemin, **({"json": corps} if corps is not None else {})
                )
            assert reponse.status_code != 403, (
                f"{methode.upper()} {chemin} refusé à une RH"
            )
        finally:
            _teardown()
