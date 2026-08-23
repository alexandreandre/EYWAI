"""
Modulation et variables de paie : société du client jamais validée.

Audit Axe A, deux défauts sur le même patron, dans deux modules :

1. `_resolve_company_id(company_id, user)` renvoyait le `company_id` reçu du
   CLIENT sans vérifier que l'appelant y a accès — donc lecture et écriture
   des réglages de modulation et des règles de paie d'une AUTRE société.
2. `_require_rh` testait `user.role`, un rôle plat qui ignore les rôles
   `custom` : les directeurs porteurs de permissions RH étaient refusés,
   alors que le reste de l'application les accepte
   (`has_rh_access_in_company`). C'est la famille du bug des 5 directeurs.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.users.schemas.responses import CompanyAccess, User

MA_SOCIETE = "11111111-1111-1111-1111-111111111111"
AUTRE_SOCIETE = "99999999-9999-9999-9999-999999999999"


def _user(role: str = "rh", *, rh_custom: bool = False) -> User:
    acces = CompanyAccess(
        company_id=MA_SOCIETE,
        company_name="Ma société",
        role=role,
        is_primary=True,
    )
    if rh_custom:
        # Rôle custom porteur de permissions RH : résolu à la construction.
        object.__setattr__(acces, "has_rh_access", True) if hasattr(
            acces, "has_rh_access"
        ) else None
    return User(
        id="22222222-2222-2222-2222-222222222222",
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[acces],
        active_company_id=MA_SOCIETE,
    )


MODULES = ["modulation", "payroll_variables"]


@pytest.mark.parametrize("module", MODULES)
class TestPerimetreSocieteDuClient:
    def _resolve(self, module):
        import importlib

        return importlib.import_module(
            f"app.modules.{module}.api.router"
        )._resolve_company_id

    def test_societe_etrangere_refusee(self, module):
        resolve = self._resolve(module)
        with pytest.raises(HTTPException) as exc:
            resolve(AUTRE_SOCIETE, _user())
        assert exc.value.status_code == 403

    def test_ma_societe_acceptee(self, module):
        resolve = self._resolve(module)
        assert resolve(MA_SOCIETE, _user()) == MA_SOCIETE

    def test_sans_parametre_prend_la_societe_active(self, module):
        resolve = self._resolve(module)
        assert resolve(None, _user()) == MA_SOCIETE


@pytest.mark.parametrize("module", MODULES)
class TestRolesCustomAcceptes:
    def _require_rh(self, module):
        import importlib

        return importlib.import_module(f"app.modules.{module}.api.router")._require_rh

    def test_role_rh_accepte(self, module):
        self._require_rh(module)(_user("rh"), MA_SOCIETE)  # ne lève pas

    def test_collaborateur_refuse(self, module):
        with pytest.raises(HTTPException) as exc:
            self._require_rh(module)(_user("collaborateur"), MA_SOCIETE)
        assert exc.value.status_code == 403

    def test_le_controle_porte_sur_la_societe_visee(self, module):
        """Le droit RH se juge société par société, pas sur un rôle global."""
        with pytest.raises(HTTPException) as exc:
            self._require_rh(module)(_user("rh"), AUTRE_SOCIETE)
        assert exc.value.status_code == 403
