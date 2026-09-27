"""Qui modifie les réglages du maintien de salaire.

Le collaborateur RH modifie ce qu'un RH modifie, comme sur les autres
réglages de la société ; un simple collaborateur, non.
"""

from __future__ import annotations

from app.modules.maintenance_settings.api.router import _can_write_maintenance_settings
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"


def _user(role: str, *, platform_admin: bool = False) -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="compte@societe.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=platform_admin,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=SOCIETE, company_name="Société", role=role, is_primary=True)
        ],
        active_company_id=SOCIETE,
    )


def test_admin_rh_et_collaborateur_rh_modifient():
    for role in ("admin", "rh", "collaborateur_rh"):
        assert _can_write_maintenance_settings(_user(role), SOCIETE), role


def test_un_collaborateur_ne_modifie_pas():
    assert not _can_write_maintenance_settings(_user("collaborateur"), SOCIETE)


def test_l_administrateur_plateforme_modifie():
    assert _can_write_maintenance_settings(_user("collaborateur", platform_admin=True), SOCIETE)
